#!/usr/bin/env python3
"""Check the SPEDAS Agent Kit MCP surface against checked-in contract snapshots.

Issue #209 Workstream J asks for checked, readable contracts for the client-facing
tool/resource/prompt surface so that accidental MCP drift fails CI. This script is
the base + env-gated slice of that work: it speaks the real MCP stdio protocol
(``initialize`` + ``list_tools``/``list_resources``/``list_resource_templates``/
``list_prompts``), canonicalizes the stable client-facing metadata, and compares it
against per-profile JSON snapshots checked into ``tests/contracts/mcp_surface/``.

Three independent profiles are covered, each a distinct server launch so the
environment gates are exercised end to end (issue #87 demoted the direct
HAPI/FDSN tools and the legacy CDAWeb/PDS compat tools out of the default
surface):

* ``base``       -- both gates unset (the default 13-tool surface);
* ``compat``     -- only ``SPEDAS_AGENT_KIT_COMPAT_TOOLS=1``;
* ``datasource`` -- only ``SPEDAS_AGENT_KIT_DATASOURCE_TOOLS=1``.

The optional ``[analysis]`` extra auto-registers 13 more tools when its backend is
importable. That surface is a *separate, later* slice (issue #209 Workstream J):
these three profiles snapshot the base install only, so the known analysis tool
names are excluded from the captured surface. This keeps the base/compat/datasource
contracts reproducible whether or not ``[analysis]`` happens to be installed in the
interpreter running the check -- it is not a claim that analysis schemas never
change. See ``tests/contracts/mcp_surface/README.md``.

Default mode checks the live surface against the snapshots and fails with a
readable unified diff on drift. ``--update`` is the explicit maintainer refresh
mode; it rewrites only the named snapshot files and refuses to run in CI so drift
is never silently accepted.

Like the sibling smokes, this is intentionally no-fetch/no-download: the server is
started with isolated CDAWeb/PDS/SPICE cache directories pointed at unique,
never-created temp paths, and only listing calls are made, so it never touches the
network or a real science backend and normally writes nothing. Nothing is deleted:
no temporary directory is created and torn down (task constraint).
"""
from __future__ import annotations

import argparse
import difflib
import inspect
import json
import os
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

from _smoke_runtime import REPO_ROOT, ensure_source_tree_on_path, isolated_cache_env

ensure_source_tree_on_path()

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from spedas_agent_kit.optional_backends import ANALYSIS_TOOL_NAMES

#: Directory holding the checked-in per-profile contract snapshots.
SNAPSHOT_DIR = REPO_ROOT / "tests" / "contracts" / "mcp_surface"

#: Profile name -> the environment flags that define that gated surface. Both
#: gates are always explicitly cleared first (see :func:`_profile_env`), so an
#: empty mapping means "default surface".
PROFILES: dict[str, dict[str, str]] = {
    "base": {},
    "compat": {"SPEDAS_AGENT_KIT_COMPAT_TOOLS": "1"},
    "datasource": {"SPEDAS_AGENT_KIT_DATASOURCE_TOOLS": "1"},
}

#: The two environment gates this slice toggles. Always reset before applying a
#: profile so an ambient value in the caller's environment cannot leak in.
_GATE_FLAGS = ("SPEDAS_AGENT_KIT_COMPAT_TOOLS", "SPEDAS_AGENT_KIT_DATASOURCE_TOOLS")

#: Optional analysis tool names excluded from these base-install profiles. Sourced
#: from the server's own gating constant so the exclusion never drifts from the
#: real registration logic.
_ANALYSIS_TOOL_NAMES = frozenset(ANALYSIS_TOOL_NAMES)

