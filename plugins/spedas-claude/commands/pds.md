# /spedas-mcp:pds

Use the `spedas` MCP server for a NASA PDS Planetary Plasma Interactions workflow.

1. Start with `browse_pds_missions(query?)` or `load_pds_mission(mission_id)`.
2. Use `browse_pds_parameters(dataset_id=...)` before `fetch_pds_data`.
3. Be explicit that some PDS datasets currently have metadata/label coverage gaps.
4. If fetching, keep the time range small and write data to `output_dir`.

Task: $ARGUMENTS
