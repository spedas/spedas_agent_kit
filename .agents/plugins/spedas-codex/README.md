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

## Compatibility pin

This in-repo fixture follows `../../../plugins/spedas-mcp-compatibility.json`: it
pins `spedas_mcp` to commit `170a8b0c0d058c729d4769f9848754cfb8ec9f8e`, bounds the
MCP protocol package as `mcp>=1.26.0,<2`, and expects the base `list_tools`
surface to advertise 17 tools. Refresh the manifest, this `.mcp.json`, and the
Claude fixture together after any server tool-surface change.
