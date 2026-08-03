# SKILLS_CLEANUP.md — removal of analysis/HAPI/FDSN skill references

Branch: `clean/merge-three-mcps` · repo: /Users/huangzesen/Downloads/spedas_mcp
Scope: `src/spedas_agent_kit/resources/skills/` (server.py, tests, pyproject, CI, smoke script untouched).

## Summary

20 skill files referenced tools removed in the main PR (13-tool CDAWeb+PDS+SPICE surface).
Outcome: **16 skill directories deleted** (git rm -r), **4 files edited** to the kept surface,
**0 references** to the 16 removed tool names or the `[analysis]`/`[hapi]`/`[fdsn]` extras remain
under `resources/skills/`. The repo-root README.md and ANATOMY.md files were checked and need no
changes (they already reference only the kept surface and surviving skills).

## Deleted skills (16, via `git rm -r`) — core workflows built on removed analysis tools

All 16 are analysis-workflow skills whose procedure steps call removed tools
(compute_particle_spectra, build/load_particle_distribution_artifact, generate_fac_matrix,
analyze_minvar_coordinates, transform_timeseries_coordinates, dynamic_power_spectrum,
wavelet_transform, render_tplot, …) and/or require the removed `[analysis]` extra. No kept-tool
workflow can express them, so they were deleted rather than dead-ended:

| skill | removed-tool core (examples from file) |
|---|---|
| pitch-angle-distribution | compute_particle_spectra, build/load_particle_distribution_artifact, render_tplot |
| particle-velocity-slice | compute_particle_spectra, build/load_particle_distribution_artifact, render_tplot, `[analysis]` extra |
| hodogram | analyze_minvar_coordinates, transform_timeseries_coordinates, render_tplot (scatter panels) |
| field-line-footpoint | calculate_lshell, evaluate_magnetic_field, render_tplot |
| magnetopause-lmn-analysis | analyze_minvar_coordinates, transform_timeseries_coordinates, render_tplot |
| model-lmn-boundary | generate_fac_matrix / model matrix steps, `[analysis]`/cotrans extras |
| boundary-minimum-variance | analyze_minvar_coordinates, render_tplot |
| neutral-sheet-distance | evaluate_magnetic_field, calculate_lshell, render_tplot |
| dual-spacecraft-timing | analyze_minvar_coordinates, render_tplot |
| multi-spacecraft-gradients | analyze_minvar_coordinates, render_tplot, `[analysis]` extra |
| coordinate-frame-tour | transform_timeseries_coordinates, generate_fac_matrix, render_tplot |
| power-spectral-density | render_tplot (line panels), dynamic_power_spectrum, wavelet_transform |
| spectral-cross-coherence | dynamic_power_spectrum / wavelet transform core, render_tplot |
| solar-wind-turbulence-spectrum | dynamic_power_spectrum, wavelet_transform, render_tplot |
| wave-polarization | analyze_minvar_coordinates, render_tplot, `[analysis]` extra |
| apply-rotation-matrix | generate_fac_matrix, analyze_minvar_coordinates, render_tplot, `[analysis]` extra |

## Edited skills (4)

### spice-conjunction-finder (kept — SPICE geometry surface)
- Description: dropped “(plotting requires the [analysis] extra)”; now “optionally produce a local separation-vs-time plot artifact”.
- Tool chain: optional `render_tplot` (requires `spedas-agent-kit[analysis]`) → optional local matplotlib script step.
- Step 8 “Optional render” (render_tplot call) → local matplotlib script writing `<bundle>/plots/separation.png`; otherwise report CSV path.
- Guardrail about render_tplot/[analysis] → “plotting is a local-script step; the geometry/CSV part is the MCP toolchain.”
- SPICE core (spedas_overview → manage_data_cache(spice) → get_ephemeris coarse→fine → compute_distance sanity check → local separation CSV → create_spedas_analysis_bundle) unchanged.

### timeseries-cleaning (kept — fetch_data_product / manage_data_cache conditioning workflow)
- Description: “feeding the turbulence, MVA/LMN, or polarization skills” → “before downstream PySPEDAS analysis (spectra, MVA, moments)”.
- Intro: removed references to deleted skills (solar-wind-turbulence-spectrum, boundary-minimum-variance, magnetopause-lmn-analysis, wave-polarization).
- Tool chain: `Use render_tplot for a before/after look` → local matplotlib script.
- Step 11 before/after: render_tplot call → local matplotlib figure from raw/cleaned CSVs.
- Example: “feeds solar-wind-turbulence-spectrum without a cadence_warning” → “feeds downstream spectral analysis without cadence surprises”.
- Kept: fetch → tplot_math chain (tdeflag, clean_spikes, tsmooth, subtract_average, tinterpol) → artifact → create_spedas_analysis_bundle.

