---
related_files:
  - CONTRACT.md
  - README.md
  - pyproject.toml
  - server.json
  - src/spedas_agent_kit/ANATOMY.md
  - src/spedas_agent_kit/CONTRACT.md
  - src/spedas_agent_kit/backends/ANATOMY.md
  - src/spedas_agent_kit/backends/CONTRACT.md
  - src/spedas_agent_kit/resources/ANATOMY.md
  - src/spedas_agent_kit/resources/CONTRACT.md
  - src/spedas_agent_kit/__init__.py
  - src/spedas_agent_kit/server.py
  - src/spedas_agent_kit/workflows.py
  - src/spedas_agent_kit/installation.py
  - src/spedas_agent_kit/optional_backends.py
  - src/spedas_agent_kit/resources/skill_catalog.py
  - src/spedas_agent_kit/resources/event_presets.py
  - src/spedas_agent_kit/resources/provenance.py
  - src/spedas_agent_kit/resources/skills/README.md
  - scripts/check_anatomy_drift.py
  - scripts/check_mcp_surface_contract.py
  - scripts/smoke_mcp_list_tools.py
  - scripts/export_packaged_skills.py
  - tests/test_architecture_documents.py
  - tests/contracts/mcp_surface/base.json
maintenance: |
  This file is both the repository-root anatomy and the normative
  anatomy-of-anatomy for the distributed code navigation system. Keep
  related_files repo-relative, duplicate-free, and linked to real files. Keep
  the root CONTRACT.md reciprocal and update the paired conventions together
  when their boundary changes. Code is the structural source of truth: repair
  stale navigation in the same change that moves files, symbols, connections,
  composition, or state. Verify every changed citation and run the
  architecture-document validation before merge. Follow the root
  Anatomy/Contract pairing rule, report mismatches, and do not duplicate or
  auto-fix the rule here.
---
# SPEDAS Agent Kit Anatomy

## Purpose

**ANATOMY is the distributed code navigation system.** Each architectural layer
keeps an `ANATOMY.md` beside the code it maps; local maps link into a graph an
agent descends from this root to the exact code that answers a structural
question.

This repo is the **SPEDAS Agent Kit**: one MCP facade giving AI agents a unified
door to heliophysics data and geometry — a single `spedas-agent-kit` MCP server
dispatching by `source_type` to three vendored data backends (CDAWeb
measurements, PDS PPI archive data, SPICE ephemeris/geometry) plus packaged
shared workflow skills that thin runtime wrappers (Claude Code, Codex, OpenCode)
package or sync instead of reimplementing.

This file has two roles: the repository's top-level map, and the **anatomy of
anatomy** — the normative template, link rules, and maintenance contract for the
distributed navigation system. `ANATOMY.md` and [`CONTRACT.md`](CONTRACT.md)
are a pair, not duplicates: anatomy maps **where code is and how it composes**
(code is the structural source of truth); CONTRACT defines **how a layer may be
used and what it promises** (normative when implementation disagrees).

## Navigation model

Navigation is distributed: the root defines the system and entry points; each
component maps only the layer it owns; parent/child and related-file links
connect the layers. For structural questions descend the graph until it points
at code; for enumeration questions use search — cited code remains the
evidence. A folder earns an anatomy when an agent can reason about it as an
architectural unit without reading all siblings. Governed components:
`src/spedas_agent_kit/` (facade), `src/spedas_agent_kit/backends/` (data
backends), `src/spedas_agent_kit/resources/` (packaged skills) — each with a
co-located, reciprocal `ANATOMY.md`/`CONTRACT.md` pair.

## Link and pairing semantics

1. Root anatomy and root contract list each other in `related_files`.
2. A governed component's co-located `ANATOMY.md`/`CONTRACT.md` list each other
   exactly once; parent/child anatomy links are reciprocal.
3. Contract owns interface behavior; anatomy owns structure/composition.
4. A structural change updates anatomy in the same change; a Port/Adapter/
   promise change updates contract and contract tests; both → the pair.
5. Orphans, missing targets, duplicate/one-way links, and unpaired governed
   components are defects and MUST fail validation
   ([`tests/test_architecture_documents.py`](tests/test_architecture_documents.py)).

## Components

- [`src/spedas_agent_kit/`](src/spedas_agent_kit/) — the package facade:
  unified `source_type` dispatch, structured errors, artifact-first responses.
  Entry: `main()` at `src/spedas_agent_kit/__init__.py:6` runs `serve()`
  (`src/spedas_agent_kit/server.py:2796`). Descend via
  [`src/spedas_agent_kit/ANATOMY.md`](src/spedas_agent_kit/ANATOMY.md).
