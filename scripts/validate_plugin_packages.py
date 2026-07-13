#!/usr/bin/env python3
"""Validate the repo's Claude Code and Codex plugin wrapper packages."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPATIBILITY = ROOT / "plugins" / "spedas-agent-kit-compatibility.json"
SERVER_JSON = ROOT / "server.json"
PYPROJECT = ROOT / "pyproject.toml"
INIT_PY = ROOT / "src" / "spedas_agent_kit" / "__init__.py"

# Core package identity that must agree across pyproject, the package __version__,
# server.json, and the declared console entry point. These are the "core" surfaces
# (not the bundled Claude/Codex wrapper plugin versions, which are validated for
# presence/format separately and are not forced to equal the core version).
CORE_PACKAGE_NAME = "spedas-agent-kit"
CORE_CONSOLE_SCRIPT = "spedas-agent-kit"
CORE_ENTRY_POINT_TARGET = "spedas_agent_kit:main"


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - failure path prints useful context
        raise SystemExit(f"Invalid JSON {path}: {exc}") from exc


def load_toml(path: Path) -> dict:
    try:
        import tomllib  # Python 3.11+ standard library
    except ModuleNotFoundError:  # Python 3.10: dev-only tomli backport
        import tomli as tomllib  # type: ignore[no-redef]
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - failure path prints useful context
        raise SystemExit(f"Invalid TOML {path}: {exc}") from exc


def parse_init_version(init_source: str) -> str:
    """Extract ``__version__`` from ``__init__.py`` source via AST.

    Reading the assignment statically avoids importing the package (and thus the
    server / optional analysis stack) merely to learn its declared version.
    """
    import ast

    module = ast.parse(init_source)
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__version__":
                    value = node.value
                    if isinstance(value, ast.Constant) and isinstance(value.value, str):
                        return value.value
    raise SystemExit(
        "src/spedas_agent_kit/__init__.py: no string __version__ assignment found"
    )


def check_core_metadata_contract(
    *,
    pyproject: dict,
    server_manifest: dict,
    init_version: str,
) -> list[str]:
    """Return human-readable mismatch messages for the core metadata contract.

    Pure over already-parsed inputs so the consistency rules can be exercised
    in-memory. ``pyproject`` ``[project].version`` is treated as the single
    source of truth for the core package version; every message names the
    mismatched field/surface. An empty list means the contract holds.
    """
    errors: list[str] = []
    project = pyproject.get("project", {})
    proj_name = project.get("name")
    proj_version = project.get("version")

    if proj_name != CORE_PACKAGE_NAME:
        errors.append(
            f"pyproject [project].name {proj_name!r} != expected core package name "
            f"{CORE_PACKAGE_NAME!r}"
        )

    if not isinstance(proj_version, str) or not proj_version:
        errors.append(f"pyproject [project].version missing or not a string: {proj_version!r}")
    else:
        if init_version != proj_version:
            errors.append(
                f"src/spedas_agent_kit/__init__.py __version__ {init_version!r} != "
                f"pyproject [project].version {proj_version!r}"
            )
        top_version = server_manifest.get("version")
        if top_version != proj_version:
            errors.append(
                f"server.json top-level version {top_version!r} != "
                f"pyproject [project].version {proj_version!r}"
            )

    scripts = project.get("scripts", {})
    target = scripts.get(CORE_CONSOLE_SCRIPT)
    if not isinstance(target, str):
        errors.append(
            f"pyproject [project.scripts] missing {CORE_CONSOLE_SCRIPT!r} console script"
        )
    elif target.replace(" ", "") != CORE_ENTRY_POINT_TARGET:
        errors.append(
            f"pyproject [project.scripts].{CORE_CONSOLE_SCRIPT} console entry target "
            f"{target!r} != expected {CORE_ENTRY_POINT_TARGET!r}"
        )

    pypi_packages = [
        pkg
        for pkg in server_manifest.get("packages", [])
        if isinstance(pkg, dict) and pkg.get("registryType") == "pypi"
    ]
    if not pypi_packages:
        errors.append("server.json: no pypi package entry found")
    for pkg in pypi_packages:
        if pkg.get("identifier") != CORE_PACKAGE_NAME:
            errors.append(
                f"server.json pypi package identifier {pkg.get('identifier')!r} != "
                f"expected {CORE_PACKAGE_NAME!r}"
            )
        if isinstance(proj_version, str) and proj_version and pkg.get("version") != proj_version:
            errors.append(
                f"server.json pypi package version {pkg.get('version')!r} != "
                f"pyproject [project].version {proj_version!r}"
            )
        transport = pkg.get("transport", {})
        transport_type = transport.get("type") if isinstance(transport, dict) else None
        if transport_type != "stdio":
            errors.append(
                f"server.json pypi package transport.type {transport_type!r} != expected 'stdio'"
            )
    return errors


def validate_core_metadata_contract() -> None:
    """Fail if the core package name/version/console/server metadata drift apart."""
    pyproject = load_toml(PYPROJECT)
    server_manifest = load_json(SERVER_JSON)
    init_version = parse_init_version(INIT_PY.read_text(encoding="utf-8"))
    errors = check_core_metadata_contract(
        pyproject=pyproject,
        server_manifest=server_manifest,
        init_version=init_version,
    )
    if errors:
        raise SystemExit(
            "Core metadata consistency contract failed:\n  - " + "\n  - ".join(errors)
        )


def require(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"Missing required plugin file: {path.relative_to(ROOT)}")


def _server_manifest_env_names() -> set[str]:
    manifest = load_json(SERVER_JSON)
    names: set[str] = set()
    for package in manifest.get("packages", []):
        for env in package.get("environmentVariables", []):
            name = env.get("name")
            if isinstance(name, str):
                names.add(name)
    return names


def _validate_server_manifest_env_flags() -> None:
    manifest_env = _server_manifest_env_names()
    compatibility = load_json(COMPATIBILITY)
    required_flags = {"SPEDAS_AGENT_KIT_COMPAT_TOOLS"}
    datasource_flag = compatibility.get("datasource_env_flag")
    if isinstance(datasource_flag, str) and datasource_flag:
        required_flags.add(datasource_flag.split("=", 1)[0])

    missing = sorted(required_flags - manifest_env)
    if missing:
        raise SystemExit(
            "server.json: missing environmentVariables for public Agent Kit gate "
            f"flags: {', '.join(missing)}"
        )


def _expected_mcp_args() -> list[str]:
    manifest = load_json(COMPATIBILITY)
    tools = manifest.get("base_tools", [])
    if manifest.get("base_tool_count") != len(tools):
        raise SystemExit(
            "plugins/spedas-agent-kit-compatibility.json: base_tool_count does not "
            "match base_tools length"
        )
    return [
        "--with",
        manifest["mcp_requirement"],
        "--from",
        manifest["spedas_agent_kit_source"],
        "spedas-agent-kit",
    ]


def _validate_mcp_server(mcp_path: Path, server: dict) -> None:
    assert server["command"] == "uvx"
    expected = _expected_mcp_args()
    if server.get("args") != expected:
        raise SystemExit(
            f"{mcp_path.relative_to(ROOT)}: spedas MCP args must match "
            f"plugins/spedas-agent-kit-compatibility.json; got {server.get('args')!r}"
        )
    env = server.get("env", {})
    for name in ["XHELIO_CDAWEB_CACHE_DIR", "PDSMCP_CACHE_DIR", "XHELIO_SPICE_KERNEL_DIR"]:
        if name not in env:
            raise SystemExit(f"{mcp_path.relative_to(ROOT)}: missing cache env {name}")


def validate_claude() -> None:
    root = ROOT / "plugins" / "spedas-claude"
    require(COMPATIBILITY)
    require(root / ".claude-plugin" / "plugin.json")
    require(root / ".mcp.json")
    require(root / "skills" / "spedas-workflow" / "SKILL.md")
    for name in ["overview", "cdaweb", "pds", "spice"]:
        require(root / "commands" / f"{name}.md")

    manifest = load_json(root / ".claude-plugin" / "plugin.json")
    assert manifest["name"] == "spedas-claude"
    assert manifest["version"]
    mcp_path = root / ".mcp.json"
    mcp = load_json(mcp_path)
    _validate_mcp_server(mcp_path, mcp["mcpServers"]["spedas"])


def validate_codex() -> None:
    root = ROOT / ".agents" / "plugins" / "spedas-codex"
    require(COMPATIBILITY)
    require(root / ".codex-plugin" / "plugin.json")
    require(root / ".mcp.json")
    require(root / "skills" / "spedas-workflow" / "SKILL.md")
    require(ROOT / ".agents" / "plugins" / "marketplace.json")

    manifest = load_json(root / ".codex-plugin" / "plugin.json")
    assert manifest["name"] == "spedas-codex"
    assert manifest["skills"] == "./skills/"
    assert manifest["mcpServers"] == "./.mcp.json"
    mcp_path = root / ".mcp.json"
    mcp = load_json(mcp_path)
    _validate_mcp_server(mcp_path, mcp["mcp_servers"]["spedas"])
    marketplace = load_json(ROOT / ".agents" / "plugins" / "marketplace.json")
    assert marketplace["plugins"][0]["source"]["path"] == "./spedas-codex"


def main() -> int:
    validate_core_metadata_contract()
    _validate_server_manifest_env_flags()
    validate_claude()
    validate_codex()
    print("Plugin package validation: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
