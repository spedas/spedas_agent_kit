---
related_files:
  - src/spedas_agent_kit/resources/CONTRACT.md
  - src/spedas_agent_kit/ANATOMY.md
  - src/spedas_agent_kit/resources/__init__.py
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
maintenance: |
  Keep related_files repo-relative, duplicate-free, and linked to real files.
  Keep this component's ANATOMY.md and CONTRACT.md reciprocal and keep
  parent/child anatomy links bidirectional. Code is the structural source of
  truth: update this anatomy in the same change that moves files, symbols,
  connections, composition, or state. Verify every changed citation and run the
  architecture-document validation before merge. Follow the root
  Anatomy/Contract pairing rule, report mismatches, and do not duplicate or
  auto-fix the rule here.
---
# src/spedas_agent_kit/resources — packaged skills and resources

## What this is

The packaged, runtime-neutral capability resources: the skill catalog (six
canonical shared workflow skills), solar-wind event presets, provenance
schemas, and the read-only accessor modules that expose them to the facade and
to thin runtime wrappers. This is where scientific workflow knowledge lives as
artifacts; the interface promise is the paired
[`src/spedas_agent_kit/resources/CONTRACT.md`](src/spedas_agent_kit/resources/CONTRACT.md).

## Components

- **`skill_catalog.py`** — dependency-free skill catalog helpers:
  `list_packaged_skills()` at
  `src/spedas_agent_kit/resources/skill_catalog.py:90`, `read_packaged_skill()`
  at `src/spedas_agent_kit/resources/skill_catalog.py:114`,
  `render_skill_index_markdown()` at
  `src/spedas_agent_kit/resources/skill_catalog.py:122`. Skills are read from
  the packaged `skills/` directory via `importlib.resources`; frontmatter is
  parsed by the local `_parse_frontmatter()` at
  `src/spedas_agent_kit/resources/skill_catalog.py:36` (no YAML dependency).
- **`event_presets.py`** — accessors for the canonical preset JSON:
  `load_preset_document()` at `src/spedas_agent_kit/resources/event_presets.py:90`,
  `list_event_presets()` at `src/spedas_agent_kit/resources/event_presets.py:95`,
  `get_event_preset()` at `src/spedas_agent_kit/resources/event_presets.py:102`,
  `render_event_preset_index_markdown()` at
  `src/spedas_agent_kit/resources/event_presets.py:122`. Presets are
  documentation-only *seeds* with honest quality labels, not a curated event
  catalog.
- **`provenance.py`** — provenance schema loading + validation:
  `load_provenance_schema()` at `src/spedas_agent_kit/resources/provenance.py:115`,
  `load_analysis_bundle_run_schema()` at
  `src/spedas_agent_kit/resources/provenance.py:124`,
  `validate_reproduction_provenance()` at
  `src/spedas_agent_kit/resources/provenance.py:171`,
  `validate_analysis_bundle_run()` at
  `src/spedas_agent_kit/resources/provenance.py:398`,
  `validate_analysis_bundle_files()` at
  `src/spedas_agent_kit/resources/provenance.py:661`.
- **`skills/`** — the six packaged skills (each `SKILL.md` with `name` +
  `description` frontmatter): `overview-geomagnetic-indices`,
  `spedas-agent-kit-anatomy`, `spedas-skills-index`, `spedas-workflow`,
  `spice-conjunction-finder`, `timeseries-cleaning`. `README.md` documents the
  runtime-wrapper integration workflow.
- **`presets/solar_wind_event_presets.json`** — the single canonical event
  preset seed resource.
- **`schemas/`** — `analysis_bundle_run.schema.json` and
  `reproduction_provenance.schema.json`, loaded and enforced by
  `provenance.py`.
- **`__init__.py`** — package marker; accessor modules are imported directly
  by the facade.

## Connections

- **In:** the facade (`src/spedas_agent_kit/server.py`) imports the accessor
  modules to expose skills/presets as read-only MCP resources and to validate
  analysis-bundle provenance before artifact writes.
- **Out:** `scripts/export_packaged_skills.py` copies the packaged skills into
  runtime wrappers (`export_skills()` at `scripts/export_packaged_skills.py:84`);
  `tests/test_resources.py` pins the catalog surface.

## Composition

- **Parent:** `src/spedas_agent_kit/`
  ([`src/spedas_agent_kit/ANATOMY.md`](src/spedas_agent_kit/ANATOMY.md)).
- **Paired contract:** `src/spedas_agent_kit/resources/CONTRACT.md`
  (reciprocal).
- **Consuming Core:** `src/spedas_agent_kit/server.py` (facade resource
  surface).

## State

- Packaged resources are immutable at runtime: skills, presets, and schemas
  are read-only `importlib.resources` assets; nothing in this component
  writes them. Validation writes nothing — `validate_analysis_bundle_files()`
  (`src/spedas_agent_kit/resources/provenance.py:661`) only checks an existing
  bundle directory against the schema.

## Notes

- The catalog modules are deliberately dependency-free (no YAML parser) so
  base MCP installs can expose skills/presets without extra dependencies;
  frontmatter parsing is intentionally minimal.
- Skills are the canonical capability surface: new scientific workflow
  knowledge lands as a new packaged skill (kebab-case directory + `name`),
  not as a new top-level tool — see
  `src/spedas_agent_kit/resources/CONTRACT.md`.
