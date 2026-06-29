# src/spedas_mcp/analysis — pyspedas-backed analysis layer

## What this is

The optional `[analysis]` layer: file-in / file-out functions wrapping pyspedas/PyWavelets/geopack for coordinate transforms, spectra, field models, and particle products. Each reads a fetched artifact, writes a result artifact (`.npz`/`.csv`/`.png`), and returns compact stats + paths — never bulk arrays. Registered as MCP tools by `server.py:create_server()` only when `_analysis_dependencies_available()` is true.

## Components

- **`coords.py`** (794) — `transform_timeseries_coordinates` `:338` (Earth-frame cotrans), `generate_fac_matrix` `:439` (field-aligned (N,3,3) stack), `tvector_rotate` `:595` (apply a matrix stack — returns a list of tplot var names), `analyze_minvar_coordinates` `:664` (MVA/LMN; returns eigenvalues + normal + rotated path).
- **`spectral.py`** (511) — `dynamic_power_spectrum` `:198` (Welch dpwrspc), `wavelet_transform` `:314` (Morlet CWT; `_sampling_interval` median-dt + `cadence_warning`).
- **`fieldmodels.py`** (819) — `evaluate_magnetic_field` `:475` (IGRF/T89/T96/T01/TS04 + tracing), `calculate_lshell` `:650` (McIlwain L; rejects out-of-domain positions with `position_domain_error`).
- **`particles.py`** (1114) — `build_particle_distribution_artifact` `:418` (the #95 bridge: real MMS/ERG CDF → distribution schema), `compute_particle_moments` `:642` (needs `magf` in the dist), `compute_particle_spectra` `:823` (energy/phi/theta/pitch-angle).
- **`plotting.py`** (693) — `render_tplot` `:391` (headless matplotlib; **one 2-D matrix per input `.npz`**, one stacked panel per file).
- **`__init__.py`** (82) — lazy-import guards; missing extra → clean `dependency_missing` error.

## Connections

- **In:** `server.py` tool closures call these with validated args + an `output_dir`.
- **Out:** import pyspedas submodules (cotrans_tools, analysis.wavelet/twavpol, geopack, particles.*, tplot_tools); PyWavelets; matplotlib (Agg).
- Artifacts chain: `fetch_data_product` CSV → these → `.npz`/`.csv` → `render_tplot` PNG. The **skills** (`plugins/spedas-claude/skills/`) encode these chains.

## Composition

- **Parent:** `src/spedas_mcp/` (`../ANATOMY.md`).

## State

- None in-process. All output written under the caller's `output_dir` (bundle `data/`/`plots/`).

## Notes

- **I/O contract discipline (load-bearing):** pyspedas backends variously *return an array*, *store a tplot var* (retrieve via `get_data`; `tnames()`-listed ≠ retrievable), or *return a dict*. State which in any new tool/skill — mismatches here are the recurring bug class.
- Reliability gates are a convention: MVA eigenvalue ratio, curlometer ∇·B/∇×B, wavelet `cadence_warning`, L-shell domain guard, particle `magf` requirement. Preserve them when editing.
