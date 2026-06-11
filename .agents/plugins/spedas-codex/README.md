# Codex plugin: spedas-codex

This is the repo-scoped `spedas-codex` Codex plugin for the shared `spedas-mcp` MCP server.

It contributes:

- `.codex-plugin/plugin.json` — Codex plugin manifest.
- `.mcp.json` — plugin-scoped MCP server entry named `spedas`.
- `skills/spedas-workflow/SKILL.md` — reusable Codex guidance for CDAWeb, PDS PPI, and SPICE workflows.

The repo also includes `.agents/plugins/marketplace.json`, pointing at `./spedas-codex`, so Codex can treat this repository as a local marketplace source while developing the plugin.

The MCP server command uses `uvx` against the GitHub repo. For local development, install the package locally or edit `.mcp.json` to point at your checkout.
