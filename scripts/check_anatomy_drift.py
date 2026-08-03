#!/usr/bin/env python3
"""Cheap, advisory ANATOMY drift checker (adapted from the LingTai kernel).

ANATOMY.md files are the repo's navigation map. The most common drift mode is
mechanically detectable:

**Citation rot** - a `file.py:line` citation points at a missing file or a line
past the end of the file (after a refactor moved/shrank the code).

This does NOT prove semantic correctness - a citation can be in-range yet point
at the wrong code. An agent still has to open the cited line and confirm the
claim. This checker only catches the *obvious* citation drift cheaply, so it
can run in CI or pre-commit as an advisory gate.

Usage (run from the repo root - cwd is taken as the repo root):
    python3 scripts/check_anatomy_drift.py            # report, exit 0 unless --check
    python3 scripts/check_anatomy_drift.py --check    # exit 1 if any drift found
    python3 scripts/check_anatomy_drift.py --root src/spedas_agent_kit
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# `file.py` or `file.py:123` or `file.py:123-456`, optionally backticked.
# The path part allows repo-relative paths (src/.../file.py) and plain names.
_CITATION_RE = re.compile(r"([A-Za-z0-9_./-]+\.py):(\d+)(?:-(\d+))?")


def find_anatomy_files(root: Path) -> list[Path]:
    return sorted(root.rglob("ANATOMY.md"))


def resolve_path(rel: str, anatomy: Path, repo_root: Path) -> Path | None:
    """Resolve a cited path to a real file.

    Citations in this repo are written repo-relative (e.g.
    `src/spedas_agent_kit/server.py:1044`), so try the repo root first. For
    backward compatibility with anatomy-local citations, also try the anatomy's
    directory and each ancestor up to the repo root.
    """
    candidates: list[Path] = []
    if rel.startswith("src/") or "/" in rel:
        candidates.append(repo_root / rel)
    else:
        # Plain filename: prefer the repo root, then the anatomy's directory
        # and each ancestor (kernel-style resolution).
        candidates.append(repo_root / rel)
        base = anatomy.parent
        while True:
            candidates.append(base / rel)
            if base == repo_root or base.parent == base:
                break
            base = base.parent
    for cand in candidates:
        if cand.is_file():
            return cand
    return None


def line_count(path: Path) -> int:
    with path.open("rb") as f:
        return sum(1 for _ in f)


def check_citations(anatomy: Path, repo_root: Path) -> list[str]:
    problems: list[str] = []
    text = anatomy.read_text(encoding="utf-8")
    for m in _CITATION_RE.finditer(text):
        rel, start, end = m.group(1), int(m.group(2)), m.group(3)
        target = resolve_path(rel, anatomy, repo_root)
        if target is None:
            problems.append(f"missing citation target {rel}:{start}")
            continue
        n = line_count(target)
        hi = int(end) if end else start
        if hi > n:
            problems.append(f"out-of-range citation {rel}:{m.group(0).split(':', 1)[1]} > {n} lines")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=".",
        help="directory to scan for ANATOMY.md files (default: repo root)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero if any drift is found (for CI / pre-commit)",
    )
    args = parser.parse_args(argv)

    repo_root = Path.cwd()
    root = Path(args.root)
    if not root.is_absolute():
        root = repo_root / root

    anatomy_files = find_anatomy_files(root)
    if not anatomy_files:
        print(f"no ANATOMY.md files found under {root}", file=sys.stderr)
        return 0

    total = 0
    for anatomy in anatomy_files:
        problems = check_citations(anatomy, repo_root)
        if problems:
            rel = anatomy.relative_to(repo_root) if anatomy.is_relative_to(repo_root) else anatomy
            print(f"\n{rel}:")
            for p in problems:
                print(f"  - {p}")
            total += len(problems)

    if total:
        print(f"\n{total} anatomy drift item(s) found across {len(anatomy_files)} file(s).")
        return 1 if args.check else 0
    print(f"No anatomy drift found across {len(anatomy_files)} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
