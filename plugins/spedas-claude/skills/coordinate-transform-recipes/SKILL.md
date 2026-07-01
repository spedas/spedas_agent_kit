---
name: coordinate-transform-recipes
description: Route PySPEDAS/IDL SPEDAS coordinate-transform requests (cotrans, FAC, MVA, LMN, quaternions, frame metadata) into the right Agent Kit skill/tool path without inventing new MCP tools. Bridges tplot coordinate metadata, SPICE frame transforms, and matrix-based rotations while preserving artifacts and provenance.
---

# Coordinate transform recipes: PySPEDAS/IDL cotrans to Agent Kit routes

Use this skill when a prompt mentions PySPEDAS `cotrans`, IDL SPEDAS `cotrans`,
THEMIS/MMS coordinate cribs, tplot coordinate metadata, FAC, MVA, LMN, quaternions,
GSE/GSM/GEI/SM/GEO/J2000, or "convert this variable/vector to another frame".
It is a **route-scout and provenance checklist**, not a new tool: it tells an agent
which existing Agent Kit skill/tool path fits the request and when a PySPEDAS/IDL
routine is only an external runtime route.

## MCP/default-surface boundary

When documenting PySPEDAS or IDL coordinate routines, use the structured marker
`external_runtime_route.not_an_mcp_tool: true`. The following are source evidence
or external runtime routes unless a current Agent Kit MCP tool explicitly exposes
them:

- `pyspedas.cotrans`, `pyspedas.cotrans_tools.*`, `fac_matrix_make`,
  `minvar_matrix_make`, `lmn_matrix_make`, `tvector_rotate`;
- IDL `cotrans`, `spd_cotrans`, `thm_cotrans`, `thm_cotrans_lmn`,
  `mms_cotrans_lmn`, `mms_qcotrans`, and mission `.pro` coordinate helpers
  (load `spedas-heritage-vocabulary` when translating legacy examples);
- PyTplot state helpers such as `cotrans_get_coord`, `cotrans_set_coord`,
  `store_data`, `get_data`, and `tplot_names`.

Do **not** present those names as Agent Kit MCP tools. The MCP-first path is:
`spedas-skills-index` -> this skill or a focused downstream skill -> existing
planning/data/geometry/analysis tools -> artifact paths + `provenance/run.json`.

## When to use

- "Convert THEMIS/MMS/OMNI position or B from GSE to GSM/SM/GEO/J2000."
- "This IDL crib calls `cotrans`/`thm_cotrans`; how do I do the Agent Kit route?"
- "Build FAC for wave polarization or PAD interpretation."
- "Rotate B into MVA/LMN for a boundary crossing, then make a hodogram."
- "Check whether a tplot variable's coordinate metadata makes the requested
  transform meaningful."

## Route table

| User intent | Preferred Agent Kit route | External PySPEDAS/IDL evidence |
|---|---|---|
| Choose a science frame (RTN, GSE/GSM, HEE/HEEQ/HCI, J2000) and transform vectors/time series with Agent Kit geometry | `coordinate-frame-tour`; use `transform_coordinates` for a single vector, or `transform_timeseries_coordinates(input_file=..., coord_in=..., coord_out=..., output_file=...)` for an artifact time series | PySPEDAS `cotrans`; IDL `cotrans` |
| Preserve / inspect loaded tplot variable names, coordinates, units, and suffixes before any transform | `tplot-data-lifecycle` and `pyspedas-load-planning`; record `coord_in`, `coord_out`, variable name, units, and support-data choices | `cotrans_get_coord`, `cotrans_set_coord`, `store_data`, `get_data` |
| FAC matrix for B-aligned wave/PAD context | `apply-rotation-matrix` after generating or importing the FAC matrix; then compose with `wave-polarization` or `pitch-angle-distribution` | `fac_matrix_make`, `tvector_rotate` |
| Data-driven MVA/LMN for a boundary or current sheet | `boundary-minimum-variance` for the MVA basis; `apply-rotation-matrix` for an explicit matrix stack; `hodogram` for rotation sense | `minvar_matrix_make`, `thm_cotrans_lmn`, `mms_cotrans_lmn` |
| Model magnetopause LMN normal / Shue cross-check | `model-lmn-boundary` or `magnetopause-lmn-analysis` | `lmn_matrix_make`, `gsm2lmn` |
| Field-line/footpoint/L-shell mapping | `field-line-footpoint`; supply positions in GSM kilometers first | IDL/PySPEDAS coordinate conversion helpers |
| Mission-specific attitude/quaternion transforms | Stay in the mission skill (`mms-basic-workflows`, `themis-workflows`, `psp-solo-heliophysics-workflows`) and record the support data/quaternion source before any transform | `mms_qcotrans`, `dsl2gse`, `gse2dsl` |

## Procedure

1. **Bundle and scope.** Start with `create_spedas_analysis_bundle(...)` and state
   the science question, interval, mission, vector variable, and desired frame.
   Keep the request narrow; coordinate mistakes are easier to catch on a compact
   interval.

2. **Identify the source coordinate.** From the data product metadata, tplot
   metadata, parameter name, or mission loader options, record the `source_frame`.
   Common Earth frames are **GSE**, **GSM**, **GEI**, **SM**, **GEO**, and
   **J2000**; FAC/LMN/MVA are derived frames and require extra provenance.
   If the source frame is unclear, stop at `needs_metadata` instead of guessing.

