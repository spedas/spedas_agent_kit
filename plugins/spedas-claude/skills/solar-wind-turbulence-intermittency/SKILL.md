---
name: solar-wind-turbulence-intermittency
description: Guide PSP/Solar Orbiter/Wind solar-wind intermittency workflows: compute PVI and vector increments, export event tables, and document proxy-vs-paper-quality energy-transfer/third-order-law assumptions without adding a new MCP tool.
---

# Solar-wind turbulence intermittency and energy-transfer workflow

Use this skill when a researcher asks for PVI, intermittent structures, vector
increments, structure functions, switchback-adjacent turbulence, or near-Sun
energy-transfer / third-order-law context. It complements
`solar-wind-turbulence-spectrum` and `power-spectral-density`: those skills cover
spectra; this one covers **intermittency diagnostics and the provenance needed to
avoid over-claiming proxy math**.

## When to use

- "Compute PVI for this PSP interval and list the strongest structures."
- "Find intermittent structures / discontinuities in a solar-wind magnetic-field interval."
- "Show increments and rolling variance around a switchback or Alfvénic impulse."
- "Can we reproduce an energy-transfer / third-order-law PSP paper?"
- "Turn a PSP Encounter-1 turbulence paper into an artifact bundle with clear proxy labels."

## Tool chain

Use existing Agent Kit primitives; do not ask for a new MCP tool first:

`create_spedas_analysis_bundle` → `plan_spedas_observation` / `fetch_data_product`
→ local artifact script for increments/PVI/event table → optional
`dynamic_power_spectrum` / `power-spectral-density` for spectral context →
`render_tplot` or a saved matplotlib figure.

For paper-driven work, load `paper-reproduction` first and keep its DOI/evidence,
artifact, and provenance discipline.

## Procedure

1. **Bundle and interval label.** Create or select an artifact bundle. Record the
   paper/event, interval, and `interval_quality`: `paper_exact`,
   `representative_proxy`, or `cached_smoke`. PSP Encounter-1 smoke windows are
   useful for tool validation, but they are not paper-quality by default.

2. **Fetch vector fields narrowly.** Fetch a magnetic-field vector in a named
   coordinate basis (RTN/GSE/etc.). For PSP first-pass work, FIELDS MAG RTN
   1-minute is acceptable for smoke/provenance; high-rate MAG is needed for
   publication-quality intermittency or sharp-impulse statistics. Add SWEAP/SPC
   plasma moments only when velocity/density or Taylor-hypothesis context is
   needed.

3. **Validate cadence and gaps.** Before computing PVI or increments, state the
   cadence, resampling method, gap/fill handling, and sample count. If cadence is
   irregular, resample to a uniform grid and record the interpolation method.

4. **Compute increments.** For lag `τ`, compute vector increments
   `δB(t, τ) = B(t + τ) - B(t)` in the chosen coordinate basis. Save compact
   columns such as `time`, `lag_s`, `dB_R`, `dB_T`, `dB_N`, `abs_dB` rather than
   pasting arrays into chat.

5. **Compute PVI.** Use
   `PVI(t, τ) = |δB(t, τ)| / sqrt(<|δB(t, τ)|^2>)`, and record exactly what the
   denominator means: whole interval, rolling window, quiet reference interval,
   or paper-defined ensemble. Thresholds such as `PVI > 3` are starting points;
   sweep at least one neighboring threshold before claiming robust structures.

6. **Export an event table.** If thresholding PVI or switchback/deflection angles,
   write a machine-readable table next to the figure, e.g. CSV/JSON with
   `start`, `stop`, `duration_s`, `peak_time`, `peak_pvi`, `lag_s`, `threshold`,
   `normalization`, and `quality_label`. Merge adjacent samples only after
   recording the merge gap/duration rule.

7. **Plot breadcrumbs.** A useful first figure has panels for vector components,
   `|B|`, PVI or `|δB|`, optional plasma speed/density, and threshold/event
   markers. For spectral context, call `solar-wind-turbulence-spectrum` or
   `power-spectral-density` instead of reimplementing PSD logic.

8. **Energy-transfer / third-order-law boundary.** Treat quantities like
   `|δB|^3 / τ`, `δz^- |δz^+|^2`, or other Yaglom/Politano–Pouquet proxies as
   **pedagogical breadcrumbs** unless you have matched the paper's variables,
   units, lag range, cadence, plasma normalization, Taylor-hypothesis assumption,
   compressive/incompressive form, and uncertainty treatment. State clearly:
   "proxy, not a cascade-rate estimate" until those conditions are met.

## Minimal provenance additions

Add a block like this to the paper-reproduction provenance:

```json
{
  "intermittency_context": {
    "vector_variable": "psp_fld_l2_mag_RTN_1min",
    "coordinate_basis": "RTN",
    "cadence_s": 60,
    "lag_s": 60,
    "normalization": "sqrt(mean(|delta_B|^2)) over the analyzed interval",
    "thresholds_tested": [3.0, 4.0],
    "event_table": "artifacts/pvi_events.csv",
    "interval_quality": "representative_proxy",
    "claim_level": "proxy"
  }
}
```

## Paper-reproduction examples

Batch-003 of the SPEDAS paper-reproduction campaign exposed the gap this skill
fills:

| Iteration | Paper theme | DOI | First-pass claim level |
|---:|---|---|---|
| 012 | PSP PVI / intermittent structures (Chhiber et al. 2020) | `10.3847/1538-4365/ab53d2` | `cached_smoke` / PVI event-table workflow |
| 014 | PSP enhanced energy transfer near the Sun | `10.3847/1538-4365/ab5dae` | `proxy` / third-order-law prerequisites |

For Horbury-style sharp impulses or switchback catalog context, combine this
skill with `psp-solar-wind-switchbacks`. For spectrum slopes and wavelet views,
combine it with `solar-wind-turbulence-spectrum`.

## Guardrails

- Artifact-first: write CSV/JSON/PNG/provenance paths; never paste long arrays.
- Do not hide judgement calls behind a tool name. Lag, cadence, normalization,
  threshold, merge rule, and claim level are part of the result.
- Prefer a table plus a plot. A thresholded event list is far easier to review,
  compare, and turn into future tests than a screenshot alone.
- Do not label a result `paper_quality` unless paper interval, product cadence,
  diagnostic definition, fit/lag bounds, and uncertainty treatment are matched.
