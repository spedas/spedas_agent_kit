# MCP surface contract snapshots

These JSON files are checked-in snapshots of the SPEDAS Agent Kit **client-facing
MCP surface** — tool names/descriptions/input+output schemas (including
`required`), fixed resources, resource templates, and prompts — captured over the
real MCP stdio protocol. They exist so that accidental drift in the advertised
surface fails CI instead of silently reaching agents (issue #209, Workstream J).

There is one snapshot per environment-gated profile:

| File | Gates set | Surface |
| --- | --- | --- |
| `base.json` | *(none)* | the default 13-tool surface |
| `compat.json` | `SPEDAS_AGENT_KIT_COMPAT_TOOLS=1` | base + 8 legacy CDAWeb/PDS compat tools |

(The one-MCP cleanup removed the optional analysis/hapi/fdsn layer and its
`datasource.json` profile, so only the two profiles above exist.)

## How to refresh (maintainer, intentional changes only)

The checker runs in **check mode by default** and never rewrites snapshots in CI
(it refuses `--update` when `CI` is set). When you intentionally change a tool
description, schema, resource, etc., regenerate the affected snapshot locally and
review the diff before committing:

```bash
# Rewrite all three snapshot files from the live server:
python scripts/check_mcp_surface_contract.py --update

# Or just one profile:
python scripts/check_mcp_surface_contract.py --update --profile base

# Verify the committed snapshots match the live surface (what CI runs):
python scripts/check_mcp_surface_contract.py
```

A refresh produces a plain, reviewable JSON diff. Treat every changed line as an
intentional change to what agents see: confirm the tool/resource is supposed to
have moved, and that no unrelated tool drifted in with it. Do **not** run
`--update` to "make CI green" without reading the diff.

## What is and isn't guaranteed

* This is a **pre-1.0 intentional-drift gate**, not a promise that names, schemas,
  or descriptions never change. It exists so a human reviews every surface change,
  not so the surface is frozen.
* The snapshots are canonicalized to be **reproducible across the CI Python matrix
  and installs**: descriptions are dedented/stripped (Python 3.13 changed docstring
  indentation), objects are sorted deterministically, and runtime noise
  (timestamps, absolute/temp paths, byte sizes, request IDs, icons, transport-only
  fields) is excluded.
* The one-MCP cleanup removed the optional `[analysis]`/`[hapi]`/`[fdsn]` extras
  and their tools, so there is no optional tool surface to exclude; the checker
  still records `"excludes_optional_analysis_tools": true` in each snapshot to
  state that explicitly.

See `scripts/check_mcp_surface_contract.py` for the checker and
`tests/test_mcp_surface_contract.py` for the focused tests (pure canonicalization
tests plus one real-stdio integration test per profile).