# Stable, client-facing metadata kept per surface object. This is an allowlist,
# not a dump, split into two tiers:
#   * "core" fields are always captured (identity, schemas), even when null, so a
#     null->value change (e.g. a title being added) still surfaces as an inline
#     diff.
#   * optional metadata blocks -- ``annotations`` and the wire-aliased ``_meta``
#     -- are captured only when present and non-null, so a future client-facing
#     annotation/_meta addition is caught without spraying ``"annotations": null``
#     across every object.
# Presentation-/transport-only fields (``icons``, ``execution``) and populated
# byte ``size`` are always excluded as noise. ``_meta`` is the real MCP wire key:
# Tool/Resource/ResourceTemplate/Prompt all serialize their ``meta`` field under
# serialization alias ``_meta``, and the capture dumps ``by_alias=True`` so the
# snapshots pin the actual client-facing key rather than the SDK's internal one.
_TOOL_CORE = ("name", "title", "description", "inputSchema", "outputSchema")
_RESOURCE_CORE = ("uri", "name", "title", "description", "mimeType")
_TEMPLATE_CORE = ("uriTemplate", "name", "title", "description", "mimeType")
_PROMPT_CORE = ("name", "title", "description", "arguments")
#: Optional metadata blocks kept only when non-null. The Prompt model exposes no
#: ``annotations`` field, so prompts keep ``_meta`` only.
_OPTIONAL_METADATA = ("annotations", "_meta")
_PROMPT_OPTIONAL = ("_meta",)
#: Human-readable fields normalized for whitespace/version stability.
_TEXT_FIELDS = ("title", "description")


def _norm_text(value: Any) -> Any:
    """Normalize a human-readable description/title to be version-independent.

    Python 3.13 changed the compiler so docstrings are dedented at compile time;
    on <=3.12 a tool docstring still carries its source indentation. Both forms
    reach the MCP client verbatim, so the same tool advertises a differently
    whitespaced ``description`` depending on the interpreter -- which would make a
    single snapshot impossible to satisfy across the CI Python matrix. Running
    :func:`inspect.cleandoc` (dedent + strip) collapses both forms to one stable
    string; it is idempotent for already-clean explicit strings (resource
    titles/descriptions), so applying it uniformly is safe.
    """
    if value is None:
        return None
    return inspect.cleandoc(str(value))


def _project(dump: dict[str, Any], core: tuple[str, ...], optional: tuple[str, ...]) -> dict[str, Any]:
    """Project a listing dump onto ``core`` (always) + ``optional`` (if non-null).

    ``core`` fields are always emitted (including nulls) so identity/schema
    changes always diff. ``optional`` metadata blocks are emitted only when
    present and non-null, so null blocks are elided while a real
    annotation/_meta addition still surfaces as drift. Text fields are
    whitespace-normalized (see :func:`_norm_text`).
    """
    view: dict[str, Any] = {
        field: (_norm_text(dump.get(field)) if field in _TEXT_FIELDS else dump.get(field)) for field in core
    }
    for field in optional:
        value = dump.get(field)
        if value is not None:
            view[field] = value
    return view


def canonicalize_tool(dump: dict[str, Any]) -> dict[str, Any]:
    """Return the stable client-facing contract view of one MCP tool."""
    return _project(dump, _TOOL_CORE, _OPTIONAL_METADATA)


def canonicalize_resource(dump: dict[str, Any]) -> dict[str, Any]:
    """Return the stable listing metadata for one fixed MCP resource."""
    view = _project(dump, _RESOURCE_CORE, _OPTIONAL_METADATA)
    view["uri"] = str(view["uri"])
    return view


def canonicalize_resource_template(dump: dict[str, Any]) -> dict[str, Any]:
    """Return the stable listing metadata for one MCP resource template."""
    view = _project(dump, _TEMPLATE_CORE, _OPTIONAL_METADATA)
    view["uriTemplate"] = str(view["uriTemplate"])
    return view


def canonicalize_prompt(dump: dict[str, Any]) -> dict[str, Any]:
    """Return the stable listing metadata for one MCP prompt."""
    return _project(dump, _PROMPT_CORE, _PROMPT_OPTIONAL)


