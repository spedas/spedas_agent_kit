---
name: spedas-data-backends
contract_version: 1
root_contract: CONTRACT.md
related_files:
  - src/spedas_agent_kit/backends/ANATOMY.md
  - src/spedas_agent_kit/server.py
  - src/spedas_agent_kit/backends/cdaweb/config.py
  - src/spedas_agent_kit/backends/cdaweb/catalog.py
  - src/spedas_agent_kit/backends/cdaweb/metadata.py
  - src/spedas_agent_kit/backends/cdaweb/fetch.py
  - src/spedas_agent_kit/backends/cdaweb/cache.py
  - src/spedas_agent_kit/backends/pds/config.py
  - src/spedas_agent_kit/backends/pds/catalog.py
  - src/spedas_agent_kit/backends/pds/metadata.py
  - src/spedas_agent_kit/backends/pds/fetch.py
  - src/spedas_agent_kit/backends/pds/cache.py
  - src/spedas_agent_kit/backends/pds/label_parser.py
  - src/spedas_agent_kit/backends/spice/kernel_manager.py
  - src/spedas_agent_kit/backends/spice/ephemeris.py
  - src/spedas_agent_kit/backends/spice/frames.py
  - src/spedas_agent_kit/backends/spice/missions.py
  - tests/test_server.py
  - tests/test_catalog_coverage.py
maintenance: |
  This component contract is governed by the root CONTRACT.md. Keep
  related_files complete and repo-relative, including the paired ANATOMY.md,
  the Port, production Adapters, and contract tests. Update the Port, affected
  Adapters, tests, and this contract together when a boundary or normative
  behavior changes; update the paired Anatomy when structure changes. Follow
  the root Anatomy/Contract pairing and ownership rules, report mismatches,
  and do not duplicate or auto-fix the rule here.
---
# Data backend Port contract

## Purpose and ownership

`src/spedas_agent_kit/backends/` owns the **source_type data Port**: the
catalog / metadata / fetch / cache / config surface that the facade (Core)
depends on. The three vendored sub-packages are the production Adapters that
implement that Port against concrete providers: `cdaweb` (NASA CDAWeb REST /
Master-CDF), `pds` (PDS PPI archive, ASCII/XML labels), and `spice` (public
NAIF kernel archives via `spiceypy`). Each adapter is a self-contained package
with no dependency on the other adapters or on the facade; the facade is the
only consumer.

Ownership rule: the Port contract lives here; the facade
(`src/spedas_agent_kit/server.py`) must depend only on this surface, and the
adapters must not import the facade. Concrete technology identity (CDAWeb,
PDS PPI, NAIF, `cdflib`/`spiceypy`) stays inside the adapters and never leaks
into Core vocabulary beyond the `source_type` string.

## Public port

**Unified `source_type` contract.** Every data-layer call reaches exactly one
backend selected by the normalized `source_type` in
`cdaweb | pds | spice | all` (`_normalize_source_type`, `src/spedas_agent_kit/server.py:1852`).
Each adapter MUST expose the following library surface (function names may
vary per adapter; the observable behavior is normative):

| Surface | cdaweb | pds | spice | Promise |
|---|---|---|---|---|
| config | `configure()`/`get_cache_root()` (`cdaweb/config.py:32`, `cdaweb/config.py:49`) | `configure()`/`get_cache_root()` (`pds/config.py:8`, `pds/config.py:24`) | kernel dir via `KernelManager` (`kernel_manager.py:61`) | deterministic cache roots; one-time bootstrap from vendored seed |
| catalog | `browse_observatories()` (`cdaweb/catalog.py:45`) | `browse_missions()` (`pds/catalog.py:99`) | `list_supported_missions()` / frame lists (`spice/__init__.py`) | enumerate the discoverable universe without network (seed-backed) |
| metadata | `browse_parameters()` (`cdaweb/metadata.py:35`) | `browse_parameters()` (`pds/metadata.py:59`) | frame/body resolution (`frames.py:260`, `missions.py`) | describe parameters/bodies for a dataset or target |
| fetch | `fetch_data()` (`cdaweb/fetch.py:59`) | `fetch_data()` (`pds/fetch.py:90`) | `get_position()`/`get_state()`/`get_trajectory()` (`ephemeris.py:152`, `ephemeris.py:209`, `ephemeris.py:275`) | fetch requested range; write artifacts; never raise raw provider errors |
| cache | `cache_status()`/`cache_clean()`/`refresh_metadata()`/`rebuild_catalog()` (`cdaweb/cache.py:196`, `cdaweb/cache.py:230`) | same surface (`pds/cache.py:196`, `pds/cache.py:536`) | `get_kernel_manager()`/`check_remote_kernels()` (`kernel_manager.py:49`, `kernel_manager.py:570`) | status / clean / refresh / rebuild for the cache root |

