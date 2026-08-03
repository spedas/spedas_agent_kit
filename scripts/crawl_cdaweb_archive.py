#!/usr/bin/env python3
"""Crawl the CDAWeb public archive directory tree and map its folder nodes.

This is the upstream-archive crawler for the ``data/cdaweb_archive_map.json``
asset. It walks https://cdaweb.gsfc.nasa.gov/pub/data/ (the public HTTP
directory listing, with an ftplib fallback to
ftp://cdaweb.gsfc.nasa.gov/pub/data/), records every node it discovers
(relative path, kind, URL, child count, HTTP status, size), and identifies
*leaf folders*: directories that contain data files and no subdirectories
(the final dataset folders where actual data files live).

The vendored observatory catalog under
``src/spedas_agent_kit/backends/cdaweb/data/observatories/`` is a separate,
curated asset and is never touched by this script.

Design notes (politeness and robustness):

* breadth-first walk with a small worker pool (default 6), 15 s per-request
  timeout, one retry per URL, and a fixed crawl budget so the tree never
  becomes an unbounded crawl;
* results are appended incrementally to a JSONL sidecar file, so a crash
  loses at most the in-flight directory listing; ``--resume`` reloads the
  JSONL and only re-lists directories that were never successfully listed;
* only directory nodes require a network request (their listing carries the
  name/size of every child file), so ``--limit N`` bounds work to N directory
  listings.

Usage::

    python scripts/crawl_cdaweb_archive.py --limit 2000 --max-depth 6
    python scripts/crawl_cdaweb_archive.py --full          # whole tree
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
from html import unescape
from urllib.parse import unquote, urljoin, urlparse

import requests

DEFAULT_ROOT = "https://cdaweb.gsfc.nasa.gov/pub/data/"
DEFAULT_MAX_DEPTH = 6
DEFAULT_WORKERS = 6
DEFAULT_TIMEOUT = 15.0
RETRIES = 1  # extra attempts after the first (retry once)
USER_AGENT = "spedas-agent-kit-archive-crawler/1.0 (data asset refresh; polite bot)"

# Apache mod_autoindex row: <td><a href="name">name</a></td><td ...>date</td><td ...>size</td>
_ROW_RE = re.compile(
    r"<tr>.*?<td[^>]*>\s*<a[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>\s*</td>"
    r"\s*<td[^>]*>.*?</td>\s*<td[^>]*>(.*?)</td>\s*</tr>",
    re.IGNORECASE | re.DOTALL,
)
_SIZE_RE = re.compile(r"^([\d.]+)\s*([KMGTP]?)$", re.IGNORECASE)

_SIZE_MULT = {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4, "P": 1024**5}


def parse_size(text: str) -> int | None:
    """Parse an Apache autoindex size cell ('3.7K', '512', '-') into bytes."""
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


def clean_name(text: str) -> str:
    """Strip tags/entities and symlink arrows from a listing entry name."""
    name = re.sub(r"<[^>]+>", "", text or "")
    name = unescape(name).strip()
    name = re.sub(r"\s*->\s*.*$", "", name).strip()  # 'name -> target'
    return name


class ListingEntry:
    __slots__ = ("name", "href", "is_dir", "size")

    def __init__(self, name: str, href: str, is_dir: bool, size: int | None):
        self.name = name
        self.href = href
        self.is_dir = is_dir
        self.size = size


def parse_http_listing(html: str) -> list[ListingEntry]:
    """Parse an Apache mod_autoindex HTML listing."""
    entries: list[ListingEntry] = []
    for href, name_html, size_html in _ROW_RE.findall(html):
        name = clean_name(name_html)
        if not name or name in ("Parent Directory", "..", "."):
            continue
        href = href.split("?", 1)[0]  # drop sort-query suffixes
        is_dir = href.endswith("/") or name.endswith("/")
        entries.append(ListingEntry(name, href, is_dir, parse_size(size_html)))
    return entries


def parse_ftp_listing(lines: list[str]) -> list[ListingEntry]:
    """Parse a classic unix FTP LIST output (drwxr-xr-x / -rw-r--r--)."""
    entries: list[ListingEntry] = []
    for line in lines:
        if len(line) < 40 or line.startswith("total"):
            continue
        perms = line[:10]
        fields = line.split()
        if len(fields) < 9:
            continue
        is_dir = perms.startswith("d")
        size = None
        if not is_dir:
            try:
                size = int(fields[4])
            except ValueError:
                size = None
        name = " ".join(fields[8:]).strip()
        if not name or name in (".", ".."):
            continue
        entries.append(ListingEntry(name, name + ("/" if is_dir else ""), is_dir, size))
    return entries


def fetch_listing_http(session: requests.Session, url: str, timeout: float) -> tuple[int, list[ListingEntry]]:
    """Fetch a directory listing over HTTP(S). Returns (status_code, entries)."""
    last_code = 0
    for attempt in range(RETRIES + 1):
        try:
            resp = session.get(url, timeout=timeout)
            last_code = resp.status_code
            if resp.status_code != 200:
                if attempt < RETRIES:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                return resp.status_code, []
            return resp.status_code, parse_http_listing(resp.text)
        except requests.RequestException:
            if attempt < RETRIES:
                time.sleep(0.5 * (attempt + 1))
                continue
            return last_code or 0, []
    return last_code, []


def fetch_listing_ftp(url: str, timeout: float) -> tuple[int, list[ListingEntry]]:
    """Fetch a directory listing over FTP (ftplib fallback)."""
    import ftplib

    parsed = urlparse(url)
    try:
        ftp = ftplib.FTP(parsed.hostname, timeout=timeout)
        ftp.login()
        lines: list[str] = []
        ftp.retrlines("LIST " + unquote(parsed.path), lines.append)
        ftp.quit()
        return 200, parse_ftp_listing(lines)
    except Exception:
        return 0, []


class Crawler:
    """BFS crawler over the CDAWeb public archive tree."""

    def __init__(self, root: str, max_depth: int, limit: int | None, workers: int,
                 timeout: float, output_map: str, jsonl_path: str, resume: bool):
        self.root = root.rstrip("/") + "/"
        self.max_depth = max_depth
        self.limit = limit
        self.workers = workers
        self.timeout = timeout
        self.output_map = output_map
        self.jsonl_path = jsonl_path

        self.nodes: dict[str, dict] = {}  # relative path -> node record
        self.lock = threading.Lock()
        self.fetched = 0          # directory listings successfully fetched
        self.failed = 0           # directory listings that errored
        self.skipped = 0          # listings dropped because limit was reached
        self._stop_enqueue = threading.Event()

        self._jsonl = None
        self._jsonl_lock = threading.Lock()
        self._session = requests.Session()
        self._session.headers["User-Agent"] = USER_AGENT
        if resume:
            self._load_jsonl()

    # ------------------------------------------------------------------ helpers
    def _rel_path(self, url: str) -> str:
        """Derive the relative path (no leading/trailing slash) from a URL."""
        root_path = urlparse(self.root).path.rstrip("/")
        p = unquote(urlparse(url).path)
        if p.startswith(root_path):
            p = p[len(root_path):]
        return p.strip("/")

    def _abs_url(self, rel: str) -> str:
        if not rel:
            return self.root
        return urljoin(self.root, rel + ("/" if not rel.endswith("/") else ""))

    def _record(self, node: dict) -> None:
        """Insert/update a node in memory and append to the JSONL sidecar."""
        with self.lock:
            self.nodes[node["path"]] = node
        with self._jsonl_lock:
            if self._jsonl is not None:
                self._jsonl.write(json.dumps(node, sort_keys=True) + "\n")
                self._jsonl.flush()

    def _load_jsonl(self) -> None:
        """Preload nodes from a previous run; only re-list unlisted dirs."""
        if not os.path.exists(self.jsonl_path):
            return
        with open(self.jsonl_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    node = json.loads(line)
                except json.JSONDecodeError:
                    continue
                self.nodes[node["path"]] = node
        # count already-fetched listings so --limit stays meaningful
        self.fetched = sum(1 for n in self.nodes.values()
                           if n["kind"] == "dir" and n.get("status") == 200)

    def _pending_dirs(self) -> list[tuple[str, str, int]]:
        """Directories known but never successfully listed, in BFS order.

        Returns (relative path, url, depth-at-which-to-list) tuples; the root
        is included when it has not been listed yet.
        """
        queue: deque[tuple[str, str, int]] = deque()
        seen: set[str] = set()
        root_node = self.nodes.get("")
        if root_node is None or root_node.get("status") != 200:
            queue.append(("", self.root, 0))
            seen.add("")
        for depth in range(0, self.max_depth + 1):
            for path, node in sorted(self.nodes.items()):
                if node["kind"] != "dir" or node.get("status") == 200:
                    continue
                if path.count("/") != depth:
                    continue
                if path not in seen:
                    queue.append((path, node["url"], depth + 1))
                    seen.add(path)
        return list(queue)

    # ------------------------------------------------------------------ crawl
    def _list_dir(self, rel: str, url: str) -> dict:
        """List one directory; returns the updated dir node."""
        status, entries = fetch_listing_http(self._session, url, self.timeout)
        if status != 200:
            status, entries = fetch_listing_ftp(url, self.timeout)
        with self.lock:
            self.fetched += 1 if status == 200 else 0
            self.failed += 0 if status == 200 else 1

        dir_node = {"path": rel, "kind": "dir", "url": url,
                    "children": len(entries), "status": status, "size": None}
        self._record(dir_node)

        if status != 200:
            return dir_node

        for e in entries:
            child_rel = ((rel + "/") if rel else "") + e.name
            child_url = urljoin(url, e.href)
            if e.is_dir:
                child_rel = child_rel.rstrip("/")
                child_node = {"path": child_rel, "kind": "dir", "url": child_url,
                              "children": 0, "status": None, "size": None}
            else:
                child_node = {"path": child_rel, "kind": "file", "url": child_url,
                              "children": 0, "status": status, "size": e.size}
            self._record(child_node)
        return dir_node

    def run(self) -> None:
        """Run the BFS crawl and write the final map."""
        os.makedirs(os.path.dirname(self.output_map) or ".", exist_ok=True)
        self._jsonl = open(self.jsonl_path, "a", encoding="utf-8")

        # seed: root node exists so children/pending logic is uniform
        if "" not in self.nodes:
            self._record({"path": "", "kind": "dir", "url": self.root,
                          "children": 0, "status": None, "size": None})

        t_start = time.monotonic()
        try:
            # Seed the BFS with pending directories (on a fresh run that is
            # just the root; on --resume it continues from wherever the
            # previous run stopped, re-listing nothing that already succeeded).
            pending = self._pending_dirs()
            round_tasks = [(p, u, d) for p, u, d in pending]
            while round_tasks and not self._stop_enqueue.is_set():
                if self.limit is not None and self.fetched >= self.limit:
                    self._stop_enqueue.set()
                    self.skipped += len(round_tasks)
                    break
                next_round: list[tuple[str, str, int]] = []
                with ThreadPoolExecutor(max_workers=self.workers) as pool:
                    futs = {}
                    for rel, url, depth in round_tasks:
                        if self.limit is not None and self.fetched + len(futs) >= self.limit:
                            self._stop_enqueue.set()
                            break
                        futs[pool.submit(self._list_dir, rel, url)] = (rel, url, depth)
                    for fut in as_completed(futs):
                        rel, url, depth = futs[fut]
                        node = fut.result()
                        if node["status"] != 200:
                            continue
                        if depth >= self.max_depth or self._stop_enqueue.is_set():
                            continue
                        # children known from the listing; enqueue only subdirs
                        prefix = rel + "/" if rel else ""
                        for path, n in sorted(self.nodes.items()):
                            if (n["kind"] == "dir" and n.get("status") is None
                                    and path.startswith(prefix) and "/" not in path[len(prefix):]):
                                next_round.append((path, n["url"], depth + 1))
                round_tasks = next_round
        finally:
            self._jsonl.close()
            self._jsonl = None

        elapsed = time.monotonic() - t_start
        self.write_map(elapsed)
        self._summary(elapsed)

    def finalize(self) -> None:
        """Write the map from the JSONL sidecar only (no network)."""
        self._load_jsonl()
        if "" not in self.nodes:
            self._record({"path": "", "kind": "dir", "url": self.root,
                          "children": 0, "status": None, "size": None})
        self.write_map(0.0)
        self._summary(0.0)

    # ------------------------------------------------------------------ output
    def leaf_folder_paths(self) -> list[str]:
        """Directories with >=1 child and no subdirectory children."""
        leaves: list[str] = []
        for path, node in self.nodes.items():
            if node["kind"] != "dir" or node.get("status") != 200 or node["children"] == 0:
                continue
            prefix = path + "/" if path else ""
            has_subdir = any(n["kind"] == "dir" and p.startswith(prefix)
                             and "/" not in p[len(prefix):]
                             for p, n in self.nodes.items())
            if not has_subdir:
                leaves.append(path)
        return leaves

    def write_map(self, elapsed: float) -> None:
        """Assemble and write the final JSON asset."""
        leaves = self.leaf_folder_paths()
        pending_dirs = sum(1 for n in self.nodes.values()
                           if n["kind"] == "dir" and n.get("status") != 200)
        partial = (pending_dirs > 0
                   or (self.limit is not None and self.fetched >= self.limit)
                   or self.skipped > 0)
        map_data = {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "root": self.root,
            "total_nodes": len(self.nodes),
            "leaf_folder_count": len(leaves),
            "partial": partial,
            "limits": {
                "max_depth": self.max_depth,
                "dir_listings_fetched": self.fetched,
                "dir_listings_failed": self.failed,
                "dir_listings_skipped": self.skipped,
                "dirs_pending": pending_dirs,
                "limit": self.limit,
            },
            "elapsed_seconds": round(elapsed, 1),
            "nodes": sorted(self.nodes.values(), key=lambda n: n["path"]),
        }
        tmp = self.output_map + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(map_data, fh, separators=(",", ":"))
        os.replace(tmp, self.output_map)

    def _summary(self, elapsed: float) -> None:
        leaves = len(self.leaf_folder_paths())
        print(f"crawl finished in {elapsed:.1f}s")
        print(f"dir listings fetched: {self.fetched}  failed: {self.failed}  skipped: {self.skipped}")
        print(f"total nodes: {len(self.nodes)}  leaf folders: {leaves}")
        print(f"map written: {self.output_map}")
        print(f"jsonl sidecar: {self.jsonl_path}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=DEFAULT_ROOT, help="archive root URL (default: %(default)s)")
    ap.add_argument("--max-depth", type=int, default=DEFAULT_MAX_DEPTH,
                    help="stop descending below this directory depth (default: %(default)s)")
    ap.add_argument("--limit", type=int, default=None, metavar="N",
                    help="max directory listings to fetch (smoke runs); None = unlimited")
    ap.add_argument("--full", action="store_true",
                    help="full crawl: no listing limit (same as omitting --limit)")
    ap.add_argument("--workers", type=int, default=DEFAULT_WORKERS,
                    help="worker pool size (default: %(default)s)")
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT,
                    help="per-request timeout seconds (default: %(default)s)")
    ap.add_argument("--output", default="data/cdaweb_archive_map.json",
                    help="map output path (default: %(default)s)")
    ap.add_argument("--jsonl", default=None,
                    help="incremental JSONL sidecar (default: <output>.jsonl)")
    ap.add_argument("--resume", action="store_true",
                    help="reload the JSONL sidecar and re-list only unfinished dirs")
    ap.add_argument("--finalize", action="store_true",
                    help="write the map from the JSONL sidecar only (no network)")
    args = ap.parse_args(argv)

    if args.full:
        args.limit = None
    if args.max_depth < 0:
        ap.error("--max-depth must be >= 0")
    if args.limit is not None and args.limit <= 0:
        ap.error("--limit must be a positive integer")

    jsonl = args.jsonl or (args.output + ".jsonl")
    crawler = Crawler(args.root, args.max_depth, args.limit, args.workers,
                      args.timeout, args.output, jsonl, args.resume)
    if args.finalize:
        crawler.finalize()
        return 0
    crawler.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
