# /spedas-mcp:spice

Use the `spedas` MCP server for SPICE ephemeris, distance, or coordinate-frame work.

1. Start with `list_spice_missions()` and, if needed, `list_coordinate_frames()`.
2. Use `get_ephemeris`, `compute_distance`, or `transform_coordinates` as appropriate.
3. For time series, require an `output_file` and keep intervals small unless the user asked otherwise.
4. Mention kernel cache/download side effects when they matter.

Task: $ARGUMENTS
