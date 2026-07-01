"""Dependency-free validation for Agent Kit provenance records.

The Agent Kit ships canonical, machine-readable provenance schemas for
paper-reproduction records and analysis-bundle ``provenance/run.json`` records.
This module loads those schemas and validates candidate objects against the
small shape invariants that Agent Kit wrappers and smoke scripts need.

The validation is deliberately **dependency-free** (no ``jsonschema`` /
``pydantic``), matching the project's hand-rolled, dependency-light idiom
(``skill_catalog._parse_frontmatter``, ``server._validate_fetch_time_range``).
It checks *shape* only — required top-level keys, sentinel schema/version hints,
array slots, and path-ish string fields. It does **not** assert that a
reproduction or analysis is scientifically correct; callers must not read a
``valid: true`` result as an endorsement of science quality.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from importlib import resources
from typing import Any

_SCHEMA_PACKAGE = "spedas_agent_kit.resources.schemas"
_SCHEMA_FILE = "reproduction_provenance.schema.json"
_ANALYSIS_BUNDLE_RUN_SCHEMA_FILE = "analysis_bundle_run.schema.json"

ANALYSIS_BUNDLE_RUN_SCHEMA_VERSION = "spedas-analysis-bundle-run-v1"
ANALYSIS_BUNDLE_RUN_SCHEMA_URI = "spedas-preset://schemas/analysis_bundle_run"
ANALYSIS_BUNDLE_RUN_SKILL_INDEX_URI = "spedas-skill://index"

# Required top-level keys for a provenance record. Kept in sync with the schema's
# top-level ``required`` array; the test-suite asserts they match so the two
# cannot silently drift.
REQUIRED_TOP_LEVEL_KEYS: tuple[str, ...] = (
    "paper",
    "target",
    "event_assumption",
    "data_plan",
    "environment",
    "status",
)

# Allowed values for ``target.status_label`` (the per-attempt quality label
# documented in paper-reproduction/SKILL.md "Quality labels").
ALLOWED_STATUS_LABELS: tuple[str, ...] = (
    "paper_quality",
    "proxy",
    "candidate_interval",
    "partial_success",
)

# Allowed values for the overall run ``status`` field.
ALLOWED_RUN_STATUS: tuple[str, ...] = (
    "success",
    "partial-success",
    "failed",
)

ANALYSIS_BUNDLE_RUN_REQUIRED_TOP_LEVEL_KEYS: tuple[str, ...] = (
    "schema_version",
    "created_by",
    "created_at",
    "study_name",
    "science_goal",
    "target",
    "start",
    "stop",
    "requested_data_sources",
    "recommended_sources",
    "plan_path",
    "artifact_dirs",
    "resource_hints",
    "tool_calls",
    "artifacts",
    "caveats",
)

ANALYSIS_BUNDLE_RUN_REQUIRED_ARTIFACT_DIRS: tuple[str, ...] = (
    "requests",
    "data",
    "plots",
    "provenance",
    "notes",
)

_ANALYSIS_BUNDLE_RUN_STRING_KEYS: tuple[str, ...] = (
    "created_by",
    "created_at",
    "study_name",
    "science_goal",
    "plan_path",
)

_ANALYSIS_BUNDLE_RUN_ARRAY_KEYS: tuple[str, ...] = (
    "requested_data_sources",
    "recommended_sources",
    "tool_calls",
    "artifacts",
    "caveats",
)


def _load_schema_file(filename: str) -> dict[str, Any]:
    text = (
        resources.files(_SCHEMA_PACKAGE)
        .joinpath(filename)
        .read_text(encoding="utf-8")
    )
    return json.loads(text)


def load_provenance_schema() -> dict[str, Any]:
    """Load and parse the canonical reproduction-provenance JSON schema.

    Returns the schema document as a plain dict. Raises ``json.JSONDecodeError``
    if the packaged schema is malformed (it never should be; a test guards it).
    """
    return _load_schema_file(_SCHEMA_FILE)


def load_analysis_bundle_run_schema() -> dict[str, Any]:
    """Load and parse the canonical analysis-bundle run JSON schema.

    Returns the schema for ``provenance/run.json`` records seeded by
    ``create_spedas_analysis_bundle``. The loader is dependency-free and mirrors
    :func:`load_provenance_schema` so wrappers and smoke scripts can validate
    local run records without adding ``jsonschema``.
    """
    return _load_schema_file(_ANALYSIS_BUNDLE_RUN_SCHEMA_FILE)


def _parse_utc_timestamp(value: str) -> datetime | None:
    """Parse the timestamp styles used by SPEDAS provenance records.

    Paper-reproduction provenance examples and event presets use the
    ``YYYY-MM-DD/hh:mm:ss`` form that PySPEDAS users recognize. The parser also
    accepts common ISO-8601 UTC strings (``...T...Z`` / ``...+00:00``) so callers
    do not have to rewrite already-valid UTC provenance. Returns ``None`` when
    the value is not parseable as an aware or UTC-assumed timestamp.
    """
    candidate = value.strip()
    for fmt in ("%Y-%m-%d/%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(candidate, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    try:
        normalized = candidate.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_trange(value: Any) -> bool:
    """True when ``value`` is a 2-element, parseable, increasing UTC range."""
    if not isinstance(value, list) or len(value) != 2:
        return False
    if not all(isinstance(item, str) and item.strip() for item in value):
        return False
    start = _parse_utc_timestamp(value[0])
    stop = _parse_utc_timestamp(value[1])
    return start is not None and stop is not None and stop > start


def validate_reproduction_provenance(obj: Any) -> dict[str, Any]:
    """Validate the *shape* of a reproduction provenance record.

    Returns a structured dict::

        {"valid": bool, "errors": [{"field": str, "code": str, "message": str}, ...]}

    The check is intentionally shape-only and dependency-free. A ``valid: True``
    result asserts the record carries the required keys, an allowed status label,
    an allowed run status, and a parseable increasing ``event_assumption.trange_utc``. It
    does **not** assert the reproduction is scientifically correct or
    paper-quality.
    """
    errors: list[dict[str, str]] = []

    if not isinstance(obj, dict):
        errors.append(
            {
                "field": "<root>",
                "code": "not_an_object",
                "message": "provenance record must be a JSON object",
            }
        )
        return {"valid": False, "errors": errors}

    # Required top-level keys.
    for key in REQUIRED_TOP_LEVEL_KEYS:
        if key not in obj:
            errors.append(
                {
                    "field": key,
                    "code": "missing_required_key",
                    "message": f"missing required top-level key: {key}",
                }
            )

    # target.status_label
    target = obj.get("target")
    if isinstance(target, dict):
        label = target.get("status_label")
        if label is None:
            errors.append(
                {
                    "field": "target.status_label",
                    "code": "missing_required_key",
                    "message": "target.status_label is required",
                }
            )
        elif label not in ALLOWED_STATUS_LABELS:
            errors.append(
                {
                    "field": "target.status_label",
                    "code": "unknown_status_label",
                    "message": (
                        f"unknown status_label {label!r}; "
                        f"allowed: {', '.join(ALLOWED_STATUS_LABELS)}"
                    ),
                }
            )
    elif "target" in obj:
        errors.append(
            {
                "field": "target",
                "code": "wrong_type",
                "message": "target must be an object",
            }
        )

    # event_assumption.trange_utc
    event = obj.get("event_assumption")
    if isinstance(event, dict):
        trange = event.get("trange_utc")
        if trange is None:
            errors.append(
                {
                    "field": "event_assumption.trange_utc",
                    "code": "missing_required_key",
                    "message": "event_assumption.trange_utc is required",
                }
            )
        elif not _is_trange(trange):
            errors.append(
                {
                    "field": "event_assumption.trange_utc",
                    "code": "malformed_trange",
                    "message": (
                        "event_assumption.trange_utc must be a 2-element list of "
                        "parseable, increasing [start, stop] UTC strings"
                    ),
                }
            )
    elif "event_assumption" in obj:
        errors.append(
            {
                "field": "event_assumption",
                "code": "wrong_type",
                "message": "event_assumption must be an object",
            }
        )

    # status (overall run status)
    status = obj.get("status")
    if status is not None and status not in ALLOWED_RUN_STATUS:
        errors.append(
            {
                "field": "status",
                "code": "unknown_run_status",
                "message": (
                    f"unknown status {status!r}; "
                    f"allowed: {', '.join(ALLOWED_RUN_STATUS)}"
                ),
            }
        )

    return {"valid": not errors, "errors": errors}



def _add_error(errors: list[dict[str, str]], field: str, code: str, message: str) -> None:
    errors.append({"field": field, "code": code, "message": message})


def validate_analysis_bundle_run(obj: Any) -> dict[str, Any]:
    """Validate the *shape* of an analysis-bundle ``provenance/run.json`` record.

    Returns a structured dict::

        {"valid": bool, "errors": [{"field": str, "code": str, "message": str}, ...]}

    The check is intentionally shape-only and dependency-free. A ``valid: True``
    result asserts that the record carries the required run-scaffold keys, the
    expected Agent Kit schema/version hint, string path-ish fields for the seeded
    bundle locations, and array slots for ``tool_calls``, ``artifacts``, and
    ``caveats``. It does **not** assert the analysis is scientifically complete
    or that referenced artifact paths currently exist.
    """
    errors: list[dict[str, str]] = []

    if not isinstance(obj, dict):
        _add_error(
            errors,
            "<root>",
            "not_an_object",
            "analysis bundle run record must be a JSON object",
        )
        return {"valid": False, "errors": errors}

    for key in ANALYSIS_BUNDLE_RUN_REQUIRED_TOP_LEVEL_KEYS:
        if key not in obj:
            _add_error(
                errors,
                key,
                "missing_required_key",
                f"missing required top-level key: {key}",
            )

    if obj.get("schema_version") != ANALYSIS_BUNDLE_RUN_SCHEMA_VERSION:
        _add_error(
            errors,
            "schema_version",
            "wrong_schema_version",
            (
                "schema_version must be "
                f"{ANALYSIS_BUNDLE_RUN_SCHEMA_VERSION!r}"
            ),
        )

    for key in _ANALYSIS_BUNDLE_RUN_STRING_KEYS:
        if key in obj and not isinstance(obj[key], str):
            _add_error(
                errors,
                key,
                "wrong_type",
                f"{key} must be a string",
            )

    # ``target``, ``start``, and ``stop`` may be null when the bundle is only a
    # planning scaffold, but any non-null value should remain string-shaped.
    for key in ("target", "start", "stop"):
        if key in obj and obj[key] is not None and not isinstance(obj[key], str):
            _add_error(
                errors,
                key,
                "wrong_type",
                f"{key} must be a string or null",
            )

    for key in _ANALYSIS_BUNDLE_RUN_ARRAY_KEYS:
        if key in obj and not isinstance(obj[key], list):
            _add_error(
                errors,
                key,
                "wrong_type",
                f"{key} must be an array",
            )

    artifact_dirs = obj.get("artifact_dirs")
    if isinstance(artifact_dirs, dict):
        for name in ANALYSIS_BUNDLE_RUN_REQUIRED_ARTIFACT_DIRS:
            value = artifact_dirs.get(name)
            if value is None:
                _add_error(
                    errors,
                    f"artifact_dirs.{name}",
                    "missing_required_key",
                    f"artifact_dirs.{name} is required",
                )
            elif not isinstance(value, str):
                _add_error(
                    errors,
                    f"artifact_dirs.{name}",
                    "wrong_type",
                    f"artifact_dirs.{name} must be a string",
                )
    elif "artifact_dirs" in obj:
        _add_error(
            errors,
            "artifact_dirs",
            "wrong_type",
            "artifact_dirs must be an object",
        )

    resource_hints = obj.get("resource_hints")
    if isinstance(resource_hints, dict):
        skill_index_uri = resource_hints.get("skill_index_uri")
        if skill_index_uri != ANALYSIS_BUNDLE_RUN_SKILL_INDEX_URI:
            _add_error(
                errors,
                "resource_hints.skill_index_uri",
                "wrong_resource_hint",
                (
                    "resource_hints.skill_index_uri must be "
                    f"{ANALYSIS_BUNDLE_RUN_SKILL_INDEX_URI!r}"
                ),
            )
        provenance_schema_uri = resource_hints.get("provenance_schema_uri")
        if provenance_schema_uri != ANALYSIS_BUNDLE_RUN_SCHEMA_URI:
            _add_error(
                errors,
                "resource_hints.provenance_schema_uri",
                "wrong_resource_hint",
                (
                    "resource_hints.provenance_schema_uri must be "
                    f"{ANALYSIS_BUNDLE_RUN_SCHEMA_URI!r}"
                ),
            )
    elif "resource_hints" in obj:
        _add_error(
            errors,
            "resource_hints",
            "wrong_type",
            "resource_hints must be an object",
        )

    return {"valid": not errors, "errors": errors}
