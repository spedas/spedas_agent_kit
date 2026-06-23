# Maintainer note: SPEDAS MCP as an agent interface layer

`spedas_mcp` is intended to be the SPEDAS-facing MCP endpoint for agentic heliophysics workflows.

It does **not** replace SPEDAS, PySPEDAS, CDAWeb, PDS, or SPICE. Instead, it provides an interface layer that MCP-capable coding/research agents can use to plan and execute SPEDAS-related work with clearer source boundaries and provenance expectations.

## Why one MCP?

Jason's three seed capabilities cover complementary layers:

- `xhelio-cdaweb` — heliophysics observatory time-series discovery, metadata, and fetch.
- `xhelio-pds` — Planetary Plasma Interactions mission/dataset discovery, metadata, and fetch.
- `xhelio-spice` — geometry, ephemeris, distances, coordinate transforms, frames, and kernel cache management.

A researcher or agent normally needs these together: measurements from CDAWeb/PDS and geometry from SPICE. A single SPEDAS MCP gives the agent one scientific entry point while preserving the underlying packages as focused maintainable components.

## Current architecture

The repo uses a two-layer design:

1. **Stable unified facade**
   - Keep low-level CDAWeb/PDS/SPICE tools explicit and close to the underlying XHelio packages.
   - Avoid duplicating domain logic that belongs in those packages.
   - Keep bulk data as files and return compact metadata/paths.

2. **SPEDAS science workflow layer**
   - Add tools that help an agent decide which source family to use first.
   - Encode reusable scientific workflow: plan before fetch, discover before selecting parameters, preserve request/provenance intent.
   - Keep this layer small until specific SPEDAS use cases justify deeper orchestration.

## Current high-level workflow tools

- `search_spedas_data_sources(...)` — rank CDAWeb/PDS/SPICE for a science question.
- `plan_spedas_observation(...)` — produce a source-specific execution plan.
- `compare_cdaweb_pds_spice(...)` — explain source boundaries for maintainers/users.
- `create_spedas_analysis_bundle(...)` — scaffold request/provenance folders before fetches.

## What should be upstreamed here vs. elsewhere?

Good fits for `spedas_mcp`:

- Unified MCP naming and schema conventions.
- Cross-source planning logic.
- Agent-facing examples and plugin wrappers.
- Provenance bundle conventions.
- Compatibility smoke tests and list-tools validation.

Better fits for underlying packages:

- CDAWeb catalog/fetch semantics → `xhelio-cdaweb`.
- PDS archive resolution and dataset metadata → `xhelio-pds`.
- SPICE kernel registry and geometry computation → `xhelio-spice`.
- Full SPEDAS/PySPEDAS numerical routines → SPEDAS/PySPEDAS proper.

## Near-term next steps

1. Add examples that combine measurement + geometry, for example Juno PDS + SPICE or MMS/CDAWeb + bow-shock geometry.
2. Add opt-in real-data integration smokes that write artifacts to temporary directories.
3. Publish a small release once the API is stable enough for Claude/Codex/OpenCode plugin users.
4. Keep the science workflow layer intentionally small until real SPEDAS users validate the best abstractions.