- [`src/spedas_agent_kit/backends/`](src/spedas_agent_kit/backends/) — the
  vendored cdaweb/pds/spice backends; each exposes a catalog / metadata /
  fetch / cache / config surface the facade imports lazily inside tool
  closures (`src/spedas_agent_kit/server.py:1329`,
  `src/spedas_agent_kit/server.py:1781`). Descend via
  [`src/spedas_agent_kit/backends/ANATOMY.md`](src/spedas_agent_kit/backends/ANATOMY.md).
- [`src/spedas_agent_kit/resources/`](src/spedas_agent_kit/resources/) — skill
  catalog, event presets, provenance schemas, and the six packaged skills.
  Descend via
  [`src/spedas_agent_kit/resources/ANATOMY.md`](src/spedas_agent_kit/resources/ANATOMY.md).
- [`src/spedas_agent_kit/server.py`](src/spedas_agent_kit/server.py) — the
  FastMCP facade. `create_server()` at `src/spedas_agent_kit/server.py:1044`
  registers tools via `_register_tool()` (`src/spedas_agent_kit/server.py:1062`);
  `_compat_tools_enabled()` at `src/spedas_agent_kit/server.py:107` gates the 8
  legacy compat tools; `_error_response()` at
  `src/spedas_agent_kit/server.py:329` builds the structured error envelope.
- [`src/spedas_agent_kit/workflows.py`](src/spedas_agent_kit/workflows.py) —
  pure-Python science planning: `search_data_sources` at
  `src/spedas_agent_kit/workflows.py:824`, `compare_sources` at
  `src/spedas_agent_kit/workflows.py:856`, `plan_observation` at
  `src/spedas_agent_kit/workflows.py:1170`, `create_analysis_bundle` at
  `src/spedas_agent_kit/workflows.py:1351`.
- [`scripts/`](scripts/) — utility/checker scripts: anatomy drift checker
  (`check_anatomy_drift.py`), MCP surface snapshot/diff
  (`check_mcp_surface_contract.py`), tool-surface smoke (`smoke_mcp_list_tools.py`),
  packaged-skill exporter (`export_packaged_skills.py`).
- [`tests/`](tests/) — pytest suite mirroring each module and packaged
  resources; `tests/contracts/mcp_surface/` holds the base/compat/datasource
  snapshots.

## Connections

- **Client → facade.** MCP stdio JSON-RPC; the client receives artifact-first
  `{status, file_path, stats}` responses — never bulk arrays. Errors use the
  structured `{status, code, message, hint}` envelope
  (`src/spedas_agent_kit/server.py:329`).
- **Facade → backends.** Tool closures lazily import the vendored
  `spedas_agent_kit.backends.*` packages and dispatch by `source_type` via
  `_normalize_source_type()` (`src/spedas_agent_kit/server.py:1852`).
- **Facade → resources.** Skills/presets are read-only MCP resources via
  `skill_catalog.py`/`event_presets.py`; bundle provenance is validated via
  `provenance.py`.
- **Runtime wrapper → facade.** Thin wrappers launch the `spedas-agent-kit`
  server (`pyproject.toml` entry point `spedas-agent-kit = spedas_agent_kit:main`)
  and sync packaged skills (`scripts/export_packaged_skills.py`).

## Composition

- **Parent:** none — this is the repository root.
- **Governed children with own anatomy/contract pairs:**
  `src/spedas_agent_kit/`, `src/spedas_agent_kit/backends/`,
  `src/spedas_agent_kit/resources/`.
- **Mapped narratively (no own anatomy):** `tests/`, `docs/`, `plugins/`.
- `pyproject.toml` declares the package, extras `mcp`/`dev`, and the console
  entry point; `server.json` is a sample wrapper launcher config.

## State

- No server-side persistent state. Backend caches live in the user's home
  (`~/.cdawebmcp/`, `~/.pdsmcp/`, `~/.xhelio_spice/kernels/`), managed via
  `manage_data_cache` (`src/spedas_agent_kit/server.py:2666`).
- Surface gating is runtime, not stored: `SPEDAS_AGENT_KIT_COMPAT_TOOLS=1`
  advertises the 8 legacy compat tools; the base surface is 13 tools
  (`scripts/check_mcp_surface_contract.py:16`), 21 with compat enabled.
- Data/workflow tools are artifact-first: bulk results are written to disk
  (bundle dirs with `requests/ data/ plots/ provenance/ notes/` via
  `create_analysis_bundle` at `src/spedas_agent_kit/workflows.py:1351`); only
  paths/stats are returned.

## Notes

- The bug-prone seam is facade↔backend adapters, not dispatch — most fixed
  issues lived there (numpy serialization, unit conventions, fill values,
  probe paths). Validate adapter I/O shapes, not just that a call returns.
- Consolidation: compat/cache tools are hidden, not deleted; new capability
  lands as a `source_type` or a **skill**, not a new top-level tool.
- These architecture documents write no runtime state. Verify every touched
  citation with `scripts/check_anatomy_drift.py` before merge.
