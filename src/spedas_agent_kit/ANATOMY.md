---
related_files:
  - ANATOMY.md
  - src/spedas_agent_kit/CONTRACT.md
  - src/spedas_agent_kit/backends/ANATOMY.md
  - src/spedas_agent_kit/backends/CONTRACT.md
  - src/spedas_agent_kit/resources/ANATOMY.md
  - src/spedas_agent_kit/resources/CONTRACT.md
  - src/spedas_agent_kit/__init__.py
  - src/spedas_agent_kit/__main__.py
  - src/spedas_agent_kit/server.py
  - src/spedas_agent_kit/workflows.py
  - src/spedas_agent_kit/installation.py
  - src/spedas_agent_kit/optional_backends.py
  - tests/test_server.py
  - tests/test_resources.py
  - tests/test_config.py
  - tests/test_architecture_documents.py
maintenance: |
  Keep related_files repo-relative, duplicate-free, and linked to real files.
  Keep this component's ANATOMY.md and CONTRACT.md reciprocal and keep
  parent/child anatomy links bidirectional. Code is the structural source of
  truth: update this anatomy in the same change that moves files, symbols,
  connections, composition, or state. Verify every changed citation and run the
  architecture-document validation before merge. Follow the root
  Anatomy/Contract pairing rule, report mismatches, and do not duplicate or
  auto-fix the rule here.
---
# src/spedas_agent_kit — the package facade

## What this is

The Python package: a FastMCP **facade** that registers heliophysics tools and
dispatches them to wrapped backends. Almost no science lives here — the value
is unified `source_type` dispatch, input validation, the structured-error
contract, kernel-download gating, and the artifact-first response shape. Its
interface promise is the paired
[`src/spedas_agent_kit/CONTRACT.md`](src/spedas_agent_kit/CONTRACT.md); this
file maps where that promise is implemented.

## Components

- **`__init__.py`/`__main__.py`** — `main()` at `src/spedas_agent_kit/__init__.py:6`
  is the console entry point: it imports `serve()` from `server.py` and runs
  it; `__main__.py` enables `python -m spedas_agent_kit`.
- **`server.py`** — the whole facade. Key anchors:
  - `create_server()` at `src/spedas_agent_kit/server.py:1044` — constructs
    the FastMCP and registers all tool closures: 13 base tools plus 8 legacy
    CDAWeb/PDS compatibility tools when enabled. Tools are nested closures,
    so grep by tool name finds the `def`.
  - `_register_tool()` at `src/spedas_agent_kit/server.py:1062` — the single
    registration path; attaches MCP `ToolAnnotations` and `meta.surface`
    (`primary` or `compat`).
  - `_compat_tools_enabled()` at `src/spedas_agent_kit/server.py:107` — gates
    the 8 legacy tools behind `SPEDAS_AGENT_KIT_COMPAT_TOOLS=1`;
    `_compat_tool()` at `src/spedas_agent_kit/server.py:1096` only registers
    those aliases when enabled.
  - `_normalize_source_type()` at `src/spedas_agent_kit/server.py:1852` — the
    unified-dispatch core: normalizes aliases (`cda`→`cdaweb`, `pds_ppi`→`pds`,
    `geometry`→`spice`, `all`) and routes by `source_type`.
  - `_wrap_data_payload()` at `src/spedas_agent_kit/server.py:1927` — wraps
    backend JSON into the uniform `{status, source_type, payload}` envelope,
    sanitizing raw error strings.
  - `_error_response()` at `src/spedas_agent_kit/server.py:329` — the
    structured `{status, code, message, hint}` error contract;
    `_sanitize_message()` at `src/spedas_agent_kit/server.py:306` redacts
    paths/URLs from user-facing strings.
  - `_size_guarded()` at `src/spedas_agent_kit/server.py:488` — caps tool
    results so bulk data goes to files, not the MCP result.
  - `_install_argument_validation_guard()` at
    `src/spedas_agent_kit/server.py:2737` — converts FastMCP arg-validation
    failures into structured errors; `serve()` at
    `src/spedas_agent_kit/server.py:2796` wires the server for the entry
    point.
- **`workflows.py`** — pure-Python planning behind the workflow tools:
  `search_data_sources` at `src/spedas_agent_kit/workflows.py:824`,
  `compare_sources` at `src/spedas_agent_kit/workflows.py:856`,
  `plan_observation` at `src/spedas_agent_kit/workflows.py:1170`,
  `create_analysis_bundle` at `src/spedas_agent_kit/workflows.py:1351`. No
  backend dependency → robust; bugs cluster in adapters, not here.
- **`installation.py`** — dependency-free install guidance: `install_hint()`
  at `src/spedas_agent_kit/installation.py:75`,
  `source_install_command()` at `src/spedas_agent_kit/installation.py:48`,
  `missing_backend_message()` at `src/spedas_agent_kit/installation.py:90`;
  renders checkout-relative install paths only (the distribution is
  source-only, not on a public index).
- **`optional_backends.py`** — optional-dependency detection:
  `required_imports_available()` at
  `src/spedas_agent_kit/optional_backends.py:58` and
  `analysis_dependencies_available()` at
  `src/spedas_agent_kit/optional_backends.py:70` gate the analysis bundle
  workflow.

## Connections

- **In:** MCP client calls a registered tool → its closure inside
  `create_server()` (`src/spedas_agent_kit/server.py:1044`).
- **Out:** tool closures lazily import the vendored `backends.cdaweb` /
  `backends.pds` / `backends.spice` packages at call time
  (`src/spedas_agent_kit/server.py:1329`, `src/spedas_agent_kit/server.py:1781`)
  and dispatch `fetch_data_product`/`browse_*`/`manage_data_cache` by
  `source_type`.
- **Out (resources):** the server exposes packaged skills, event presets, and
  provenance schemas through `resources/` (see
  [`src/spedas_agent_kit/resources/ANATOMY.md`](src/spedas_agent_kit/resources/ANATOMY.md)).
- **Down:** `workflows.py` is called by the workflow tool closures; it never
  imports a backend.

## Composition

- **Parent:** repository root (`ANATOMY.md`).
- **Paired contract:** `src/spedas_agent_kit/CONTRACT.md` (reciprocal).
- **Direct child components:** `backends/` and `resources/`, each with its own
  anatomy/contract pair (see `related_files`).

## State

- None persistent in-process. Writes happen only through the data tools (to
  backend caches and bundle directories) and through `manage_data_cache`
  (`src/spedas_agent_kit/server.py:2666`).
- Surface composition is decided at `create_server()` time from the
  `SPEDAS_AGENT_KIT_COMPAT_TOOLS` env flag (`src/spedas_agent_kit/server.py:107`).

## Notes

- `server.py` is large (2821 lines) and closure-heavy by design (FastMCP
  registration). Navigate by tool name → its nested `def`, or by the helper
  anchors above — not by reading top-to-bottom.
- The facade↔backend seam is the bug-prone place (numpy serialization, unit
  conventions, fill values, probe paths). Validate adapter I/O shapes, not
  just that a call returns.
- Compat tools are hidden, not deleted: the unified tools call the same
  underlying backend functions, and `SPEDAS_AGENT_KIT_COMPAT_TOOLS=1` only
  re-advertises the legacy names.
