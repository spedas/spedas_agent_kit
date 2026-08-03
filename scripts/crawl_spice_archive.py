#!/usr/bin/env python3
"""Crawl the NAIF SPICE kernel archive directory tree and map its folder nodes.

This is the upstream-archive crawler for the ``data/spice_archive_map.json``
asset (a spedas MCP asset). It walks the NAIF public SPICE kernel archive
root (https://naif.jpl.nasa.gov/pub/naif/, an Apache autoindex-style
directory listing) and records every directory node it discovers: relative
path, URL, depth, child directory names, file count, min/max child mtime,
aggregate file size when the listing exposes it, and a leaf-folder
classification.  A leaf folder that contains SPICE kernel files (extensions
such as .bsp/.bpc/.bc/.tf/.tls/.tsc/.tpc/.ti/.tl/.tm/.mk/.txt and the other
standard kernel types) is additionally flagged as a *kernel leaf folder* so
consumers can find the actual kernel data directories.

Design notes (politeness and robustness), mirroring ``crawl_pds_archive.py``:

* breadth-first walk with a small worker pool (default 6), a per-request
  timeout, one retry per URL, a node cap (``--limit`` bounds the number of
  directory listings performed) and an optional wall-clock ``--max-time``
  budget, so the tree can never become an unbounded crawl;
* results are appended incrementally to a JSONL sidecar in append mode, so
  a crash or a timeout loses at most the in-flight listing; ``--resume``
  reloads the JSONL and only re-lists directories that were never
  successfully listed;
* HTTP errors are handled per node (status/error recorded on the node, its
  children skipped) and never abort the whole crawl;
* some NAIF directories are not served as an HTML autoindex over HTTP; when
  the HTTP fetch fails or yields no parseable listing, the crawler falls
  back to the FTP service (ftp://naif.jpl.nasa.gov/pub/naif/) using
  ftplib (MLSD when the server supports it, ``LIST`` otherwise) with one
  connection per worker thread.  If FTP proves unreachable (e.g. a
  firewall), the fallback is disabled for the rest of the run and the
  affected nodes keep their recorded HTTP error;
* when the node budget or max-depth stops expansion, parents are marked
  with ``children_explored: false`` so consumers know the tree is partial
  (the asset carries ``partial: true`` in that case).

Usage::

    python scripts/crawl_spice_archive.py --limit 2000 --max-depth 8 --workers 6
    python scripts/crawl_spice_archive.py --limit 2000 --max-depth 8 --resume
    python scripts/crawl_spice_archive.py --consolidate-only
    python scripts/crawl_spice_archive.py --full                     # whole tree
"""

from __future__ import annotations

import argparse
import ftplib
import json
import os
import re
import sys
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import unquote, urljoin

import requests

DEFAULT_ROOT = "https://naif.jpl.nasa.gov/pub/naif/"
DEFAULT_MAX_DEPTH = 8
DEFAULT_WORKERS = 6
DEFAULT_TIMEOUT = 15.0
RETRIES = 1  # extra attempts after the first (retry once)
USER_AGENT = "spedas-agent-kit-archive-crawler/1.0 (NAIF SPICE archive map; polite bot)"

# SPICE kernel / kernel-support file extensions.  A leaf folder containing at
# least one file with one of these extensions is classified as a kernel leaf
# folder ("is_kernel_leaf": true).
KERNEL_EXTS = frozenset({
    ".bsp", ".bpc", ".bc", ".tf", ".tls", ".tsc", ".tpc", ".ti", ".tl",
    ".tm", ".mk", ".txt",            # primary text/binary kernel types
    ".bds", ".bes", ".bpo", ".bdb", ".bbs", ".bcs", ".bph", ".bpl",
    ".bpr", ".bpx", ".bf", ".bt",  # other binary SPK/PCK family variants
    ".lsk", ".pck", ".sclk", ".ck", ".fk", ".ik", ".ek", ".spk",
})

