#!/usr/bin/env python3
"""Crawl the PDS PPI public archive directory tree and map its folder nodes.

This is the upstream-archive crawler for the ``data/pds_archive_map.json``
asset (a spedas MCP asset). It walks the PDS Planetary Plasma
Interactions (PPI) node's public archive root
(https://pds-ppi.igpp.ucla.edu/data, the Apache autoindex-style directory
listing) and records every directory node it discovers: relative path, URL,
depth, child directory names, file count, min/max child mtime, aggregate
file size when the listing exposes it, and a leaf-folder classification
(a directory that contains files and has no subdirectories is the final
data folder where actual data files live).

Design notes (politeness and robustness):

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
* only directory nodes require a network request (their listing carries the
  name/mtime/size of every child entry), so ``--limit N`` bounds work to N
  directory listings;
* when the node budget or max-depth stops expansion, parents are marked
  with ``children_explored: false`` so consumers know the tree is partial.

Usage::

    python scripts/crawl_pds_archive.py --limit 2000 --max-depth 8 --workers 6
    python scripts/crawl_pds_archive.py --limit 2000 --max-depth 8 --resume
    python scripts/crawl_pds_archive.py --full                     # whole tree
"""

from __future__ import annotations

import argparse
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

DEFAULT_ROOT = "https://pds-ppi.igpp.ucla.edu/data"
DEFAULT_MAX_DEPTH = 8
DEFAULT_WORKERS = 6
DEFAULT_TIMEOUT = 15.0
RETRIES = 1  # extra attempts after the first (retry once)
USER_AGENT = "spedas-agent-kit-archive-crawler/1.0 (PDS PPI archive map; polite bot)"

# Apache mod_autoindex <pre> row (PDS PPI style):
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


def parse_size(text: str) -> int | None:
    """Parse an Apache autoindex size cell ('458K', '13K', '-') into bytes."""
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


def parse_listing(html: str) -> tuple[list[dict], int | None, int | None]:
    """Parse an autoindex page into (children, first_mtime, last_mtime).

    Each child is ``{"name", "href", "is_dir", "mtime", "size"}``. The
    sort-link rows (``?C=...``) and the Parent Directory row are skipped.
    Returns min/max mtime (as raw strings) across the children, if any.
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
    return children, first, last


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
        self.stop_at = time.monotonic() + args.max_time if args.max_time else None
        self.start = time.monotonic()
        # --resume: preload successfully listed paths from the JSONL sidecar
        if args.resume and os.path.exists(args.jsonl):
            pre = 0
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
            self.listed = min(pre, args.limit)
            print(f"[resume] preloaded {pre} listed directories from {args.jsonl}",
                  file=sys.stderr)

    # -- network ------------------------------------------------------------
    def list_dir(self, path: str, url: str, depth: int) -> dict:
        """Fetch one directory listing; never raises; returns the node record."""
        node = {
            "path": path, "url": url, "depth": depth, "kind": "dir",
            "status": None, "error": None, "child_dirs": [],
            "child_dir_count": 0, "file_count": 0, "file_size_total": None,
            "first_mtime": None, "last_mtime": None, "is_leaf": False,
            "children_explored": False,
        }
        attempts = RETRIES + 1
        for attempt in range(attempts):
            try:
                resp = self.session.get(url, timeout=self.args.timeout)
                if resp.status_code == 200:
                    children, first, last = parse_listing(resp.text)
                    node["status"] = 200
                    node["error"] = None  # a later attempt may succeed
                    node["first_mtime"] = first
                    node["last_mtime"] = last
                    dirs = [c["name"] for c in children if c["is_dir"]]
                    files = [c for c in children if not c["is_dir"]]
                    node["child_dirs"] = sorted(dirs)
                    node["child_dir_count"] = len(dirs)
                    node["file_count"] = len(files)
                    sizes = [c["size"] for c in files if c["size"] is not None]
                    node["file_size_total"] = sum(sizes) if sizes else None
                    node["is_leaf"] = (len(files) > 0 and len(dirs) == 0)
                    return node
                if resp.status_code < 500:
                    node["status"] = resp.status_code
                    node["error"] = f"HTTP {resp.status_code}"
                    return node
                node["status"] = resp.status_code
                node["error"] = f"HTTP {resp.status_code} (attempt {attempt + 1})"
            except requests.RequestException as exc:  # network-level, retryable
                node["error"] = f"{type(exc).__name__}: {exc} (attempt {attempt + 1})"
            if attempt + 1 < attempts:
                time.sleep(1.0 + attempt)
        node["status"] = node["status"] or 0
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
                            # enqueue child dirs within depth/budget; flag exploration
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
    file_entries = sum(n.get("file_count") or 0 for n in nodes.values())
    errors = sum(1 for n in nodes.values() if n.get("status") != 200)
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
            "file_count": rec.get("file_count"),
            "file_size_total": rec.get("file_size_total"),
            "first_mtime": rec.get("first_mtime"),
            "last_mtime": rec.get("last_mtime"),
            "is_leaf": rec.get("is_leaf"),
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
        "schema": "spedas.pds_archive_map.v1",
        "description": "PDS PPI public archive directory tree map (https://pds-ppi.igpp.ucla.edu/data)",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "crawl": crawl,
        "stats": {
            "dir_nodes": dir_count,
            "leaf_folder_count": leaf_count,
            "total_file_entries": file_entries,
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
    ap.add_argument("--output", default="data/pds_archive_map.json",
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
                if rec.get("status") != 200:
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
    print(json.dumps({"crawl": crawl, "stats": st}, indent=1))
    print(f"[done] asset written to {args.output} "
          f"({st['dir_nodes']} dir nodes, {st['leaf_folder_count']} leaf folders)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
