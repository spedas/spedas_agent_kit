---
name: spedas-skills-index
description: Start here. Routes a heliophysics intent to the right spedas skill and the first tool to call, so an agent needs to know one thing up front instead of memorizing the runtime MCP tool list. Read this, then load one focused skill.
---

# SPEDAS skills index

The `spedas` MCP server advertises a small, focused tool surface, but you should not
need to memorize it. **The agent-facing surface is: a small unified vocabulary + these
skills.** Pick the skill matching the intent, load it, follow it. Call
`spedas_overview()` if unsure what exists; treat the full tool list as discoverable on
demand, not memorized.

## The unified vocabulary (what skills compose)
- **Plan:** `search_spedas_data_sources`, `plan_spedas_observation`, `compare_cdaweb_pds_spice`, `create_spedas_analysis_bundle`
- **Data (one set of verbs, switch by `source_type=cdaweb|pds|spice`):** `browse_data_sources`, `load_data_source`, `browse_data_parameters`, `fetch_data_product`, `manage_data_cache`
- **Geometry:** `get_ephemeris`, `compute_distance`, `transform_coordinates`

That is the whole advertised surface (13 base tools; 8 legacy CDAWeb/PDS compat
tools exist under `SPEDAS_AGENT_KIT_COMPAT_TOOLS=1` for maintenance only — skills do
not use them). There are **no MCP analysis/plotting tools** (spectra, MVA, particle
moments, renderers were removed in the one-MCP cleanup): for that science, fetch data
with the unified tools and run PySPEDAS/matplotlib locally.

## Intent → skill → first step

| If the user wants… | Use skill | First call |
|---|---|---|
| Times two spacecraft/bodies are close | `spice-conjunction-finder` | `spedas_overview` then `manage_data_cache(source_type="spice", action="status")` |
| Clean/condition a messy time-series before analysis (despike, deflag, smooth, gap-fill) | `timeseries-cleaning` | `create_spedas_analysis_bundle` |
| Just fetch & plot a time series | `spedas-workflow` | `plan_spedas_observation` |
| Standard mission overview plot or Dst/AE/Kp/SYM-H context | `overview-geomagnetic-indices` | `spedas_overview` |
| To know what data/sources exist at all | `spedas-workflow` | `spedas_overview` |

Analysis intents (turbulence spectra, wave polarization, LMN/boundary frames,
hodograms, particle pitch-angle/velocity-space, multi-spacecraft gradients) previously
routed to dedicated skills. Those skills were removed with the analysis tools: fetch
the needed series with the unified data tools, then run the analysis in PySPEDAS locally
— see `timeseries-cleaning` for conditioning the fetched series first.

## Load order
1. (this index) → 2. one focused skill → 3. that skill's tool chain. Don't pre-read every skill.

## For coding agents (maintenance)
- To navigate or change the spedas_agent_kit codebase, use the **`spedas-agent-kit-anatomy`** skill: descend the `ANATOMY.md` tree from the repo root, read cited `file:line` code, and update anatomy in the same commit as code.

## Universal rules (every skill obeys)
- **Artifact-first:** bundle the run, pass `output_dir` everywhere, return paths + compact stats, never pasted arrays.
- **Plan before fetch:** know source_type, dataset_id, parameters, time range, output_dir first.
- **New capability is a skill or a `source_type`, not a new tool.**