# Apache mod_autoindex <pre> row (NAIF style, same as PDS PPI):
#   <img src="/icons/folder.gif" alt="[DIR]"> <a href="1998/">1998/</a>  2023-12-05 01:39    -
#   <img src="/icons/text.gif" alt="[TXT]"> <a href="readme.txt">readme.txt</a>  2023-11-03 19:56  458K
_ROW_RE = re.compile(
    r"<img[^>]*alt=\"\[?([^\]]*)\]?\"[^>]*>\s*"
    r"<a href=\"([^\"]+)\"[^>]*>(.*?)</a>\s*"
    r"(?:(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s+)?"
    r"(?:([\d.,]+\s*[KMGTP]?|-)?\s*)?$",
    re.IGNORECASE | re.MULTILINE,
)
_SIZE_RE = re.compile(r"^([\d.]+)\s*([KMGTP]?)$", re.IGNORECASE)
_SIZE_MULT = {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4, "P": 1024**5}

# FTP LIST lines look like one of:
#   drwxr-xr-x   2 owner group     4096 Jul 30 15:49 kernels
#   -rw-r--r--   1 owner group     1433 Aug 29  2021 AAREADME
_FTP_LIST_RE = re.compile(
    r"^(?P<mode>[dl-])(?:[rwxsStT-]{9})\s+\d+\s+\S+\s+\S+\s+"
    r"(?P<size>\d+)\s+(?P<month>[A-Z][a-z]{2})\s+(?P<day>\d{1,2})\s+"
    r"(?P<time>(?:\d{1,2}:\d{2}|\d{4}))\s+(?P<name>.+)$"
)
_FTP_MONTHS = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
               "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}


def parse_size(text: str) -> int | None:
    """Parse an Apache autoindex size cell ('458K', '1.4K', '-') into bytes."""
    text = (text or "").strip()
    if not text or text == "-":
        return None
    m = _SIZE_RE.match(text)
    if not m:
        return None
    try:
        return int(float(m.group(1)) * _SIZE_MULT[m.group(2).upper()])
    except (TypeError, ValueError):
        return None


def parse_listing(html: str) -> tuple[list[dict], str | None, str | None, bool]:
    """Parse an autoindex page into (children, first_mtime, last_mtime, ok).

    Each child is ``{"name", "href", "is_dir", "mtime", "size"}``. The
    sort-link rows (``?C=...``) and the Parent Directory row are skipped.
    ``ok`` is False when the page does not look like an autoindex listing at
    all (no ``<pre>`` block, no rows, no 'Index of' title), which triggers the
    FTP fallback in the crawler.
    """
    children: list[dict] = []
    mtims: list[str] = []
    for m in _ROW_RE.finditer(html):
        alt, href, text, mtime, size_txt = m.groups()
        href = href.strip()
        name = unquote(text.strip())
        if not href or href.startswith("?") or href.startswith("/") or href == "..":
            continue  # sort links, parent directory, absolute links
        is_dir = href.endswith("/") or alt.strip().upper() == "DIR"
        if is_dir:
            name = name.rstrip("/")
        size = parse_size(size_txt) if not is_dir else None
        children.append(
            {"name": name, "href": href, "is_dir": is_dir,
             "mtime": mtime or None, "size": size}
        )
        if mtime:
            mtims.append(mtime)
    first = min(mtims) if mtims else None
    last = max(mtims) if mtims else None
    ok = bool(children) or "<pre>" in html or "Index of" in html
    return children, first, last, ok


def ext_of(name: str) -> str:
    """Return the lower-cased extension (with dot) of a file name, or ''."""
    base = name.rsplit("/", 1)[-1]
    dot = base.rfind(".")
    return base[dot:].lower() if dot > 0 else ""


def classify_files(files: list[dict]) -> tuple[list[str], int]:
    """Return (sorted kernel extensions present, kernel file count)."""
    exts = {ext_of(f["name"]) for f in files} & KERNEL_EXTS
    count = sum(1 for f in files if ext_of(f["name"]) in KERNEL_EXTS)
    return sorted(exts), count


