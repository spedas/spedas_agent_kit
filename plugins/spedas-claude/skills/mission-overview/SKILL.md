---
name: mission-overview
description: Produce the standard multi-panel "overview / summary" plot for a mission and date (the #1 SPEDAS entry workflow) — resolve intent to the canonical instrument datasets, fetch the key quantities (B, plasma, particles, position), and render a stacked overview. Composes existing tools; adds none. Resolves the intent->dataset_id step that the MCP otherwise forces you to do by hand.
---

# Mission overview / summary plot

The single most common SPEDAS entry point (`thm_gen_overplot`, `mms_overview_plot`):
"show me the standard summary for mission X on date Y." The data is all reachable
through the unified layer today — the value this skill adds is the **intent →
dataset_id → canonical variables** resolution, which the raw tools otherwise force
you to do by hand.

## When to use
- "Give me an overview / summary plot for THEMIS-A (or MMS1, Wind, ACE) on <date>."
- "What were the field + plasma conditions for <mission> during <interval>?"
- A first look before a focused analysis (turbulence, boundary, etc.).

## Tool chain (all existing)
`load_data_source` → `browse_data_parameters` → `fetch_data_product` (one per quantity)
→ `render_tplot`, in a `create_spedas_analysis_bundle`. Optionally `get_ephemeris` for position.

## Verified-resolvable missions (this MCP's CDAWeb catalog)
`load_data_source(source_type="cdaweb", source_id=...)` resolves for: **themis, mms, wind, ace** (and PSP, others — confirm with `browse_data_sources(source_type="cdaweb", query=...)`). Always `load_data_source` first to enumerate the actual dataset IDs + coverage, then `browse_data_parameters` to get exact variable names — do **not** hardcode dataset IDs that may not exist in a given deployment.

## Procedure

1. **Bundle.** `create_spedas_analysis_bundle(study_name, output_dir, science_goal, target, start, stop)`.

2. **Resolve the mission → datasets.** `load_data_source(source_type="cdaweb", source_id="<mission>")` returns the enumerated `datasets` (id, instrument, coverage). This is the intent→dataset_id step. Pick the canonical overview set by instrument keyword:
   - **Magnetic field:** the FGM/MAG dataset (e.g. THEMIS `*_FGM_*`, MMS `*_FGM_*`/`MEC` for position).
   - **Plasma moments:** ion/electron density, velocity, temperature (THEMIS ESA/MOM, MMS FPI-DIS/DES).
   - **Particles (optional):** energy spectra (ESA/SST, FPI).
   - **Position (optional):** the mission ephemeris dataset, or `get_ephemeris`.
   Confirm each variable name with `browse_data_parameters(source_type="cdaweb", dataset_id=...)` before fetching — instrument variable names vary by mission/level.

3. **Check coverage** against your date (`load_data_source` reports per-dataset coverage; reject if the date is outside it) before fetching.

4. **Fetch each quantity** with `fetch_data_product(... output_dir=<bundle>/data)`. Keep to the standard overview set (B, |B|, density, velocity, temperature, a particle spectrogram if available) — an overview is a fixed, legible panel stack, not everything.

5. **Render the stack.** `render_tplot(input_files=[...], output_file=<bundle>/plots/overview.png, panel_types=[...])` in the canonical order: |B| / B-components / density / velocity / temperature / (particle spectrogram). Read it back to sanity-check.

6. **Record** the mission, date, datasets used, and a one-line conditions summary in `notes/`.

## Guardrails
- Artifact-first: dataset IDs + the PNG path + a compact conditions summary, not pasted arrays.
- **Resolve, don't hardcode:** always `load_data_source` + `browse_data_parameters` to get real IDs/variables for the deployment; instrument naming differs across missions and levels.
- Keep the panel set canonical and small — an overview is for orientation.
- Needs the date within each dataset's coverage; check before fetching.

## Known gap (geomagnetic indices)
Geomagnetic **indices (Dst / AE / Kp / SYM-H) and OMNI are NOT currently discoverable** through this MCP's CDAWeb catalog (`browse_data_sources(query="omni"|"dst")` returns nothing; OMNI source_ids do not load). A full IDL-style overview often overlays these. Until the data layer exposes them (tracked separately), this skill omits indices rather than reference datasets that won't resolve. Do not fabricate OMNI/index dataset IDs in an overview.

## Example
THEMIS-A on a chosen day: `load_data_source(cdaweb, themis)` → pick `THx_L2_FGM` + ESA moments → fetch → 5-panel overview. (Mirrors the THEMIS magnetometer overview produced earlier in this project, generalized to the resolve-then-fetch recipe.)
