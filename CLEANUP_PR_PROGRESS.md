# CLEANUP PR PROGRESS — one primary MCP (CDAWeb + PDS + SPICE)

Branch: `clean/merge-three-mcps` (already checked out). All work was done in this branch; **nothing was committed or pushed**.

Pre-existing (per parent instructions, NOT re-done): `git rm` of `src/spedas_agent_kit/datasources`, `src/spedas_agent_kit/analysis`, `plugins/`, `.agents/`, `scripts/validate_plugin_packages.py`, and 8 test files; deletion of stray `edge_probe*.py`/`verify_pr68.py`/`mth5/`. Those deletions are staged (`D` in `git status`).

## Files changed by this run (unstaged modifications)

| File | Change |
|---|---|
| `src/spedas_agent_kit/server.py` | 3833 → 2822 lines (−1011). All HAPI/FDSN/analysis/cdawebmcp-fallback code removed; `create_server()` takes no args. |
| `tests/test_server.py` | 3109 → 2805 lines. Removed ~50 hapi/fdsn + ~39 analysis references; converted analysis-based tests to core tools. |
| `scripts/smoke_mcp_list_tools.py` | Removed hapi/fdsn from BASE_EXPECTED_TOOLS (13 core tools), deleted ANALYSIS_EXPECTED_TOOLS and `_analysis_dependencies_available()` and its use; dropped `analysis_extra_detected`. |
| `pyproject.toml` | Removed `[analysis]`, `[hapi]`, `[fdsn]` extras (+ their dependency lists); kept `mcp`/`dev`. |
| `.github/workflows/ci.yml` | Removed the `validate_plugin_packages.py` step and the entire `analysis` job lane. |
| `README.md` | 412 → 276 lines. Tool count 17→13, `advanced` surface removed, hapi/fdsn/analysis sections/table rows/recipes/install blocks removed, plugin-fixture paragraph updated. |
| `ANATOMY.md` (root) | Rewritten without datasources/analysis/plugins refs; 13/21 tool counts; citations updated. |
| `src/spedas_agent_kit/ANATOMY.md` | Rewritten without analysis/datasources refs; citations updated to current line numbers. |
| `src/spedas_agent_kit/resources/skills/overview-geomagnetic-indices/SKILL.md` | Replaced `browse_hapi_catalog`/`fetch_hapi_data`/[hapi]-extra instructions with CDAWeb unified data-layer calls; removed `render_tplot`/[analysis] guidance. |
| `src/spedas_agent_kit/resources/skills/spedas-agent-kit-anatomy/SKILL.md` | Removed `analysis/`+`datasources/` directory refs and analysis-maintenance bullets; skills dir now `resources/skills/`. |

`server.json` was reviewed: it only describes the unified CDAWeb+PDS+SPICE server (no hapi/fdsn/analysis mentions) — left unchanged. `docs/maintainer_note.md`, `docs/public_api_strategy.md`, `docs/examples/*.md`, `src/spedas_agent_kit/backends/ANATOMY.md` were checked: no stale hapi/fdsn/analysis-tool references (only the core `create_spedas_analysis_bundle` workflow tool, which is kept).

## Every server.py section removed

