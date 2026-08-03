#!/usr/bin/env python3
"""Per-layer CDF/skeleton drift scanner for the spedas_agent_kit catalogs.

Maintains a heuristic drift manifest PER data-folder layer so that periodic
full scans of CDAWeb (and the PDS/SPICE layers) can detect catalog rot:
renames, case changes, 404s, parameter changes and date anomalies in the
vendored dataset catalogs vs. the upstream archives.

Design (Jason):
  * one `DRIFT.md` snapshot per data folder (committed to the repo),
  * one append-only `drift_scan_results.jsonl` sidecar per data folder
    (the machine-readable manifest; committed so history is portable),
  * results are written incrementally: an interrupted run keeps every
    completed check and a later run resumes (skips ids already live-checked).

Usage:
  python scripts/scan_drift.py --layer cdaweb --limit 50
  python scripts/scan_drift.py --layer pds --limit 50
  python scripts/scan_drift.py --layer spice --limit 20

Only stdlib + `requests` are required. Network failures are caught per
dataset and never abort the run. See README "Periodic catalog drift scans".
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------
# URL conventions -- kept in sync with the backend implementations.
#   cdaweb: src/spedas_agent_kit/backends/cdaweb/metadata.py
#           (MASTER_CDF_BASE + "{dataset_id.lower()}_00000000_v01.cdf")
#   pds:    slot paths in src/spedas_agent_kit/backends/pds/data/missions/*.json
#           hosted under https://pds-ppi.igpp.ucla.edu
#   spice:  kernel URLs in src/spedas_agent_kit/backends/spice/manifests/*.json
# --------------------------------------------------------------------------
CDAWEB_MASTER_BASE = "https://cdaweb.gsfc.nasa.gov/pub/software/cdawlib/0MASTERS"
PDS_BASE = "https://pds-ppi.igpp.ucla.edu"

# Heuristic: stop dates >= this year are treated as a date anomaly.  The
# 2026-08-03 audit independently flagged stop_date >= 2031 as anomalous.
DATE_ANOMALY_YEAR = 2031

# Drift types reported in DRIFT.md (see README).  "fail" is a separate bucket
# for network errors / unexpected HTTP statuses (timeouts etc.).
DRIFT_TYPES = ("renamed", "case_change", "404", "param_change", "date_anomaly")

SIDECAR_JSONL = "drift_scan_results.jsonl"
META_JSON = "drift_scan_meta.json"
MANIFEST_MD = "DRIFT.md"

LAYERS = {
    "cdaweb": {
        "data_dir": "src/spedas_agent_kit/backends/cdaweb/data/observatories",
        "title": "CDAWeb Master-CDF skeleton drift",
        "host_note": "0MASTERS master CDFs at cdaweb.gsfc.nasa.gov (server is case-sensitive)",
        # Best-effort seed artifacts from previous audit runs.  Discovery is by
        # generic filename glob inside the seed directory (--seed-dir), so no
        # audit-daemon tmp paths are hardcoded here.
        "seed_globs": ("*shard1_results*.json", "*cdaweb_shard1_report*.md", "*shard1_report*.md"),
    },
    "pds": {
        "data_dir": "src/spedas_agent_kit/backends/pds/data/missions",
        "title": "PDS PPI archive slot drift",
        "host_note": "PPI archive slots at pds-ppi.igpp.ucla.edu",
        "seed_globs": ("*pds_slot_status*.json",),
    },
    "spice": {
        "data_dir": "src/spedas_agent_kit/backends/spice/manifests",
        "title": "SPICE NAIF kernel manifest drift",
        "host_note": "NAIF kernel URLs at naif.jpl.nasa.gov",
        "seed_globs": ("*spice_audit_results*.json",),
    },
}


# ---------------------------------------------------------------------------
# catalog enumeration
# ---------------------------------------------------------------------------

def _load_json(path: Path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"  ! skipping {path.name}: {exc}", file=sys.stderr)
        return None


def iter_cdaweb_targets(data_dir: Path):
    """Yield (dataset_id, obs, url, expected_filename) for every catalog dataset."""
    for path in sorted(data_dir.glob("*.json")):
        doc = _load_json(path)
        if not isinstance(doc, dict):
            continue
        obs = str(doc.get("id") or path.stem)
        for inst in (doc.get("instruments") or {}).values():
            for dsid in (inst.get("datasets") or {}):
                expected = f"{dsid.lower()}_00000000_v01.cdf"
                url = f"{CDAWEB_MASTER_BASE}/{expected}"
                yield dsid, obs, url, expected


def iter_pds_targets(data_dir: Path):
    """Yield (dataset_id, mission, url, expected_path) for every PDS dataset slot."""
    for path in sorted(data_dir.glob("*.json")):
        doc = _load_json(path)
        if not isinstance(doc, dict):
            continue
        mission = path.stem
        for inst in (doc.get("instruments") or {}).values():
            for dsid, ds in (inst.get("datasets") or {}).items():
                slot = (ds or {}).get("slot")
                if not slot:
                    # construct a best-effort slot from the dataset id
                    base = re.sub(r"^(pds3:|urn:nasa:pds:)", "", dsid).split(":")[0]
                    slot = "/data/" + base.replace("/", "_")
                url = PDS_BASE + slot + "/"
                yield dsid, mission, url, slot


def iter_spice_targets(data_dir: Path):
    """Yield (kernel_id, mission, url, expected_filename) for every manifest kernel."""
    for path in sorted(data_dir.glob("*.json")):
        doc = _load_json(path)
        if not isinstance(doc, list):
            continue
        mission = path.stem
        for seg in doc:
            url = (seg or {}).get("url", "")
            fname = (seg or {}).get("file", "")
            if not url:
                continue
            kernel_id = f"{mission}/{fname or Path(url).name}"
            yield kernel_id, mission, url, fname or Path(url).name


ITERATORS = {"cdaweb": iter_cdaweb_targets, "pds": iter_pds_targets, "spice": iter_spice_targets}


# ---------------------------------------------------------------------------
# HTTP checking
# ---------------------------------------------------------------------------

def _url_basename(url: str) -> str:
    return unquote(url.rstrip("/").rsplit("/", 1)[-1])


def check_url(session: requests.Session, url: str, timeout: float) -> dict:
    """HEAD (fallback GET-stream) check.  Never raises.

    Returns dict(status, actual, redirect, error) where status is an int HTTP
    code on success or a short error tag like "ERR_TimeoutError".
    """
    try:
        resp = session.head(url, allow_redirects=True, timeout=timeout)
        if resp.status_code in (405, 501):  # HEAD unsupported -> cheap GET
            resp = session.get(url, stream=True, timeout=timeout)
            resp.close()
        return {
            "status": resp.status_code,
            "actual": _url_basename(resp.url or url),
            "redirect": (resp.url if resp.url and resp.url != url else ""),
            "error": "",
        }
    except requests.exceptions.Timeout:
        return {"status": "ERR_TimeoutError", "actual": "", "redirect": "", "error": "timeout"}
    except requests.exceptions.ConnectionError:
        return {"status": "ERR_ConnectionError", "actual": "", "redirect": "", "error": "connection error"}
    except requests.exceptions.RequestException as exc:
        return {"status": "ERR_RequestException", "actual": "", "redirect": "", "error": str(exc)[:200]}


def classify(layer: str, target, result: dict, catalog_dates=None) -> dict:
    """Map a check result onto an ok / drift / fail record."""
    dsid, scope, url, expected = target
    status = result["status"]
    record = {
        "dataset_id": dsid,
        "layer": layer,
        "scope": scope,
        "url": url,
        "status": str(status),
        "actual": result.get("actual", ""),
        "drift_type": "",
        "detail": "",
    }
    detail_bits = []
    if result.get("redirect"):
        detail_bits.append(f"redirect {url} -> {result['redirect']}")
    if isinstance(status, int) and status == 200:
        actual = result.get("actual", "")
        # pds slots are directory URLs (expected = full path), so a basename
        # diff there is not drift; only cdaweb/spice compare filenames.
        if layer != "pds" and actual:
            if actual.lower() != expected.lower():
                record["drift_type"] = "renamed"
                detail_bits.append(f"expected {expected!r}, got {actual!r}")
            elif actual != expected:
                record["drift_type"] = "case_change"
                detail_bits.append(f"expected {expected!r}, got {actual!r} (case)")
    elif isinstance(status, int) and status == 404:
        record["drift_type"] = "404"
        detail_bits.append("HTTP 404 at constructed URL")
    else:
        record["drift_type"] = "fail"
        detail_bits.append(f"status {status}{(' (' + result['error'] + ')') if result.get('error') else ''}")
    # catalog-level date anomaly (no network needed)
    if catalog_dates:
        stop = catalog_dates.get("stop_date", "") or ""
        start = catalog_dates.get("start_date", "") or ""
        if stop[:4].isdigit() and int(stop[:4]) >= DATE_ANOMALY_YEAR:
            record["drift_type"] = "date_anomaly"
            detail_bits.append(f"catalog stop_date {stop} >= {DATE_ANOMALY_YEAR} (heuristic)")
        elif start and stop and start > stop:
            record["drift_type"] = "date_anomaly"
            detail_bits.append(f"catalog start_date {start} > stop_date {stop}")
    record["detail"] = "; ".join(detail_bits)
    return record


# ---------------------------------------------------------------------------
# sidecar persistence (incremental)
# ---------------------------------------------------------------------------

_write_lock = threading.Lock()


def load_sidecar(path: Path) -> dict:
    """Return {dataset_id: record} for every dataset line in the jsonl."""
    records: dict = {}
    if not path.exists():
        return records
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict) and rec.get("dataset_id"):
            records[rec["dataset_id"]] = rec
    return records


def append_record(path: Path, record: dict) -> None:
    with _write_lock:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")


def save_meta(path: Path, meta: dict) -> None:
    with _write_lock:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=1, sort_keys=True)
            fh.write("\n")


def load_meta(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


# ---------------------------------------------------------------------------
# best-effort seeding from previous audit artifacts
# ---------------------------------------------------------------------------

def _seed_dir(args) -> Path | None:
    """Resolve the seed directory (CLI > env > tempdir detection)."""
    if args.seed_dir:
        p = Path(args.seed_dir)
        return p if p.is_dir() else None
    env = os.environ.get("SPEDAS_DRIFT_SEED_DIR")
    if env and Path(env).is_dir():
        return Path(env)
    tmp = Path(tempfile.gettempdir())
    if any(glob.glob(str(tmp / g)) for g in ("*shard1_results*.json", "*pds_slot_status*.json", "*spice_audit_results*.json")):
        return tmp
    return None


def _first_glob(seed_dir: Path, patterns) -> Path | None:
    for pat in patterns:
        hits = sorted(glob.glob(str(seed_dir / pat)))
        if hits:
            return Path(hits[0])
    return None


def seed_cdaweb(seed_dir: Path):
    """Seed cdaweb drift records + totals from the 2026-08-03 audit artifacts."""
    records = []
    results_file = _first_glob(seed_dir, ("*shard1_results*.json",))
    report_file = _first_glob(seed_dir, ("*cdaweb_shard1_report*.md", "*shard1_report*.md"))
    n_datasets = 0
    if results_file:
        data = _load_json(results_file)
        if isinstance(data, dict):
            n_datasets = int(data.get("n_datasets") or 0)
            for dsid in data.get("missing_master_cdf") or []:
                records.append({
                    "dataset_id": dsid, "layer": "cdaweb", "scope": "cnofs",
                    "url": f"{CDAWEB_MASTER_BASE}/{dsid.lower()}_00000000_v01.cdf",
                    "status": "404", "actual": "", "drift_type": "404",
                    "detail": "master CDF missing from 0MASTERS listing (audit 2026-08-03)",
                })
            for d in data.get("datasets") or []:
                stop = (d.get("stop_date") or "")[:4]
                if stop.isdigit() and int(stop) >= DATE_ANOMALY_YEAR:
                    records.append({
                        "dataset_id": d["dsid"], "layer": "cdaweb", "scope": d.get("obs", ""),
                        "url": f"{CDAWEB_MASTER_BASE}/{d['dsid'].lower()}_00000000_v01.cdf",
                        "status": "200", "actual": "", "drift_type": "date_anomaly",
                        "detail": f"catalog stop_date {d.get('stop_date')} >= {DATE_ANOMALY_YEAR} (audit 2026-08-03)",
                    })
    # Per-dataset table in the audit report: 0-param rows -> param_change,
    # NO rows -> 404/case drift with the report's own wording.
    if report_file:
        try:
            text = report_file.read_text(encoding="utf-8")
        except OSError:
            text = ""
        for m in re.finditer(r"^\|\s*(\S+)\s*\|\s*(\S+)\s*\|\s*(yes \(0 params[^)]*\)|NO[^|]*)", text, re.M):
            obs, dsid, cell = m.group(1), m.group(2), m.group(3).strip()
            if "0 params" in cell:
                records.append({
                    "dataset_id": dsid, "layer": "cdaweb", "scope": obs,
                    "url": f"{CDAWEB_MASTER_BASE}/{dsid.lower()}_00000000_v01.cdf",
                    "status": "200", "actual": "", "drift_type": "param_change",
                    "detail": f"master CDF resolves but only Time variable present (audit 2026-08-03): {cell}",
                })
            elif cell.startswith("NO"):
                drift_type = "case_change" if "case" in cell.lower() else "404"
                records.append({
                    "dataset_id": dsid, "layer": "cdaweb", "scope": obs,
                    "url": f"{CDAWEB_MASTER_BASE}/{dsid.lower()}_00000000_v01.cdf",
                    "status": "404", "actual": "", "drift_type": drift_type,
                    "detail": f"(audit 2026-08-03): {cell}",
                })
    # dedupe by dataset_id, last wins (report rows are more precise)
    seen = {}
    for r in records:
        seen[r["dataset_id"]] = r
    drift = len(seen)
    meta = {
        "layer": "cdaweb", "seeded": True,
        "seed_source": f"audit artifacts {results_file.name if results_file else '?'} + {report_file.name if report_file else '?'}",
        "seed_scope": "22/65 observatories (ace..genesis), first audit shard",
        "seed_checked": n_datasets or len(seen),
        "seed_ok": max((n_datasets or len(seen)) - drift, 0),
        "seed_drift": drift,
        "seed_fail": 0,
        "seed_date": "2026-08-03",
    }
    return list(seen.values()), meta


def seed_pds(seed_dir: Path):
    records = []
    status_file = _first_glob(seed_dir, ("*pds_slot_status*.json",))
    if not status_file:
        return [], {}
    data = _load_json(status_file)
    if not isinstance(data, list):
        return [], {}
    ok = drift = fail = 0
    for item in data:
        status = item.get("status")
        if status == 200:
            ok += 1
        elif status == "HTTP_404":
            drift += 1
            records.append({
                "dataset_id": item["dataset_id"], "layer": "pds", "scope": item.get("mission", ""),
                "url": item.get("url", ""), "status": "404", "actual": "",
                "drift_type": "404", "detail": "HTTP 404 at PPI archive slot (audit 2026-08-03)",
            })
        else:
            fail += 1
            records.append({
                "dataset_id": item["dataset_id"], "layer": "pds", "scope": item.get("mission", ""),
                "url": item.get("url", ""), "status": str(status), "actual": "",
                "drift_type": "fail", "detail": f"slot check {status} (audit 2026-08-03)",
            })
    meta = {
        "layer": "pds", "seeded": True,
        "seed_source": f"audit artifact {status_file.name}",
        "seed_scope": f"{len(data)} PPI archive slots across all missions",
        "seed_checked": ok + drift + fail,
        "seed_ok": ok, "seed_drift": drift, "seed_fail": fail,
        "seed_date": "2026-08-03",
    }
    return records, meta


def seed_spice(seed_dir: Path):
    records = []
    results_file = _first_glob(seed_dir, ("*spice_audit_results*.json",))
    if not results_file:
        return [], {}
    data = _load_json(results_file)
    if not isinstance(data, dict):
        return [], {}
    problems = data.get("problems") or []
    for idx, prob in enumerate(problems):
        text = str(prob)
        if "used by multiple missions" in text:
            m = re.search(r"filename '([^']+)'", text)
            dsid = f"kernel:{m.group(1)}" if m else f"problem:{idx}"
            scope = "grail" if "grail" in text else "multi-mission"
            dtype, detail = "renamed", f"duplicate kernel filename across missions -> flat cache overwrite risk (audit 2026-08-03): {text[:220]}"
        elif "duplicate NAIF ID" in text:
            m = re.search(r"duplicate NAIF ID ([^ ]+)", text)
            dsid = f"naif_id:{m.group(1)}" if m else f"problem:{idx}"
            scope = "multi-mission"
            dtype, detail = "param_change", f"duplicate NAIF ID assignment (identity metadata conflict, audit 2026-08-03): {text[:220]}"
        else:
            dsid = f"problem:{idx}"
            scope = "manifests"
            dtype, detail = "fail", f"(audit 2026-08-03): {text[:220]}"
        records.append({
            "dataset_id": dsid, "layer": "spice", "scope": scope, "url": "",
            "status": "200", "actual": "", "drift_type": dtype, "detail": detail,
        })
    n_segments = int(data.get("total_segments") or 0)
    meta = {
        "layer": "spice", "seeded": True,
        "seed_source": f"audit artifact {results_file.name}",
        "seed_scope": f"{len(problems)} catalog problems across mission manifests",
        "seed_checked": n_segments,
        "seed_ok": max(n_segments - len(records), 0),
        "seed_drift": len(records),
        "seed_fail": 0,
        "seed_date": "2026-08-03",
    }
    return records, meta


SEEDERS = {"cdaweb": seed_cdaweb, "pds": seed_pds, "spice": seed_spice}


# ---------------------------------------------------------------------------
# DRIFT.md rendering
# ---------------------------------------------------------------------------

def _date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def render_manifest(layer: str, records: dict, meta: dict, prev: dict, args) -> str:
    cfg = LAYERS[layer]
    now = _date()
    drift_rows = [r for r in records.values() if r.get("drift_type") in DRIFT_TYPES]
    fail_rows = [r for r in records.values() if r.get("drift_type") == "fail"]
    live = [r for r in records.values() if r.get("source") == "live"]
    live_ok = [r for r in live if r.get("drift_type") in ("", None)]
    live_drift = [r for r in live if r.get("drift_type") in DRIFT_TYPES]
    live_fail = [r for r in live if r.get("drift_type") == "fail"]

    # history vs previous run
    prev_drift = {k for k, r in prev.items() if r.get("drift_type") in DRIFT_TYPES}
    cur_drift = {r["dataset_id"] for r in drift_rows}
    new_ids = sorted(cur_drift - prev_drift)
    rec_ids = sorted(prev_drift - cur_drift)
    pers_ids = sorted(cur_drift & prev_drift)
    live_ids = {r["dataset_id"] for r in live}

    lines = [
        f"# CDF/Skeleton Drift Registry \u2014 {layer}",
        "",
        f"**Layer**: {cfg['title']}  ",
        f"**Catalog root**: `{cfg['data_dir']}/`  ",
        f"**Host**: {cfg['host_note']}  ",
        f"**Scan timestamp**: {now} (UTC)  ",
        f"**Scanner**: `python scripts/scan_drift.py --layer {layer}` (see README \"Periodic catalog drift scans\")",
        "",
        "## Totals",
        "",
        "| metric | value |",
        "|---|---|",
    ]
    if meta.get("seeded"):
        lines += [
            f"| seeded from audit artifacts | {meta.get('seed_checked', 0)} checked / {meta.get('seed_ok', 0)} ok / {meta.get('seed_drift', 0)} drift / {meta.get('seed_fail', 0)} fail |",
            f"| seed scope | {meta.get('seed_scope', '')} |",
            f"| seed source | {meta.get('seed_source', '')} |",
        ]
    lines += [
        f"| live checks (this run) | {len(live)} checked / {len(live_ok)} ok / {len(live_drift)} drift / {len(live_fail)} fail |",
        f"| registry state | {len(drift_rows)} drifted datasets, {len(fail_rows)} failed checks |",
        "",
        "Drift types: `renamed` | `case_change` | `404` | `param_change` | `date_anomaly`; "
        "`fail` = network error / unexpected HTTP status (not a skeleton-drift classification).",
        "",
    ]

    rows = sorted(drift_rows + fail_rows, key=lambda r: (r.get("drift_type") or "", r["dataset_id"]))
    top = args.top
    truncated = len(rows) > top
    if truncated:
        rows = rows[:top]
    lines += [
        f"## Drifted datasets (top {top}{', truncated from ' + str(len(drift_rows) + len(fail_rows)) if truncated else ''})",
        "",
        "| dataset_id | observatory/mission | drift_type | detail | first_seen |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        first = r.get("first_seen") or (r.get("checked_at") or "")[:10] or "unknown"
        detail = (r.get("detail") or "").replace("|", "\\|")
        lines.append(f"| {r['dataset_id']} | {r.get('scope', '')} | {r.get('drift_type') or 'ok'} | {detail} | {first} |")
    if not rows:
        lines.append("| _(no drift detected)_ | | | | |")

    # scan history note
    lines += ["", "## Scan history"]
    if not prev:
        lines.append(
            "Initial snapshot \u2014 no previous manifest on disk. All entries are "
            "first_seen at their seed/live scan date; subsequent runs classify "
            "new / recovered / persistent drift against this snapshot."
        )
    else:
        lines.append(f"- **new** ({len(new_ids)}): {', '.join(new_ids[:8]) if new_ids else '(none)'}")
        lines.append(f"- **recovered** ({len(rec_ids)}): {', '.join(rec_ids[:8]) if rec_ids else '(none)'}")
        lines.append(f"- **persistent** ({len(pers_ids)}): {', '.join(pers_ids[:8]) if pers_ids else '(none)'}")
        if live_ids:
            lines.append(f"- live-checked this run: {len(live_ids)} datasets")
    lines += ["", "## How to run", "", "```bash", f"python scripts/scan_drift.py --layer {layer} --limit 50", "```", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def run_layer(args) -> int:
    cfg = LAYERS[args.layer]
    data_dir = REPO_ROOT / cfg["data_dir"]
    if not data_dir.is_dir():
        print(f"error: data dir not found: {data_dir}", file=sys.stderr)
        return 2
    jsonl_path = data_dir / SIDECAR_JSONL
    meta_path = data_dir / META_JSON
    md_path = data_dir / MANIFEST_MD

    records = load_sidecar(jsonl_path)
    meta = load_meta(meta_path)
    prev = dict(records)  # state before this run (for history)
    now = _date()

    # 1) best-effort seed from audit artifacts (only ids not already known)
    if not args.no_seed:
        seed_dir = _seed_dir(args)
        if seed_dir:
            seeded_recs, seed_meta = SEEDERS[args.layer](seed_dir)
            if seed_meta:
                meta = seed_meta
                save_meta(meta_path, meta)
            added = 0
            for rec in seeded_recs:
                if rec["dataset_id"] not in records:
                    rec["source"] = "seed"
                    rec["first_seen"] = meta.get("seed_date") or now[:10]
                    rec["checked_at"] = now
                    records[rec["dataset_id"]] = rec
                    append_record(jsonl_path, rec)
                    added += 1
            print(f"seeded {added} records from {seed_dir}")
        else:
            print("no seed artifacts found (--seed-dir); running live only", file=sys.stderr)

    # 2) live scan (resumable: skip ids already live-checked)
    targets = list(ITERATORS[args.layer](data_dir))
    todo = []
    for t in targets:
        dsid = t[0]
        if records.get(dsid, {}).get("source") == "live":
            continue
        if args.limit is not None and len(todo) >= args.limit:
            break
        todo.append(t)
    print(f"layer={args.layer}: {len(targets)} catalog targets, {len(todo)} to check live")

    if todo:
        session = requests.Session()
        session.headers.update({"User-Agent": "spedas-drift-scanner/1.0"})
        catalog_dates = {}
        if args.layer == "cdaweb":
            # pre-build catalog date map for the date-anomaly heuristic
            for path in data_dir.glob("*.json"):
                doc = _load_json(path)
                if not isinstance(doc, dict):
                    continue
                for inst in (doc.get("instruments") or {}).values():
                    for dsid, dd in (inst.get("datasets") or {}).items():
                        if isinstance(dd, dict):
                            catalog_dates[dsid] = {"start_date": dd.get("start_date"), "stop_date": dd.get("stop_date")}
        done = 0
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(check_url, session, t[2], args.timeout): t for t in todo}
            for fut in as_completed(futures):
                t = futures[fut]
                dsid = t[0]
                result = fut.result()
                rec = classify(args.layer, t, result, catalog_dates=catalog_dates.get(dsid))
                rec["source"] = "live"
                rec["first_seen"] = now[:10]
                rec["checked_at"] = now
                records[dsid] = rec
                append_record(jsonl_path, rec)
                done += 1
                if done % 10 == 0 or done == len(todo):
                    print(f"  ... {done}/{len(todo)} checked")

    # 3) render + write DRIFT.md
    meta["last_run"] = now
    save_meta(meta_path, meta)
    md = render_manifest(args.layer, records, meta, prev, args)
    md_path.write_text(md, encoding="utf-8")
    print(f"wrote {md_path}")
    print(f"wrote {jsonl_path} ({len(records)} records), {meta_path}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="scan_drift.py",
        description="Per-layer CDF/skeleton drift scanner for spedas_agent_kit catalogs.",
    )
    ap.add_argument("--layer", required=True, choices=sorted(LAYERS),
                    help="data layer to scan: cdaweb | pds | spice")
    ap.add_argument("--limit", type=int, default=None, metavar="N",
                    help="max live URL checks this run (smoke runs; 0 = seed/render only)")
    ap.add_argument("--workers", type=int, default=8, metavar="N",
                    help="ThreadPoolExecutor size (default 8)")
    ap.add_argument("--timeout", type=float, default=15.0, metavar="S",
                    help="per-request timeout in seconds (default 15)")
    ap.add_argument("--seed-dir", default=None, metavar="DIR",
                    help="directory with previous audit artifacts for seeding "
                         "(default: $SPEDAS_DRIFT_SEED_DIR, else tempdir if artifacts present)")
    ap.add_argument("--no-seed", action="store_true",
                    help="skip best-effort seeding from audit artifacts")
    ap.add_argument("--top", type=int, default=200, metavar="N",
                    help="max drifted rows in DRIFT.md (default 200)")
    args = ap.parse_args(argv)
    if args.limit is not None and args.limit < 0:
        ap.error("--limit must be >= 0")
    return run_layer(args)


if __name__ == "__main__":
    sys.exit(main())
