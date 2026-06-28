---
name: multi-spacecraft-gradients
description: Compute spatial gradients of the magnetic field from a 4-spacecraft constellation (MMS, Cluster) — current density via the curlometer (J = ∇×B/μ0 with the ∇·B reliability check), full gradient/curl/divergence + field-line curvature (lingradest), and magnetic-null detection & classification (FOTE). One skill for the flagship multi-spacecraft science; composes existing tools, adds none.
---

# Multi-spacecraft magnetic-field gradients (curlometer / lingradest / nulls)

The flagship 4-spacecraft analyses from IDL SPEDAS/Cluster, none of which a single
spacecraft can do: estimate the *spatial* derivatives of B across a tetrahedron to
get current density, gradients, and magnetic nulls. All three share the same input
(4× B + 4× position), so they live in one skill.

## When to use
- "What's the current density (curlometer J) across this MMS/Cluster crossing?"
- "Gradient / divergence / curl of B, or field-line curvature, from the four spacecraft."
- "Is there a magnetic null here, and what type (A/B/X/O)?"

## Tool chain (all existing)
`load_data_source`×4 → `fetch_data_product`×4 (B) + `get_ephemeris`/fetch ×4 (position)
→ a small multi-s/c call (`mms_curl` | `lingradest` | `find_magnetic_nulls_fote`) → `render_tplot`,
in a `create_spedas_analysis_bundle`. Generic for any 4-s/c set (the `mms_*` name is historical; the method is the Chanteur curlometer).

## Backends (output contracts verified live)

**Curlometer — `pyspedas.projects.mms.mms_curl(fields=[b1,b2,b3,b4], positions=[r1,r2,r3,r4], suffix=...)`**
(note: under `projects.mms`, NOT top-level pyspedas; generic 4-s/c despite the name).
Stores these tplot vars (retrieve via `get_data`):
- `jtotal{suffix}` (N,3) — **current density vector** (the headline result),
- `jpar{suffix}` (N,1), `jperp{suffix}` (N,3) — para/perp current,
- `curlB{suffix}` (N,3), `divB{suffix}` (N,) — **|divB|/|curlB| is the reliability metric** (should be ≪1 for a good tetrahedron),
- `baryb{suffix}` (N,3), `alpha{suffix}`, `alphaparallel{suffix}`.

**Gradients — `pyspedas.lingradest(Bx1..Bx4, By1..By4, Bz1..Bz4, R1..R4, scale_factor=1000.0)`**
takes the 12 component tplot-var names + 4 position vars; outputs linear gradient/curl/divergence of B and field-line **curvature** as tplot vars.

**Nulls — `pyspedas.find_magnetic_nulls_fote(positions=[r1..r4], fields=[b1..b4], ...)`** then
`pyspedas.classify_null_type(lambdas)` → null location + eigenvalue-based type (A/B/As/Bs/X/O).

## Procedure

1. **Bundle** and pick the 4 spacecraft (MMS1-4, or any 4-s/c set). Window: tight around the feature; the constellation must be a reasonable tetrahedron over it.

2. **Fetch B + position for all four**, same time grid where possible. Confirm vector variable names with `browse_data_parameters`. Curlometer/lingradest assume the field varies ~linearly across the constellation — only valid when inter-spacecraft separation ≪ the gradient scale.

3. **Pick the estimator** (or run several):
   - **Current density** → `mms_curl(fields=[...], positions=[...], suffix=...)`. Read `jtotal{suffix}` for J; read `divB`/`curlB` and report **|∇·B| / |∇×B|** as the trust metric.
   - **Full gradients / curvature** → `lingradest(...)` (12 component vars + 4 positions).
   - **Magnetic nulls** → `find_magnetic_nulls_fote(positions=..., fields=...)` + `classify_null_type(...)`.
   Write the results you need to `<bundle>/data/*.npz` via `get_data` (these functions store tplot vars; they do **not** return arrays — retrieve by name).

4. **Tetrahedron-quality caveat (mandatory in the report).** All multi-s/c gradient estimates degrade as the constellation departs from a regular tetrahedron. Report the curlometer **|∇·B|/|∇×B|** ratio (a built-in quality check: physically ∇·B=0, so a large ratio means the gradient estimate is unreliable). If it's not small (≲0.1–0.3), treat J/gradients/nulls as suspect.

5. **Render & interpret.** `render_tplot` the J components (and |J|), divB-ratio, and any null markers. Interpret: large field-aligned J at a current sheet; a classified X/O null indicates reconnection topology.

6. **Record** J magnitude/direction, the divB-ratio quality, and any null type in `notes/`.

## Guardrails
- Artifact-first: report J + the quality ratio + null type, with paths — never the full sampled gradients.
- **Always report the |∇·B|/|∇×B| reliability ratio** — a curlometer J without it is not trustworthy. This is the multi-s/c analogue of the MVA eigenvalue-ratio check.
- Linear-gradient assumption: valid only when separation ≪ gradient scale and the tetrahedron is non-degenerate.
- These functions store tplot variables and return success/None — retrieve outputs via `get_data(name)`, don't expect arrays from the call.
- Needs the `[analysis]` extra; needs genuine 4-spacecraft data (MMS/Cluster).

## Example (curlometer contract verified live)
`mms_curl(fields=[b0..b3], positions=[pos0..pos3], suffix='_mc')` on a synthetic tetrahedron stored `jtotal_mc (N,3)`, `curlB_mc (N,3)`, `divB_mc (N,)`, `jpar_mc`/`jperp_mc`, `baryb_mc`, `alpha_mc` — confirming the current-density + ∇·B-reliability output contract this skill relies on.
