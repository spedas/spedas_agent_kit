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
| Reproduce a published paper, figure, event, or DOI with artifact/provenance output | `paper-reproduction` | `spedas_overview` then `search_spedas_data_sources` / `plan_spedas_observation` |
| PSP/Solar Orbiter heliospheric load-plan bridge, FIELDS/SWEAP/SolO MAG/SWA/RPW/EPD product selection, radial-alignment route scout, or inner-heliosphere in-situ comparison | `psp-solo-heliophysics-workflows` | `spedas_overview` then `search_spedas_data_sources` / `plan_spedas_observation`; load `spice-conjunction-finder` when geometry matters |
| Parker Solar Probe / Solar Orbiter switchbacks, Alfvénic impulses, or radial-alignment in-situ comparisons | `psp-solar-wind-switchbacks` | `spedas_overview` then `search_spedas_data_sources` / `plan_spedas_observation`; load `spice-conjunction-finder` when geometry matters |
| Solar-wind storm, ICME, magnetic cloud, stream interaction, SEP reduced proxy, or multi-spacecraft in-situ overview (OMNI/Wind/ACE/STEREO/PSP/SolO) | `solar-wind-icme-storm` | `spedas_overview` then `search_spedas_data_sources` / `plan_spedas_observation`; compose scalar OMNI vectors, start STEREO multi-day runs at 1-minute cadence, and keep SEP onset/fluence claims gated on channel metadata |
| Solar-wind intermittency, PVI, vector increments, thresholded event tables, or proxy-labelled energy-transfer / third-order-law workflow | `solar-wind-turbulence-intermittency` | `create_spedas_analysis_bundle` |

| Times two spacecraft/bodies are close | `spice-conjunction-finder` | `spedas_overview` then `manage_data_cache(source_type="spice", action="status")` |
| Clean/condition a messy time-series before analysis (despike, deflag, smooth, gap-fill) | `timeseries-cleaning` | `create_spedas_analysis_bundle` |

| Just fetch & plot a time series | `spedas-workflow` | `plan_spedas_observation` |
| ERG/Arase radiation-belt, wave-particle, PWE/MGF/particle, or ground-conjugate ISEE/OMTI/MAGDAS route scout | `erg-arase-radiation-belt-waves` | `spedas_overview`; use this skill to choose `pyspedas.erg.*` / CDAWeb satellite routes, and keep ground routes labeled PySPEDAS-only |
| Standard mission overview plot, geomagnetic-index context, GOES XRS operational storm context, THEMIS FGM/ESA substorm/dipolarization proxy, or RBSP MagEIS/REPT radiation-belt overview | `overview-geomagnetic-indices` | `spedas_overview` |
| THEMIS mission route scout, substorm/dipolarization context, magnetotail boundary preflight, or FGM/state/ESA/SST/SCM workflow planning | `themis-workflows` | `create_spedas_analysis_bundle` then `spedas_overview` / `search_spedas_data_sources` |
| MMS FGM/MEC/EDP/SCM/FPI/HPCA quicklook, reconnection route scout, product-selection workflow, particle/PAD preflight, or curlometer/linear-gradient readiness check | `mms-basic-workflows` | `create_spedas_analysis_bundle` then `spedas_overview` / `search_spedas_data_sources` |
| Lightweight OMNI/Kyoto/NOAA space-weather smoke workflow, storm-context bundle, or cache-only geomagnetic-index validation | `omni-kyoto-noaa-smoke-workflows` | `create_spedas_analysis_bundle` then `spedas_overview` / `overview-geomagnetic-indices` |
| To know what data/sources exist at all | `spedas-workflow` | `spedas_overview` |
| Plan a PySPEDAS mission/product/time data load with `time_clip=True`, cache, `downloadonly`, `notplot`, and provenance hygiene | `pyspedas-load-planning` | `create_spedas_analysis_bundle` |
| Manage tplot variables from load through inspect, derive, plot/export, and cleanup without raw-array chat output | `tplot-data-lifecycle` | `create_spedas_analysis_bundle` |
| Choose PyTplot/SPEDAS plotting options for line plots, spectrograms, legends, limits, event bars, annotations, and saved figure artifacts | `pytplot-plotting-options` | `create_spedas_analysis_bundle` |
| Translate IDL SPEDAS / PySPEDAS / plugin vocabulary into Agent Kit skills/resources while marking external routines as `not_an_mcp_tool` | `spedas-heritage-vocabulary` | `spedas_overview` |

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
- **Run provenance:** after `create_spedas_analysis_bundle(...)`, update the seeded `provenance/run.json` (`paths.run_provenance`) with compact `tool_calls`, `artifacts`, and `caveats`; read `spedas-preset://schemas/analysis_bundle_run` for the record shape.
- **Plan before fetch:** know source_type, dataset_id, parameters, time range, output_dir first.
- **New capability is a skill or a `source_type`, not a new tool.**
