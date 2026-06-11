#!/usr/bin/env python3
"""Validate the repo's Claude Code and Codex plugin wrapper packages."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - failure path prints useful context
        raise SystemExit(f"Invalid JSON {path}: {exc}") from exc


def require(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"Missing required plugin file: {path.relative_to(ROOT)}")


def validate_claude() -> None:
    root = ROOT / "plugins" / "spedas-claude"
    require(root / ".claude-plugin" / "plugin.json")
    require(root / ".mcp.json")
    require(root / "skills" / "spedas-workflow" / "SKILL.md")
    for name in ["overview", "cdaweb", "pds", "spice"]:
        require(root / "commands" / f"{name}.md")

    manifest = load_json(root / ".claude-plugin" / "plugin.json")
    assert manifest["name"] == "spedas-claude"
    assert manifest["version"]
    mcp = load_json(root / ".mcp.json")
    server = mcp["mcpServers"]["spedas"]
    assert server["command"] == "uvx"
    assert "spedas-mcp" in server["args"]


def validate_codex() -> None:
    root = ROOT / ".agents" / "plugins" / "spedas-codex"
    require(root / ".codex-plugin" / "plugin.json")
    require(root / ".mcp.json")
    require(root / "skills" / "spedas-workflow" / "SKILL.md")
    require(ROOT / ".agents" / "plugins" / "marketplace.json")

    manifest = load_json(root / ".codex-plugin" / "plugin.json")
    assert manifest["name"] == "spedas-codex"
    assert manifest["skills"] == "./skills/"
    assert manifest["mcpServers"] == "./.mcp.json"
    mcp = load_json(root / ".mcp.json")
    server = mcp["mcp_servers"]["spedas"]
    assert server["command"] == "uvx"
    assert "spedas-mcp" in server["args"]
    marketplace = load_json(ROOT / ".agents" / "plugins" / "marketplace.json")
    assert marketplace["plugins"][0]["source"]["path"] == "./spedas-codex"


def main() -> int:
    validate_claude()
    validate_codex()
    print("Plugin package validation: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
