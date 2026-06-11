# SPEDAS MCP agent plugins

This repository contains two agent-facing wrappers around the same `spedas-mcp` MCP server:

- `plugins/spedas-claude/` — Claude Code plugin package named `spedas-claude`.
- `.agents/plugins/spedas-codex/` — Codex plugin package named `spedas-codex`, with `.agents/plugins/marketplace.json` for repo-scoped marketplace testing.

Both wrappers intentionally reuse the same Python MCP server instead of duplicating science logic. The server exposes CDAWeb, PDS PPI, and SPICE tools.

## Validation

Run:

```bash
python scripts/validate_plugin_packages.py
uv run --extra dev --extra mcp python -m pytest -q
uv run --extra mcp python scripts/smoke_mcp_list_tools.py --json
```
