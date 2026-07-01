---
name: themis-workflows
description: Plan THEMIS mission route-scout, substorm/dipolarization, magnetotail, state/orbit, particle, and wave-context workflows as Agent Kit skill/resource recipes without expanding the default MCP tool surface.
---

# THEMIS workflows

Use this skill when the user asks for a THEMIS mission workflow, a THEMIS
substorm/dipolarization route scout, a THEMIS magnetotail boundary/current-sheet
context bundle, or a THEMIS FGM/state/particle/wave preflight. This is a router
skill: it connects THEMIS mission vocabulary to existing Agent Kit analysis skills
and external PySPEDAS loaders without creating one MCP tool per loader.

Compose it with:

- `overview-geomagnetic-indices` for quick THEMIS FGM/ESA/SST/SSC overview routing
  and OMNI/Kyoto/NOAA storm-index context.
- `spedas-workflow` and `multi-spacecraft-gradients` for magnetotail boundary,
  current-sheet, and multi-probe route-scouts.
- `boundary-minimum-variance`, `model-lmn-boundary`, `apply-rotation-matrix`, and
  `hodogram` for LMN/MVA handoffs after a real boundary interval exists.
- `wave-polarization` for THEMIS SCM `scf` / `scp` / `scw` valid-window checks.
- `neutral-sheet-distance` and `field-line-footpoint` when state/orbit products
  are needed for tail geometry or ionospheric mapping.
- `pyspedas-load-planning` and `tplot-data-lifecycle` for loader/cache/tplot hygiene.

## MCP/default-surface boundary

This skill adds **no MCP tool**. Keep the default Agent Kit `list_tools` surface
compact. The names below are external PySPEDAS runtime routes, not Agent Kit MCP
names:

```yaml
external_runtime_route:
  not_an_mcp_tool: true
  examples:
    - pyspedas.projects.themis.load
    - pyspedas.projects.themis.fgm
    - pyspedas.projects.themis.fit
    - pyspedas.projects.themis.state
    - pyspedas.projects.themis.ssc
    - pyspedas.projects.themis.ssc_pre
    - pyspedas.projects.themis.esa
    - pyspedas.projects.themis.esd
    - pyspedas.projects.themis.sst
    - pyspedas.projects.themis.mom
    - pyspedas.projects.themis.gmom
    - pyspedas.projects.themis.scm
    - pyspedas.projects.themis.efi
    - pyspedas.projects.themis.gmag
    - pyspedas.projects.themis.ask
```

Do not invent MCP tools such as `themis_fgm`, `themis_state`, `load_themis`,
`themis_esa`, `themis_sst`, or `themis_scm`. MCP-only clients should use the
resource/plan/fetch verbs:

1. `create_spedas_analysis_bundle(...)` before any fetch.
2. `spedas_overview()` and `spedas-skill://skills/overview-geomagnetic-indices`
   for initial THEMIS overview routing.
3. `search_spedas_data_sources(...)` / `browse_data_sources(source_type="cdaweb", query="THEMIS")`.
4. `load_data_source(...)`, `browse_data_parameters(...)`, then
   `fetch_data_product(...)` for a bounded dataset/parameter/time range.
5. If exact PySPEDAS THEMIS loader behavior is required, record it as an external
   runtime requirement with `external_runtime_route.not_an_mcp_tool: true`.

## Workflow cards

### 1. Single-probe substorm / dipolarization route scout

Use this for a fast THEMIS context bundle around a candidate onset, flow burst, or
near-Earth tail dipolarization. Treat it as a **route scout**, not a paper
reproduction, until the exact products and event timing are verified.

- Start with one probe (`tha`, `thd`, etc.) and a narrow interval (tens of minutes).
- MCP-first dataset families to browse first:
  - `THA_L2_FGM` for magnetic field; replace `THA` with `THB`-`THE` as needed.
  - `THA_L2_ESA` for plasma moments where available.
  - `THA_L2_SST` for energetic-particle context when requested.
  - `THA_OR_SSC` for spacecraft position/orbit context.
- Pair with `omni-kyoto-noaa-smoke-workflows` if storm/solar-wind context is part
  of the question.
- Return artifact paths, variable/parameter names, sample counts, actual clipped
  time span, and caveats. Do not paste arrays into chat.