def ftp_children_from_list(lines: list[str]) -> list[dict]:
    """Parse raw FTP LIST output into the standard child dicts."""
    children: list[dict] = []
    year_now = datetime.now().year
    for line in lines:
        m = _FTP_LIST_RE.match(line.strip())
        if not m:
            continue
        is_dir = m.group("mode") == "d"
        name = m.group("name")
        if name in (".", ".."):
            continue
        size = None if is_dir else int(m.group("size"))
        tpart = m.group("time")
        if tpart.isdigit():  # year form: "2021"
            year = int(tpart)
            mtime = f"{year:04d}-{m.group('month')}-{m.group('day'):>02s} 00:00"
        else:
            month = _FTP_MONTHS.get(m.group("month"), 1)
            day = int(m.group("day"))
            mtime = f"{year_now:04d}-{month:02d}-{day:02d} {tpart}"
        children.append({"name": name, "href": name + ("/" if is_dir else ""),
                         "is_dir": is_dir, "mtime": mtime, "size": size})
    return children


class FtpFallback:
    """Thread-local anonymous FTP client pool with a global kill switch.

    If FTP proves unreachable (connect refused/timed out), ``disabled`` is set
    and no further connections are attempted for the rest of the run.
    """

    def __init__(self, root_url: str, timeout: float):
        self.host = "naif.jpl.nasa.gov"
        self.root_path = "/pub/naif"
        self.timeout = timeout
        self.disabled = False
        self.attempts = 0
        self.connect_failures = 0
        self.lock = threading.Lock()
        self.local = threading.local()

    def _connect(self) -> ftplib.FTP:
        conn = ftplib.FTP(timeout=self.timeout)
        conn.connect(self.host, 21, timeout=self.timeout)
        conn.login()  # anonymous
        return conn

    def _conn(self) -> ftplib.FTP:
        conn = getattr(self.local, "conn", None)
        if conn is None:
            conn = self._connect()
            self.local.conn = conn
        return conn

    def close(self) -> None:
        conn = getattr(self.local, "conn", None)
        if conn is not None:
            try:
                conn.quit()
            except Exception:
                pass
            self.local.conn = None

    def list(self, path: str) -> tuple[list[dict], bool]:
        """List a directory over FTP; returns (children, ok) and never raises.

        ``ok`` is True when the FTP session answered (even for an empty
        directory), False on connection/listing failure or when disabled.
        """
        if self.disabled:
            return [], False
        with self.lock:
            self.attempts += 1
        try:
            conn = self._conn()
            rel = path.strip("/")
            conn.cwd(self.root_path + ("/" + rel if rel else ""))
            children: list[dict] = []
            try:
                for name, facts in conn.mlsd():
                    if name in (".", ".."):
                        continue
                    is_dir = facts.get("type") == "dir"
                    size = None
                    if not is_dir and facts.get("size") not in (None, ""):
                        try:
                            size = int(facts["size"])
                        except (TypeError, ValueError):
                            size = None
                    mtime = None
                    mod = facts.get("modify")  # YYYYMMDDHHMMSS
                    if mod and len(mod) >= 12 and mod.isdigit():
                        mtime = (f"{mod[0:4]}-{mod[4:6]}-{mod[6:8]} {mod[8:10]}:{mod[10:12]}")
                    children.append({"name": name,
                                     "href": name + ("/" if is_dir else ""),
                                     "is_dir": is_dir, "mtime": mtime, "size": size})
            except ftplib.error_perm:
                # MLSD unsupported -> classic LIST
                lines: list[str] = []
                conn.retrlines("LIST", lines.append)
                children = ftp_children_from_list(lines)
            return children, True
        except Exception:
            self.close()
            with self.lock:
                self.connect_failures += 1
                if self.connect_failures >= 3:
                    self.disabled = True
            return [], False