**Cache root paths.** Adapters MUST bootstrap and manage exactly these
user-home cache roots (never repo or cwd): `~/.cdawebmcp/` (cdaweb),
`~/.pdsmcp/` (pds), `~/.xhelio_spice/kernels/` (spice — kept for
backward-compatible on-demand NAIF downloads).

**Artifact I/O shape.** Fetch surfaces write data files (CSV/JSON) into the
caller-supplied output directory and return a JSON-serializable summary
containing `status` and `file_path` plus compact stats — bulk data never
returns inline. Per-parameter failures are classified, not thrown, so the
facade can wrap them into the structured error envelope without scraping
tracebacks.

## Internal composition

Each adapter is composed of small, focused modules (config / catalog /
metadata / fetch / cache, plus pds `label_parser.py` and spice
`kernel_manager.py`/`ephemeris.py`/`frames.py`/`missions.py`). Internal
imports are adapter-local; the adapter `__init__.py` files re-export the
public library surface (e.g. `spice/__init__.py`). The spice adapter keeps a
thread-safe `KernelManager` singleton (`get_kernel_manager`, `kernel_manager.py:49`)
so concurrent geometry calls serialize kernel loads.

## Error semantics

- Adapters MUST NOT raise raw provider exceptions through the Port.
  Provider/HTTP/label failures are returned as classified per-parameter or
  per-request errors (message + code) that the facade wraps verbatim into the
  structured `{status, code, message, hint}` envelope.
- Adapter messages MUST NOT embed absolute local paths or URLs as the primary
  payload; the facade redacts paths/URLs as a second line of defense
  (`_sanitize_message`, `src/spedas_agent_kit/server.py:306`).
- Cache operations are idempotent where the name says so (`cache_clean`,
  `refresh_*`, `rebuild_catalog`) and MUST return status dictionaries, not
  raise on partially missing cache state.

## Ordering and state

- Catalog/metadata reads prefer bundled seed data; refresh/rebuild operations
  update the runtime cache in place. Reads and writes to the same cache root
  are serialized by the adapter where concurrent access is possible (spice
  kernel loads use `threading.RLock`, `kernel_manager.py:87`).
- Cache state is the only persistent state owned by this component; it is
  created lazily at first use and managed exclusively through the cache
  surface (never by hand-editing files).
- Kernel downloads are gated: the facade only loads kernels on explicit user
  action or configured tool calls; `manage_data_cache(source_type="spice",
  action="load", ...)` (`src/spedas_agent_kit/server.py:2666`) is the
  authorized path.

## Contract tests

Focused evidence:

```bash
python -m pytest -q tests/test_server.py tests/test_catalog_coverage.py \
  tests/test_architecture_documents.py
```

`tests/test_catalog_coverage.py` pins the seed-backed catalog surface;
`tests/test_server.py` exercises the facade→adapter dispatch, cache
management, and artifact I/O shapes.

## Maintenance

Keep this contract in sync with the paired
[`src/spedas_agent_kit/backends/ANATOMY.md`](src/spedas_agent_kit/backends/ANATOMY.md).
Adding or renaming an adapter surface function, changing a cache root, changing
artifact I/O shape, or changing error semantics updates this contract, the
affected adapter, the facade dispatch, and tests in the same change. Bump
`contract_version` for breaking Port changes (per the root CONTRACT.md
versioning rule).
