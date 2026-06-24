# Codex plugin fixture: spedas-codex

This in-repo fixture mirrors the standalone <https://github.com/spedas/spedas_codex>
plugin wrapper for the shared `spedas_mcp` MCP server.

It contains:

- `.codex-plugin/plugin.json` — Codex plugin manifest.
- `.mcp.json` — plugin-scoped MCP server entry named `spedas`.
- `skills/spedas-workflow/SKILL.md` — reusable Codex guidance for the unified
  SPEDAS data layer and science workflow layer.

The repo also includes `.agents/plugins/marketplace.json`, pointing at
`./spedas-codex`, so Codex can treat this repository as a local marketplace
source while developing the plugin fixture.
