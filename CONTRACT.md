---
name: spedas-agent-kit-contract-convention
contract_version: 1
related_files:
  - ANATOMY.md
  - README.md
  - pyproject.toml
  - src/spedas_agent_kit/ANATOMY.md
  - src/spedas_agent_kit/CONTRACT.md
  - src/spedas_agent_kit/backends/ANATOMY.md
  - src/spedas_agent_kit/backends/CONTRACT.md
  - src/spedas_agent_kit/resources/ANATOMY.md
  - src/spedas_agent_kit/resources/CONTRACT.md
  - src/spedas_agent_kit/server.py
  - src/spedas_agent_kit/workflows.py
  - src/spedas_agent_kit/resources/skill_catalog.py
  - src/spedas_agent_kit/resources/provenance.py
  - scripts/check_anatomy_drift.py
  - tests/test_architecture_documents.py
maintenance: |
  This file is the normative root of the distributed code interface definition
  system and the contract-of-contract. Keep the root ANATOMY.md reciprocal. Keep
  each governed child CONTRACT.md linked here exactly once and require every
  child to point back with root_contract: CONTRACT.md and pair with its
  co-located ANATOMY.md. Apply the governed-component pairing and ownership
  rule below; report mismatches and never manufacture or auto-fix empty or
  duplicate Contracts. Change architecture rules, templates, maintenance
  contracts, and validation together. Revalidate all linked pairs whenever
  this convention changes; bump contract_version for a breaking convention
  change.
---
# SPEDAS Agent Kit Contract Convention

## Design principles

These repository-wide design principles are normative for every capability,
Contract, Anatomy, and skill in this repository. Read and apply them before any
change; they stay concise here by design (progressive disclosure).

1. **Artifact-first responses.** Data and workflow tools never return bulk
   arrays or raw tables in the MCP result. They write artifacts to disk
   (`output_dir`/`output_file` or a bundle directory) and return a compact
   `{status, file_path, stats}` envelope. Callers branch on `status` and follow
   `file_path`, never parse free text.
2. **Unified `source_type` dispatch.** One vocabulary — `cdaweb`, `pds`,
   `spice` (plus `all`) — drives the data layer. New data capability lands as a
   `source_type` or a packaged skill, never as a new top-level tool.
   Normalization lives in the facade (`_normalize_source_type`,
   `src/spedas_agent_kit/server.py:1852`).
3. **Backend port isolation.** The facade depends only on each backend's
   catalog / metadata / fetch / cache / config port, imported lazily inside
   tool closures. Backend internals (numpy serialization, fill values, label
   parsing, kernel downloads) never leak past the port or the sanitized
   response envelope.
4. **Packaged skills are the capability surface.** Scientific workflow
   knowledge is packaged as read-only, runtime-neutral skills under
   `src/spedas_agent_kit/resources/skills/`, exposed through the skill catalog
   port, and synced by thin runtime wrappers. Wrappers stay thin; this repo
   owns the science.
5. **Thin wrappers.** Runtime integrations (Claude Code, Codex, OpenCode) are
   thin launchers around the `spedas-agent-kit` server and the packaged
   skills. Any capability that must exist in one place lives here, not in a
   wrapper.

## Purpose

**CONTRACT is the distributed code interface definition system.** Each governed
architectural component keeps a `CONTRACT.md` beside the code whose interface it
owns: Core/use cases, inbound and outbound Ports, Adapters, expected agent
behavior, errors, ordering, state semantics, and conformance tests. Local
contracts link into a graph that an agent can descend from this repository root
to the exact interface promise relevant to a change.

This file is the repository's Ports & Adapters foundation and the **contract of
contract**: the normative meaning, child template, link rules, versioning, and
maintenance contract for that distributed system. Existing specialized
contracts are governed only when this file lists them as children.

[`ANATOMY.md`](ANATOMY.md) is the paired distributed code navigation system. It
describes where code is and how it is composed; this contract defines how a
layer may be used and what it promises. They cross-link instead of duplicating
each other's content.

## Architecture foundation

Normative rules:

1. Components are reasoned about as **Core / Use Cases**, **Ports / Contracts**,
   and **Adapters**. Core owns domain decisions, orchestration, and policy;
   Ports are technology-neutral boundaries owned by Core; Adapters translate
   concrete providers, protocols, SDKs, or filesystems into Ports.
