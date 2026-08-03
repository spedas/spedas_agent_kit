---
name: packaged-skills-resources
contract_version: 1
root_contract: CONTRACT.md
related_files:
  - src/spedas_agent_kit/resources/ANATOMY.md
  - src/spedas_agent_kit/resources/skill_catalog.py
  - src/spedas_agent_kit/resources/event_presets.py
  - src/spedas_agent_kit/resources/provenance.py
  - src/spedas_agent_kit/resources/skills/README.md
  - src/spedas_agent_kit/resources/skills/overview-geomagnetic-indices/SKILL.md
  - src/spedas_agent_kit/resources/skills/spedas-agent-kit-anatomy/SKILL.md
  - src/spedas_agent_kit/resources/skills/spedas-skills-index/SKILL.md
  - src/spedas_agent_kit/resources/skills/spedas-workflow/SKILL.md
  - src/spedas_agent_kit/resources/skills/spice-conjunction-finder/SKILL.md
  - src/spedas_agent_kit/resources/skills/timeseries-cleaning/SKILL.md
  - src/spedas_agent_kit/resources/presets/solar_wind_event_presets.json
  - src/spedas_agent_kit/resources/schemas/analysis_bundle_run.schema.json
  - src/spedas_agent_kit/resources/schemas/reproduction_provenance.schema.json
  - scripts/export_packaged_skills.py
  - tests/test_resources.py
  - tests/test_architecture_documents.py
maintenance: |
  This component contract is governed by the root CONTRACT.md. Keep
  related_files complete and repo-relative, including the paired ANATOMY.md,
  the Port, production Adapters, and contract tests. Update the Port, affected
  Adapters, tests, and this contract together when a boundary or normative
  behavior changes; update the paired Anatomy when structure changes. Follow
  the root Anatomy/Contract pairing and ownership rules, report mismatches,
  and do not duplicate or auto-fix the rule here.
---
# Packaged skills and resources contract

## Purpose and ownership

`src/spedas_agent_kit/resources/` owns the **packaged-skills capability**: the
canonical, runtime-neutral scientific workflow skills plus the event-preset
seeds and provenance schemas that support the facade's artifact discipline.
This component is the single owner of these artifacts — thin runtime wrappers
(Claude Code, Codex, OpenCode) package or sync them via
`scripts/export_packaged_skills.py` rather than reimplementing or forking
scientific workflow knowledge.

The capability surface is read-only: skills, presets, and schemas are
immutable packaged assets exposed through the catalog port; validation
functions read only.

## Public port

**Skill catalog port** (`skill_catalog.py`):

| Operation | Promise |
|---|---|
| `list_packaged_skills()` (`skill_catalog.py:90`) | enumerate every packaged skill as `{name, description, resource_uri}` |
| `read_packaged_skill(name)` (`skill_catalog.py:114`) | return the full SKILL.md text; fail loudly for unknown names |
| `render_skill_index_markdown()` (`skill_catalog.py:122`) | deterministic index of all skills for resource exposure |

**Skill frontmatter and name rules.** Every packaged skill is a directory
under `src/spedas_agent_kit/resources/skills/` containing a `SKILL.md` whose
YAML frontmatter has exactly `name` and `description`. `name` MUST be
kebab-case and MUST equal the directory name (e.g. directory
`spedas-workflow/` → `name: spedas-workflow`). Names MUST be unique across the
catalog. The frontmatter parser is intentionally minimal
(`_parse_frontmatter()` at `skill_catalog.py:36`) — no YAML dependency — so
skills MUST NOT rely on YAML features beyond simple scalar values.

**Event preset port** (`event_presets.py`):
`load_preset_document()` (`event_presets.py:90`), `list_event_presets()`
(`event_presets.py:95`), `get_event_preset()` (`event_presets.py:102`),
`render_event_preset_index_markdown()` (`event_presets.py:122`). Presets are
*documentation-only seeds* sourced from the single canonical JSON
(`presets/solar_wind_event_presets.json`); quality labels and caveat notes
are preserved verbatim and MUST NOT be silently upgraded to curated facts.

**Provenance schema port** (`provenance.py`): the two schemas under
`schemas/` are loaded by `load_provenance_schema()` (`provenance.py:115`) and
`load_analysis_bundle_run_schema()` (`provenance.py:124`) and enforced by
`validate_reproduction_provenance()` (`provenance.py:171`),
`validate_analysis_bundle_run()` (`provenance.py:398`), and
`validate_analysis_bundle_files()` (`provenance.py:661`).

**Artifact discipline.** Validation happens before artifact writes: the
analysis bundle workflow validates request/provenance intent against the
schemas, then writes files; bulk data always goes to disk and only
paths/stats return to the caller.

## Internal composition

- `skill_catalog.py` / `event_presets.py` load assets via
  `importlib.resources` from the packaged `skills/` and `presets/`
  directories; both are dependency-free so base MCP installs can expose the
  resources without extra packages.
- `provenance.py` embeds the JSON schema documents as packaged assets and
  implements schema validation + bundle-file checks in pure Python (no
  `jsonschema` runtime dependency).
- `scripts/export_packaged_skills.py` (`export_skills()` at
  `scripts/export_packaged_skills.py:84`) is the sanctioned copy path into
  runtime wrappers.

## Error semantics

- Unknown skill/preset names fail loudly with a clear error naming the
  available names — never silently return an empty document.
- Schema validation returns structured error lists (field, code, message),
  not exceptions, so the facade can wrap them into the structured error
  envelope (`src/spedas_agent_kit/server.py:329`).
- Frontmatter that violates the minimal-shape rules (missing `name`/
  `description`, non-kebab-case name, name/directory mismatch) is a defect
  that MUST fail catalog rendering rather than being skipped silently.

## Ordering and state

- All operations are read-only and order-independent; the packaged assets are
  immutable at runtime. No cache or persistent state is owned by this
  component.
- `render_*_markdown` functions MUST be deterministic so resource exposure
  and snapshots are stable across runs.

## Contract tests

Focused evidence:

```bash
python -m pytest -q tests/test_resources.py tests/test_architecture_documents.py
```

`tests/test_resources.py` pins the catalog surface, preset accessors, and
schema validation behavior.

## Maintenance

Keep this contract in sync with the paired
[`src/spedas_agent_kit/resources/ANATOMY.md`](src/spedas_agent_kit/resources/ANATOMY.md).
Adding a skill, changing the catalog port, changing the frontmatter rules,
changing a schema, or changing artifact discipline updates this contract,
the affected module/asset, and tests in the same change. Bump
`contract_version` for breaking public changes (per the root CONTRACT.md
versioning rule).
