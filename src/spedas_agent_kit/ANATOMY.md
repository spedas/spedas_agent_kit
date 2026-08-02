# src/spedas_agent_kit — the package

## What this is

The Python package: a FastMCP **facade** that registers heliophysics tools and dispatches them to wrapped backends. Almost no science lives here — the value is unified `source_type` dispatch, input validation, the structured-error contract, kernel-download gating, and the artifact-first response shape.

## Components

- **`__init__.py:6`** `main()` — entry point; builds and runs the server (`create_server().run()`). `__main__.py` makes `python -m spedas_agent_kit` work.
- **`server.py`** — the whole facade. Key anchors:
  - `create_server()` `server.py:1044` — constructs the FastMCP and registers all tool closures (13 base data/workflow/geometry tools, plus 8 legacy CDAWeb/PDS compatibility tools when enabled). Tool registration flows through `_register_tool()` `server.py:1062` so every advertised tool carries MCP `ToolAnnotations` and `meta.surface` (`primary` or `compat`). One big factory; tools are nested closures, so grep by tool name finds the `def`.
  - `_compat_tools_enabled()` `server.py:107` — gates the 8 legacy per-source tools behind `SPEDAS_AGENT_KIT_COMPAT_TOOLS`; `_compat_tool()` `server.py:1096` marks those advertised aliases as `meta.surface="compat"` when enabled.
  - `_normalize_source_type()` and `_wrap_data_payload()` — the unified-dispatch core: route by `source_type`, wrap backend output.
  - `_error_response()` `server.py:329` — the structured `{status,code,message,hint}` contract (issue #27).
  - `_install_argument_validation_guard()` `server.py:2737` — turns FastMCP arg-validation failures into structured errors.
- **`workflows.py`** (1087 lines) — pure-Python planning behind the workflow tools: `search_data_sources` `:816`, `compare_sources` `:848`, `plan_observation` `:870`, `create_analysis_bundle` `:1016`. No backend dependency → robust; this is why bugs cluster in adapters, not here.

## Connections

- **In:** MCP client calls a registered tool → its closure in `create_server()`.
- **Out:** lazily imports the in-tree vendored `backends.cdaweb`/`backends.pds`/`backends.spice` packages for data+geometry.
- Dispatch fans `fetch_data_product`/`browse_*`/`manage_data_cache` to the right backend by `source_type`.

## Composition

- **Parent:** repo root (`ANATOMY.md`).
- **Subfolders:** `backends/` (`backends/ANATOMY.md`), `resources/` (packaged skills).

## State

- None persistent in-process. Writes only via the data tools (to backend caches / bundle dirs). Surface composition is decided at `create_server()` time from the env flag.

## Notes

- `server.py` is large and closure-heavy by design (FastMCP registration). Navigate by tool name → its nested `def`, or by the helper anchors above — not by reading top-to-bottom.
- Surface gating is runtime: `SPEDAS_AGENT_KIT_COMPAT_TOOLS=1` advertises the 8 legacy CDAWeb/PDS compat tools; the unified layer calls the same underlying functions regardless.
