---
name: spedas-workflow
description: Use spedas-mcp from Codex for safe CDAWeb, PDS PPI, and SPICE heliophysics workflows.
---

# SPEDAS MCP workflow for Codex

Use this skill when a task involves SPEDAS/PySPEDAS modernization, heliophysics time series, CDAWeb, NASA PDS Planetary Plasma Interactions datasets, or SPICE ephemeris/coordinate work.

## Tool map

Use the bundled `spedas` MCP server.

- Overview: `spedas_overview`
- CDAWeb: `browse_observatories`, `load_observatory`, `browse_parameters`, `fetch_data`, `manage_cdaweb_cache`
- PDS PPI: `browse_pds_missions`, `load_pds_mission`, `browse_pds_parameters`, `fetch_pds_data`, `manage_pds_cache`
- SPICE: `list_spice_missions`, `get_ephemeris`, `compute_distance`, `transform_coordinates`, `list_coordinate_frames`, `manage_spice_kernels`

## Operating procedure

1. Discover first. Call `spedas_overview`, then the relevant browse/load tool.
2. Inspect metadata before fetching (`browse_parameters` for CDAWeb, `browse_pds_parameters` for PDS).
3. Use small time windows by default.
4. Write any fetched data or trajectory products to explicit files, not chat.
5. Summarize with paths, row counts, units, time range, cache side effects, and known caveats.
6. Separate MCP/server failures from source-archive metadata gaps.

## Known PDS caveat

A full `xhelio-pds` MCP metadata audit found that the MCP transport and mission catalog surfaces work, but many PDS datasets still have metadata/label resolution gaps. If `browse_pds_parameters` fails with “Could not fetch metadata,” report it as a dataset metadata coverage issue and suggest a targeted fix or fallback inspection.
