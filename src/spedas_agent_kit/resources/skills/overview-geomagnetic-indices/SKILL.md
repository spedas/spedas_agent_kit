---
name: overview-geomagnetic-indices
description: Resolve IDL-SPEDAS-style overview and geomagnetic-index intents to concrete SPEDAS Agent Kit data-source calls and dataset/parameter choices (THEMIS/MMS/RBSP overview context; Dst, AE/AL/AU, Kp, SYM-H).
---

# Overview recipes + geomagnetic indices

Use this skill when the user asks for a standard summary/overview plot (IDL-SPEDAS
style `thm_gen_overplot` / `mms_overview_plot`) or for common geomagnetic indices
(Dst, AE/AL/AU, Kp, SYM-H) to contextualize a near-Earth interval.

This is intentionally an **intent-to-dataset/parameter recipe**, not a new backend.
Plan first, then use the existing unified data layer and HAPI tools.

## First calls

1. `spedas_overview()` — confirms the current recipe catalog.
2. `plan_spedas_observation(science_goal=..., start=..., stop=...)` — infer target,
   time range, and recommended source types.
3. For mission data: use `browse_data_sources(source_type="cdaweb", query=<mission>)`,
   `load_data_source(source_type="cdaweb", source_id=<observatory>)`, then
   `browse_data_parameters(source_type="cdaweb", dataset_id=<dataset_id>)` before
   fetching.
