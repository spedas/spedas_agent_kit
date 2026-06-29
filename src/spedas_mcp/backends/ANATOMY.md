# src/spedas_mcp/backends — vendored data backends

## What this is

In-tree copies of the data backends the facade dispatches to (issue #107: absorb the former external `xhelio-*` packages so the repo is self-contained). Each sub-package exposes a library surface (catalog / metadata / fetch / cache / config) that `server.py` imports; their former standalone MCP servers/CLIs are dropped — the spedas_mcp facade replaces them.

## Components

- **`cdaweb/`** — vendored CDAWeb backend (was `xhelio-cdaweb`/`cdawebmcp`). Modules: `config.py` (cache root + bundled-data bootstrap), `catalog.py` (observatories), `metadata.py` (parameters; local cache → Master-CDF fallback), `fetch.py` (CDF fetch), `cache.py` (status/clean/rebuild), `http.py`, `prompts.py`, `validation.py`, `scripts/` (catalog/metadata builders). `data/observatories` + `data/prompts` are vendored seed; the 23 MB `data/metadata` bundle is excluded (regenerable via `scripts/build_metadata.py`, fetched on-miss). Imported by `server.py` for `source_type="cdaweb"`.
- **`pds/`** — vendored PDS PPI backend (was `xhelio-pds`/`pdsmcp`). Same module shape as cdaweb plus `label_parser.py` (PDS3/PDS4 ASCII/XML labels). `data/missions` (432KB) + `data/prompts` vendored seed; 4.4MB `data/metadata` excluded (regenerable, fetched on-miss). Imported by `server.py` for `source_type="pds"`. Deps: pandas/numpy/requests (no cdflib — PDS is ASCII/XML, not CDF).
- **`spice/`** — NOT YET vendored; still external (`xhelio-spice`). Final absorption step per #107.

## Connections

- **In:** `server.py` tool closures import `spedas_mcp.backends.cdaweb.{catalog,metadata,fetch,cache,config}`.
- **Out:** cdaweb → `cdflib`/pandas/numpy/requests + CDAWeb REST/Master-CDF; pds → pandas/numpy/requests + PDS PPI archive (ASCII/XML labels via `label_parser`).

## Composition

- **Parent:** `src/spedas_mcp/`.

## State

- cdaweb bootstraps a runtime cache at `~/.cdawebmcp/` (metadata, cdf_cache) from the vendored seed; `manage_data_cache(source_type="cdaweb")` manages it.

## Notes

- Internal imports were rewritten `cdawebmcp.* → spedas_mcp.backends.cdaweb.*`. The absorption surfaced + fixed a latent bug: the facade called `cache_clean(observatory=...)` but the backend takes `observatories=[...]` (server.py now maps singular→list).
- Remaining work (#107): vendor `spice/` the same way (kernel-download gating + `.kernel_manager` submodule) (each its own PR, anatomy updated in the same commit); fold their deps; drop the remaining `xhelio-spice` line.