def build_profile_snapshot(
    profile: str,
    env_flags: dict[str, str],
    tools: list[dict[str, Any]],
    resources: list[dict[str, Any]],
    resource_templates: list[dict[str, Any]],
    prompts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Assemble one profile's canonical, deterministically ordered snapshot.

    Pure: takes already-``model_dump``ed listing objects and returns a plain
    JSON-ready structure. Analysis tools are dropped (see the module docstring);
    every collection is sorted by its natural key so ordering is independent of
    server registration order.
    """
    canonical_tools = sorted(
        (canonicalize_tool(tool) for tool in tools if tool.get("name") not in _ANALYSIS_TOOL_NAMES),
        key=lambda tool: tool["name"],
    )
    canonical_resources = sorted(
        (canonicalize_resource(resource) for resource in resources),
        key=lambda resource: resource["uri"],
    )
    canonical_templates = sorted(
        (canonicalize_resource_template(template) for template in resource_templates),
        key=lambda template: template["uriTemplate"],
    )
    canonical_prompts = sorted(
        (canonicalize_prompt(prompt) for prompt in prompts),
        key=lambda prompt: prompt["name"],
    )
    return {
        "profile": profile,
        "env": dict(env_flags),
        # Documented inline so a reviewer reading a snapshot knows the optional
        # analysis surface is deliberately out of scope here, not accidentally
        # missing. Constant across environments, so it adds no drift noise.
        "excludes_optional_analysis_tools": True,
        "tools": canonical_tools,
        "resources": canonical_resources,
        "resource_templates": canonical_templates,
        "prompts": canonical_prompts,
    }


def render_snapshot(snapshot: dict[str, Any]) -> str:
    """Serialize a snapshot to recursively key-sorted JSON with a final newline."""
    return json.dumps(snapshot, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def diff_snapshots(expected: str, actual: str, label: str) -> str:
    """Return a readable unified diff between the checked-in and live snapshots."""
    return "".join(
        difflib.unified_diff(
            expected.splitlines(keepends=True),
            actual.splitlines(keepends=True),
            fromfile=f"{label} (checked-in)",
            tofile=f"{label} (live)",
        )
    )


def _cache_root(profile: str) -> Path:
    """Return a unique, deliberately UNCREATED cache-root path for a launch.

    ``isolated_cache_env`` only maps the CDAWeb/PDS/SPICE cache environment
    variables onto subpaths of this root; it does not create it. Because the
    contract capture issues only listing calls (no fetch/download), the server
    normally writes nothing under it. The path is never created and never
    deleted -- this checker introduces no ``TemporaryDirectory``/``rmtree``/
    ``unlink`` cleanup (task constraint). Uniqueness (PID + random + profile)
    keeps concurrent or repeated runs from colliding.
    """
    unique = f"spedas-agent-kit-contract-{os.getpid()}-{uuid.uuid4().hex}-{profile}"
    return Path(tempfile.gettempdir()) / unique


def _profile_env(cache_root: str | Path, flags: dict[str, str]) -> dict[str, str]:
    """Build the isolated-cache environment for a profile launch.

    Both gate flags are reset first so an ambient value in the caller's
    environment cannot silently change the captured surface; the profile's own
    flags are then applied. ``cache_root`` is mapped to cache env vars but is not
    created here.
    """
    env = isolated_cache_env(cache_root)
    for flag in _GATE_FLAGS:
        env.pop(flag, None)
    env.update(flags)
    return env


async def _capture_raw(
    module: str, env: dict[str, str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """List tools/resources/templates/prompts from a live stdio server launch."""
    params = StdioServerParameters(command=sys.executable, args=["-m", module], env=env)
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            resources = (await session.list_resources()).resources
            templates = (await session.list_resource_templates()).resourceTemplates
            prompts = (await session.list_prompts()).prompts
            # by_alias=True so `meta` serializes under its real wire alias
            # `_meta`, matching exactly what an MCP client receives.
            return (
                [tool.model_dump(mode="json", by_alias=True) for tool in tools],
                [resource.model_dump(mode="json", by_alias=True) for resource in resources],
                [template.model_dump(mode="json", by_alias=True) for template in templates],
                [prompt.model_dump(mode="json", by_alias=True) for prompt in prompts],
            )


def capture_profile(profile: str, module: str = "spedas_agent_kit") -> tuple[dict[str, Any], list[str]]:
    """Launch one profile over stdio and return its ``(snapshot, filtered)`` pair.

    ``filtered`` is the sorted list of optional analysis tool names that were
    present in the live surface and dropped, surfaced by the CLI so a run in an
    analysis-enabled interpreter is transparent about the exclusion.
    """
    flags = PROFILES[profile]
    # Point cache env vars at a unique, uncreated temp path. No TemporaryDirectory
    # context is used, so nothing is created up front and nothing is deleted on
    # exit; listing-only calls write nothing under it.
    env = _profile_env(_cache_root(profile), flags)
    tools, resources, templates, prompts = anyio.run(_capture_raw, module, env)
    snapshot = build_profile_snapshot(profile, dict(flags), tools, resources, templates, prompts)
    filtered = sorted(
        {tool["name"] for tool in tools if tool.get("name") in _ANALYSIS_TOOL_NAMES}
    )
    return snapshot, filtered


def snapshot_path(profile: str) -> Path:
    """Return the checked-in snapshot path for ``profile``."""
    return SNAPSHOT_DIR / f"{profile}.json"


def _ci_environment() -> bool:
    """Return whether we appear to be running in CI (GitHub Actions sets CI=true)."""
    return os.environ.get("CI", "").strip().lower() in {"1", "true", "yes", "on"}


def _run(profiles: list[str], *, update: bool, module: str) -> tuple[bool, list[dict[str, Any]]]:
    """Check or update each profile; return ``(ok, per-profile reports)``."""
    reports: list[dict[str, Any]] = []
    ok = True
    for profile in profiles:
        snapshot, filtered = capture_profile(profile, module)
        live_text = render_snapshot(snapshot)
        path = snapshot_path(profile)
        try:
            rel: Path = path.relative_to(REPO_ROOT)
        except ValueError:  # snapshot dir relocated (e.g. a unit test's tmp dir)
            rel = path
        report: dict[str, Any] = {
            "profile": profile,
            "snapshot": str(rel),
            "tool_count": len(snapshot["tools"]),
            "resource_count": len(snapshot["resources"]),
            "resource_template_count": len(snapshot["resource_templates"]),
            "prompt_count": len(snapshot["prompts"]),
            "filtered_analysis_tools": filtered,
        }
        if update:
            path.parent.mkdir(parents=True, exist_ok=True)
            existed = path.exists()
            changed = not existed or path.read_text(encoding="utf-8") != live_text
            path.write_text(live_text, encoding="utf-8")
            report.update(action="updated", changed=changed, created=not existed)
        else:
            expected_text = path.read_text(encoding="utf-8") if path.exists() else ""
            matched = expected_text == live_text
            report.update(action="checked", matched=matched, missing=not path.exists())
            if not matched:
                ok = False
                report["diff"] = diff_snapshots(expected_text, live_text, str(rel))
        reports.append(report)
    return ok, reports


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--profile",
        action="append",
        choices=sorted(PROFILES),
        dest="profiles",
        help="Restrict to these profiles (repeatable). Default: check all three.",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Maintainer refresh mode: rewrite the named snapshot files instead of checking. Refuses to run in CI.",
    )
    parser.add_argument("--json", action="store_true", help="Print a machine-readable JSON report.")
    parser.add_argument(
        "--module",
        default="spedas_agent_kit",
        help="Python module launched as the MCP server (default: spedas_agent_kit).",
    )
    args = parser.parse_args(argv)

    if args.update and _ci_environment():
        print(
            "Refusing to --update MCP surface snapshots in CI; contract drift must be "
            "reviewed and refreshed by a maintainer locally.",
            file=sys.stderr,
        )
        return 2

    # Check all three profiles in a single invocation by default (one server
    # launch per profile, which is required to exercise each env gate), rather
    # than shelling out three separate times.
    profiles = sorted(set(args.profiles)) if args.profiles else sorted(PROFILES)
    ok, reports = _run(profiles, update=args.update, module=args.module)

    if args.json:
        print(json.dumps({"ok": ok, "update": args.update, "profiles": reports}, indent=2, ensure_ascii=False))
        return 0 if ok else 1

    if args.update:
        for report in reports:
            state = "created" if report.get("created") else ("updated" if report["changed"] else "unchanged")
            print(f"[{state}] {report['snapshot']} (profile={report['profile']}, tools={report['tool_count']})")
        print("Updated MCP surface snapshots. Review the diff before committing.")
        return 0

    for report in reports:
        if report["matched"]:
            extra = (
                f", filtered {len(report['filtered_analysis_tools'])} analysis tool(s)"
                if report["filtered_analysis_tools"]
                else ""
            )
            print(
                f"OK  profile={report['profile']:<10} tools={report['tool_count']} "
                f"resources={report['resource_count']} "
                f"templates={report['resource_template_count']} "
                f"prompts={report['prompt_count']}{extra}"
            )
        else:
            why = "no checked-in snapshot" if report.get("missing") else "surface drifted from snapshot"
            print(f"DRIFT profile={report['profile']} ({report['snapshot']}): {why}", file=sys.stderr)
            print(report["diff"], file=sys.stderr, end="")

    if not ok:
        print(
            "\nMCP surface contract check failed. If this change is intentional, "
            "refresh the named snapshot(s) with:\n"
            "    python scripts/check_mcp_surface_contract.py --update\n"
            "and review the resulting diff.",
            file=sys.stderr,
        )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