1. Constants `ANALYSIS_TOOL_NAMES`, `HAPI_TOOL_NAMES`, `FDSN_TOOL_NAMES` (was lines 35–52).
2. `_ANALYSIS_REQUIRED_IMPORTS` block + its comment (was 54–84).
3. `_analysis_dependencies_available()` (was 161–177).
4. `_module_available()` (was 180–185) — dead after #5.
5. `_optional_backend_availability()` (was 188–256) — after removing analysis/hapi/fdsn entries it only returned an empty dict, so the whole function was removed; `optional_backends` computed in `create_server` and its use in `spedas_overview` metadata were removed too.
6. `import importlib` (was line 17) — orphaned by 3/4.
7. `create_server(*, include_analysis_tools=...)` → `create_server()`; gating docstring/auto-detect removed.
8. `_advanced_tool` decorator (was 1262–1275) — only analysis tools used it.
9. `spedas_overview` `capability_groups.analysis` group + `optional_backends` key (was 1328–1340).
10. `_normalize_source_type` aliases `hapi`/`hapi_server`/`fdsn`/`mth5`/`magnetotelluric`.
11. Unreachable legacy fallback `from cdawebmcp.catalog import load_observatory_json` (was ~2221); the in-tree `spedas_agent_kit.backends.cdaweb.catalog` import is now direct.
12. `browse_data_sources`: hapi/fdsn entries in the `all` source_types list, the standalone `if source == "hapi"/"fdsn"` branches, and the note; allowed list → `["all","cdaweb","pds","spice"]`.
13. `load_data_source`: hapi/fdsn `use_dedicated_tool` branches; allowed list → `["cdaweb","pds","spice"]`.
14. `browse_data_parameters`: hapi/fdsn branches; allowed list → `["cdaweb","pds","spice"]`.
15. `fetch_data_product`: hapi/fdsn branches; allowed list → `["cdaweb","pds","spice"]`.
16. The whole `if include_analysis_tools:` analysis registration block (13 tool defs, was 3067–3617) and the 4 HAPI/FDSN tool defs + their comment header (was 3619–3741).
17. `_install_argument_validation_guard` hint text that named analysis tools (was 3796–3799).

Kept intact: `workflows.py` tools incl. `create_spedas_analysis_bundle`, all `backends/`, all `resources/` skills, the 8 compat tools, SPICE geometry tools, and the unified CDAWeb/PDS/SPICE dispatch.

## Tests changes (tests/test_server.py)

- Import line 9: dropped `ANALYSIS_TOOL_NAMES`; only `create_server` imported.
- `test_server_has_expected_tools`: now asserts the 13-tool base surface; removed 13 analysis + 4 hapi/fdsn names; `create_server()`.
- Removed: `test_analysis_tools_are_gated_when_analysis_extra_is_absent`, `test_analysis_tools_register_when_analysis_extra_is_available`, `test_optional_backend_availability_metadata_when_base_deps_missing`, `test_analysis_tools_expose_advanced_surface_metadata`.
- `test_base_tools_expose_primary_surface_metadata`: `create_server(include_analysis_tools=False)` → `create_server()`.
- `test_browse_data_sources_lists_spedas_source_categories`: set now `{cdaweb, pds, spice}`.
- `test_no_legacy_status_error_returns_on_data_layer_and_analysis_surfaces` → `test_no_legacy_status_error_returns_on_data_layer` (server_mod only; removed the `spedas_agent_kit.analysis.coords` check).
- Removed: `test_analysis_tools_are_wrapped_in_safe_tool`, `test_render_tplot_registered_and_validates`, `test_render_tplot_missing_file_is_structured`, `test_render_tplot_wrapped_in_safe_tool`, `test_analysis_safe_tool_converts_unexpected_exception`.
- Removed the whole `# Issues #21/#22: HAPI + FDSN` section (7 tests: all-lists/alias/routing/unknown-allowed-list/missing-dep/bad-trange).
- Rewrote the 3 arg-validation tests (previously analysis-tool based) onto core tools: valid args → `fetch_data_product(cdaweb, missing start/stop/output_dir)` reaches body; wrong types → `fetch_data_product` with `source_type=123`, `parameters="not-a-list"` → `invalid_arguments` naming both; valid args → `load_data_source(source_type="nope")` reaches body (`invalid_argument`, not `invalid_arguments`).

## Validation results (all from repo root)