2. The allowed conceptual dependency is `Adapter -> Port <- Core`. Core MUST
   NOT depend on, import, construct, branch on, or name a concrete adapter
   except through the Port.
3. A Port is more than a Python interface: its component `CONTRACT.md` owns
   units, ordering, errors, state domains, and observable guarantees; adapters
   and Core use cases are tested against those same rules.
4. Concrete technology belongs only in the Adapter at the boundary where that
   technology actually varies (CDAWeb REST/Master-CDF, PDS PPI labels, NAIF
   kernel archives, `cdflib`/`spiceypy`). These identities MUST NOT leak up
   through otherwise technology-neutral parent Ports.
5. A Port is earned by an architectural boundary, not by file count.

For this repository:

- **Core** = the MCP facade (`src/spedas_agent_kit/server.py`) plus the
  pure-Python science-planning workflows (`src/spedas_agent_kit/workflows.py`).
  Core owns tool registration, `source_type` dispatch, validation, the
  structured-error contract, artifact discipline, and workflow orchestration.
- **Ports** =
  - the **source_type data port**: a unified catalog / metadata / fetch / cache
    surface keyed by `source_type` in `cdaweb | pds | spice | all`, owned by
    the facade and defined by `src/spedas_agent_kit/backends/CONTRACT.md`;
  - the **skill catalog port**: list / read / render packaged skills, owned by
    the facade and defined by `src/spedas_agent_kit/resources/CONTRACT.md`;
  - the **event preset port** and the **provenance schema port**, also owned by
    `src/spedas_agent_kit/resources/CONTRACT.md`.
- **Adapters** = the vendored backends `src/spedas_agent_kit/backends/cdaweb/`,
  `src/spedas_agent_kit/backends/pds/`, `src/spedas_agent_kit/backends/spice/`,
  which implement the data port against their concrete providers and are wired
  lazily by the facade.

## Behavior

Every contract includes an expected-agent-behavior agreement. Root behavior
rules:

1. Before reasoning about or changing a governed component, agents MUST read
   the nearest `ANATOMY.md` to navigate its code and the paired `CONTRACT.md`
   to learn its interface and behavior promises.
2. Agents MUST traverse YAML `related_files` as the distributed graph and
   repair missing, stale, duplicate, one-way, or orphaned edges they touch.
   They MUST NOT invent a second registry or copy the same normative rule into
   multiple layers.
3. Coding agents MUST keep implementation, the Anatomy/Contract pair, Ports,
   affected Adapters, and contract tests synchronized in the same change
   whenever their governed facts or promises change.
4. Agents MUST keep concrete technology outside Core, wire implementations
   only at the Composition Root (the `create_server` factory,
   `src/spedas_agent_kit/server.py:1044`), and never weaken a written promise
   to match accidental behavior.

## Governed components

The governed component index is the child `CONTRACT.md` list in this file's
`related_files`, each exactly once:

- [`src/spedas_agent_kit/CONTRACT.md`](src/spedas_agent_kit/CONTRACT.md) — the
  package facade component contract (Core): MCP tool surface, artifact-first
  responses, structured errors, `source_type` dispatch, composition.
- [`src/spedas_agent_kit/backends/CONTRACT.md`](src/spedas_agent_kit/backends/CONTRACT.md)
  — the data-backend Port contract (Adapters): the catalog / metadata / fetch /
  cache / config surface every vendored backend (cdaweb, pds, spice) must
  expose, cache roots, and artifact I/O shape.
- [`src/spedas_agent_kit/resources/CONTRACT.md`](src/spedas_agent_kit/resources/CONTRACT.md)
  — the packaged-skills capability contract: skill catalog port, skill
  frontmatter/name rules, index rendering, provenance schema, artifact
  discipline.

A component enters the paired governed system only when its co-located
contract is listed here. Each governed child points back with
`root_contract: CONTRACT.md` and pairs with its co-located `ANATOMY.md`, which
lists the child contract in return.

## Child contract frontmatter

Every governed child contract has exactly these frontmatter keys, in this
order:

