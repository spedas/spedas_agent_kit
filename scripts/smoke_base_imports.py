#!/usr/bin/env python3
"""Prove the base SPEDAS Agent Kit server starts without loading heavy backends.

This is the read-only companion to ``scripts/smoke_installed_artifact.py``: it is
meant to run inside the same clean base-install wheel venv (base dependencies
only, no optional science extras). It imports the package, builds the server,
and lists the base tool/resource surface **in-process**, then asserts that none
of the optional heavy backends were imported as a side effect.

Why in-process rather than a subprocess probe: the only way to observe that a
module was *not* imported is to inspect ``sys.modules`` of the very interpreter
that started the server. A subprocess could not report its own import table back
without extra machinery, and the brief forbids spawning background jobs. Running
in-process also means this smoke needs **no** filesystem at all:

* it never fetches CDAWeb/PDS data or downloads SPICE kernels;
* it never creates a temporary directory, file, cache, or ``__pycache__`` (the
  process is launched with ``PYTHONDONTWRITEBYTECODE=1`` by the caller / CI);
* it starts no subprocess or background job.

Like the installed-artifact smoke, it refuses to add ``src/`` to ``sys.path`` and
fails if the imported package resolves back to the repository source tree, so a
stale editable checkout cannot mask a heavy transitive import that a real base
wheel would avoid.

The check that matters: importing/starting/listing the base server must not pull
in ``pyspedas``, ``matplotlib``, ``pywt``, ``hapiclient``, ``mth5``, or
``obspy``. Those belong to the optional ``[analysis]``/``[hapi]``/``[fdsn]``
extras and are imported lazily by their tools; loading any of them at base
startup would silently make the base install heavier than advertised (issue
#209).

Any heavy optional import, a source-tree import, or a startup failure makes this
exit non-zero with useful JSON output.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

# Optional heavy backend top-level modules that the base install must not load at
# import/startup/list time. These are the roots of the optional
# [analysis]/[hapi]/[fdsn] extras; their tools import them lazily on first call.
FORBIDDEN_OPTIONAL_MODULES = (
    "pyspedas",
    "matplotlib",
    "pywt",
    "hapiclient",
    "mth5",
    "obspy",
)


class SmokeFailure(Exception):
    """Raised with a human-readable reason when a contract check fails."""


def _fail(reason: str) -> None:
    raise SmokeFailure(reason)


def _check_installed_location(repo_root: Path | None) -> str:
    """Import the package and ensure it is not the repo source tree.

    Mirrors ``smoke_installed_artifact.py``: a source-tree import would let a
    heavy transitive dependency present only in the dev checkout hide behind a
    "base install looks clean" result. When ``repo_root`` is not supplied the
    source-tree guard is skipped (the import location is still reported).
    """
    try:
        import spedas_agent_kit  # noqa: F401
    except Exception as exc:  # pragma: no cover - surfaced as a smoke failure
        _fail(f"cannot import spedas_agent_kit: {exc!r}")
    pkg_file = Path(spedas_agent_kit.__file__).resolve()
    if repo_root is not None:
        repo_src = (repo_root / "src").resolve()
        try:
            pkg_file.relative_to(repo_src)
        except ValueError:
            return str(pkg_file)
        _fail(
            "spedas_agent_kit resolved to the repository source tree "
            f"({pkg_file}); run this smoke against an installed wheel, not an "
            "editable/source checkout (or omit --repo-root to skip this guard)"
        )
    return str(pkg_file)


def _loaded_optional_modules() -> list[str]:
    """Return the forbidden optional roots currently present in ``sys.modules``."""
    return [name for name in FORBIDDEN_OPTIONAL_MODULES if name in sys.modules]


def _start_and_list_base_server() -> dict[str, Any]:
    """Run the real default startup path and list its base surface, in-process.

    Calls ``create_server()`` with no override, matching the installed ``serve()``
    entrypoint and therefore exercising optional-backend auto-detection. In the
    clean base-wheel venv no optional extras are installed, so detection must leave
    their modules unloaded and the surface at base. No tool is *called*.
    """
    from spedas_agent_kit.server import create_server

    server = create_server()
    tools = asyncio.run(server.list_tools())
    resources = asyncio.run(server.list_resources())
    return {
        "tool_count": len(tools),
        "tool_names": sorted(tool.name for tool in tools),
        "resource_count": len(resources),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output")
    parser.add_argument(
        "--repo-root",
        default=None,
        help=(
            "Repository root. When given, fail if spedas_agent_kit imports from "
            "<repo-root>/src (guards against a source-tree import masking heavy "
            "transitive deps). Omit to skip the source-tree guard."
        ),
    )
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else None

    payload: dict[str, Any] = {"ok": False}
    try:
        # Baseline: importing the package itself must not drag in a heavy backend.
        payload["installed_package"] = _check_installed_location(repo_root)
        after_import = _loaded_optional_modules()
        if after_import:
            _fail(
                "importing spedas_agent_kit loaded optional heavy backends: "
                + ", ".join(sorted(after_import))
            )

        # Starting + listing the base server must also stay backend-free.
        surface = _start_and_list_base_server()
        payload.update(surface)
        after_start = _loaded_optional_modules()
        if after_start:
            _fail(
                "starting/listing the base server loaded optional heavy backends: "
                + ", ".join(sorted(after_start))
            )

        payload["checked_optional_modules"] = list(FORBIDDEN_OPTIONAL_MODULES)
        payload["ok"] = True
        payload["note"] = (
            "base-import smoke: package imported, base server started and listed "
            "in-process; no optional heavy backend "
            "(pyspedas/matplotlib/pywt/hapiclient/mth5/obspy) loaded; no data "
            "fetch, kernel download, temp dir, or subprocess"
        )
    except SmokeFailure as exc:
        payload["error"] = str(exc)
    except Exception as exc:  # keep --json machine-readable on unexpected failures
        payload["error"] = f"{type(exc).__name__}: {exc}"

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"SPEDAS Agent Kit base-import smoke: {'OK' if payload['ok'] else 'FAIL'}")
        if payload.get("installed_package"):
            print("installed package:", payload["installed_package"])
        if payload.get("tool_count") is not None:
            print("base tools:", payload["tool_count"], "| resources:", payload.get("resource_count"))
        if not payload["ok"]:
            print("error:", payload.get("error"), file=sys.stderr)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