class Crawler:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.lock = threading.Lock()
        self.visited: set[str] = set()      # dir paths already listed/attempted
        self.queue: deque[tuple[str, str, int]] = deque()  # (path, url, depth)
        self.listed = 0                     # directory listings performed
        self.error_count = 0
        self.budget_exhausted = False
        self.time_budget_hit = False
        self.ftp = FtpFallback(args.root, args.timeout)
        self.stop_at = time.monotonic() + args.max_time if args.max_time else None
        self.start = time.monotonic()
        # --resume: preload successfully listed paths from the JSONL sidecar and
        # re-enqueue the children of parents whose exploration was cut short
        # (budget/time limit), so a later run with a bigger --limit extends the
        # map instead of re-listing everything.
        if args.resume and os.path.exists(args.jsonl):
            pre = 0
            pending_parents: list[dict] = []
            with open(args.jsonl, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if rec.get("status") == 200 and rec.get("path") is not None:
                        self.visited.add(rec["path"])
                        pre += 1
                        if rec.get("child_dir_count") and not rec.get("children_explored"):
                            pending_parents.append(rec)
            self.listed = min(pre, args.limit)
            requeued = 0
            for rec in pending_parents:
                depth = rec.get("depth") or 0
                if depth + 1 > args.max_depth:
                    continue
                for cd in rec.get("child_dirs") or []:
                    child_path = f"{rec['path']}/{cd}" if rec["path"] else cd
                    if child_path in self.visited:
                        continue
                    self.queue.append((child_path, urljoin(rec["url"], cd + "/"), depth + 1))
                    requeued += 1
            print(f"[resume] preloaded {pre} listed directories from {args.jsonl}, "
                  f"requeued {requeued} unexplored children",
                  file=sys.stderr)

    # -- network ------------------------------------------------------------
    def _fill_node(self, node: dict, children: list[dict], method: str) -> None:
        """Populate a node record from parsed children."""
        dirs = [c["name"] for c in children if c["is_dir"]]
        files = [c for c in children if not c["is_dir"]]
        node["method"] = method
        node["status"] = 200
        node["error"] = None
        node["child_dirs"] = sorted(dirs)
        node["child_dir_count"] = len(dirs)
        node["file_count"] = len(files)
        sizes = [c["size"] for c in files if c["size"] is not None]
        node["file_size_total"] = sum(sizes) if sizes else None
        mtims = [c["mtime"] for c in children if c["mtime"]]
        node["first_mtime"] = min(mtims) if mtims else None
        node["last_mtime"] = max(mtims) if mtims else None
        node["is_leaf"] = (len(files) > 0 and len(dirs) == 0)
        node["kernel_extensions"], node["kernel_file_count"] = classify_files(files)
        node["is_kernel_leaf"] = node["is_leaf"] and bool(node["kernel_extensions"])

    def list_dir(self, path: str, url: str, depth: int) -> dict:
        """Fetch one directory listing (HTTP, then FTP fallback); never raises."""
        node = {
            "path": path, "url": url, "depth": depth, "kind": "dir",
            "method": "http", "status": None, "error": None, "child_dirs": [],
            "child_dir_count": 0, "file_count": 0, "file_size_total": None,
            "first_mtime": None, "last_mtime": None, "is_leaf": False,
            "kernel_extensions": [], "kernel_file_count": 0, "is_kernel_leaf": False,
            "children_explored": False,
        }
        http_ok = False
        attempts = RETRIES + 1
        for attempt in range(attempts):
            try:
                resp = self.session.get(url, timeout=self.args.timeout)
                if resp.status_code == 200:
                    children, first, last, ok = parse_listing(resp.text)
                    if ok:
                        self._fill_node(node, children, "http")
                        node["first_mtime"] = first
                        node["last_mtime"] = last
                        http_ok = True
                        break
                    node["status"] = 200
                    node["error"] = "listing parse produced no rows (HTML not autoindex)"
                elif resp.status_code < 500:
                    node["status"] = resp.status_code
                    node["error"] = f"HTTP {resp.status_code}"
                    break
                else:
                    node["status"] = resp.status_code
                    node["error"] = f"HTTP {resp.status_code} (attempt {attempt + 1})"
            except requests.RequestException as exc:  # network-level, retryable
                node["error"] = f"{type(exc).__name__}: {exc} (attempt {attempt + 1})"
            if attempt + 1 < attempts:
                time.sleep(1.0 + attempt)
        node["status"] = node["status"] or 0

        # FTP fallback for nodes HTTP could not serve
        if not http_ok:
            ftp_children, ftp_ok = self.ftp.list(path)
            if ftp_ok:
                self._fill_node(node, ftp_children, "ftp")
            else:
                node["error"] = (node["error"] + "; " if node["error"] else "") \
                    + "FTP fallback failed (ftp_fallback_disabled=%s)" % self.ftp.disabled
        return node

    # -- orchestration ------------------------------------------------------
    def run(self) -> dict:
        root = self.args.root.rstrip("/")
        with self.lock:
            if "" not in self.visited and self.listed < self.args.limit:
                self.queue.append(("", root + "/", 0))
        out = open(self.args.jsonl, "a", encoding="utf-8")
        try:
            with ThreadPoolExecutor(max_workers=self.args.workers) as ex:
                while True:
                    with self.lock:
                        if self.stop_at and time.monotonic() >= self.stop_at:
                            self.time_budget_hit = True
                            print("[crawl] wall-clock budget reached; stopping",
                                  file=sys.stderr)
                            break
                        if self.listed >= self.args.limit:
                            self.budget_exhausted = True
                            print(
                                f"[crawl] node cap reached ({self.args.limit} listings); stopping",
                                file=sys.stderr)
                            break
                        batch = []
                        while self.queue and len(batch) < self.args.workers * 2:
                            item = self.queue.popleft()
                            if item[0] not in self.visited:
                                self.visited.add(item[0])
                                batch.append(item)
                        if not batch and not self.queue:
                            break
                    if not batch:
                        if not self.queue:
                            break
                        continue
                    futs = [ex.submit(self.list_dir, *it) for it in batch]
                    for fut in as_completed(futs):
                        node = fut.result()
                        with self.lock:
                            self.listed += 1
                            if node["status"] == 200 and node["child_dir_count"] == 0:
                                node["children_explored"] = True
                            elif (
                                node["status"] == 200
                                and node["depth"] < self.args.max_depth
                                and self.listed < self.args.limit
                                and not (self.stop_at and time.monotonic() >= self.stop_at)
                            ):
                                for cd in node["child_dirs"]:
                                    child_path = f"{node['path']}/{cd}" if node["path"] else cd
                                    child_url = urljoin(node["url"], cd + "/")
                                    if child_path not in self.visited:
                                        self.queue.append((child_path, child_url, node["depth"] + 1))
                                if node["child_dir_count"]:
                                    node["children_explored"] = True
                            out.write(json.dumps(node, sort_keys=True) + "\n")
                            out.flush()
                            if node["status"] != 200 or node["error"]:
                                self.error_count += 1
        finally:
            out.close()
            self.ftp.close()
        return self.summary()

    def summary(self) -> dict:
        return {
            "root_url": self.args.root,
            "max_depth": self.args.max_depth,
            "workers": self.args.workers,
            "limit": self.args.limit,
            "timeout": self.args.timeout,
            "listed_dirs": self.listed,
            "error_nodes": self.error_count,
            "budget_exhausted": self.budget_exhausted,
            "time_budget_hit": self.time_budget_hit,
            "partial": self.budget_exhausted or self.time_budget_hit,
            "ftp_fallback_attempts": self.ftp.attempts,
            "ftp_fallback_disabled": self.ftp.disabled,
            "duration_s": round(time.monotonic() - self.start, 1),
            "jsonl": self.args.jsonl,
        }


def build_asset(jsonl_path: str, crawl: dict) -> dict:
    """Consolidate the JSONL sidecar into the final tree-map asset."""
    nodes: dict[str, dict] = {}
    with open(jsonl_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            nodes[rec["path"]] = rec

    dir_count = len(nodes)
    leaf_count = sum(1 for n in nodes.values() if n.get("is_leaf"))
    kernel_leaf_count = sum(1 for n in nodes.values() if n.get("is_kernel_leaf"))
    file_entries = sum(n.get("file_count") or 0 for n in nodes.values())
    kernel_file_entries = sum(n.get("kernel_file_count") or 0 for n in nodes.values())
    errors = sum(1 for n in nodes.values() if n.get("status") != 200 or n.get("error"))
    explored = sum(1 for n in nodes.values() if n.get("children_explored"))
    truncated = any(
        n.get("status") == 200 and n.get("child_dir_count") and not n.get("children_explored")
        for n in nodes.values()
    )

    def tree_node(path: str) -> dict:
        rec = nodes[path]
        tn = {
            "path": path,
            "url": rec.get("url"),
            "depth": rec.get("depth"),
            "status": rec.get("status"),
            "method": rec.get("method"),
            "file_count": rec.get("file_count"),
            "file_size_total": rec.get("file_size_total"),
            "first_mtime": rec.get("first_mtime"),
            "last_mtime": rec.get("last_mtime"),
            "is_leaf": rec.get("is_leaf"),
            "is_kernel_leaf": rec.get("is_kernel_leaf"),
            "kernel_extensions": rec.get("kernel_extensions"),
            "child_dir_count": rec.get("child_dir_count"),
            "children_explored": rec.get("children_explored"),
        }
        children = [
            tree_node(f"{path}/{cd}" if path else cd)
            for cd in rec.get("child_dirs") or []
            if (f"{path}/{cd}" if path else cd) in nodes
        ]
        if children:
            tn["children"] = children
        return tn

    tree = tree_node("") if "" in nodes else None

    return {
        "schema": "spedas.spice_archive_map.v1",
        "description": "NAIF SPICE kernel archive directory tree map (https://naif.jpl.nasa.gov/pub/naif/)",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "crawl": crawl,
        "partial": bool(crawl.get("partial") or truncated),
        "stats": {
            "dir_nodes": dir_count,
            "leaf_folder_count": leaf_count,
            "kernel_leaf_folder_count": kernel_leaf_count,
            "total_file_entries": file_entries,
            "kernel_file_entries": kernel_file_entries,
            "error_nodes": errors,
            "nodes_with_explored_children": explored,
            "tree_truncated": truncated,
        },
        "nodes": sorted(nodes.values(), key=lambda n: n["path"]),
        "tree": tree,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=DEFAULT_ROOT, help="archive root URL")
    ap.add_argument("--max-depth", type=int, default=DEFAULT_MAX_DEPTH,
                    help="max directory depth below root (default %(default)s)")
    ap.add_argument("--workers", type=int, default=DEFAULT_WORKERS,
                    help="concurrent listing workers (default %(default)s)")
    ap.add_argument("--limit", type=int, default=2000,
                    help="node cap: max directory listings to perform (default %(default)s)")
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT,
                    help="per-request timeout seconds (default %(default)s)")
    ap.add_argument("--max-time", type=int, default=0,
                    help="hard wall-clock budget in seconds (0 = unlimited)")
    ap.add_argument("--jsonl", default=None,
                    help="incremental JSONL sidecar (default: <output>.jsonl)")
    ap.add_argument("--output", default="data/spice_archive_map.json",
                    help="final JSON asset path (default %(default)s)")
    ap.add_argument("--resume", action="store_true",
                    help="resume from existing JSONL sidecar, skip listed dirs")
    ap.add_argument("--full", action="store_true",
                    help="crawl the whole tree (limit=unlimited)")
    ap.add_argument("--consolidate-only", action="store_true",
                    help="no network; rebuild the final JSON asset from the JSONL sidecar")
    args = ap.parse_args()

    if args.full:
        args.limit = 10**9
    if not args.jsonl:
        args.jsonl = args.output + ".jsonl"
    if args.limit <= 0:
        print("error: --limit must be > 0", file=sys.stderr)
        return 2

    if args.consolidate_only:
        records = 0
        errors = 0
        with open(args.jsonl, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                records += 1
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("status") != 200 or rec.get("error"):
                    errors += 1
        crawl = {
            "root_url": args.root,
            "max_depth": args.max_depth,
            "workers": args.workers,
            "limit": args.limit,
            "timeout": args.timeout,
            "listed_dirs": records,
            "error_nodes": errors,
            "budget_exhausted": records >= args.limit,
            "time_budget_hit": False,
            "partial": records >= args.limit,
            "ftp_fallback_attempts": None,
            "ftp_fallback_disabled": None,
            "duration_s": None,
            "jsonl": args.jsonl,
            "consolidated_from": "jsonl",
        }
    else:
        crawler = Crawler(args)
        crawl = crawler.run()
    asset = build_asset(args.jsonl, crawl)
    # defensive: the output dir may have been removed by a concurrent worker
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(asset, fh, indent=1)
        fh.write("\n")

    st = asset["stats"]
    print(json.dumps({"crawl": crawl, "stats": st, "partial": asset["partial"]}, indent=1))
    print(f"[done] asset written to {args.output} "
          f"({st['dir_nodes']} dir nodes, {st['leaf_folder_count']} leaf folders, "
          f"{st['kernel_leaf_folder_count']} kernel leaf folders)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