- `python -m py_compile src/spedas_agent_kit/server.py` → OK; `python -m py_compile tests/test_server.py` → OK; `python -m py_compile scripts/smoke_mcp_list_tools.py` → OK.
- `.venv/bin/python -m pytest tests/test_server.py tests/test_config.py tests/test_resources.py -q` → **238 passed, 0 failed** (~2.4–2.9 s).
- `.venv/bin/python scripts/smoke_mcp_list_tools.py --json` → `ok: true`, `tool_count: 13`.
- `.venv/bin/python scripts/smoke_mcp_list_tools.py --json --compat-tools` → `ok: true`, `tool_count: 21` (13 + 8 compat).
- Zero-reference grep (`datasources|_analysis|ANALYSIS_TOOL|browse_hapi|fetch_hapi|browse_fdsn|fetch_fdsn|hapi|fdsn` over src/ tests/ scripts/ pyproject.toml server.json .github/, excluding git-ignored `__pycache__`/`.pyc`) → **clean**; the only matches are the legit core `create_spedas_analysis_bundle`/`create_analysis_bundle` workflow tool. Stale `__pycache__/*.pyc` from the deleted modules exist but are git-ignored (`.gitignore:2`) and were left untouched per instructions.

## Judgment calls

1. **Removed `_advanced_tool` + `meta.surface="advanced"`** everywhere (docs included) — it was used only by analysis tools; the surface set is now `primary`/`compat`.
2. **Removed `_module_available` and the `importlib` import** — orphaned once `_optional_backend_availability` went.
3. **Rewrote 3 arg-validation tests onto core tools** rather than deleting them — they lock in the #57 validation contract, which still exists.
4. **Updated 2 resource skills** that would have failed the mandated `src/` grep and/or misled agents (hapi tool calls in `overview-geomagnetic-indices`; `analysis/`/`datasources/` directory guidance in `spedas-agent-kit-anatomy`).
5. **Not touched (out of the enumerated docs scope):** the remaining ~18 `resources/skills/*.md` still describe the removed analysis tools (`render_tplot`, `analyze_minvar_coordinates`, `transform_timeseries_coordinates`, `dynamic_power_spectrum`, `wavelet_transform`, `evaluate_magnetic_field`, `calculate_lshell`, particle tools, `generate_fac_matrix`, `tvector_rotate`) as MCP tool chains. These do not match the mandated grep pattern and do not break tests, but agents following them would reference tools that no longer exist. **Recommended follow-up PR:** rewrite those skills to call PySPEDAS directly or drop the analysis steps.
6. Legit uppercase prose remains (e.g. "CDAWeb HAPI OMNI" in `spedas_overview` guided recipes / README), which the spec explicitly allows; it does not match the lowercase grep.
7. `CLEANUP_AUDIT.md` remains untracked at repo root (pre-existing, per the audit's own note it was the only file it wrote).

## git status --short

```
D  .agents/plugins/marketplace.json
D  .agents/plugins/spedas-codex/.codex-plugin/plugin.json
D  .agents/plugins/spedas-codex/.mcp.json
D  .agents/plugins/spedas-codex/README.md
D  .agents/plugins/spedas-codex/skills/spedas-workflow/SKILL.md
 M .github/workflows/ci.yml
 M ANATOMY.md
 M README.md
D  plugins/README.md
D  plugins/spedas-agent-kit-compatibility.json
D  plugins/spedas-claude/.claude-plugin/plugin.json
D  plugins/spedas-claude/.mcp.json
D  plugins/spedas-claude/README.md
D  plugins/spedas-claude/commands/analyze.md
D  plugins/spedas-claude/commands/cdaweb.md
D  plugins/spedas-claude/commands/overview.md
D  plugins/spedas-claude/commands/pds.md
D  plugins/spedas-claude/commands/spice.md
D  plugins/spedas-claude/hooks/hooks.json
D  plugins/spedas-claude/skills/apply-rotation-matrix/SKILL.md
D  plugins/spedas-claude/skills/boundary-minimum-variance/SKILL.md
D  plugins/spedas-claude/skills/coordinate-frame-tour/SKILL.md
D  plugins/spedas-claude/skills/dual-spacecraft-timing/SKILL.md
D  plugins/spedas-claude/skills/field-line-footpoint/SKILL.md
D  plugins/spedas-claude/skills/hodogram/SKILL.md
D  plugins/spedas-claude/skills/magnetopause-lmn-analysis/SKILL.md
D  plugins/spedas-claude/skills/model-lmn-boundary/SKILL.md
D  plugins/spedas-claude/skills/multi-spacecraft-gradients/SKILL.md
D  plugins/spedas-claude/skills/neutral-sheet-distance/SKILL.md
D  plugins/spedas-claude/skills/overview-geomagnetic-indices/SKILL.md
D  plugins/spedas-claude/skills/particle-velocity-slice/SKILL.md
D  plugins/spedas-claude/skills/pitch-angle-distribution/SKILL.md
D  plugins/spedas-claude/skills/power-spectral-density/SKILL.md
D  plugins/spedas-claude/skills/solar-wind-turbulence-spectrum/SKILL.md
D  plugins/spedas-claude/skills/spectral-cross-coherence/SKILL.md
D  plugins/spedas-claude/skills/spedas-agent-kit-anatomy/SKILL.md
D  plugins/spedas-claude/skills/spedas-skills-index/SKILL.md
D  plugins/spedas-claude/skills/spedas-workflow/SKILL.md
D  plugins/spedas-claude/skills/spice-conjunction-finder/SKILL.md
D  plugins/spedas-claude/skills/timeseries-cleaning/SKILL.md
D  plugins/spedas-claude/skills/wave-polarization/SKILL.md
 M pyproject.toml
 M scripts/smoke_mcp_list_tools.py
D  scripts/validate_plugin_packages.py
 M src/spedas_agent_kit/ANATOMY.md
D  src/spedas_agent_kit/analysis/ANATOMY.md
D  src/spedas_agent_kit/analysis/__init__.py
D  src/spedas_agent_kit/analysis/coords.py
D  src/spedas_agent_kit/analysis/fieldmodels.py
D  src/spedas_agent_kit/analysis/particles.py
D  src/spedas_agent_kit/analysis/plotting.py
D  src/spedas_agent_kit/analysis/spectral.py
D  src/spedas_agent_kit/datasources/ANATOMY.md
D  src/spedas_agent_kit/datasources/__init__.py
D  src/spedas_agent_kit/datasources/fdsn.py
D  src/spedas_agent_kit/datasources/hapi.py
 M src/spedas_agent_kit/resources/skills/overview-geomagnetic-indices/SKILL.md
 M src/spedas_agent_kit/resources/skills/spedas-agent-kit-anatomy/SKILL.md
 M src/spedas_agent_kit/server.py
D  tests/test_analysis_coords.py
D  tests/test_analysis_fieldmodels.py
D  tests/test_analysis_particles.py
D  tests/test_analysis_plotting.py
D  tests/test_analysis_spectral.py
D  tests/test_datasources_fdsn.py
D  tests/test_datasources_hapi.py
D  tests/test_plugin_skills.py
 M tests/test_server.py
?? CLEANUP_AUDIT.md
```

## git diff --stat

```
 .github/workflows/ci.yml                           |   31 -
 ANATOMY.md                                         |   17 +-
 README.md                                          |  176 +---
 pyproject.toml                                     |   20 -
 scripts/smoke_mcp_list_tools.py                    |   54 -
 src/spedas_agent_kit/ANATOMY.md                    |   17 +-
 .../skills/overview-geomagnetic-indices/SKILL.md   |   23 +-
 .../skills/spedas-agent-kit-anatomy/SKILL.md       |   12 +-
 src/spedas_agent_kit/server.py                     | 1032 +-------------------
 tests/test_server.py                               |  364 +------
 10 files changed, 94 insertions(+), 1652 deletions(-)
```
