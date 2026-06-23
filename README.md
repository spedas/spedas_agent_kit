# SPEDAS MCP

`spedas_mcp` is the SPEDAS organization MCP server for agentic heliophysics workflows. It turns the three XHelio capability layers Jason provided — CDAWeb, PDS, and SPICE — into one SPEDAS-facing MCP endpoint.

The design follows two layers:

- **A. Stable unified facade** — preserve clear low-level tool groups for `xhelio-cdaweb`, `xhelio-pds`, and `xhelio-spice` so each package can keep evolving independently.
- **B. SPEDAS science workflow layer** — add high-level planning tools so Claude Code, Codex, OpenCode, LingTai, or another agent can start from a science question and then choose CDAWeb/PDS/SPICE tools deliberately.

This is not a replacement for SPEDAS/PySPEDAS. It is an agent interface layer that lets MCP-capable runtimes discover, plan, fetch, compute, and preserve provenance around SPEDAS-related data workflows.

## Repository

- Official repo: <https://github.com/spedas/spedas_mcp>
- Python package name: `spedas-mcp`
- Python module / CLI module: `spedas_mcp`

## Capability map

### SPEDAS workflow tools

Start here for open-ended science requests.

- `spedas_overview()` — compact map of available capability groups and recommended workflow.
- `search_spedas_data_sources(question, target=None, observables=None)` — recommend whether the request should start with CDAWeb, PDS, SPICE, or a mix.
- `plan_spedas_observation(science_goal, start=None, stop=None, target=None, observables=None, data_sources=None)` — build a source-specific plan before fetching data.
- `compare_cdaweb_pds_spice(science_goal="")` — explain what each source family is good for and where it should not be used.
- `create_spedas_analysis_bundle(study_name, output_dir, ...)` — create a lightweight request/provenance bundle with `requests/`, `data/`, `plots/`, `provenance/`, and `notes/` folders.

### CDAWeb tools

Use for heliophysics observatory time series, CDF-style datasets, plasma/field/particle measurements, and solar-wind context.

- `browse_observatories()`
- `load_observatory(observatory_id)`
- `browse_parameters(dataset_id, dataset_ids=None)`
- `fetch_data(dataset_id, parameters, start, stop, output_dir, format="csv")`
- `manage_cdaweb_cache(action, cache_dir=None)`

### PDS PPI tools

Use for Planetary Plasma Interactions mission/dataset discovery, PDS parameter metadata, and archive-backed planetary plasma products.

- `browse_pds_missions(query=None)`
- `load_pds_mission(mission_id)`
- `browse_pds_parameters(dataset_id, dataset_ids=None)`
- `fetch_pds_data(dataset_id, parameters, start=None, stop=None, output_dir=None, format="csv", limit=None)`
- `manage_pds_cache(action, cache_dir=None)`

### SPICE tools

Use for spacecraft/body geometry, ephemerides, distances, coordinate transforms, frames, and kernel cache management.

- `list_spice_missions()`
- `get_ephemeris(mission, target, start, stop, step="1h", frame="J2000", observer=None)`
- `compute_distance(mission, target, observer, start, stop, step="1h")`
- `transform_coordinates(mission, coordinates, from_frame, to_frame, epoch=None)`
- `list_coordinate_frames(mission=None)`
- `manage_spice_kernels(action, mission=None, cache_dir=None)`

## Recommended agent workflow

1. Call `spedas_overview()` to learn the available groups.
2. For a natural-language or science-goal request, call `search_spedas_data_sources(...)` or `plan_spedas_observation(...)`.
3. Use source-specific discovery before data movement:
   - CDAWeb: `browse_observatories` → `load_observatory` → `browse_parameters` → `fetch_data`
   - PDS: `browse_pds_missions` → `load_pds_mission` → `browse_pds_parameters` → `fetch_pds_data`
   - SPICE: `list_spice_missions` / `list_coordinate_frames` → `get_ephemeris` / `compute_distance` / `transform_coordinates`
4. For any real analysis, call `create_spedas_analysis_bundle(...)` and write fetched files under the generated `data/` directory.
5. Return compact summaries and file paths. Do not return bulk science arrays directly in chat.

## Quick start for local development

```bash
git clone https://github.com/spedas/spedas_mcp.git
cd spedas_mcp
uv sync --extra dev --extra mcp
uv run --extra mcp python -m spedas_mcp
```

Run tests and smoke checks:

```bash
uv run --extra dev --extra mcp python -m pytest -q
uv run --extra mcp python scripts/smoke_mcp_list_tools.py --json
uv run --extra dev --extra mcp python scripts/validate_plugin_packages.py
```

The list-tools smoke starts the stdio MCP server with isolated temporary cache directories, performs MCP `initialize` + `list_tools`, and verifies the expected advertised tool names. It does not fetch CDAWeb/PDS data or download SPICE kernels.

## MCP client configuration

Example stdio configuration:

```json
{
  "mcpServers": {
    "spedas": {
      "command": "uv",
      "args": ["run", "--extra", "mcp", "python", "-m", "spedas_mcp"],
      "cwd": "/path/to/spedas_mcp"
    }
  }
}
```

For plugin-style distribution, see:

- `plugins/spedas-claude/` — Claude Code wrapper.
- `.agents/plugins/spedas-codex/` — Codex plugin wrapper.
- `plugins/README.md` — plugin packaging notes.

## Maintainer-facing positioning

`spedas_mcp` should stay thin where the underlying science packages already have strong ownership, and become thick only at the SPEDAS workflow level:

- Keep CDAWeb, PDS, and SPICE domain details in their focused XHelio packages.
- Keep this repo responsible for unified naming, agent-facing workflow, packaging, plugin wrappers, examples, and provenance conventions.
- Add higher-level tools only when they encode reusable SPEDAS scientific method rather than one-off prompt text.

See `docs/maintainer_note.md` and `docs/examples/agent_workflow.md` for the current framing.
