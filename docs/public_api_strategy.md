# Public API strategy

SPEDAS MCP's public surface is intentionally layered so agents can start from a
science question instead of choosing backend packages first.

## Preferred mental model

1. **SPEDAS MCP** is the single user-facing server.
2. **Science workflow layer** helps scope the request, choose source families,
   and preserve provenance before bulk fetches.
3. **Data layer** provides one set of browse/load/parameter/fetch/cache verbs.
4. **Data source categories** (`cdaweb`, `pds`, `spice`) select the archive or
   geometry family under those verbs.

Use this path for new prompts, docs, demos, and agent behavior:

```text
spedas_overview
  -> search_spedas_data_sources or plan_spedas_observation
  -> browse_data_sources / load_data_source / browse_data_parameters
  -> fetch_data_product for CDAWeb/PDS data, or geometry tools for SPICE
  -> create_spedas_analysis_bundle for real analyses
```

## Compatibility tools

The server still advertises source-specific CDAWeb/PDS/SPICE tools because hiding
or renaming them would break existing MCP clients and saved prompts. They are
**supported compatibility tools**, not the preferred starting point for new
workflows.

| Compatibility surface | Preferred new entry point |
|---|---|
| `browse_observatories` | `browse_data_sources(source_type="cdaweb")` |
| `load_observatory` | `load_data_source(source_type="cdaweb", source_id=...)` |
| `browse_parameters` | `browse_data_parameters(source_type="cdaweb", dataset_id=...)` |
| `fetch_data` | `fetch_data_product(source_type="cdaweb", ...)` |
| `manage_cdaweb_cache` | `manage_data_cache(source_type="cdaweb", action=..., category=..., observatory=..., dataset_ids=..., older_than_days=..., dry_run=..., detail=...)` |
| `browse_pds_missions` | `browse_data_sources(source_type="pds")` |
| `load_pds_mission` | `load_data_source(source_type="pds", source_id=...)` |
| `browse_pds_parameters` | `browse_data_parameters(source_type="pds", dataset_id=...)` |
| `fetch_pds_data` | `fetch_data_product(source_type="pds", ...)` |
| `manage_pds_cache` | `manage_data_cache(source_type="pds", action=..., category=..., mission=..., dataset_ids=..., older_than_days=..., dry_run=..., detail=..., force=...)` |
| `manage_spice_kernels` | `manage_data_cache(source_type="spice", action=..., mission=..., filenames=...)` |

SPICE geometry operations (`get_ephemeris`, `compute_distance`,
`transform_coordinates`, `list_coordinate_frames`, `list_spice_missions`) remain
explicit public tools because they are scientific operations rather than archive
fetch aliases. The unified data layer routes SPICE data-product fetch attempts to
these geometry tools.

## Deprecation guidance

Do not remove or hide compatibility tools in a minor cleanup. A future breaking
API pass may make them opt-in or move them behind a compatibility namespace, but
that should require maintainer review and a migration plan that includes:

- a release note and version bump policy,
- at least one release where descriptions and docs warn about the change,
- client examples rewritten to use the science workflow and data-layer tools,
- smoke tests for both the preferred surface and the compatibility surface until
  removal actually happens.