4. For HAPI OMNI context: start with `browse_data_sources(source_type="hapi")` and
   follow its `next_tools` to `browse_hapi_catalog(server_url="https://cdaweb.gsfc.nasa.gov/hapi", query="OMNI_HRO")`,
   then `fetch_hapi_data(...)` with the dataset/parameters below. The direct HAPI
   tools are demoted out of the default `list_tools` surface (issue #87); reach
   them via that discovery route or set `SPEDAS_AGENT_KIT_DATASOURCE_TOOLS=1`. HAPI
   support requires the optional `spedas-agent-kit[hapi]` extra; if unavailable,
   fall back to CDAWeb discovery for the same OMNI dataset IDs.

## Geomagnetic-index intent table

| User intent | Preferred dataset / loader | Parameters / variables | Notes |
|---|---|---|---|
| Dst / ring-current context | PySPEDAS Kyoto `pyspedas.projects.kyoto.dst` (tplot `kyoto_dst`) | `kyoto_dst` | Verified local source: `pyspedas/projects/kyoto/load_dst.py`; Kyoto WDC data are acknowledged and redistribution-restricted. Use for field-model `dst` inputs when the agent/runtime can call PySPEDAS directly. |
| SYM-H / high-cadence storm index | CDAWeb HAPI `OMNI_HRO_1MIN` or `OMNI_HRO2_1MIN` | `SYM_H` (plus `SYM_D`, `ASY_H`, `ASY_D` if requested) | Source evidence: PySPEDAS `load_geomagnetic_indices.py` lists OMNI variables `SYM_D`, `SYM_H`, `ASY_D`, `ASY_H`; CDAWeb HAPI catalog advertises OMNI HRO datasets. |
| AE / AL / AU electrojet context | CDAWeb HAPI `OMNI_HRO_1MIN` / `OMNI_HRO2_1MIN`, or PySPEDAS Kyoto `load_ae` | `AE_INDEX`, `AL_INDEX`, `AU_INDEX`; Kyoto tplot variables `kyoto_ae`, `kyoto_al`, `kyoto_au` when available | Prefer OMNI HAPI for MCP artifact fetches; use Kyoto loader when exact Kyoto WDC AE products are needed. |
| Kp / T89 activity class | PySPEDAS NOAA/GFZ `noaa_load_kp` | `Kp` (also `ap`, `Kp_Sum`, etc.) | Source evidence: `pyspedas/projects/noaa/noaa_load_kp.py`; use `pyspedas.geopack.kp2iopt` to convert to T89 `iopt` if running PySPEDAS code. |
| Solar-wind dynamic pressure for Tsyganenko models | CDAWeb/HAPI `OMNI_HRO_1MIN` | `Pressure`, `BY_GSM`, `BZ_GSM` | Pair with Dst for T96/T01/TS04-style external-field parameters. |

## Standard overview starting points

These are canonical **first dataset choices**; always browse parameters before fetch
because CDAWeb variable names differ by product/version.

| Mission intent | Source | First dataset IDs to inspect | Typical observable groups |
|---|---|---|---|
| THEMIS magnetotail/substorm overview | CDAWeb | `THA_L2_FGM`, `THA_L2_ESA`, `THA_L2_SST`, `THA_OR_SSC` (replace `THA` with `THB`-`THE` as requested) | magnetic field, plasma moments, energetic particles, position |
| MMS magnetopause/reconnection overview | CDAWeb | `MMS1_FGM_SRVY_L2`, `MMS1_FPI_FAST_L2_DIS-MOMS`, `MMS1_EDP_SRVY_L2_DCE`, `MMS1_MEC_SRVY_L2_EPHT89D` (replace spacecraft/cadence as requested) | B-field, ion/electron moments, electric field, ephemeris |
| Van Allen Probes / RBSP radiation-belt overview | CDAWeb | query `RBSP` / `Van Allen Probes`; inspect `EMFISIS`, `MagEIS`, `REPT`, `HOPE`, `EFW`, and `RBSPICE` products | waves/fields, energetic particles, plasma, orbit/magnephem |


## Batch 005 THEMIS/RBSP guardrails

The Batch 005 paper-reproduction probes extended this overview recipe beyond
solar-wind context into narrow near-Earth proxy workflows. Keep these lessons in
mind before escalating to new tools or dedicated skills:

- **THEMIS substorm/dipolarization first route:** for Angelopoulos et al. 2008
  (`10.1126/science.1160495`) and Runov et al. 2009 (`10.1029/2009GL038980`),
  a cache-friendly first artifact can start with one THEMIS spacecraft FGM + ESA
  moments (for example THEMIS-A 2008-02-26 04:45–05:15 UTC or THEMIS-D
  2008-02-27 07:10–07:25 UTC). Label this as `proxy` unless paper markers,
  multi-probe timing, and ground/auroral context are reproduced.
- **THEMIS ESA availability:** ESA loaders may expose many mode variables, but
  several can be empty after clipping to a narrow interval. Record both the raw
  tplot inventory and the variables that have samples after clipping; do not make
  the researcher infer usable density/temperature/velocity panels from a long
  empty-mode list.
- **THEMIS SCM as overview adjunct:** if a THEMIS wave-context paper starts from
  this overview skill, route the waveform/polarization decision to
  `wave-polarization` after checking whether `scf`, `scp`, or `scw` actually has
  samples in the requested interval.
- **RBSP / Van Allen ECT first route:** for Baker et al. 2013
  (`10.1126/science.1233518`) and Reeves et al. 2013
  (`10.1126/science.1237743`), MagEIS + REPT are practical first-load products.
  Use suffixes/namespaces for overlapping variables such as `FEDU` and `L`
  (`FEDU_mageis`, `L_mageis`, `FEDU_rept`, `L_rept`) and preserve energy/L-shell
  metadata in provenance.
- **Optional RBSP context is a fallback, not an assumption:** EMFISIS may be
  transiently unavailable and HOPE moments can return no matching CDF for a smoke
  route. Record those as warnings while keeping the successful ECT artifact
  valid. Do not claim third-belt persistence, local acceleration, L*, or PSD
  diagnostics from a six-hour flux/L-shell overview alone.

## Fetch pattern

- Create an analysis bundle first when the task is more than a single index:
  `create_spedas_analysis_bundle(study_name=..., science_goal=..., output_dir=...)`.
- Fetch mission and index products into separate subdirectories under the same
  `output_dir` so provenance remains clear.
- For bulk data, never paste arrays; return only artifact paths, variable names,
  record counts, and provenance.
- If the user asks for plotting, use `render_tplot` when the `[analysis]` extra is
  available; otherwise produce fetch artifacts and a reproducible next-step note.

## Source evidence recorded for this skill

- Issue #98 requested a skill for IDL-SPEDAS overview recipes and geomagnetic
  indices without backend work.
- PySPEDAS local source has Kyoto Dst/AE loaders, NOAA/GFZ Kp loader, and a
  combined `load_geomagnetic_indices` helper listing Kyoto (`dst`, `ae`, `al`,
  `ao`, `au`, `ax`), NOAA/GFZ (`Kp`, `ap`, ...), and OMNI (`AE_INDEX`, `AL_INDEX`,
  `AU_INDEX`, `SYM_D`, `SYM_H`, `ASY_D`, `ASY_H`, `Pressure`) variables.
