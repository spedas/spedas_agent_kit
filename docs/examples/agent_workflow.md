# Example: agent workflow with SPEDAS MCP

This example is intentionally tool-oriented rather than tied to one agent runtime. Claude Code, Codex, OpenCode, LingTai, or another MCP-capable client can follow the same sequence.

## Open-ended science request

> Plan a Juno magnetic-field and geometry study near Jupiter for a selected interval.

Recommended sequence:

1. Start with the semantic layer:

   ```text
   search_spedas_data_sources(
     question="Study Juno magnetic field measurements near Jupiter and add spacecraft geometry context",
     target="Jupiter",
     observables=["magnetic field", "spacecraft position"]
   )
   ```

   Expected result: PDS and SPICE should rank high, because PDS can provide archived Juno field products while SPICE provides geometry/trajectory context.

2. Create a plan:

   ```text
   plan_spedas_observation(
     science_goal="Plan a Juno magnetic field and geometry study",
     target="Jupiter",
     start="YYYY-MM-DDTHH:MM:SSZ",
     stop="YYYY-MM-DDTHH:MM:SSZ",
     data_sources=["pds", "spice"]
   )
   ```

3. Scaffold a provenance bundle:

   ```text
   create_spedas_analysis_bundle(
     study_name="juno-jupiter-field-geometry",
     output_dir="./runs",
     science_goal="Plan a Juno magnetic field and geometry study",
     target="Jupiter",
     data_sources=["pds", "spice"]
   )
   ```

4. Use source-specific discovery:

   ```text
   browse_pds_missions(query="juno")
   load_pds_mission("JUNO_PPI")
   browse_pds_parameters(dataset_id="...")
   list_spice_missions()
   list_coordinate_frames(mission="JUNO")
   ```

5. Fetch/compute only after the mission, dataset, parameters, frames, and time range are explicit:

   ```text
   fetch_pds_data(..., output_dir="./runs/juno-jupiter-field-geometry/data")
   get_ephemeris(...)
   compute_distance(...)
   ```

6. Return compact summaries and paths to generated artifacts. Do not paste large data arrays into chat.

## Mixed heliophysics request

> Compare solar wind plasma and spacecraft geometry during an Earth bow-shock interval.

Likely source families:

- CDAWeb for OMNI/MMS/THEMIS/other time-series measurements.
- SPICE for geometry, frames, and distance/position context when applicable.

Recommended first calls:

```text
search_spedas_data_sources(
  question="Compare solar wind plasma and spacecraft geometry during an Earth bow shock interval",
  target="Earth bow shock",
  observables=["plasma", "magnetic field", "position"]
)

plan_spedas_observation(
  science_goal="Compare solar wind plasma and spacecraft geometry during an Earth bow shock interval",
  target="Earth bow shock",
  start="YYYY-MM-DDTHH:MM:SSZ",
  stop="YYYY-MM-DDTHH:MM:SSZ"
)
```

Then continue with `browse_observatories`, `load_observatory`, `browse_parameters`, and `fetch_data`, plus SPICE tools when geometry context is required.
