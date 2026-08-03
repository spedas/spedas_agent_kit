---
name: spedas-agent-kit-facade
contract_version: 1
root_contract: CONTRACT.md
related_files:
  - src/spedas_agent_kit/ANATOMY.md
  - src/spedas_agent_kit/server.py
  - src/spedas_agent_kit/workflows.py
  - src/spedas_agent_kit/__init__.py
  - src/spedas_agent_kit/installation.py
  - src/spedas_agent_kit/optional_backends.py
  - src/spedas_agent_kit/backends/CONTRACT.md
  - src/spedas_agent_kit/resources/CONTRACT.md
  - tests/test_server.py
  - tests/test_resources.py
  - tests/test_config.py
  - tests/test_architecture_documents.py
  - tests/contracts/mcp_surface/base.json
  - tests/contracts/mcp_surface/compat.json
maintenance: |
  This component contract is governed by the root CONTRACT.md. Keep
  related_files complete and repo-relative, including the paired ANATOMY.md,
  the Port, production Adapters, and contract tests. Update the Port, affected
  Adapters, tests, and this contract together when a boundary or normative
  behavior changes; update the paired Anatomy when structure changes. Follow
  the root Anatomy/Contract pairing and ownership rules, report mismatches,
  and do not duplicate or auto-fix the rule here.
---
# SPEDAS Agent Kit facade contract

## Purpose and ownership

The `spedas_agent_kit` package is the **Core** of the system: one FastMCP
facade over the vendored CDAWeb/PDS/SPICE backends and the packaged skills. It
owns the MCP tool surface, `source_type` dispatch, input validation, the
structured-error contract, artifact discipline, and the science-workflow
use cases. It owns no science and no concrete provider access; those live in
the backends (`src/spedas_agent_kit/backends/CONTRACT.md`) and the packaged
skills (`src/spedas_agent_kit/resources/CONTRACT.md`).

The facade is the only component that imports backend adapters, and it does so
lazily inside tool closures so an unused backend never pays an import cost.

## Public port

The public port is the MCP tool surface registered by `create_server()`
(`src/spedas_agent_kit/server.py:1044`) through `_register_tool()`
(`src/spedas_agent_kit/server.py:1062`):

- **13 base tools**, always advertised:
  - data layer (5): `browse_data_sources`, `load_data_source`,
    `browse_data_parameters`, `fetch_data_product`, `manage_data_cache`;
  - science workflows (4): `search_spedas_data_sources`, `plan_spedas_observation`,
    `compare_cdaweb_pds_spice`, `create_spedas_analysis_bundle`;
  - geometry (3): `get_ephemeris`, `compute_distance`, `transform_coordinates`;
  - overview (1): `spedas_overview`.
- **8 compat tools**, advertised only when `SPEDAS_AGENT_KIT_COMPAT_TOOLS=1`
  (`_compat_tools_enabled()` at `src/spedas_agent_kit/server.py:107`):
  `browse_observatories`, `load_observatory`, `browse_parameters`,
  `fetch_data`, `browse_pds_missions`, `load_pds_mission`,
  `browse_pds_parameters`, `fetch_pds_data`. They are `meta.surface="compat"`
  aliases; the unified tools call the same backend functions regardless.

Every registered tool carries MCP `ToolAnnotations` and `meta.surface`
(`primary` or `compat`).

**Artifact-first response shape.** Data and workflow tools return a compact
`{status, file_path, stats}` envelope — bulk arrays never appear in tool
results. The analysis bundle workflow writes a directory tree
(`requests/ data/ plots/ provenance/ notes/`) via `create_analysis_bundle`
(`src/spedas_agent_kit/workflows.py:1351`) and returns paths/stats only.

**Structured error shape.** Every user-facing error is the envelope
`{status: "error", code, message, hint?}` built by `_error_response()`
(`src/spedas_agent_kit/server.py:329`); `message` and string extras are
path/URL-redacted (`_sanitize_message()` at
`src/spedas_agent_kit/server.py:306`). Agents branch on `status`/`code`, never
parse free text.

**Unified `source_type` dispatch.** All data-layer tools accept
`source_type` in `cdaweb | pds | spice | all` (with aliases), normalized by
`_normalize_source_type()` at `src/spedas_agent_kit/server.py:1852`;
backend output is wrapped by `_wrap_data_payload()` at
`src/spedas_agent_kit/server.py:1927`.

## Internal composition

- `create_server()` is a closure factory: it builds the FastMCP instance,
  reads the compat gate, defines `_register_tool`/`_primary_tool`/
  `_compat_tool` decorators, and defines every tool as a nested closure
  (`src/spedas_agent_kit/server.py:1044-1107`).
- `_register_tool()` is the single registration path — every advertised tool
  passes through it, which is why `meta.surface` and annotations are uniform
  (`src/spedas_agent_kit/server.py:1062`).
- `_normalize_source_type()` canonicalizes the dispatch key
  (`src/spedas_agent_kit/server.py:1852`); `_wrap_data_payload()` normalizes
  backend JSON into the uniform envelope and preserves an already-structured
  error verbatim (`src/spedas_agent_kit/server.py:1927`).
- Lazy backend imports: each tool closure imports only the backend module it
  needs at call time (`src/spedas_agent_kit/server.py:1329`,
  `src/spedas_agent_kit/server.py:1781`, `src/spedas_agent_kit/server.py:1829`).
- `serve()` at `src/spedas_agent_kit/server.py:2796` is the Composition Root:
  it wires `create_server()` with the arg-validation guard
  (`src/spedas_agent_kit/server.py:2737`) and runs the MCP server; `main()`
  (`src/spedas_agent_kit/__init__.py:6`) delegates to it.
- `workflows.py` is pure Core: no backend imports, so its use cases are
  testable without providers.

## Error semantics

- **Structured, always:** errors carry `{status: "error", code, message,
  hint}`; known codes include `invalid_argument`, `no_data`, and backend
  failure classifications produced by `_error_response()`.
- **Sanitized:** absolute paths and URLs are redacted from every user-facing
  string so backend internals never leak.
- **Validation before I/O:** fetch times are validated locally
  (`_validate_fetch_time_range`, `src/spedas_agent_kit/server.py:365`) before
  any network round-trip; FastMCP argument-validation failures are converted
  to structured errors by `_install_argument_validation_guard()`
  (`src/spedas_agent_kit/server.py:2737`).

## Ordering and state

- Registration order inside `create_server()` decides MCP tool listing order,
  but tools are stateless closures; no cross-tool ordering guarantees exist.
- Persistent state is written only by data tools (backend caches and bundle
  directories) and managed through `manage_data_cache`
  (`src/spedas_agent_kit/server.py:2666`); the facade keeps no in-process
  mutable state beyond per-call locals.
- The compat gate is read once per `create_server()` call, so surface
  composition is fixed for the life of a server instance.

## Contract tests

Focused evidence:

```bash
python -m pytest -q tests/test_server.py tests/test_resources.py \
  tests/test_config.py tests/test_architecture_documents.py
```

The MCP surface snapshots under `tests/contracts/mcp_surface/`
(`base.json`, `compat.json`) pin the 13-base / 8-compat tool surface via
`scripts/check_mcp_surface_contract.py`.

## Maintenance

Keep this contract in sync with the paired
[`src/spedas_agent_kit/ANATOMY.md`](src/spedas_agent_kit/ANATOMY.md). Adding a
tool, changing the response/error envelope, changing `source_type` vocabulary,
or moving a Port boundary updates this contract, the surface snapshots, and
the affected tests in the same change. Bump `contract_version` for breaking
public changes (per the root CONTRACT.md versioning rule).
