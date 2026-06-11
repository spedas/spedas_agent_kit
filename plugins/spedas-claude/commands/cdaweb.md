# /spedas-mcp:cdaweb

Use the `spedas` MCP server for a CDAWeb workflow.

1. Start with `browse_observatories()` or `load_observatory(observatory_id)`.
2. Use `browse_parameters(dataset_id=...)` before any fetch.
3. If fetching, keep the time range small unless the user explicitly requested more, and write data to `output_dir`.
4. Report file paths, row counts, units, and caveats.

Task: $ARGUMENTS