1. `name`: non-empty kebab-case identity, unique among root-linked children.
2. `contract_version`: positive YAML integer.
3. `root_contract`: literal repo-relative path `CONTRACT.md`.
4. `related_files`: non-empty duplicate-free list of repo-relative regular
   files — the co-located paired `ANATOMY.md`, the Port, every production
   Adapter, contract tests, and directly relevant component contracts. Paths
   MUST be repository-relative, MUST resolve to real files, MUST NOT contain
   `.` or `..` segments, and MUST use `/` separators.
5. `maintenance`: a concise maintenance note that preserves the root guidance:
   keep `related_files` complete, keep the Anatomy/Contract and ownership links
   reciprocal, and update the pair when structure or normative behavior
   changes.

## Child contract body

Every governed child body has these `##` headings, once and in this order:

1. `## Purpose and ownership`
2. `## Public port`
3. `## Internal composition`
4. `## Error semantics`
5. `## Ordering and state`
6. `## Contract tests`
7. `## Maintenance`

Child contracts describe behavior and maintenance obligations; they do not use
the ANATOMY structural section template and do not require line citations.

## Governed component pairing and ownership

The unit of pairing is a **governed architectural component**, not every
directory. Every governed component MUST have co-located, reciprocal
`ANATOMY.md` and `CONTRACT.md` twins. Do not create an empty or duplicate
Contract merely to make filenames symmetrical.

The twins provide mutual progressive disclosure without copying each other:
Anatomy answers where code lives and how it composes, then points to Contract
for promises and boundaries; Contract states the normative promises, then
points to Anatomy for code locations, composition, and call chains.

A maintainer who finds a pairing or ownership mismatch MUST fail loud and
report it rather than ignore, normalize, or auto-fix it. The report MUST name
the component or directory, the actual `ANATOMY.md`/`CONTRACT.md` pair state,
the violated rule, and a suggested action — the suggestion is not
authorization to create, delete, move, or rewrite files.

Contract-to-contract links are reciprocal when either contract depends on the
other's normative rules. Unrelated children do not link to each other or copy
each other's promises.

## Versioning and maintenance

A breaking Port-contract change — a removed or renamed operation, a changed
domain, units, ordering, error semantics, narrowed guarantee, or newly
required behavior — bumps `contract_version` and updates the Port, affected
Adapters, contract tests, and paired Anatomy in the same change. This root
convention bumps its own `contract_version` for a breaking convention change.

Every code change MUST assess both distributed systems: structure changes
update Anatomy; interface/promise changes update Contract and contract tests;
changes affecting both update the pair together. Code is normally the
structural source of truth for Anatomy; Contract is normative for behavior —
if implementation and a governed contract disagree, treat that as a defect and
do not silently rewrite the promise to match accidental behavior.

## Validation

`tests/test_architecture_documents.py` validates parseable frontmatter (with a
minimal parser — no PyYAML dependency), non-empty duplicate-free safe
repo-relative `related_files`, the reciprocal root Anatomy/Contract link,
governed child `root_contract` and twin pairing, and that root `related_files`
lists every governed child contract exactly once. `scripts/check_anatomy_drift.py`
cheaply checks every `file:line` citation in every ANATOMY.md for missing or
out-of-range targets. Other frontmatter ordering, naming, and version
conventions and Maintenance prose are normative documentation reviewed by
maintainers, while behavioral truth remains in each component's contract tests
and code review.

## Template

```markdown
---
name: <kebab-case-component-name>
contract_version: 1
root_contract: CONTRACT.md
related_files:
  - <repo-relative paired ANATOMY.md>
  - <repo-relative Port file>
  - <repo-relative production Adapter file>
  - <repo-relative contract-test file>
maintenance: |
  This component contract is governed by the root CONTRACT.md. Keep
  related_files complete and repo-relative, including the paired ANATOMY.md,
  Port, production Adapters, and contract tests. Update the Port, affected
  Adapters, tests, and this contract together when a boundary or normative
  behavior changes; update the paired Anatomy when structure changes. Follow
  the root Anatomy/Contract pairing and ownership rules, report mismatches,
  and do not duplicate or auto-fix the rule here.
---
# <Component Name>

## Purpose and ownership

## Public port

## Internal composition

## Error semantics

## Ordering and state

## Contract tests

## Maintenance
```
