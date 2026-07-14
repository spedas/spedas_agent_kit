#!/usr/bin/env python3
"""Prove the *installed* wheel's ``[analysis]`` profile registers every analysis tool.

Companion to ``scripts/smoke_installed_artifact.py`` (which validates the base
installed wheel) and to ``scripts/smoke_analysis_imports.py`` (which validates the
same analysis surface but from the *source checkout*). This script sits in the
gap the CI green run does not otherwise cover: it runs inside a clean virtual
environment where only the built wheel — installed through its declared
``[analysis]`` extra — is present, and proves that the wheel researchers receive
can install its advertised analysis profile and expose the complete canonical
analysis tool surface without borrowing any code from the repository checkout.

Unlike ``smoke_analysis_imports.py`` it therefore does **not** import
``_smoke_runtime`` and never calls ``ensure_source_tree_on_path()``: adding
``src/`` to ``sys.path`` would let the source tree — not the installed wheel —
satisfy the imports and the tool registration, silently hiding a broken
``[analysis]`` extra (undeclared/unresolvable optional dependency, wrong install
origin, or failed auto-detection).

It checks, network-free (no CDAWeb/PDS fetch, no SPICE kernel download):

1. ``spedas_agent_kit`` imports from an installed location, not repo ``src/``
   (fails loudly if it resolves beneath ``<repo-root>/src``);
2. every canonical required analysis module/attribute in the installed package's
   ``ANALYSIS_REQUIRED_IMPORTS`` imports successfully (the exact backends the
   analysis tools call, read from the installed package rather than hand-copied);
3. the installed package reports ``analysis_dependencies_available()`` is True;
4. the real default server built by ``create_server()`` — with *normal* optional
   auto-detection, i.e. ``include_analysis_tools`` is left at its ``None`` default
   and never forced to ``True`` — advertises every member of the installed
   package's ``ANALYSIS_TOOL_NAMES`` in ``list_tools()`` (the expected list is
   imported from the package, never hand-copied here).

Any missing/undeclared analysis dependency, a source-tree import, or a missing
analysis tool makes this exit non-zero with useful JSON output, matching the
existing smoke conventions.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import importlib
import io
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any


class SmokeFailure(Exception):
    """Raised with a human-readable reason when a contract check fails."""


def _fail(reason: str) -> None:
    raise SmokeFailure(reason)


def source_tree_import_error(pkg_file: str, repo_root: Path | None) -> str | None:
    """Return an error message if ``pkg_file`` resolves beneath ``<repo_root>/src``.

    Pure over the already-resolved package ``__file__`` and the repo root so the
    installed-vs-source guard can be unit tested without building or installing a
    wheel. Returns ``None`` when the import location is acceptable (installed
    wheel, or no ``repo_root`` supplied to guard against). Mirrors the guard in
    ``smoke_installed_artifact._check_installed_location`` but as a testable
    return-value helper rather than a raising side effect.
    """
    if repo_root is None:
        return None
    resolved = Path(pkg_file).resolve()
    repo_src = (repo_root / "src").resolve()
    try:
        resolved.relative_to(repo_src)
    except ValueError:
        return None
    return (
        "spedas_agent_kit resolved to the repository source tree "
        f"({resolved}); this validator must run against an installed wheel with "
        "the [analysis] extra, not an editable/source checkout"
    )


def _check_installed_location(repo_root: Path | None) -> str:
    """Import the package and ensure it is an installed copy, not repo ``src/``."""
    try:
        import spedas_agent_kit  # noqa: F401
    except Exception as exc:  # pragma: no cover - surfaced as a smoke failure
        _fail(f"cannot import spedas_agent_kit from the installed environment: {exc!r}")
    pkg_file = str(Path(spedas_agent_kit.__file__).resolve())
    error = source_tree_import_error(pkg_file, repo_root)
    if error is not None:
        _fail(error)
    return pkg_file


def _probe_required_imports(
    required_imports: Sequence[tuple[str, str | None]],
) -> tuple[list[str], list[dict[str, str]]]:
    """Return (missing, captured_notes) for the analysis import probes.

    Mirrors ``smoke_analysis_imports._probe_required_imports`` but drives the
    ``ANALYSIS_REQUIRED_IMPORTS`` read from the *installed* package.
    """
    missing: list[str] = []
    notes: list[dict[str, str]] = []
    for module_name, attr_name in required_imports:
        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                module = importlib.import_module(module_name)
        except Exception as exc:  # pragma: no cover - exercised by smoke failures
            missing.append(f"{module_name}: {type(exc).__name__}: {exc}")
        else:
            if attr_name is not None and not hasattr(module, attr_name):
                missing.append(f"{module_name}.{attr_name}: missing attribute")
        out = stdout.getvalue().strip()
        err = stderr.getvalue().strip()
        if out or err:
            notes.append({"module": module_name, "stdout": out, "stderr": err})
    return missing, notes


async def _default_tool_names() -> list[str]:
    """Names advertised by the real default server with normal auto-detection.

    ``create_server()`` is called with no arguments: ``include_analysis_tools``
    stays at its ``None`` default so the server's own optional-backend
    auto-detection — not a forced override — is what must register the analysis
    group in the clean analysis-wheel venv.
    """
    from spedas_agent_kit.server import create_server

    server = create_server()
    return [tool.name for tool in await server.list_tools()]


def _missing_analysis_tools(
    tool_names: Sequence[str], analysis_tool_names: Sequence[str]
) -> list[str]:
    names = set(tool_names)
    return [name for name in analysis_tool_names if name not in names]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output")
    parser.add_argument(
        "--repo-root",
        default=None,
        help=(
            "Repository root. When given, fail if spedas_agent_kit imports from "
            "<repo-root>/src (guards against a source-tree import satisfying the "
            "analysis surface instead of the installed wheel). Omit to skip the "
            "source-tree guard."
        ),
    )
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else None

    payload: dict[str, Any] = {"ok": False}
    try:
        # 1. Installed-location guard: never satisfy this from the repo src tree.
        payload["installed_package"] = _check_installed_location(repo_root)

        # Read the canonical analysis constants from the INSTALLED package, so a
        # stale/hand-copied list cannot mask a wheel that ships a different set.
        from spedas_agent_kit.optional_backends import (
            ANALYSIS_REQUIRED_IMPORTS,
            ANALYSIS_TOOL_NAMES,
            analysis_dependencies_available,
        )

        # The selected installed-artifact contract is exactly 13 unique canonical
        # analysis tools. Requiring only "every current member" would let an
        # accidentally shortened or duplicate wheel constant pass silently.
        analysis_tool_names = tuple(ANALYSIS_TOOL_NAMES)
        unique_analysis_tool_names = set(analysis_tool_names)
        if len(analysis_tool_names) != 13 or len(unique_analysis_tool_names) != 13:
            _fail(
                "installed ANALYSIS_TOOL_NAMES must contain exactly 13 unique names; "
                f"got {len(analysis_tool_names)} entries / "
                f"{len(unique_analysis_tool_names)} unique: {analysis_tool_names}"
            )

        # 2. Every canonical required analysis import must succeed from the wheel's
        #    installed [analysis] dependency closure.
        missing_imports, import_notes = _probe_required_imports(ANALYSIS_REQUIRED_IMPORTS)
        if missing_imports:
            _fail(
                "installed [analysis] extra is missing required imports: "
                + "; ".join(missing_imports)
            )

        # 3. The package's own availability probe must agree.
        analysis_available = analysis_dependencies_available()
        if not analysis_available:
            _fail(
                "installed package reports analysis_dependencies_available() is "
                "False despite the [analysis] extra being installed"
            )

        # 4. Default auto-detection (no forced include_analysis_tools) must register
        #    the full canonical analysis tool group in the real list_tools().
        tool_names = asyncio.run(_default_tool_names())
        missing_tools = _missing_analysis_tools(tool_names, analysis_tool_names)
        if missing_tools:
            _fail(
                "default server (normal auto-detection) is missing canonical "
                "analysis tools: " + ", ".join(missing_tools)
            )

        payload["analysis_dependencies_available"] = analysis_available
        payload["required_imports_count"] = len(ANALYSIS_REQUIRED_IMPORTS)
        payload["analysis_tool_count"] = len(analysis_tool_names)
        payload["default_tool_count"] = len(tool_names)
        payload["analysis_tools"] = list(analysis_tool_names)
        payload["import_notes"] = import_notes
        payload["ok"] = True
        payload["note"] = (
            "installed-wheel analysis smoke: [analysis] extra imports resolved "
            "from the installed wheel (not repo src), default auto-detection "
            "registered every canonical analysis tool; no data fetch or kernel "
            "download"
        )
    except SmokeFailure as exc:
        payload["error"] = str(exc)
    except Exception as exc:  # keep --json machine-readable on dependency/protocol failures
        payload["error"] = f"{type(exc).__name__}: {exc}"

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(
            "SPEDAS Agent Kit installed-analysis smoke: "
            f"{'OK' if payload['ok'] else 'FAIL'}"
        )
        if payload.get("installed_package"):
            print("installed package:", payload["installed_package"])
        if payload.get("default_tool_count") is not None:
            print(
                "analysis tools:",
                payload.get("analysis_tool_count"),
                "| default tools:",
                payload["default_tool_count"],
            )
        if not payload["ok"]:
            print("error:", payload.get("error"), file=sys.stderr)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
