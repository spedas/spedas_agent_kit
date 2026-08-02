# spedas_agent_kit

> **What is an `ANATOMY.md`?** A code-cited structural map of one folder, written for an agent reader, sitting next to the code it describes (the LingTai anatomy convention). Every structural claim points at a `file:line`. ~80-line cap per file. **Reading and maintaining are the same act:** if anatomy disagrees with code, fix the anatomy in the same change. This is the repo-root anatomy — the only file with a complete child enumeration; descend it to navigate by structure instead of grep.

## What this is

The SPEDAS Agent Kit core: one package/repo that gives AI agents a unified MCP door to heliophysics data (CDAWeb, PDS, SPICE) and packaged shared workflow **skills**. A thin **facade** (`server.py`) does dispatch + validation + artifact discipline; the science lives in wrapped backends. Runtime wrappers such as Claude Code/Codex/OpenCode should stay thin and package or sync the shared skills from this core.

## Components

- **`src/spedas_agent_kit/`** — the package (see `src/spedas_agent_kit/ANATOMY.md`). Entry: `__init__.py:6` `main()` → `server.create_server().run()`; `__main__.py` enables `python -m spedas_agent_kit`.
- **`src/spedas_agent_kit/server.py`** — the FastMCP facade. `create_server()` at `server.py:1044` registers tools through `_register_tool()` `server.py:1062`, so every advertised tool carries MCP `ToolAnnotations` and `meta.surface`; gating helper `_compat_tools_enabled()` `server.py:107` decides whether the 8 legacy CDAWeb/PDS compatibility tools are advertised. Avoid hard-coding this large file's total line count; it shifts whenever tools are added.
- **`src/spedas_agent_kit/workflows.py`** (1087 lines) — pure-Python science-planning logic behind the workflow tools (`search_data_sources` `workflows.py:816`, `plan_observation` `workflows.py:870`, …).
- **`src/spedas_agent_kit/resources/skills/`** — canonical packaged shared workflow skills for runtime wrappers.
- **`tests/`** — pytest suite mirroring each module and packaged resources.
- **`scripts/smoke_mcp_list_tools.py`** — lists the advertised tool surface (the consolidation check).

## Connections

- **Client → facade.** MCP stdio JSON-RPC; client sees tool names/schemas only, receives `{status, file_path, stats}` — never bulk arrays (artifact-first).
- **Facade → backends.** `server.py` lazily imports the in-tree vendored `spedas_agent_kit.backends.cdaweb` / `pds` / `spice` packages (data + geometry). Unified `fetch_data_product(source_type=...)` dispatches by source.
- **Runtime wrapper → server.** Thin wrapper fixtures launch the `spedas-agent-kit` server; wrapper commands/skills should reference the unified tools and packaged shared skills from this core.

## Composition

- **Parent:** repo root (this file).
- **Subfolders with their own anatomy:** `src/spedas_agent_kit/`, `src/spedas_agent_kit/backends/`.
- **Mapped narratively (no own anatomy yet):** `tests/`, `docs/`, `scripts/`.

## State

- No server-side persistent state. Caches live in the user's home (`~/.cdawebmcp/`, `~/.pdsmcp/`, `~/.xhelio_spice/kernels/`), managed via `manage_data_cache`.
- Surface gating is runtime, not stored: the `SPEDAS_AGENT_KIT_COMPAT_TOOLS` env flag. The smoke script advertises 13 base tools and 21 tools with compat enabled. Advertised tools also expose `meta.surface` (`primary`, `compat`) plus side-effect hints through MCP `ToolAnnotations`.
- Data/workflow tools are artifact-first: packaged shared skills live under `src/spedas_agent_kit/resources/skills/`; bulk results are written under a `create_spedas_analysis_bundle` directory (`requests/ data/ plots/ provenance/ notes/`).

## Notes

- The bug-prone seam is **facade↔backend adapters**, not the dispatch — most fixed issues lived there (numpy serialization, unit conventions, fill values, probe paths). Validate adapter I/O shapes, not just that a call returns.
- Consolidation: the compat/cache tools are *hidden*, not deleted — the unified tools call the same underlying functions. New capability lands as a `source_type` or a **skill**, not a new top-level tool.
