---
name: spedas-workflow
description: Use the spedas-mcp MCP server for safe SPEDAS/CDAWeb/PDS/SPICE heliophysics workflows in Claude Code.
---

# SPEDAS MCP workflow for Claude Code

Use this skill when a task involves SPEDAS, PySPEDAS, heliophysics time series, CDAWeb datasets, NASA PDS Planetary Plasma Interactions datasets, or SPICE ephemeris/coordinate work.

## Capability map

The plugin exposes one MCP server named `spedas`. Start with `spedas_overview()` when uncertain.

- CDAWeb: `browse_observatories`, `load_observatory`, `browse_parameters`, `fetch_data`, `manage_cdaweb_cache`.
- PDS PPI: `browse_pds_missions`, `load_pds_mission`, `browse_pds_parameters`, `fetch_pds_data`, `manage_pds_cache`.
- SPICE: `list_spice_missions`, `get_ephemeris`, `compute_distance`, `transform_coordinates`, `list_coordinate_frames`, `manage_spice_kernels`.

## Default workflow

1. Discover first: call `spedas_overview()`, then the relevant browse/load tool.
2. Inspect parameters before fetching data:
   - CDAWeb: `browse_parameters(dataset_id=...)`
   - PDS: `browse_pds_parameters(dataset_id=...)`
3. Keep data ranges small by default. Prefer minutes/hours/days for examples, not mission-scale downloads.
4. Always write bulk data to files with `output_dir` or `output_file`. Do not ask the MCP server to return arrays inline.
5. Return compact summaries to the user: file paths, row counts, parameter names, units, time ranges, cache notes, and caveats.
6. Treat downloads, cache refreshes, and SPICE kernel loads as integration actions. Explain expected side effects before broad operations.

## Guardrails

- Do not bulk-fetch every dataset or every mission unless the human explicitly asks and understands the archive size.
- For PDS, remember the audit result: many datasets currently fail metadata resolution; report metadata/label gaps separately from MCP transport failures.
- For SPICE, `get_ephemeris` may download kernels; use `list_spice_missions` and cache status first when possible.
- For CDAWeb/PDS data fetches, make output locations explicit and stable.

## Useful first prompts

- “Use `spedas_overview` and summarize which CDAWeb, PDS, and SPICE tools are available.”
- “Find a Juno PDS FGM dataset, inspect its parameters, and propose a small fetch window.”
- “List PSP/SPICE support and compute a short ephemeris CSV for a tiny interval.”
- “Compare whether a question should use CDAWeb, PDS PPI, or SPICE.”