A cache-friendly seed for route-shape validation is THEMIS-A around
`2008-02-26T04:45:00Z/2008-02-26T05:15:00Z`; verify product availability and label
it `route_scout` unless it is tied to the user's exact event/paper.

### 2. Multi-probe magnetotail boundary / current-sheet scout

Use this when the user asks for current sheet, neutral sheet, magnetotail boundary,
flow-braking, or multi-spacecraft timing/curlometer claims.

- First build a bundle with FGM and state/SSC position candidates for the requested
  THEMIS probes.
- Before any curlometer, linear-gradient, timing-normal, shock-normal, KH-vortex,
  or reconnection-rate claim, require:
  - four magnetic-field vector streams;
  - four spacecraft position streams;
  - common coordinate frame and cadence;
  - documented interpolation/quality gates;
  - provenance for missing products and rejected intervals.
- Route validated boundary intervals to `boundary-minimum-variance`,
  `model-lmn-boundary`, `apply-rotation-matrix`, and `hodogram` rather than
  reimplementing LMN/MVA logic here.
- If only one or two useful streams are available, label the artifact
  `single_spacecraft_route_scout` or `not_gradient_ready`.

### 3. THEMIS SCM / wave context

Use this when the user asks for THEMIS whistler/EMIC/chorus/wave context.

- Browse/load THEMIS SCM candidates and pair with FGM background field.
- THEMIS SCM products can expose `scf`, `scp`, and `scw` cadence families; a tplot
  variable name alone does not prove non-empty samples after clipping.
- Count samples in the requested interval before recommending a cadence family.
- Record rejected empty waveform variables in provenance.
- Route polarization/spectral analysis to `wave-polarization`; local PySPEDAS
  `twavpol` execution is an external runtime route, not an MCP tool.

Known route-scout evidence from existing Agent Kit guardrails: a THEMIS-C whistler
proxy around `2007-03-23T12:00:00Z/2007-03-23T12:10:00Z` rerouted from empty
`thc_scw_gse` to non-empty `thc_scf_gse`. Treat it as a proxy seed, not a general
availability guarantee.

### 4. State/orbit, neutral-sheet distance, and footpoints

Use this when geometry matters more than particle/field content.

- Prefer MCP/CDAWeb position products such as `THA_OR_SSC` when available.
- External PySPEDAS state routes include `state`, `ssc`, and `ssc_pre`; all are
  external runtime routes, not MCP tools.
- Use `neutral-sheet-distance` for signed spacecraft-to-neutral-sheet distance and
  validity caveats (near-tail / nightside / model domain).
- Use `field-line-footpoint` for Tsyganenko-style footpoint context; report model,
  input coordinates, and reliability caveats.

### 5. Ground/ASI context for substorm overview

Use this when the user needs ground magnetometer or auroral-imager context around
a THEMIS event. Treat it as context for human-reviewed onset analysis, not as an
automatic substorm detector.

- External routes include `pyspedas.projects.themis.gmag` for THEMIS GMAG station
  or network products and `pyspedas.projects.themis.ask` for all-sky imager /
  keogram context.
- Ground-network groups seen in local examples include `thm`, `epo`, `tgo`, `dtu`,
  `maccs`, `usgs`, `ua`, and `atha`; station examples include `bmls`, `ccnv`, and
  `fykn`.
- Use GMAG/ASI panels as overview/context artifacts and record station/group,
  site, cadence, zrange/display choices, and whether the artifact is only a route
  scout.

### 6. Particle context without overclaiming slice support

Use THEMIS ESA/SST/moments for context and quality checks, not as a shortcut to
unsupported particle products.

- External routes include `esa`, `esd(datatype="peif")`, `sst`, `mom`, and `gmom`.
- Use `notplot=True` for compact metadata inspection before deciding whether to
  create tplot variables.
- Use `downloadonly=True` for source-file availability checks without loading state.
- Existing Python velocity-slice support is not a blanket THEMIS ESA promise; do
  not route THEMIS ESA to particle-slice workflows unless the exact runtime support
  is verified.

## External PySPEDAS loader option evidence

Common THEMIS loader options found in PySPEDAS wrappers include:

- top-level `load(..., instrument="fgm", probe="c", level="l2", datatype=None,
  prefix="", suffix="", get_support_data=False, varformat=None,
  exclude_format=None, varnames=[], downloadonly=False, notplot=False,
  no_update=False, time_clip=False, force_download=False)`;
- `fgm(..., coord=None, downloadonly=False, notplot=False, no_update=False,
  time_clip=False)`;
- `state(..., level="l1", exclude_format=None, keep_spin=False, downloadonly=False,
  notplot=False, no_update=False, time_clip=False)`;
- `ssc(..., time_clip=True)` and `ssc_pre(..., time_clip=True)`;
- `esa`, `esd(datatype="peif")`, `sst`, `mom`, `gmom`, `scm`, and `efi`, each with
  the same support/varformat/varnames/download/cache flags.

Use run-scoped `suffix` (and top-level `prefix` where the route supports it) to
avoid tplot name collisions. Always record whether the run used `no_update=True`,
`downloadonly=True`, `notplot=True`, live archive fetch, or cache-only mode.

## IDL/SPEDAS vocabulary bridge

Useful IDL-to-Agent-Kit vocabulary for user requests:

- `thm_load_fgm` -> THEMIS FGM route (`pyspedas.projects.themis.fgm`) or CDAWeb
  `TH?_L2_FGM` browse/fetch; IDL variables often include `fgs`, `fgl`, `fgh`,
  `fge`, and `_btotal` in `dsl/gse/gsm/ssl` frames.
- `thm_load_state` / `thm_load_ssc` -> state/orbit products (`state`, `ssc`,
  `ssc_pre`, `TH?_OR_SSC`), with GEI/GSE/GSM coordinate and Re conversion caveats.
- `thm_load_esa`, `thm_load_sst`, `thm_load_mom`, `thm_part_products` -> context
  particle panels and derived spectra/moments; require explicit calibration,
  spacecraft-potential, FAC, and sun-bin/decontamination choices before claiming
  science products.
- `thm_fac_matrix_make`, `minvar_matrix_make`, `thm_cotrans_lmn`, and
  `tvector_rotate` are analysis handoffs: record interval/window, basis method,
  eigenvalue/quality diagnostics, and solar-wind/model choices before using their
  outputs in conclusions.

## Minimal route-scout template

```yaml
study_name: themis_route_scout
quality_label: route_scout
probe: tha
trange: ["2008-02-26T04:45:00Z", "2008-02-26T05:15:00Z"]
agent_kit_route:
  source_type: cdaweb
  candidate_datasets: [THA_L2_FGM, THA_L2_ESA, THA_L2_SST, THA_OR_SSC]
  browse_parameters_first: true
  next_skills:
    - overview-geomagnetic-indices
    - tplot-data-lifecycle
    - neutral-sheet-distance
external_runtime_route:
  not_an_mcp_tool: true
  pyspedas_loaders:
    - pyspedas.projects.themis.fgm
    - pyspedas.projects.themis.fit
    - pyspedas.projects.themis.state
    - pyspedas.projects.themis.gmag
    - pyspedas.projects.themis.esa
    - pyspedas.projects.themis.sst
provenance_required:
  - probe
  - dataset_id_or_loader
  - variable_or_parameter_subset
  - requested_trange
  - actual_clipped_range
  - cache_mode
  - coordinate_frame
  - station_or_ground_site_when_used
  - artifact_paths
  - quality_label
  - caveats
```

## Provenance and reporting checklist

For every THEMIS workflow artifact, include:

- probe(s), dataset IDs or exact external loader names, and loader options;
- requested and actual clipped intervals;
- coordinate frame, cadence, units, and support-data choices;
- sample counts for every panel used in a conclusion;
- cache/data-access mode and public-archive caveats;
- labels such as `route_scout`, `context_smoke`, `single_spacecraft_route_scout`,
  `not_gradient_ready`, `proxy_seed`, or `paper_exact` only when justified;
- links to downstream skills used for LMN/MVA, wave polarization, neutral-sheet,
  footpoint, or multi-spacecraft analysis.

Do not upgrade a route scout to a scientific conclusion merely because a plot or
variable name exists. Require actual non-empty samples, correct products, and the
analysis-specific preconditions owned by the downstream skill.