### spedas-agent-kit-anatomy (kept — maintenance convention; was already M from main PR)
- “No MCP rendering tools — the analysis/plotting layer (`render_tplot` and friends) was removed…” → wording without the tool name: “the optional analysis/plotting layer was removed in the one-MCP cleanup”.
- No other changes needed; it already documents the 13-tool surface and the analysis-layer removal.

### spedas-skills-index (kept — must reflect the surface)
- Vocabulary section: removed the `[analysis]` extra bullet (render_tplot etc.); now states exactly the 13 base tools + 8 compat tools (SPEDAS_AGENT_KIT_COMPAT_TOOLS=1) and that no MCP analysis/plotting tools exist (run PySPEDAS locally).
- Intent→skill table: removed 16 rows routing to deleted analysis skills; kept spice-conjunction-finder, timeseries-cleaning, spedas-workflow, overview-geomagnetic-indices (2 rows) — the 6 remaining skills incl. this index and anatomy.
- Added a note routing analysis intents (turbulence, polarization, LMN, hodogram, particle distributions, multi-s/c gradients) to unified-data fetch + local PySPEDAS, with timeseries-cleaning as the conditioning first step.

## Step 2 — index/anatomy sweep
- `spedas-skills-index/SKILL.md` and `spedas-agent-kit-anatomy/SKILL.md` updated (above).
- No ANATOMY.md exists under `src/spedas_agent_kit/resources/` or inside any skill dir; `src/spedas_agent_kit/ANATOMY.md` and repo-root `ANATOMY.md` reference skills only generically (no per-skill listings) — no edits needed.
- Root `README.md` checked: references only `overview-geomagnetic-indices` (surviving) — no edits needed.

## Validation

1. `grep -rn '<16 removed tool names>' src/spedas_agent_kit/resources/skills/` → **no matches** (exit 1).
2. `grep -rn '\[analysis\]\|\[hapi\]\|\[fdsn\]' src/spedas_agent_kit/resources/skills/` → **no matches** (exit 1).
3. `.venv/bin/python -m pytest tests/test_resources.py -q` → **2 passed in 0.00s**.
4. `.venv/bin/python scripts/smoke_mcp_list_tools.py --json` → **"ok": true, "tool_count": 13**, missing: [], unexpected: [] (tools: spedas_overview, search_spedas_data_sources, plan_spedas_observation, compare_cdaweb_pds_spice, create_spedas_analysis_bundle, get_ephemeris, compute_distance, transform_coordinates, browse_data_sources, load_data_source, browse_data_parameters, fetch_data_product, manage_data_cache).
5. `git status --short src/spedas_agent_kit/resources/skills/`: 16 staged deletions (D) + 5 modified (M: overview-geomagnetic-indices [pre-existing from main PR], spedas-agent-kit-anatomy, spedas-skills-index, spice-conjunction-finder, timeseries-cleaning).
6. `git diff --stat src/spedas_agent_kit/resources/skills/`: 5 files, +46/−51 (anatomy 12, index 37, spice 8, timeseries 17, overview-geomagnetic-indices 23 [pre-existing]).

## Judgment calls
- **Deleted rather than “kept-tool-ified”**: every analysis skill’s scientific core (spectrogram, MVA/LMN, hodogram, PSD, wavelet, particle distributions, FAC rotation, field models) depends on a removed tool; a kept-tool-only rewrite would strip the science and leave dead instruction. Per instructions, deletion is the correct outcome.
- **Kept timeseries-cleaning**: its toolchain (fetch_data_product, create_spedas_analysis_bundle + pyspedas tplot_math backend) is fully on the kept surface; only plot/downstream-skill wording was stale.
- **Kept spice-conjunction-finder**: entirely SPICE geometry (get_ephemeris/compute_distance/manage_data_cache); only the optional-render step referenced removed surface.
- **spedas-workflow and overview-geomagnetic-indices**: verified 0 references to removed tools/skills/extras — untouched (overview-geomagnetic-indices already carries main-PR edits).
- **No commit/push performed** — changes staged/working-tree only, as instructed.
