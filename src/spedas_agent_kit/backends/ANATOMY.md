---
related_files:
  - src/spedas_agent_kit/backends/CONTRACT.md
  - src/spedas_agent_kit/ANATOMY.md
  - src/spedas_agent_kit/server.py
  - src/spedas_agent_kit/backends/cdaweb/__init__.py
  - src/spedas_agent_kit/backends/cdaweb/config.py
  - src/spedas_agent_kit/backends/cdaweb/catalog.py
  - src/spedas_agent_kit/backends/cdaweb/metadata.py
  - src/spedas_agent_kit/backends/cdaweb/fetch.py
  - src/spedas_agent_kit/backends/cdaweb/cache.py
  - src/spedas_agent_kit/backends/pds/__init__.py
  - src/spedas_agent_kit/backends/pds/config.py
  - src/spedas_agent_kit/backends/pds/catalog.py
  - src/spedas_agent_kit/backends/pds/metadata.py
  - src/spedas_agent_kit/backends/pds/fetch.py
  - src/spedas_agent_kit/backends/pds/cache.py
  - src/spedas_agent_kit/backends/pds/label_parser.py
  - src/spedas_agent_kit/backends/spice/__init__.py
  - src/spedas_agent_kit/backends/spice/kernel_manager.py
  - src/spedas_agent_kit/backends/spice/ephemeris.py
  - src/spedas_agent_kit/backends/spice/frames.py
  - src/spedas_agent_kit/backends/spice/missions.py
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
# src/spedas_agent_kit/backends — vendored data backends

## What this is

In-tree copies of ALL data backends the facade dispatches to (issue #107: the
former external `xhelio-*` packages, now fully absorbed so the repo is
self-contained). Each sub-package exposes the library surface
(catalog / metadata / fetch / cache / config) that `server.py` imports lazily;
their former standalone MCP servers/CLIs are dropped — the `spedas_agent_kit`
facade replaces them. The interface each backend must satisfy is the paired
[`src/spedas_agent_kit/backends/CONTRACT.md`](src/spedas_agent_kit/backends/CONTRACT.md).

## Components

- **`cdaweb/`** — vendored CDAWeb backend (was `xhelio-cdaweb`/`cdawebmcp`),
  imported for `source_type="cdaweb"` (`src/spedas_agent_kit/server.py:1329`).
  Anchors: `configure()` at `src/spedas_agent_kit/backends/cdaweb/config.py:32`,
  `get_cache_root()` at `src/spedas_agent_kit/backends/cdaweb/config.py:49`,
  `browse_observatories()` at `src/spedas_agent_kit/backends/cdaweb/catalog.py:45`,
  `browse_parameters()` at `src/spedas_agent_kit/backends/cdaweb/metadata.py:36`,
  `fetch_data()` at `src/spedas_agent_kit/backends/cdaweb/fetch.py:59`,
  `cache_status()`/`cache_clean()` at
  `src/spedas_agent_kit/backends/cdaweb/cache.py:196`/
  `src/spedas_agent_kit/backends/cdaweb/cache.py:230`, `rebuild_catalog()` at
  `src/spedas_agent_kit/backends/cdaweb/cache.py:469`. `data/observatories` +
  `data/prompts` are vendored seed; the large `data/metadata` bundle is
  excluded (regenerable via `scripts/build_metadata.py`, fetched on miss).
- **`pds/`** — vendored PDS PPI backend (was `xhelio-pds`/`pdsmcp`), imported
  for `source_type="pds"` (`src/spedas_agent_kit/server.py:1473`). Same module
  shape as cdaweb plus `label_parser.py` (PDS3/PDS4 ASCII/XML labels).
  Anchors: `browse_missions()` at `src/spedas_agent_kit/backends/pds/catalog.py:99`,
  `fetch_data()` at `src/spedas_agent_kit/backends/pds/fetch.py:90`,
  `cache_status()` at `src/spedas_agent_kit/backends/pds/cache.py:196`,
  `build_metadata()` at `src/spedas_agent_kit/backends/pds/cache.py:536`.
  Deps: pandas/numpy/requests (no cdflib — PDS is ASCII/XML, not CDF).
- **`spice/`** — vendored SPICE/ephemeris backend (was `xhelio-spice`),
  imported for `source_type="spice"` + the geometry tools
  (`src/spedas_agent_kit/server.py:1612`). Anchors: `get_kernel_manager()` at
  `src/spedas_agent_kit/backends/spice/kernel_manager.py:49`, `KernelManager`
  at `src/spedas_agent_kit/backends/spice/kernel_manager.py:61`,
  `download_kernel()` at `src/spedas_agent_kit/backends/spice/kernel_manager.py:99`,
  `check_remote_kernels()` at `src/spedas_agent_kit/backends/spice/kernel_manager.py:570`,
  `get_position()` at `src/spedas_agent_kit/backends/spice/ephemeris.py:152`,
  `get_state()` at `src/spedas_agent_kit/backends/spice/ephemeris.py:209`,
  `get_trajectory()` at `src/spedas_agent_kit/backends/spice/ephemeris.py:275`,
  `FRAME_ALIASES` at `src/spedas_agent_kit/backends/spice/frames.py:25`,
  `transform_vector()` at `src/spedas_agent_kit/backends/spice/frames.py:179`,
  `has_kernels()` at `src/spedas_agent_kit/backends/spice/missions.py:852`.
  `manifests/` vendored; kernels download on-demand to `~/.xhelio_spice/kernels/`
  (none bundled). Deps: spiceypy, numpy, pandas, requests, beautifulsoup4.

## Connections

- **In:** `server.py` tool closures import
  `spedas_agent_kit.backends.cdaweb.{catalog,metadata,fetch,cache,config}` (and
  the pds/spice equivalents) lazily at call time
  (`src/spedas_agent_kit/server.py:1329`, `src/spedas_agent_kit/server.py:1781`,
  `src/spedas_agent_kit/server.py:1829`).
- **Out:** cdaweb → `cdflib`/pandas/numpy/requests + CDAWeb REST/Master-CDF;
  pds → pandas/numpy/requests + PDS PPI archive (ASCII/XML labels via
  `label_parser.py`); spice → spiceypy/numpy/pandas/requests/beautifulsoup4 +
  public NAIF kernel archives.

## Composition

- **Parent:** `src/spedas_agent_kit/`
  ([`src/spedas_agent_kit/ANATOMY.md`](src/spedas_agent_kit/ANATOMY.md)).
- **Paired contract:** `src/spedas_agent_kit/backends/CONTRACT.md`
  (reciprocal).
- **Consuming Core:** `src/spedas_agent_kit/server.py` (the facade).

## State

- cdaweb bootstraps `~/.cdawebmcp/` (metadata, cdf_cache) from vendored seed;
  pds bootstraps `~/.pdsmcp/` (metadata, data_cache); spice keeps
  `~/.xhelio_spice/kernels/` for backward-compatible on-demand NAIF downloads.
  All are managed via `manage_data_cache(source_type=...)`.

## Notes

- Internal imports were rewritten `cdawebmcp.* → spedas_agent_kit.backends.cdaweb.*`.
  The absorption surfaced + fixed a latent bug: the facade called
  `cache_clean(observatory=...)` but the backend takes `observatories=[...]`
  (server.py now maps singular→list).
- #107 COMPLETE: all three backends are vendored; no `xhelio-*` runtime
  dependencies remain. The adapter seam (numpy serialization, unit
  conventions, fill values, probe paths) is the historical bug cluster.
