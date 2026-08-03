# TESTFIX_REPORT — one-MCP cleanup test fixes (branch clean/merge-three-mcps)

## Result

- `pytest tests/ -q` → **504 passed, 0 failed** (was 489 passed / 15 failed).
- `scripts/smoke_mcp_list_tools.py --json` → `ok: true`, `tool_count: 13`.
- `scripts/smoke_mcp_list_tools.py --json --compat-tools` → `ok: true`, `tool_count: 21`.
- `scripts/check_mcp_surface_contract.py` → `OK profile=base tools=13`, `OK profile=compat tools=21`.
- `grep -rn 'include_analysis_tools|optional_backends|SPEDAS_AGENT_KIT_DATASOURCE_TOOLS' tests/` → empty.
- No commit/push made; merge left in progress (worktree state otherwise untouched).

## Tests changed

### tests/test_server.py (8 previously failing tests + 2 cleanups)

1. `test_public_server_manifest_advertises_gate_env_flags` — the `plugins/spedas-agent-kit-compatibility.json`
   file no longer exists. Rewrote to read only `server.json` and assert the public manifest advertises
   exactly one tool gate: `SPEDAS_AGENT_KIT_COMPAT_TOOLS` (no other `SPEDAS_AGENT_KIT_*` gate).
2. `test_server_exposes_packaged_skills_as_mcp_resources` — replaced the stale `spedas-skill://skills/wave-polarization`
   assertion with a surviving skill (`pyspedas-load-planning`).
3. `test_overview_advertises_skill_resources` — skill count bound `>= 22` → `>= 19` (surviving catalog size).
4. `test_build_capability_manifest_is_pure_and_deterministic` — dropped the removed
   `include_analysis_tools` / `datasource_tools_enabled` / `optional_backends` kwargs; the pure builder now
   receives only `package_version`, `tool_surface_pairs`, `compat_tools_enabled`, `packaged_skills`, `event_presets`.
5. `test_build_error_contract_is_pure_and_deterministic` — the mutation-isolation check now mutates
   `scope.not_covered.legacy_cache_tools.tools` (the only remaining mutable list) instead of the removed
   `analysis_tools.codes`.
6. `test_error_contract_scope_is_honest_about_optional_modules` — rewrote to the post-cleanup reality:
   asserts the `analysis/` and `datasources/` packages no longer exist, `scope.not_covered` has no
   `analysis_tools`/`datasource_tools` keys, and the serialized contract contains no `analysis`/`hapi`/`fdsn`
   references (while keeping the legacy-cache/protocol-error disclosures).
7. `test_representative_error_paths_carry_v1_fields_without_leaks` — replaced the HAPI `use_dedicated_tool`
   block with a surviving hint-carrying error path (`fetch_data_product(cdaweb)` missing
   start/stop/output_dir → `invalid_argument` with `suggested_action == hint`).
8. `test_error_contract_vocabulary_matches_emitted_server_codes` — fixed by removing the never-emitted
   `use_dedicated_tool` code from `_PRIMARY_ERROR_CODES` in `src/spedas_agent_kit/server.py` (see judgment calls).
9. Cleanup: removed the unused `_install_hint` import and the now-dead `_emitted_codes_in_package` helper
   (both existed only to serve the removed optional-backend surface).

### Other test files

- `tests/test_resources.py` — `len(skills) >= 22` → `>= 19`.
- `tests/test_export_packaged_skills.py` — `skills_count >= 22` → `>= 19`.
- `tests/test_metadata_contract.py` — unchanged; the four README contract tests were satisfied by restoring
  the honest status/install content to `README.md` (see below).
- `tests/test_event_presets.py` — unchanged; the data-consistency failure was fixed in the preset data (below).

## Data / docs updated (test-driven)

- `src/spedas_agent_kit/resources/presets/solar_wind_event_presets.json` — six preset `skills` references
  pointed at skills deleted in the one-MCP cleanup. Replaced with the closest surviving skills:
  - `solar-wind-turbulence-spectrum` → `solar-wind-turbulence-intermittency` (PSP cascade-rate preset)
  - `magnetopause-lmn-analysis` → `mms-basic-workflows` (3 MMS presets; consistent with the surviving Lavraud preset)
  - `multi-spacecraft-gradients` → `themis-workflows` (Cluster preset; matches its sibling Cluster preset)
  - `neutral-sheet-distance` → dropped (Geotail scout preset keeps `spedas-workflow`)
- `README.md` — restored the honest alpha/source-only contract content that `test_metadata_contract.py` pins:
  CI badge + workflow URL, `Development Status :: 3 - Alpha` / "not published on PyPI" / "pre-1.0" notice,
  and the source-checkout pip commands (`python -m pip install .`, `python -m pip install '.[mcp]'`).
- `tests/contracts/mcp_surface/README.md` — removed the `datasource.json` profile row and the `[analysis]`
  extra paragraph (that profile/gate no longer exists).
- `src/spedas_agent_kit/server.py` — removed the never-emitted `use_dedicated_tool` entry from
  `_PRIMARY_ERROR_CODES` (the published contract must equal the codes the server really emits).

## Snapshot regeneration

None needed. `base.json` and `compat.json` already matched the live server
(`check_mcp_surface_contract.py` passed for both profiles). The `datasource.json` profile was **not**
regenerated (it no longer exists) and its references were removed from `tests/contracts/mcp_surface/README.md`.

## Judgment calls

1. **`use_dedicated_tool` removed from server.py, not just the test.** The vocabulary test requires
   published == emitted; after the HAPI layer was removed the code was published but never emitted, so
   keeping it would have forced a dishonest test exemption. Removing it from the in-code source of truth
   is the minimal honest change (policy item 4: error vocabulary updated to the new reality).
2. **Preset data fixed instead of weakening `test_event_presets.py`.** The failing test is a legitimate
   data-integrity invariant; the stale `skills` references were data drift from the deleted skills, so the
   data was corrected (policy: keep preset tests intact).
3. **README updated instead of weakening `test_metadata_contract.py`.** The four failures were contract
   tests pinning the honest alpha/source-only install story; the merged README had dropped that content.
   Restoring it is accurate (pyproject still declares the alpha classifier, the CI workflow exists, and
   pip-from-checkout works), so the tests were kept intact.
4. **Skill-count bounds `>= 19` (not `== 19`).** Matches the original `>= N` style and the surviving
   19-skill catalog while remaining robust to future additions.
5. **Deleted stale `src/spedas_agent_kit/analysis/` and `src/spedas_agent_kit/datasources/` directories.**
   They contained only untracked, gitignored `__pycache__` bytecode from the removed optional layer
   (no source files, not tracked by git); they are gone so the honest "no optional modules" scope test passes.
6. **Docs not updated.** `docs/examples/solar_wind_event_presets.md` (and a few SKILL.md files) still
   mention the deleted skill names in prose; no test validates them, so they were left as-is (remaining risk).

## Remaining risks

- Prose references to deleted skills remain in `docs/examples/solar_wind_event_presets.md` and in some
  surviving SKILL.md files (cosmetic only; not test-covered).
- The README/skill/preset content changes are unstaged worktree modifications belonging to the in-progress
  merge; they will be picked up when the merge is committed.
