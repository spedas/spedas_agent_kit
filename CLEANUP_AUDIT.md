# CLEANUP AUDIT — spedas_agent_kit (repo: /Users/huangzesen/Downloads/spedas_mcp)

**Goal (Jason):** one primary MCP (`spedas_agent_kit`) that merges CDAWeb + PDS + SPICE; clean everything else out.

**Headline finding:** the merge already happened. `src/spedas_agent_kit/server.py` builds **one** `FastMCP` instance (`"spedas-agent-kit"`, `create_server()` at `server.py:1200`) that dispatches CDAWeb/PDS/SPICE through a unified data layer (`browse_data_sources` / `load_data_source` / `browse_data_parameters` / `fetch_data_product` / `manage_data_cache` with `source_type=` routing) plus three SPICE geometry tools and a workflow layer. The three backends were vendored in-tree (`spedas_agent_kit/backends/{cdaweb,pds,spice}`, issue #107) and the old standalone MCP servers/CLIs were dropped. **No architectural merging is left** — the cleanup is purely deletion of peripheral layers (HAPI/FDSN datasources, analysis, plugin fixtures, stray files, stale docs) plus small fixes.

Audit performed: read-only, 2026-08-02. No tracked files were modified; the only file written is this report.

---

## 1. FULL FILE TREE (tracked, `git ls-files`)

**246 tracked files** total, organized by top-level directory:

| Dir | Files | Contents |
|---|---|---|
| `src/spedas_agent_kit/backends/` | 142 | vendored cdaweb (~80: 13 .py + 63 observatory JSON + prompts/LICENSE/NOTICE/py.typed/scripts), pds (~35: 12 .py + 17 mission JSON + prompts/LICENSE/NOTICE/scripts), spice (~25: 7 .py + 15 manifest JSON + LICENSE/NOTICE), `__init__.py` (empty, 0 lines), `ANATOMY.md` |
| `src/spedas_agent_kit/resources/` | 24 | `__init__.py` (docstring only) + 22 packaged skills (`skills/*/SKILL.md`) + `skills/README.md` |
| `src/spedas_agent_kit/analysis/` | 7 | `__init__.py` (82), `coords.py` (821), `fieldmodels.py` (819), `particles.py` (1578), `plotting.py` (890), `spectral.py` (511), `ANATOMY.md` |
| `src/spedas_agent_kit/datasources/` | 4 | `__init__.py` (159), `hapi.py` (315), `fdsn.py` (288), `ANATOMY.md` |
| `src/spedas_agent_kit/` core | 4 | `server.py` (3833), `workflows.py` (1087), `__init__.py` (16), `__main__.py` (4), `ANATOMY.md` |
| `tests/` | 11 | see §6 (14,594 lines) |
| `plugins/` | 33 | `spedas-claude/` fixture (26 files: commands/{analyze,cdaweb,overview,pds,spice}.md, hooks, 21 skills), `README.md`, `spedas-agent-kit-compatibility.json` |
| `.agents/` | 5 | `plugins/marketplace.json` + `plugins/spedas-codex/` fixture (plugin.json, .mcp.json, README.md, skills/spedas-workflow/SKILL.md) |
| `docs/` | 6 | `maintainer_note.md` (3338 B), `public_api_strategy.md` (3762 B), `examples/{agent_workflow,juno_pds_spice_workflow,mms_magnetopause_workflow,psp_perihelion_solar_wind}.md` |
| `scripts/` | 2 | `smoke_mcp_list_tools.py` (175), `validate_plugin_packages.py` (99) |
| root | 9 | `.gitignore`, `ANATOMY.md` (4899 B), `LICENSE` (1068 B), `README.md` (37,268 B), `pyproject.toml` (3032 B), `server.json` (1461 B), `.github/workflows/ci.yml` (2170 B), `src/`, `tests/` |

**Stray / untracked files (NOT in git):**
- `edge_probe.py`, `edge_probe2.py`, `edge_probe3.py`, `edge_probe4.py`, `verify_pr68.py` — root-level throwaway probe scripts, all `import from spedas_mcp.server` (a module that **does not exist** in this repo; the package is `spedas_agent_kit`). Zero references anywhere in tracked files. Dead. → delete.
- `mth5/` — **empty directory** (0 files), untracked, not in git. Leftover scaffold. → delete.
- `.venv/`, `.pytest_cache/`, `uv.lock` — gitignored (`.gitignore` has `.venv/`, `.pytest_cache/`, `uv.lock`); fine to leave.

---

## 2. SERVER WIRING (`src/spedas_agent_kit/server.py`, read fully)

**One FastMCP instance.** `create_server()` (`server.py:1200`) creates a single `FastMCP("spedas-agent-kit", ...)` and registers every tool on it via `_register_tool()` (`server.py:1228`) with MCP `ToolAnnotations` + `meta.surface` (`primary`/`advanced`/`compat`). CDAWeb/PDS/SPICE are **already merged into this one instance** — there is no separate `cdawebmcp`/`pdsmcp`/`spicemcp` server anywhere. `serve()` (`server.py:3808`) runs stdio with `--cdaweb-cache-dir/--spice-kernel-dir/--pds-cache-dir` overrides; `python -m spedas_agent_kit` → `__main__.py` → `main()` → `serve()`.

### Registered tools → backend/source map

**Base primary tools (17, always registered):**
| Tool | Backend/source |
|---|---|
| `spedas_overview` | self-describing (no backend) |
| `search_spedas_data_sources` | `workflows.search_data_sources` |
| `plan_spedas_observation` | `workflows.plan_observation` |
| `compare_cdaweb_pds_spice` | `workflows.compare_sources` |
| `create_spedas_analysis_bundle` | `workflows.create_analysis_bundle` |
| `browse_data_sources` | routes `source_type`: cdaweb→`backends.cdaweb.catalog.browse_observatories` (+curated OMNI overlay), pds→`backends.pds.catalog.browse_missions`, spice→`backends.spice.list_supported_missions` + frame catalog, hapi/fdsn→metadata-only |
| `load_data_source` | cdaweb→`backends.cdaweb.catalog.load_observatory_json`/`prompts.build_observatory_prompt`, pds→`backends.pds.prompts.build_mission_prompt`, spice→frame catalog |
| `browse_data_parameters` | cdaweb→`backends.cdaweb.metadata.browse_parameters`, pds→`backends.pds.metadata.browse_parameters`, spice→frame catalog |
| `fetch_data_product` | cdaweb→`backends.cdaweb.fetch.fetch_data`, pds→`backends.pds.fetch.fetch_data` (2115-line module), spice→error routing to geometry tools |
| `manage_data_cache` | cdaweb→`backends.cdaweb.cache.*`, pds→`backends.pds.cache.*`, spice→`backends.spice.kernel_manager.KernelManager` |
| `get_ephemeris` / `compute_distance` / `transform_coordinates` | `backends.spice` (`get_state`/`get_trajectory`, `transform_vector`) with #26/#29 preflight |
| `browse_hapi_catalog` / `fetch_hapi_data` | `datasources.hapi` (hapiclient) — **out of CDAWeb/PDS/SPICE scope** |
| `browse_fdsn_datasets` / `fetch_fdsn_data` | `datasources.fdsn` (pyspedas.mth5/mth5/obspy) — **out of scope** |

**Compat tools (8, registered ONLY when `SPEDAS_AGENT_KIT_COMPAT_TOOLS=1`):** `browse_observatories`, `load_observatory`, `browse_parameters`, `fetch_data` (→ cdaweb backend), `browse_pds_missions`, `load_pds_mission`, `browse_pds_parameters`, `fetch_pds_data` (→ pds backend). Hidden by default; used internally by the unified layer (the unified tools call the same underlying functions).

**Analysis tools (13, registered only when the `[analysis]` extras import):** `ANALYSIS_TOOL_NAMES` at `server.py:35-49`: `transform_timeseries_coordinates`, `generate_fac_matrix`, `tvector_rotate`, `analyze_minvar_coordinates`, `dynamic_power_spectrum`, `wavelet_transform`, `evaluate_magnetic_field`, `calculate_lshell`, `build_particle_distribution_artifact`, `load_particle_distribution_artifact`, `compute_particle_moments`, `compute_particle_spectra`, `render_tplot` — each lazily imports `analysis/{coords,spectral,fieldmodels,particles,plotting}`. Gated by `_analysis_dependencies_available()` (`server.py:161`) probing `_ANALYSIS_REQUIRED_IMPORTS` (`server.py:59-84`, submodule-level probes).

**Constants:** `ANALYSIS_TOOL_NAMES` (13, `server.py:35`), `HAPI_TOOL_NAMES = ("browse_hapi_catalog", "fetch_hapi_data")` (`server.py:51`), `FDSN_TOOL_NAMES = ("browse_fdsn_datasets", "fetch_fdsn_data")` (`server.py:52`). `_optional_backend_availability()` (`server.py:188`) reports hapi/fdsn as `always_registered` (return `missing_dependency` error payloads when extras absent) and analysis as `registered_when_available`.

**Defined but NOT registered as MCP tools** (plain functions inside `create_server`; test `test_server_has_expected_tools` asserts they are absent from `list_tools`): `list_spice_missions`, `list_coordinate_frames`, `manage_cdaweb_cache`, `manage_pds_cache`, `manage_spice_kernels`. They are internal helpers for the unified layer.

---

## 3. BACKEND PACKAGES (`src/spedas_agent_kit/backends/`)

- `backends/__init__.py` — **empty (0 lines)**; no package-level exports. (Each sub-backend is a self-contained vendored package with its own `__init__.py`.)

### `backends/cdaweb/` (vendored former `xhelio-cdaweb`/`cdawebmcp`, issue #107; `__init__.py` 13 lines, `__version__ 0.3.0`)
| Module | Lines | Provides |
|---|---|---|
| `fetch.py` | 617 | `fetch_data` (per-dataset param fetch → DataFrames) |
| `cache.py` | 516 | cache_status/clean/refresh_metadata/refresh_time_ranges/rebuild_catalog |
| `validation.py` | 363 | CDF parameter validation |
| `metadata.py` | 240 | `browse_parameters` |
| `catalog.py` | 183 | `browse_observatories`, `load_observatory_json` |
| `config.py` | 120 | cache-dir configure (default `~/.cdawebmcp/`) |
| `prompts.py` | 79 | `build_observatory_prompt` |
| `http.py` | 58 | SPDF/CDF HTTP helpers |
| `scripts/build_catalog.py`, `scripts/build_metadata.py` | 551+234 | catalog/metadata build tooling |
| data | — | 63 observatory JSON, 2 prompts, LICENSE, NOTICE, py.typed |

### `backends/pds/` (vendored former `xhelio-pds`/`pdsmcp`; `__init__.py` 13 lines, `__version__ 0.3.0`)
| Module | Lines | Provides |
|---|---|---|
| `fetch.py` | 2115 | `fetch_data` (archive download + PDS3/PDS4 label parsing) — largest single module in repo |
| `metadata.py` | 782 | `browse_parameters`, label metadata |
| `cache.py` | 629 | cache mgmt + `build_metadata` |
| `label_parser.py` | 305 | PDS label parsing |
| `validation.py` | 289 | schema validation |
| `catalog.py` | 253 | `browse_missions` |
| `config.py` | 38 | cache-dir configure (default `~/.pdsmcp/`) |
| `prompts.py` | 72 | `build_mission_prompt` |
| `http.py` | 51 | HTTP helpers |
| `scripts/` | 692 | build_catalog, build_metadata, validate_schema |
| data | — | 17 mission JSON, 2 prompts, LICENSE, NOTICE |

### `backends/spice/` (vendored `xhelio_spice`; `__init__.py` 116 lines, `__version__ 0.6.1, 87 missions`)
| Module | Lines | Provides |
|---|---|---|
| `missions.py` | 905 | resolve_mission, list_supported_missions, GENERIC/MISSION/SEGMENTED kernel tables |
| `kernel_manager.py` | 584 | KernelManager (download/cache/load), check_remote_kernels |
| `ephemeris.py` | 379 | get_position/get_state/get_trajectory |
| `frames.py` | 278 | transform_vector, list_available_frames, list_frames_with_descriptions, FRAME_ALIASES |
| `manifests/` | 15 JSON | per-mission kernel manifests |
| LICENSE/NOTICE | — | vendored licensing |

**Import verification (repo `.venv`, Python 3.13.1) — ALL PASS:**
```
.venv/bin/python -c "import spedas_agent_kit"                                  → pkg ok 0.1.0
.venv/bin/python -c "from spedas_agent_kit.backends.cdaweb import configure, catalog, fetch, metadata, cache, validation"  → cdaweb ok
.venv/bin/python -c "from spedas_agent_kit.backends.pds import configure, catalog, fetch, metadata, cache, label_parser, validation" → pds ok
.venv/bin/python -c "from spedas_agent_kit.backends.spice import get_state, get_trajectory, transform_vector, list_supported_missions, get_kernel_manager" → spice ok
.venv/bin/python -c "from spedas_agent_kit.server import create_server; m=create_server(include_analysis_tools=False)" → server ok
```

---

## 4. DEAD / STRAY CODE

| Item | What it is | Referenced? | Verdict |
|---|---|---|---|
| `edge_probe.py`, `edge_probe2.py`, `edge_probe3.py`, `edge_probe4.py`, `verify_pr68.py` (root, untracked) | ad-hoc probe scripts, all import nonexistent `spedas_mcp.server` (stale package name; this repo is `spedas_agent_kit`) | **No** (grep across all tracked files: zero hits) | **DELETE** (untracked → plain `rm`; they are not in git) |
| `mth5/` (root) | empty directory, untracked | — | **DELETE** |
| `datasources/hapi.py` (315) + `datasources/fdsn.py` (288) + `datasources/__init__.py` (159) + `datasources/ANATOMY.md` | optional HAPI/FDSN adapters (issues #21/#22), NOT part of CDAWeb/PDS/SPICE | `server.py:3645,3673,3703,3733` (4 lazy imports); `tests/test_datasources_{hapi,fdsn}.py` | **NOT dead** but **out of scope** → remove with their 4 tools (see §6) |
| `analysis/` (4,701 lines incl. `__init__`) | optional pyspedas analysis layer (coords/spectral/fieldmodels/particles/plotting) | `server.py` 13 lazy imports; 5 test files (4,081 lines); CI analysis lane; `ANALYSIS_TOOL_NAMES` | **NOT dead** but **out of scope** → remove or keep-as-extra (see §6) |
| `workflows.py` (1087) | science-workflow planning layer (search/plan/compare/bundle) — part of the primary “A+B” vision | `server.py:1452,1479,1493,1508`; many `test_server.py` cases | **KEEP** (core of the primary MCP) |
| `server.py:2221` `from cdawebmcp.catalog import load_observatory_json` fallback | pre-#111 legacy-layout fallback; the in-tree import (line 2218) always succeeds first | — | dead/unreachable → **remove the fallback lines** (minor) |
| `plugins/` + `.agents/` | in-repo Claude/Codex plugin fixtures + `marketplace.json` + `spedas-agent-kit-compatibility.json` | `scripts/validate_plugin_packages.py`, `tests/test_plugin_skills.py`, CI step | fixtures only; README says canonical wrappers moved to standalone `spedas_claude`/`spedas_codex` repos → **remove** (or keep as intentional fixtures; see §6) |
| `resources/` (24 files, docstring-only `__init__.py`) | packaged shared skills | `tests/test_resources.py`, CI; README calls them canonical | **KEEP** (part of primary MCP deliverable) |

---

## 5. DOCS / PLUGINS — keep vs remove

- `README.md` (37,268 B) — describes the unified one-MCP design (A+B), tool table, guides. **Keep** (trim HAPI/FDSN/analysis sections if those layers go; note tool count 17→13 base changes).
- `ANATOMY.md` (root, 4,899 B) + `src/spedas_agent_kit/ANATOMY.md` + `backends/ANATOMY.md` — structural maps of kept code. **Keep** (update if components are removed).
- `analysis/ANATOMY.md`, `datasources/ANATOMY.md` — **remove** with their components (or keep if layers kept).
- `docs/maintainer_note.md`, `docs/public_api_strategy.md` — both frame the CDAWeb/PDS/SPICE one-layer model; **keep** (edit HAPI/FDSN mentions).
- `docs/examples/` (4 files) — `juno_pds_spice_workflow.md` (6,222 B) and `mms_magnetopause_workflow.md` (7,169 B) directly exercise the CDAWeb+PDS+SPICE merge; **keep all four** (check for HAPI/FDSN/analysis references).
- `plugins/` (33 files) — see §4; `spedas-agent-kit-compatibility.json` documents the 17-tool base surface (would need editing if hapi/fdsn tools are removed).
- `.agents/` (5 files) — Codex fixture; same decision as `plugins/`.
- `LICENSE` (MIT) + per-backend `LICENSE`/`NOTICE.md` (cdaweb/pds/spice) — **keep** (vendored-license hygiene).
- `server.json` (1461 B) — MCP registry manifest; **keep** (it already describes the unified CDAWeb+PDS+SPICE server; remove `hapi`/`fdsn` mentions only if tools removed — currently it doesn’t mention them).

---

## 6. RECOMMENDED CLEANUP (PR branch plan)

### KEEP (everything that serves ONE primary CDAWeb+PDS+SPICE MCP)
```
src/spedas_agent_kit/__init__.py        src/spedas_agent_kit/__main__.py
src/spedas_agent_kit/server.py          src/spedas_agent_kit/workflows.py
src/spedas_agent_kit/ANATOMY.md
src/spedas_agent_kit/backends/          # entire vendored cdaweb/ pds/ spice/ + __init__.py + ANATOMY.md
src/spedas_agent_kit/resources/         # packaged skills (canonical)
tests/test_server.py  tests/test_config.py  tests/test_resources.py
scripts/smoke_mcp_list_tools.py         # FIX first: stale analysis probe + missing tvector_rotate (below)
README.md  LICENSE  pyproject.toml  server.json  .gitignore  .github/workflows/ci.yml
ANATOMY.md  docs/  .venv/ (untracked, fine)
```

### REMOVE (git rm) — peripheral layers outside CDAWeb/PDS/SPICE
```
# HAPI/FDSN datasource layer + its 4 tools
src/spedas_agent_kit/datasources/                  # __init__.py, hapi.py, fdsn.py, ANATOMY.md
tests/test_datasources_hapi.py  tests/test_datasources_fdsn.py
# server.py edits: drop HAPI_TOOL_NAMES, FDSN_TOOL_NAMES, _optional_backend_availability's hapi/fdsn
#   entries, the 4 tool defs (browse_hapi_catalog, fetch_hapi_data, browse_fdsn_datasets,
#   fetch_fdsn_data), hapi/fdsn branches in browse_data_sources/load_data_source/
#   browse_data_parameters/fetch_data_product, and hapi/fdsn aliases in _normalize_source_type
# pyproject.toml: drop [hapi] and [fdsn] extras

# Analysis layer (only if Jason wants it gone; it is optional and gated, so safe to delete)
src/spedas_agent_kit/analysis/                     # 7 files incl. ANATOMY.md
tests/test_analysis_coords.py  tests/test_analysis_fieldmodels.py  tests/test_analysis_particles.py
tests/test_analysis_plotting.py  tests/test_analysis_spectral.py
# server.py edits: delete ANALYSIS_TOOL_NAMES, _ANALYSIS_REQUIRED_IMPORTS,
#   _analysis_dependencies_available, and the include_analysis_tools registration block
# pyproject.toml: drop [analysis] extra; ci.yml: drop the `analysis` job lane

# Plugin fixtures (README says canonical wrappers live in standalone spedas_claude/spedas_codex repos)
plugins/                                            # 33 files (spedas-claude fixture, README, compatibility json)
.agents/                                            # 5 files (spedas-codex fixture, marketplace.json)
scripts/validate_plugin_packages.py  tests/test_plugin_skills.py
# ci.yml: drop the `python scripts/validate_plugin_packages.py` step

# Dead code in server.py
server.py:2221  `from cdawebmcp.catalog import load_observatory_json` fallback (unreachable)
```

### DELETE from working tree (untracked — no git rm needed)
```
rm edge_probe.py edge_probe2.py edge_probe3.py edge_probe4.py verify_pr68.py && rmdir mth5
```

### FIX before the PR (found during audit — verified failures)
1. **`scripts/smoke_mcp_list_tools.py` reports `ok: false` even though the server boots and all tools register.** Root cause: (a) its `_analysis_dependencies_available()` (`smoke:70-97`) probes `pyspedas.particles.spd_part_products` with `hasattr` for `spd_pgs_*`, but those helpers live in per-function *submodules* — `server.py` was already fixed to probe submodules (`server.py:80-83`), the smoke script was not; (b) `ANALYSIS_EXPECTED_TOOLS` omits `tvector_rotate`. Verified live: `.venv/bin/python scripts/smoke_mcp_list_tools.py --json` → `ok: false, tool_count: 30`, the 13 analysis tools listed as `unexpected`. (Not a server bug — the server is correct.)
2. If hapi/fdsn tools are removed, base tool count drops 17 → 13; update `plugins/spedas-agent-kit-compatibility.json` (if kept), README “17 tools” statements, `docs/`, and smoke `BASE_EXPECTED_TOOLS`.

### Validation commands (verified working in this repo today)
```bash
cd /Users/huangzesen/Downloads/spedas_mcp
.venv/bin/python -m pytest -q                                  # full suite; core subset (test_server+config+resources+plugin_skills): 257 passed in ~9s
.venv/bin/python scripts/smoke_mcp_list_tools.py --json        # boots `python -m spedas_agent_kit` over stdio, MCP initialize + list_tools; currently ok:false → fix per above
.venv/bin/python scripts/smoke_mcp_list_tools.py --json --compat-tools   # same with SPEDAS_AGENT_KIT_COMPAT_TOOLS=1 (expects +8 compat tools)
.venv/bin/python -m spedas_agent_kit                            # blocking stdio server (do NOT run in CI; the smoke script covers boot)
```

### Tests inventory (11 files, 14,594 lines)
- `test_server.py` (3,109) — facade surface, unified data-layer dispatch, compat gating, error envelopes, workflows; **the core regression suite for the merged MCP**. Keep.
- `test_config.py` (17) — server construction + gitignore hygiene. Keep.
- `test_resources.py` (21), `test_plugin_skills.py` (21) — packaged skills / plugin fixtures. Keep `test_resources.py`; remove `test_plugin_skills.py` with `plugins/`.
- `test_datasources_{hapi,fdsn}.py` (501) — remove with `datasources/`.
- `test_analysis_*.py` (4,081) — remove with `analysis/` (or keep if the analysis layer stays).

### CI (`.github/workflows/ci.yml`)
- `test` job: py3.10–3.13, `pip install -e ".[dev,mcp]"`, `pytest -q`, `python scripts/validate_plugin_packages.py`, `python scripts/smoke_mcp_list_tools.py --json`.
- `analysis` job: py3.11/3.12, `pip install -e ".[analysis,dev,mcp]"`, runs the 3 real-backend analysis test files.
- Post-cleanup: `test` job loses the `validate_plugin_packages.py` step (if plugins removed); `analysis` job removed (if analysis removed).

---

## Bottom line

The repo is already **one merged MCP** for CDAWeb+PDS+SPICE — the PR is a **deletion + hygiene PR**, not a merge. Minimum safe scope: (1) `rm` the 5 stray probe scripts + empty `mth5/`; (2) decide HAPI/FDSN (recommend remove: out of scope, adds 4 always-advertised tools + 2 extras) and analysis (recommend remove for a lean primary MCP, or keep as optional extra since it is already gated); (3) remove plugin fixtures unless Jason wants them; (4) fix the smoke script probe + `tvector_rotate` omission; (5) update README/docs/pyproject/ci surface numbers; (6) rerun `pytest -q` and the smoke script before merging.
