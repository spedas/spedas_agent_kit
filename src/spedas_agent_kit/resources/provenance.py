"""Dependency-free validation for Agent Kit provenance records.

The Agent Kit ships canonical, machine-readable provenance schemas for
paper-reproduction records and analysis-bundle ``provenance/run.json`` records.
This module loads those schemas and validates candidate objects against the
small shape invariants that Agent Kit wrappers and smoke scripts need.

The validation is deliberately **dependency-free** (no ``jsonschema`` /
``pydantic``), matching the project's hand-rolled, dependency-light idiom
(``skill_catalog._parse_frontmatter``, ``server._validate_fetch_time_range``).
The existing run-record validator checks *shape* only — required top-level
keys, sentinel schema/version hints, array slots, and path-ish string fields;
the filesystem-aware bundle validator additionally checks recorded local paths.
Neither helper asserts that an analysis is scientifically correct; callers must
not read a ``valid: true`` result as an endorsement of science quality.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
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


def _portable_relative_path_error(value: str) -> str | None:
    """Return a non-portability error code for ``value``, or ``None`` if portable.

    ``provenance/run.json`` fields such as ``plan_path`` and ``artifact_dirs.*``
    must stay bundle-relative so a relocated or copied bundle remains
    self-describing. This is a pure string check (no filesystem access, no
    ``pathlib`` resolution) so it works identically regardless of the host OS
    and never depends on whether the referenced path currently exists.

    Classification priority: the specific non-relative-root codes (UNC,
    Windows drive, POSIX absolute) and ``parent_traversal`` are always
    reported first, even when the value also has a generic normalization
    problem (e.g. a UNC path with trailing whitespace is reported as
    ``unc_path``, not ``untrimmed_whitespace``). Only once a value has none
    of those specific problems do the generic *normalized POSIX* checks run:
    no backslashes, no leading/trailing whitespace, no internal ``.``
    segments, no doubled separators, and no trailing separator. A value that
    only becomes portable after normalization (e.g.
    ``"requests\\spedas_plan.json"`` or ``"requests//spedas_plan.json/"``) is
    still rejected, so callers cannot silently rely on implicit normalization.
    """
    if not value:
        return "empty_or_dot_only_path"
    stripped = value.strip()
    if not stripped or stripped.replace(".", "") == "":
        # Empty, whitespace-only, or dot-only ("." / ".." / "...") values
        # carry no usable relative location, regardless of surrounding
        # whitespace.
        return "empty_or_dot_only_path"
    normalized = stripped.replace("\\", "/")
    if normalized.startswith("//"):
        # UNC paths (``\\server\share`` or its forward-slash form ``//server/share``).
        return "unc_path"
    if normalized.startswith("/"):
        return "posix_absolute_path"
    if len(normalized) >= 2 and normalized[1] == ":" and normalized[0].isalpha():
        # Windows drive paths (``C:\...`` / ``C:/...``), with or without a
        # trailing separator (a bare ``C:`` is still drive-rooted).
        return "windows_drive_path"
    segments = normalized.split("/")
    if any(segment == ".." for segment in segments):
        return "parent_traversal"
    # From here the value has no non-relative root and no traversal segment,
    # so any remaining problem is a generic normalization defect rather than
    # one of the specific classifications above.
    if value != stripped:
        return "untrimmed_whitespace"
    if "\\" in value:
        # Backslashes anywhere (not just a leading UNC/drive marker) are not
        # normalized POSIX separators, even if the value is otherwise relative.
        return "non_posix_separator"
    if any(segment == "" for segment in segments):
        # Doubled ("a//b") or trailing ("a/") separators.
        return "doubled_or_trailing_separator"
    if any(segment == "." for segment in segments):
        return "internal_dot_segment"
    return None


def _validate_artifact_records(
    artifacts: Any, errors: list[dict[str, str]]
) -> None:
    """Validate the portable path contract for analysis-bundle artifacts."""
    if not isinstance(artifacts, list):
        return
    for index, artifact in enumerate(artifacts):
        field = f"artifacts[{index}]"
        if not isinstance(artifact, dict):
            _add_error(
                errors,
                field,
                "wrong_type",
                f"{field} must be an object",
            )
            continue
        if "path" not in artifact:
            _add_error(
                errors,
                f"{field}.path",
                "missing_required_key",
                f"{field}.path is required",
            )
            continue
        path = artifact["path"]
        if not isinstance(path, str):
            _add_error(
                errors,
                f"{field}.path",
                "wrong_type",
                f"{field}.path must be a string",
            )
            continue
        portability_error = _portable_relative_path_error(path)
        if portability_error is not None:
            _add_error(
                errors,
                f"{field}.path",
                portability_error,
                (
                    f"{field}.path must be a normalized, bundle-relative POSIX "
                    f"path (got {path!r})"
                ),
            )


def validate_analysis_bundle_run(obj: Any) -> dict[str, Any]:
    """Validate the *shape* of an analysis-bundle ``provenance/run.json`` record.

    Returns a structured dict::

        {"valid": bool, "errors": [{"field": str, "code": str, "message": str}, ...]}

    The check is intentionally shape-only and dependency-free. A ``valid: True``
    result asserts that the record carries the required run-scaffold keys, the
    expected Agent Kit schema/version hint, string path-ish fields for the seeded
    bundle locations, and array slots for ``tool_calls``, ``artifacts``, and
    ``caveats``. ``plan_path``, every present ``artifact_dirs.*`` value (not
    just the five required names), and every recorded ``artifacts[].path``
    value must also be normalized, bundle-relative POSIX paths: empty/dot-only
    values, POSIX absolute paths,
    Windows drive paths, UNC paths, ``..`` parent-traversal segments,
    backslashes, leading/trailing whitespace, internal ``.`` segments, and
    doubled/trailing separators are all rejected — a value that would only
    become portable after normalization is not accepted as-is. It does
    **not** assert the analysis is scientifically complete or that
    referenced artifact paths currently exist.
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

    plan_path = obj.get("plan_path")
    if isinstance(plan_path, str):
        portability_error = _portable_relative_path_error(plan_path)
        if portability_error is not None:
            _add_error(
                errors,
                "plan_path",
                portability_error,
                (
                    "plan_path must be a normalized, bundle-relative POSIX path "
                    f"(got {plan_path!r})"
                ),
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

    _validate_artifact_records(obj.get("artifacts"), errors)

    artifact_dirs = obj.get("artifact_dirs")
    if isinstance(artifact_dirs, dict):
        # First, the five required bundle-scaffold directory names must be
        # present at all (independent of whatever else the caller appended).
        for name in ANALYSIS_BUNDLE_RUN_REQUIRED_ARTIFACT_DIRS:
            if artifact_dirs.get(name) is None:
                _add_error(
                    errors,
                    f"artifact_dirs.{name}",
                    "missing_required_key",
                    f"artifact_dirs.{name} is required",
                )
        # Then, every *present* value (the five required names plus any
        # extra keys a caller appended) must be a portable relative path.
        # This intentionally covers keys beyond the required five so a
        # caller cannot smuggle a non-portable absolute path in under a
        # custom artifact_dirs name.
        for name, value in artifact_dirs.items():
            if value is None:
                # Required null values already receive the historical
                # ``missing_required_key`` error above.  Extra null values must
                # still be rejected as a type mismatch, matching the packaged
                # schema's string-only ``additionalProperties`` contract.
                if name not in ANALYSIS_BUNDLE_RUN_REQUIRED_ARTIFACT_DIRS:
                    _add_error(
                        errors,
                        f"artifact_dirs.{name}",
                        "wrong_type",
                        f"artifact_dirs.{name} must be a string",
                    )
                continue
            if not isinstance(value, str):
                _add_error(
                    errors,
                    f"artifact_dirs.{name}",
                    "wrong_type",
                    f"artifact_dirs.{name} must be a string",
                )
                continue
            portability_error = _portable_relative_path_error(value)
            if portability_error is not None:
                _add_error(
                    errors,
                    f"artifact_dirs.{name}",
                    portability_error,
                    (
                        f"artifact_dirs.{name} must be a normalized, "
                        f"bundle-relative POSIX path (got {value!r})"
                    ),
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


def _resolved_bundle_reference(
    bundle_root: Path,
    value: str,
) -> tuple[Path | None, str | None]:
    """Resolve a portable record path and classify containment failures."""
    # The shape validator has already rejected absolute, traversal, and
    # non-POSIX paths. Splitting explicitly on ``/`` keeps this filesystem
    # check independent of the host's path separator as well.
    candidate = bundle_root.joinpath(*value.split("/"))
    try:
        resolved = candidate.resolve(strict=False)
    except (OSError, RuntimeError):
        return None, "path_resolution_error"
    try:
        resolved.relative_to(bundle_root)
    except ValueError:
        return None, "path_outside_bundle"
    return resolved, None


def _check_bundle_reference(
    bundle_root: Path,
    field: str,
    value: Any,
    expected_kind: str,
    errors: list[dict[str, str]],
) -> None:
    """Check one recorded path for existence, containment, and kind."""
    if not isinstance(value, str):
        # Shape validation normally catches this; retaining a defensive guard
        # keeps the filesystem helper exception-free for malformed callers.
        _add_error(errors, field, "wrong_type", f"{field} must be a string")
        return
    resolved, containment_error = _resolved_bundle_reference(bundle_root, value)
    if containment_error is not None:
        if containment_error == "path_resolution_error":
            message = (
                f"{field} could not be resolved under the supplied bundle root "
                f"(got {value!r})"
            )
        else:
            message = (
                f"{field} resolves outside the supplied bundle root "
                f"(got {value!r})"
            )
        _add_error(errors, field, containment_error, message)
        return
    assert resolved is not None
    if not resolved.exists():
        _add_error(
            errors,
            field,
            "missing_path",
            f"{field} does not exist under the supplied bundle root (got {value!r})",
        )
        return
    if expected_kind == "file" and not resolved.is_file():
        _add_error(
            errors,
            field,
            "wrong_kind",
            f"{field} must resolve to a file (got {value!r})",
        )
    elif expected_kind == "directory" and not resolved.is_dir():
        _add_error(
            errors,
            field,
            "wrong_kind",
            f"{field} must resolve to a directory (got {value!r})",
        )


def validate_analysis_bundle_files(
    bundle_dir: str | Path,
    run_record: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate an analysis bundle's recorded files and directories locally.

    This helper first applies :func:`validate_analysis_bundle_run`, preserving
    its dependency-free shape and normalized-path contract. It then checks the
    recorded plan file, every ``artifact_dirs`` directory, and every artifact
    record's ``path`` (which denotes a file) under ``bundle_dir``. References are
    resolved before containment is tested, so a symlink that points outside the
    bundle cannot pass merely because its textual path is relative. No files are
    modified and no unrecorded files are scanned.

    When ``run_record`` is omitted, the helper reads
    ``bundle_dir/provenance/run.json``. A caller may supply an already-loaded
    mapping to avoid reading it again (for example, immediately after updating
    a record). All malformed input and filesystem failures are returned as
    structured errors rather than escaping as exceptions.
    """
    errors: list[dict[str, str]] = []
    record: Any = run_record
    shape_validation: dict[str, Any] | None = None
    if record is not None:
        if isinstance(record, Mapping) and not isinstance(record, dict):
            # ``validate_analysis_bundle_run`` intentionally retains its
            # historical plain-dict input contract; normalize only the outer
            # mapping here.
            record = dict(record)
        shape_validation = validate_analysis_bundle_run(record)
        if not shape_validation["valid"]:
            return shape_validation

    bundle_path = Path(bundle_dir).expanduser()
    if not bundle_path.exists():
        _add_error(
            errors,
            "bundle_dir",
            "missing_bundle",
            f"bundle directory does not exist: {bundle_dir!s}",
        )
        return {"valid": False, "errors": errors}
    if not bundle_path.is_dir():
        _add_error(
            errors,
            "bundle_dir",
            "wrong_kind",
            f"bundle_dir must be a directory: {bundle_dir!s}",
        )
        return {"valid": False, "errors": errors}

    try:
        bundle_root = bundle_path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        _add_error(
            errors,
            "bundle_dir",
            "path_resolution_error",
            f"could not resolve bundle directory {bundle_dir!s}: {exc}",
        )
        return {"valid": False, "errors": errors}
    if record is None:
        run_path = bundle_root / "provenance" / "run.json"
        if not run_path.is_file():
            _add_error(
                errors,
                "provenance/run.json",
                "missing_run_record",
                f"analysis bundle run record does not exist: {run_path}",
            )
            return {"valid": False, "errors": errors}
        try:
            record = json.loads(run_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            _add_error(
                errors,
                "provenance/run.json",
                "malformed_run_record",
                f"could not read analysis bundle run record: {exc}",
            )
            return {"valid": False, "errors": errors}
        shape_validation = validate_analysis_bundle_run(record)
        if not shape_validation["valid"]:
            return shape_validation

    _check_bundle_reference(
        bundle_root,
        "plan_path",
        record["plan_path"],
        "file",
        errors,
    )
    for name, relative_dir in record["artifact_dirs"].items():
        _check_bundle_reference(
            bundle_root,
            f"artifact_dirs.{name}",
            relative_dir,
            "directory",
            errors,
        )
    for index, artifact in enumerate(record["artifacts"]):
        _check_bundle_reference(
            bundle_root,
            f"artifacts[{index}].path",
            artifact["path"],
            "file",
            errors,
        )
    return {"valid": not errors, "errors": errors}
