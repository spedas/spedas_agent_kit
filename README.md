# SPEDAS Agent Kit

`spedas_agent_kit` is the SPEDAS organization MCP server for agentic heliophysics workflows. It presents one SPEDAS-facing **data layer** and organizes capabilities by data source category instead of by the internal backend packages used to implement them.

[![CI](https://github.com/spedas/spedas_agent_kit/actions/workflows/ci.yml/badge.svg)](https://github.com/spedas/spedas_agent_kit/actions/workflows/ci.yml)

> **Status: alpha, source-only.** `spedas-agent-kit` is pre-1.0
> (`Development Status :: 3 - Alpha` in `pyproject.toml`) and is **not published
> on PyPI**; install it from the official source checkout below.

The current design follows Jason's A+B direction:

- **A. SPEDAS data layer** — one unified entry point for source categories such as `cdaweb`, `pds`, and `spice`/geometry.
- **B. SPEDAS science workflow layer** — high-level planning tools that let Claude Code, Codex, OpenCode, LingTai, or another agent start from a science question before choosing source-specific operations.

Implementation backend packages should stay visible to maintainers, but they should not be the user's first mental model.

## Repository

- Official repo: <https://github.com/spedas/spedas_agent_kit>
- Python package name: `spedas-agent-kit`
- Python module / CLI module: `spedas_agent_kit`
- Canonical shared skills: `src/spedas_agent_kit/resources/skills/` (packaged with the kit; wrappers should stay thin)
- MCP skill resources: `spedas-skill://index` lists the packaged skills and `spedas-skill://skills/<skill-name>` returns the full `SKILL.md`; skills are exposed as resources rather than extra tools.
- Default MCP tool count: 13 (legacy CDAWeb/PDS compatibility tools are conditionally registered); advertised tools carry MCP `ToolAnnotations` plus `meta.surface` (`primary` or `compat`) so launchers can filter by surface and side-effect hints.

## Practical guide: run a SPEDAS Agent Kit study

Use this section as the README-level operating guide for researchers and agents.
The detailed capability map below is the reference; this guide is the shortest
safe path from a science question to reproducible artifacts.

### The default loop

1. **Restate the science question and constraints.** Capture the target, mission,
   instrument or observable, time range, and whether the request is heliophysics,
   planetary, geometry-only, or analysis oriented.
2. **Ask SPEDAS Agent Kit to choose the data-source family before fetching data.** Start
   with `spedas_overview()`, then call `search_spedas_data_sources(...)` or
   `plan_spedas_observation(...)`. Do not jump directly to a low-level archive
   tool just because a mission name matched a backend.
3. **Create a run directory.** For work that may fetch, transform, render, or be
   cited later, call `create_spedas_analysis_bundle(...)` first and keep data,
   plots, provenance, and notes under that bundle.
4. **Browse narrowly, then fetch narrowly.** Use the data-layer tools to browse
   source categories and parameters. Keep public-archive requests to small,
   reproducible intervals and explicit parameters.
5. **Use geometry as a follow-on step.** SPICE geometry, ephemeris, and frame
   transforms consume explicit files/artifacts. They should not hide large
   downloads or return bulk arrays inline.
6. **Return paths, provenance, and caveats.** A good answer names the source,
   dataset/product, variables, time window, output files, validation/caveats, and
   the next reproducible command. It does not paste CDF contents or giant arrays
   into chat.

### Choose the leading source family

| User request pattern | Lead with | Then use | Common caveat |
|---|---|---|---|
| Near-Earth magnetosphere, solar wind, MMS, THEMIS, Cluster, Geotail, Van Allen / RBSP, STEREO, PSP, Solar Orbiter, Ulysses, Voyager heliosphere | `source_type="cdaweb"` | CDAWeb browse/load/fetch tools; SPICE only if geometry is part of the question | Mission names may also appear in planetary archives; keep the science context in the plan. |
| Planetary mission fields/particles at a planet, e.g. Juno/Jupiter, Cassini/Saturn, MAVEN/Mars, New Horizons/Pluto | `source_type="pds"` | PDS discovery/fetch, plus SPICE geometry when trajectory or observation geometry matters | Generic words like "bow shock", "magnetosphere", "plasma", or "energetic particle" are not enough to choose CDAWeb if the target is planetary. |
| Ephemeris, distance, trajectory, frame transforms, observer-target geometry | `source_type="spice"` | Browse missions/frames with `browse_data_sources` / `load_data_source`; compute with `get_ephemeris`, `compute_distance`, `transform_coordinates` | SPICE is geometry, not measurement data. Pair it with CDAWeb/PDS when you also need fields or particles. |

### Minimal MCP call sequence

For an open-ended question, the safe skeleton is:

```text
spedas_overview()
search_spedas_data_sources(question="...", target="...", observables=[...])
plan_spedas_observation(science_goal="...", start="...", stop="...", target="...", observables=[...])
create_spedas_analysis_bundle(study_name="...", output_dir="...")
browse_data_sources(source_type="cdaweb|pds|spice")
load_data_source(source_type="...", source_id="...")
browse_data_parameters(source_type="...", dataset_id="...")
fetch_data_product(source_type="...", dataset_id="...", parameters=[...], start="...", stop="...", output_dir="...")
```

Add geometry only when the plan calls for it:

```text
get_ephemeris(...)
compute_distance(...)
transform_coordinates(...)
```

### Practical recipes

- **PSP perihelion solar wind**: route the science question first, let CDAWeb lead
  measurement discovery, then add SPICE only for spacecraft-Sun geometry. See
  `docs/examples/psp_perihelion_solar_wind.md`.
- **MMS magnetopause interval**: use `plan_spedas_observation` to keep mission,
  observable, and interval explicit; fetch selected CDAWeb variables into an
  analysis bundle before plotting or transforming. See
  `docs/examples/mms_magnetopause_workflow.md`.
- **Juno / planetary plasma interactions**: let PDS lead MAG/plasma archive
  discovery and use SPICE as a geometry companion. See
  `docs/examples/juno_pds_spice_workflow.md`.
- **Overview + geomagnetic-index context**: for IDL-SPEDAS-style summary plots
  or Dst/AE/Kp/SYM-H context, load the Claude skill
  `overview-geomagnetic-indices` and use `spedas_overview()["guided_recipes"]`
  to map the intent to CDAWeb/HAPI OMNI datasets or PySPEDAS Kyoto/NOAA loaders.

### Artifact and provenance contract

Every non-trivial run should leave a directory that another researcher can audit:

```text
<run>/
  requests/      original prompt, plan, or recipe
  data/          fetched or prepared measurement files
  plots/         PNG/SVG/PDF renderings
  provenance/    source IDs, parameters, cache notes, tool versions, hashes
  notes/         interpretation, caveats, and next steps
```

When reporting results, include at least:

- science goal and time range;
- selected source family (`cdaweb`, `pds`, or `spice`);
- dataset/product IDs and parameters/variables;
- output files and hashes when available;
- dependency or data-access caveats (`missing_dependency`, archive rate limits,
  cache-only validation, unavailable kernels, no matching station, etc.);
- the next command or MCP call needed to reproduce or extend the run.

### Agent safety checklist

- Prefer the unified data-layer and science-workflow tools over compatibility
  low-level tools for new work.
- Do not infer a source from one keyword. Use target + mission + observable + time
  context, especially for planetary versus near-Earth uses of generic words such
  as "magnetosphere", "bow shock", "radiation belt", "solar wind", and
  "energetic particle".
- Keep fetches narrow. Public archives can rate-limit or be cold; long intervals
  should be split deliberately and recorded in provenance.
- The base install exposes the bundled CDAWeb/PDS/SPICE surface only; the optional
  `analysis`, `hapi`, and `fdsn` extras (and their tools) were removed in the
  one-MCP cleanup.
- Validate generated artifacts before interpreting them. Check file existence,
  row/sample counts, time coverage, coordinate frame, and whether the tool returned
  warnings or caveats.

## Layered capability map

### 1. Data layer tools

Start here when the user asks for data, datasets, parameters, products, archives, or cache status.

- `browse_data_sources(source_type="all", query=None)` — browse SPEDAS data source categories, or drill into one category.
- `load_data_source(source_type, source_id, mode="compact", limit=None, offset=0, instrument=None, dataset_query=None, include_full_prompt=False)` — load source context. CDAWeb observatories default to a compact structured dataset page (dataset IDs, instruments, coverage, next calls); use `limit`/`offset` and filters for large catalogs, or `mode="full"` / `include_full_prompt=True` for the legacy full prompt.
- `browse_data_parameters(source_type, dataset_id, dataset_ids=None)` — browse parameters/metadata for CDAWeb or PDS datasets; for SPICE, returns geometry/frame context.
- `fetch_data_product(source_type, dataset_id, parameters, start=None, stop=None, output_dir=None, format="csv", limit=None)` — unified measurement/archive data fetch for CDAWeb/PDS. SPICE requests are routed to geometry tools instead. `limit` is currently a CDAWeb-oriented safety control; PDS fetches should be narrowed by time/parameters.
- `manage_data_cache(source_type="all", action="status", cache_dir=None, mission=None, ...)` — unified cache status/maintenance for the source categories. It passes source-specific cache options through one advertised tool: CDAWeb (`category`, `observatory`, `dataset_ids`, `older_than_days`, `dry_run`, `detail`), PDS (`category`, `mission`, `dataset_ids`, `older_than_days`, `dry_run`, `detail`, `force`), and SPICE (`mission`, `filenames`). Per-call `cache_dir` is reported as guidance only; backend cache roots are configured by the MCP server environment.

Supported `source_type` values:

| source_type | Use for | Main data-layer path |
|---|---|---|
| `cdaweb` | heliophysics observatory time-series, plasma/fields/particles, solar wind, CDF-like intervals | `browse_data_sources` → `load_data_source` → `browse_data_parameters` → `fetch_data_product` |
| `pds` | Planetary Plasma Interactions archives, planetary mission datasets, PDS metadata/products | `browse_data_sources` → `load_data_source` → `browse_data_parameters` → `fetch_data_product` |
| `spice` | geometry, ephemeris, trajectory, distance, coordinate frames/transforms | `browse_data_sources` → `load_data_source` → geometry tools |


Compact CDAWeb catalog discovery examples:

```python
# Default MMS page is compact (<12 KB) and includes exact next calls per dataset.
load_data_source(source_type="cdaweb", source_id="mms")

# Page through or narrow large observatories.
load_data_source(source_type="cdaweb", source_id="mms", limit=10, offset=10)
load_data_source(source_type="cdaweb", source_id="mms", instrument="fgm", dataset_query="srvy")

# Opt into the legacy human prompt only when needed.
load_data_source(source_type="cdaweb", source_id="mms", mode="full")
```

### 2. Science workflow tools

Start here for open-ended science requests.

- `spedas_overview()` — compact map of capability groups and recommended workflow.
- `search_spedas_data_sources(question, target=None, observables=None)` — recommend which data source categories should lead a request.
- `plan_spedas_observation(science_goal, start=None, stop=None, target=None, observables=None, data_sources=None)` — produce a source-specific plan before fetching data.
- `compare_cdaweb_pds_spice(science_goal="")` — explain source boundaries and choose the right source family.
- `create_spedas_analysis_bundle(study_name, output_dir, ...)` — create a request/provenance scaffold with `requests/`, `data/`, `plots/`, `provenance/`, and `notes/` folders.

### 3. Geometry tools

SPICE is exposed as a data source category, but geometry operations are clearer as explicit tools:

- Browse SPICE missions with `browse_data_sources(source_type="spice")`; the response also includes a `frame_catalog` with frame descriptions and aliases.
- Browse the same SPICE coordinate-frame catalog explicitly with `load_data_source(source_type="spice", source_id="frames")` or `browse_data_parameters(source_type="spice", dataset_id="frames")`; use `supported_frame_names` as `transform_coordinates` `from_frame`/`to_frame` values.
- `get_ephemeris(mission, target, start, stop, step="1h", frame="J2000", observer=None)`
- `compute_distance(mission, target, observer, start, stop, step="1h")`
- `transform_coordinates(mission, coordinates, from_frame, to_frame, epoch=None)`

SPICE kernel cache status/load/clean/check/purge actions are exposed through `manage_data_cache(source_type="spice", action=..., mission=..., filenames=...)`.

### 4. Compatibility low-level tools

These remain available for clients that already know the source-specific browse/fetch operations:

- CDAWeb: `browse_observatories`, `load_observatory`, `browse_parameters`, `fetch_data`
- PDS: `browse_pds_missions`, `load_pds_mission`, `browse_pds_parameters`, `fetch_pds_data`
- SPICE: the geometry tools above

The former dedicated cache tools (`manage_cdaweb_cache`, `manage_pds_cache`, `manage_spice_kernels`) are no longer advertised as MCP tools because their actions and kwargs are covered by `manage_data_cache`. See `docs/public_api_strategy.md` for the compatibility map and deprecation guidance.

## Recommended agent workflow

1. Call `spedas_overview()`.
2. For a natural-language science request, call `search_spedas_data_sources(...)` or `plan_spedas_observation(...)`.
3. Use the data layer:
   - `browse_data_sources(source_type="all")`
   - `browse_data_sources(source_type="cdaweb" | "pds" | "spice")`
   - `load_data_source(...)`
   - `browse_data_parameters(...)`
   - `fetch_data_product(...)` for CDAWeb/PDS measurement/archive products
4. Use geometry tools directly for SPICE ephemeris, distance, frame, and coordinate-transform work.
5. For any real analysis, call `create_spedas_analysis_bundle(...)` and write fetched files under the generated `data/` directory.
6. Return compact summaries and file paths. Do not paste large science arrays into chat.

## Quick start for local development

```bash
git clone https://github.com/spedas/spedas_agent_kit.git
cd spedas_agent_kit
uv sync --extra dev --extra mcp
uv run --extra mcp python -m spedas_agent_kit
```

Source-checkout install with pip works too (the package is not published on PyPI):

```bash
python -m pip install .
python -m pip install '.[mcp]'
```

Run tests and smoke checks:

```bash
uv run --extra dev --extra mcp python -m pytest -q
uv run --extra mcp python scripts/smoke_mcp_list_tools.py --json
```

The list-tools smoke starts the stdio MCP server with isolated temporary cache directories, performs MCP `initialize` + `list_tools`, and verifies the expected advertised tool names. It does not fetch CDAWeb/PDS data or download SPICE kernels.

The base install is sufficient for the full CDAWeb/PDS/SPICE tool surface; the
optional `analysis`, `hapi`, and `fdsn` extras (and their tools) were removed in
the one-MCP cleanup.

## MCP client configuration

Example stdio configuration:

```json
{
  "mcpServers": {
    "spedas": {
      "command": "uv",
      "args": ["run", "--extra", "mcp", "python", "-m", "spedas_agent_kit"],
      "cwd": "/path/to/spedas_agent_kit"
    }
  }
}
```

For plugin-style distribution, the canonical standalone wrappers now live in separate SPEDAS org repos:

- <https://github.com/spedas/spedas_claude> — Claude Code plugin wrapper.
- <https://github.com/spedas/spedas_codex> — Codex plugin wrapper.

The in-repo plugin fixtures were removed in the one-MCP cleanup; runtime-specific
packaging should evolve in the standalone repos while this repository owns the MCP
server itself. The current base `list_tools` count is 13, plus 8 legacy CDAWeb/PDS
compatibility tools when `SPEDAS_AGENT_KIT_COMPAT_TOOLS=1`.

## Maintainer-facing positioning

`spedas_agent_kit` should be thick at the SPEDAS data/workflow layer and thin at the backend implementation layer:

- Users see one SPEDAS Agent Kit and one `data` layer.
- Data source categories are scientific concepts: CDAWeb, PDS, SPICE/geometry.
- Backend packages remain maintainable internal implementation surfaces.
- Higher-level tools should encode reusable SPEDAS scientific method: source selection, planning, provenance, and artifact discipline.

See `docs/maintainer_note.md` and `docs/examples/agent_workflow.md` for the current framing.
- `docs/examples/juno_pds_spice_workflow.md` — Juno MAG/PDS discovery plus SPICE geometry planning, including current caveats.