3. **Choose the route.**
   - Agent Kit geometry frame transform -> load `coordinate-frame-tour`; use
     `transform_coordinates` for one vector, or for a time-series artifact use
     `transform_timeseries_coordinates(input_file="<bundle>/data/in.csv",
     coord_in="GSE", coord_out="GSM", output_file="<bundle>/data/out.csv")`.
     Do not copy the single-vector `from_frame`/`to_frame` argument names into
     the time-series analysis tool.
   - Matrix-derived frame (FAC/MVA/LMN) -> load `apply-rotation-matrix`, plus the
     specialized skill that creates or validates the matrix.
   - Mission-specific crib (THEMIS `thm_cotrans`, MMS quaternion/LMN, PSP/SolO
     frame labels) -> load that mission workflow skill and treat the crib as
     `external_runtime_route.not_an_mcp_tool: true` evidence.

4. **Write artifacts.** Put transformed vectors in `<bundle>/data/` as CSV/NPZ
   with explicit component names (`B_GSE`, `B_GSM`, `B_L/B_M/B_N`, or
   `B_perp1/B_perp2/B_para`). Write plots to `<bundle>/plots/` and notes to
   `<bundle>/notes/`. Do not paste arrays into chat.

5. **Update provenance.** Add a compact entry to `provenance/run.json` with:
   - source dataset/parameter and original variable name;
   - `source_frame`, `target_frame`, component labels, units, and time basis;
   - transform route (`transform_timeseries_coordinates` with `input_file`,
     `coord_in`, `coord_out`, and `output_file`; FAC matrix + `tvector_rotate`;
     MVA/LMN skill; or external PySPEDAS/IDL crib);
   - support data (state, position, quaternions, magnetic field used for FAC,
     solar-wind/model choices) and cadence/interpolation method;
   - validation checks and caveats.

6. **Verify before interpreting.** Magnitude should be invariant under a pure
   rotation; positions must keep their units (km vs Re); FAC needs a co-temporal
   B field; MVA/LMN needs a reliability metric; field-line tools need GSM km.

## Provenance checklist

Record these fields in notes or `provenance/run.json` before claiming a result:

```yaml
coordinate_transform:
  source_variable: <tplot-or-artifact-name>
  source_frame: GSE|GSM|GEI|SM|GEO|J2000|RTN|instrument|unknown
  target_frame: GSE|GSM|SM|GEO|J2000|FAC|LMN|MVA|RTN
  route: Agent Kit transform_coordinates|transform_timeseries_coordinates|matrix+tvector_rotate|external PySPEDAS cotrans crib
  support_data: [position, attitude, quaternion, magnetic_field, solar_wind_model]
  component_labels: [Bx, By, Bz]
  units: nT|km|km/s|...
  time_basis: UTC or TT2000 source and interpolation method
  validation: [magnitude_invariant, metadata_checked, reliability_ratio, matrix_source]
  caveats: [source_frame_uncertain, cadence_mismatch, model_domain_limit]
```

## Guardrails

- **No hidden-tool routing.** `pyspedas.cotrans`, `pyspedas.cotrans_tools.*`,
  `cotrans`, `thm_cotrans`, `mms_cotrans_lmn`, `fac_matrix_make`, and
  `tvector_rotate` are not default Agent Kit MCP tools. They may be used only as
  source evidence or by an external runtime that actually imports PySPEDAS.
- **Metadata first.** A coordinate transform without a verified source frame is a
  plausible-looking failure. Return `needs_metadata` or write a caveat instead of
  inventing the frame.
- **Derived frames have prerequisites.** FAC needs a B-field definition and a
  reference direction; MVA/LMN needs interval/window, eigenvalue ratio or model
  normal, and a sign convention; quaternion transforms need the attitude product.
- **Compose, don't duplicate.** Use `coordinate-frame-tour`,
  `apply-rotation-matrix`, `boundary-minimum-variance`, `model-lmn-boundary`,
  `magnetopause-lmn-analysis`, `field-line-footpoint`, `tplot-data-lifecycle`,
  and mission workflow skills for specialized details.
- **Artifact-first.** Return paths, frame labels, validation stats, and caveats.
  Do not paste arrays or tplot/CDF contents.

## Example route cards

### THEMIS state GSE -> GSM/SM/GEO

PySPEDAS docs show a `pyspedas.cotrans` crib over a THEMIS position variable, but
for an MCP-only Agent Kit client the route is: load/identify the state product ->
write position vectors to `<bundle>/data/tha_state_gse.csv` -> use
`coordinate-frame-tour` and
`transform_timeseries_coordinates(input_file="<bundle>/data/tha_state_gse.csv",
coord_in="GSE", coord_out="GSM",
output_file="<bundle>/data/tha_state_gsm.csv")` for the artifact route ->
record the original tplot variable, `source_frame="GSE"`, `target_frame="GSM"`,
output artifact path, and units (km or Re) before using the position in
boundary/footpoint skills.

### FAC for wave or PAD interpretation

A FAC request is not a generic GSE/GSM `cotrans`. Identify the B field that defines
parallel, check cadence and frame against the distribution/wave vector, generate or
import the FAC matrix, then use `apply-rotation-matrix` / `tvector_rotate` to write
`B_perp1`, `B_perp2`, `B_para`. Record `mag_source`, source frame, reference
direction, and interpolation caveat.

### LMN / MVA boundary frame

For "rotate this magnetopause crossing into LMN", start with
`boundary-minimum-variance` or `model-lmn-boundary` rather than a blind frame-name
conversion. Record the interval, input frame, eigenvalue ratio or model normal,
matrix source, sign convention, and transformed `B_L/B_M/B_N` artifact. Use
`hodogram` or `magnetopause-lmn-analysis` only after that provenance exists.
