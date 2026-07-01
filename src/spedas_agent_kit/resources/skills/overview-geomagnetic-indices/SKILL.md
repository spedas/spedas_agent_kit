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

## MCP/default-surface boundary

Treat `pyspedas...` loader names in this skill as **external runtime routes**, not
Agent Kit MCP tool names (`external_runtime_route.not_an_mcp_tool: true`). MCP-only
clients should call `spedas_overview()` and follow each
`guided_recipes.geomagnetic_indices[*].mcp_first_route` before trying local Python.
Those MCP-first routes use `browse_data_sources`, `load_data_source`,
`browse_data_parameters`, and `fetch_data_product` against CDAWeb candidates:

- Dst: `OMNI2_H0_MRG1HR`, browse `Dst`.
- AE/AL/AU: `OMNI_HRO_1MIN`, `OMNI_HRO2_1MIN`, or `OMNI2_H0_MRG1HR`, browse
  `AE_INDEX`, `AL_INDEX`, and `AU_INDEX`.
- Kp/ap: `OMNI2_H0_MRG1HR`, browse `Kp` and `ap`.
- SYM-H/SYM-D/ASY-H/ASY-D: `OMNI_HRO_1MIN` or `OMNI_HRO2_1MIN`, browse the named
  parameters.

Use direct Kyoto/NOAA/GOES PySPEDAS loaders only when the surrounding runtime can
import PySPEDAS and run local scripts; otherwise report the external-runtime
requirement instead of inventing MCP tool names.

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
| Dst / ring-current context | MCP-first: CDAWeb `OMNI2_H0_MRG1HR` (`Dst`); external runtime: PySPEDAS Kyoto `pyspedas.projects.kyoto.dst` (tplot `kyoto_dst`) | `Dst` or `kyoto_dst` | Verified local source: `pyspedas/projects/kyoto/load_dst.py`; Kyoto WDC data are acknowledged and redistribution-restricted. The Kyoto loader is not an MCP tool; use it only when the agent/runtime can call PySPEDAS directly. |
| SYM-H / high-cadence storm index | CDAWeb HAPI `OMNI_HRO_1MIN` or `OMNI_HRO2_1MIN` | `SYM_H` (plus `SYM_D`, `ASY_H`, `ASY_D` if requested) | Source evidence: PySPEDAS `load_geomagnetic_indices.py` lists OMNI variables `SYM_D`, `SYM_H`, `ASY_D`, `ASY_H`; CDAWeb HAPI catalog advertises OMNI HRO datasets. |
| AE / AL / AU electrojet context | MCP-first: CDAWeb/unified data layer `OMNI_HRO_1MIN` / `OMNI_HRO2_1MIN` / `OMNI2_H0_MRG1HR`; external runtime: PySPEDAS Kyoto `load_ae` | `AE_INDEX`, `AL_INDEX`, `AU_INDEX`; Kyoto tplot variables `kyoto_ae`, `kyoto_al`, `kyoto_au` when available | Prefer OMNI/CDAWeb for MCP artifact fetches. The Kyoto loader is not an MCP tool; use it only when exact Kyoto WDC AE products are needed and local PySPEDAS is available. |
| Kp / T89 activity class | MCP-first: CDAWeb `OMNI2_H0_MRG1HR` (`Kp`, `ap`); external runtime: PySPEDAS NOAA/GFZ `noaa_load_kp` | `Kp`, `ap`; external loader also exposes `Kp_Sum`, etc. | Source evidence: `pyspedas/projects/noaa/noaa_load_kp.py`; `noaa_load_kp` and `pyspedas.geopack.kp2iopt` are not MCP tools, so use them only in local PySPEDAS code. |
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

## GOES XRS operational context

Use GOES XRS only as compact flare / operational context beside storm-index
overviews unless the paper's calibration and event-selection recipe is explicit.
The Batch 009 September 2017 route scout loaded XRS through PySPEDAS directly:

```python
pyspedas.goes.xrs(probe="15", trange=["2017-09-06", "2017-09-08"])
# example tplot variable: g15_xrs_B_AVG
```

Guidance:

- Choose the GOES spacecraft/probe from the event year and record that choice in
  provenance. GOES-15 is appropriate for the 2017-09 scout; older events may
  require GOES-13/14/15 overlap checks, while GOES-16/17/18 use a newer product
  family.
- Treat `g*_xrs_*` variables as X-ray-flux context. They are not a GIC driver,
  not a calibrated flare-class/event-selection product, and not a ground-network
  reproduction without an explicit paper recipe and citation.
- Do not promise an Agent Kit `load_data_source` route for XRS from the packaged
  CDAWeb catalog. GOES appears as a CDAWeb observatory, but Batch 009 reached XRS
  through `pyspedas.goes.xrs`; say that plainly in reports.
- Treat `pyspedas.goes.xrs` as `external_runtime_route.not_an_mcp_tool: true`.
  MCP-only clients should keep GOES XRS as an external-runtime caveat or route
  scout, not attempt to call `goes.xrs` as an Agent Kit MCP tool.

## Batch 009 storm/operational-context guardrails

Batch 009 used OMNI HRO 1-min, Kyoto Dst, OMNI `SYM_H`/AE/AL/AU, and one GOES-15
XRS route scout for storm-linked papers. Keep these as `proxy` / `route_scout`
results unless the paper's exact products, cadence, station/spacecraft selection,
and analysis recipe are reproduced.

- St. Patrick's Day 2015 papers can share one verified OMNI/Kyoto storm-context
  bundle, but keep their DOIs and science targets distinct. OMNI/Kyoto overlays
  are not a TEC, GNSS, or ionosphere data assimilation reproduction.
- September 2017 GOES XRS context must remain `route_scout`; label the ESSOAr DOI
  as `doi_verified_crossref_preprint` / preprint, and do not claim a GIC
  reproduction or calibrated flare attribution from `g15_xrs_B_AVG` alone.
- Halloween 2003 ENA-emission and Bastille Day 2000 Brazilian-anomaly
  precipitation papers revisit intervals already seeded elsewhere. Do not add
  duplicate event rows for those intervals; use them as overclaim reminders.
  OMNI/Kyoto context cannot reproduce ENA imaging, particle precipitation, or
  ground-detector response.
- Multiple papers may target the same storm interval. Share a verified
  OMNI/Kyoto/GOES bundle in provenance, but keep the paper target, DOI,
  quality label, and non-reproduced observables explicit rather than inventing a
  resolver tool.

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
