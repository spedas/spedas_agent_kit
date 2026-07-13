#!/usr/bin/env python3
"""Prove the *installed* SPEDAS Agent Kit wheel is usable, not just the source tree.

Unlike the other ``smoke_*`` scripts under ``scripts/`` (which deliberately
prepend the repository ``src/`` tree to ``sys.path`` so they exercise the
checked-out working copy), this validator is meant to run inside a clean virtual
environment where only the built wheel has been installed. It therefore refuses
to add ``src/`` to the path and actively fails if the imported package resolves
back to the repository source tree — that would silently hide missing package
data or undeclared dependencies.

It checks, network-free:

1. ``spedas_agent_kit`` imports from an installed location (not repo ``src/``);
2. the ``spedas-agent-kit`` console entry point is declared and its script is
   installed beside the running interpreter (or supplied via ``--console``);
3. packaged data (skills ``SKILL.md``, provenance/analysis schemas, event
   presets) is discoverable through ``importlib.resources`` from the installed
   package;
4. launching the real console entry point over MCP stdio advertises the canonical
   base tools (from ``plugins/spedas-agent-kit-compatibility.json``) and exposes
   the packaged skills/schemas as readable MCP resources.

The canonical base-tool manifest is intentionally read from the repository
checkout, so this CI validator must run with that checkout available (or an
explicit ``--repo-root``). Its isolated scratch directory is retained and
reported for post-failure inspection rather than deleted implicitly.

Any missing package data, undeclared runtime dependency, broken entry point, or
MCP timeout makes this exit non-zero with useful JSON output.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from importlib import metadata, resources
from pathlib import Path
from typing import Any

CONSOLE_SCRIPT = "spedas-agent-kit"
ENTRY_POINT_TARGET = "spedas_agent_kit:main"

# Canonical resource URIs that must be discoverable and readable from a base
# (no optional extras) install. These mirror scripts/smoke_mcp_resources.py but
# are asserted here against the *installed* wheel rather than the source tree.
REQUIRED_RESOURCES = [
    "spedas-skill://index",
    "spedas-skill://skills/spedas-workflow",
    "spedas-skill://skills/spedas-skills-index",
    "spedas-preset://schemas/reproduction_provenance",
    "spedas-preset://schemas/analysis_bundle_run",
]


class SmokeFailure(Exception):
    """Raised with a human-readable reason when a contract check fails."""


def _fail(reason: str) -> None:
    raise SmokeFailure(reason)


def _canonical_base_tools(repo_root: Path) -> list[str]:
    """Load the canonical base tool list from the compatibility manifest."""
    manifest = repo_root / "plugins" / "spedas-agent-kit-compatibility.json"
    if not manifest.is_file():
        _fail(f"canonical compatibility manifest not found: {manifest}")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    tools = data.get("base_tools")
    if not isinstance(tools, list) or not tools:
        _fail(f"{manifest}: base_tools missing or empty")
    count = data.get("base_tool_count")
    if count != len(tools):
        _fail(f"{manifest}: base_tool_count {count} != len(base_tools) {len(tools)}")
    return list(tools)


def _check_installed_location(repo_root: Path) -> str:
    """Ensure the imported package is an installed copy, not the repo source tree."""
    try:
        import spedas_agent_kit  # noqa: F401
    except Exception as exc:  # pragma: no cover - surfaced as a smoke failure
        _fail(f"cannot import spedas_agent_kit from the installed environment: {exc!r}")
    pkg_file = Path(spedas_agent_kit.__file__).resolve()
    repo_src = (repo_root / "src").resolve()
    try:
        pkg_file.relative_to(repo_src)
    except ValueError:
        return str(pkg_file)
    _fail(
        "spedas_agent_kit resolved to the repository source tree "
        f"({pkg_file}); this validator must run against an installed wheel, not "
        "an editable/source checkout"
    )
    return str(pkg_file)  # pragma: no cover - unreachable


def _check_entry_point() -> str:
    """Confirm the console_scripts entry point is declared with the expected target."""
    eps = metadata.entry_points(group="console_scripts")
    match = next((ep for ep in eps if ep.name == CONSOLE_SCRIPT), None)
    if match is None:
        _fail(f"console_scripts entry point '{CONSOLE_SCRIPT}' not declared by the installed dist")
    if match.value.replace(" ", "") != ENTRY_POINT_TARGET:
        _fail(
            f"console entry point target mismatch: expected '{ENTRY_POINT_TARGET}', "
            f"got '{match.value}'"
        )
    return match.value


def _resolve_console(explicit: str | None) -> str:
    """Locate the console script installed beside the running interpreter.

    A PATH fallback would let an ambient conda/system install masquerade as the
    clean-venv wheel if the wheel failed to install its own script, so the default
    path is intentionally strict.
    """
    if explicit:
        path = Path(explicit)
        if not path.is_file():
            _fail(f"--console path does not exist: {explicit}")
        return str(path)
    # Use the *unresolved* interpreter path: a venv's python is often a symlink
    # to the base interpreter, and resolving it would jump the bin dir back to
    # the base environment and miss the venv's console script.
    candidate = Path(sys.executable).parent / CONSOLE_SCRIPT
    if candidate.is_file():
        return str(candidate)
    _fail(
        f"console script '{CONSOLE_SCRIPT}' not found next to {sys.executable}; "
        "the wheel may not have installed its entry point correctly"
    )
    return ""  # pragma: no cover - unreachable


def _check_packaged_data() -> dict[str, Any]:
    """Verify packaged skills/schemas/presets are present via importlib.resources."""
    from spedas_agent_kit.resources.skill_catalog import list_packaged_skills

    skills = list_packaged_skills()
    if not skills:
        _fail("no packaged skills discovered via importlib.resources (missing SKILL.md data?)")
    unreadable = []
    for skill in skills:
        skill_md = resources.files("spedas_agent_kit.resources").joinpath(
            "skills", skill.name, "SKILL.md"
        )
        if not skill_md.is_file():
            unreadable.append(skill.name)
    if unreadable:
        _fail(f"packaged skills missing SKILL.md payload: {', '.join(sorted(unreadable))}")

    res_root = resources.files("spedas_agent_kit.resources")
    required_files = [
        ("schemas", "reproduction_provenance.schema.json"),
        ("schemas", "analysis_bundle_run.schema.json"),
        ("presets", "solar_wind_event_presets.json"),
    ]
    missing_files = [
        "/".join(parts)
        for parts in required_files
        if not res_root.joinpath(*parts).is_file()
    ]
    if missing_files:
        _fail(f"packaged data files missing from installed wheel: {', '.join(missing_files)}")
    return {"packaged_skill_count": len(skills)}


async def _probe_console(console: str, env: dict[str, str]) -> dict[str, Any]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(command=console, args=[], env=env)
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = [tool.name for tool in (await session.list_tools()).tools]
            listed = await session.list_resources()
            resource_uris = [str(res.uri) for res in listed.resources]
            reads: dict[str, int] = {}
            unreadable: dict[str, str] = {}
            for uri in REQUIRED_RESOURCES:
                if uri not in resource_uris:
                    continue
                try:
                    result = await session.read_resource(uri)
                except Exception as exc:  # pragma: no cover - smoke failure path
                    unreadable[uri] = f"{type(exc).__name__}: {exc}"
                    continue
                text = "".join(getattr(c, "text", "") or "" for c in getattr(result, "contents", []))
                reads[uri] = len(text)
            return {
                "tools": tools,
                "resource_uris": resource_uris,
                "resource_reads": reads,
                "unreadable_resources": unreadable,
            }


async def _probe_console_with_timeout(
    console: str, env: dict[str, str], timeout_seconds: float
) -> dict[str, Any]:
    """Run the entire MCP lifecycle under a bounded cancellation scope."""
    import anyio

    with anyio.fail_after(timeout_seconds):
        return await _probe_console(console, env)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output")
    parser.add_argument(
        "--console",
        default=None,
        help="Path to the installed spedas-agent-kit console script (default: beside sys.executable)",
    )
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Repository root holding the canonical compatibility manifest",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=60.0,
        help="Maximum seconds for the complete MCP stdio probe (default: 60)",
    )
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()

    payload: dict[str, Any] = {"ok": False}
    try:
        base_tools = _canonical_base_tools(repo_root)
        payload["installed_package"] = _check_installed_location(repo_root)
        payload["entry_point_target"] = _check_entry_point()
        console = _resolve_console(args.console)
        payload["console_script"] = console
        payload.update(_check_packaged_data())

        import anyio

        if args.timeout_seconds <= 0:
            _fail("--timeout-seconds must be greater than zero")
        # Retain the isolated scratch tree for post-failure inspection instead of
        # deleting evidence implicitly. Hosted CI discards its runner afterward;
        # local callers can remove the reported path under their own policy.
        root = Path(tempfile.mkdtemp(prefix="spedas-agent-kit-installed-smoke-"))
        payload["scratch_dir"] = str(root)
        env = dict(os.environ)
        # Do NOT leak the repo src tree into the launched server.
        env.pop("PYTHONPATH", None)
        env["XHELIO_CDAWEB_CACHE_DIR"] = str(root / "cdaweb")
        env["XHELIO_SPICE_KERNEL_DIR"] = str(root / "spice")
        env["PDSMCP_CACHE_DIR"] = str(root / "pds")
        probe = anyio.run(
            _probe_console_with_timeout, console, env, args.timeout_seconds
        )

        tools = probe["tools"]
        payload["tool_count"] = len(tools)
        payload["resource_count"] = len(probe["resource_uris"])
        payload["resource_reads"] = probe["resource_reads"]

        missing_tools = [t for t in base_tools if t not in tools]
        if missing_tools:
            _fail(f"installed server missing canonical base tools: {', '.join(missing_tools)}")
        missing_resources = [u for u in REQUIRED_RESOURCES if u not in probe["resource_uris"]]
        if missing_resources:
            _fail(f"installed server missing required resources: {', '.join(missing_resources)}")
        if probe["unreadable_resources"]:
            _fail(f"unreadable resources: {json.dumps(probe['unreadable_resources'])}")
        empty_reads = [u for u, n in probe["resource_reads"].items() if n <= 0]
        if empty_reads:
            _fail(f"required resources read empty: {', '.join(empty_reads)}")

        payload["ok"] = True
        payload["note"] = (
            "installed-wheel smoke: entry point launched, base tools advertised, "
            "packaged skills/schemas/presets readable; no data fetch or kernel download"
        )
    except SmokeFailure as exc:
        payload["error"] = str(exc)
    except TimeoutError:
        payload["error"] = f"MCP stdio probe timed out after {args.timeout_seconds:g} seconds"
    except Exception as exc:  # keep --json machine-readable on dependency/protocol failures
        payload["error"] = f"{type(exc).__name__}: {exc}"

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"SPEDAS Agent Kit installed-artifact smoke: {'OK' if payload['ok'] else 'FAIL'}")
        if payload.get("installed_package"):
            print("installed package:", payload["installed_package"])
        if payload.get("console_script"):
            print("console script:", payload["console_script"])
        if payload.get("tool_count") is not None:
            print("tools:", payload["tool_count"], "| resources:", payload.get("resource_count"))
        if not payload["ok"]:
            print("error:", payload.get("error"), file=sys.stderr)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
