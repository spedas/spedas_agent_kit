from __future__ import annotations

import copy
import json
import re
import shutil
from importlib import resources
from pathlib import Path

import pytest

from spedas_agent_kit.resources.provenance import (
    ALLOWED_RUN_STATUS,
    ALLOWED_STATUS_LABELS,
    ANALYSIS_BUNDLE_RUN_REQUIRED_ARTIFACT_DIRS,
    ANALYSIS_BUNDLE_RUN_REQUIRED_TOP_LEVEL_KEYS,
    ANALYSIS_BUNDLE_RUN_SCHEMA_URI,
    ANALYSIS_BUNDLE_RUN_SCHEMA_VERSION,
    ANALYSIS_BUNDLE_RUN_SKILL_INDEX_URI,
    REQUIRED_TOP_LEVEL_KEYS,
    load_analysis_bundle_run_schema,
    load_provenance_schema,
    validate_analysis_bundle_files,
    validate_analysis_bundle_run,
    validate_reproduction_provenance,
)


def _valid_provenance() -> dict:
    """A minimal, shape-valid provenance record."""
    return {
        "paper": {"title": "Example", "doi": "10.0/x", "year": 2026},
        "target": {
            "science_question": "test",
            "figure_or_result": "fig 1",
            "status_label": "proxy",
        },
        "event_assumption": {
            "trange_utc": ["2018-11-05/00:00:00", "2018-11-07/00:00:00"],
            "mission": "PSP",
        },
        "data_plan": {
            "source_type": "cdaweb",
            "datasets_or_products": ["PSP_FLD_L2_MAG_RTN_1MIN"],
        },
        "environment": {"python": "3.11"},
        "status": "partial-success",
    }


def test_schema_resource_loads_and_is_valid_json() -> None:
    text = (
        resources.files("spedas_agent_kit.resources.schemas")
        .joinpath("reproduction_provenance.schema.json")
        .read_text(encoding="utf-8")
    )
    schema = json.loads(text)
    assert schema["title"] == "SPEDAS Agent Kit reproduction provenance"
    assert schema["type"] == "object"


def test_load_provenance_schema_matches_constants() -> None:
    schema = load_provenance_schema()
    # Required top-level keys must stay in lockstep with the validator constants.
    assert tuple(schema["required"]) == REQUIRED_TOP_LEVEL_KEYS
    # Status-label enum in the schema mirrors ALLOWED_STATUS_LABELS.
    label_enum = schema["properties"]["target"]["properties"]["status_label"]["enum"]
    assert tuple(label_enum) == ALLOWED_STATUS_LABELS
    status_enum = schema["properties"]["status"]["enum"]
    assert tuple(status_enum) == ALLOWED_RUN_STATUS


def test_validate_accepts_minimal_shape_valid_record() -> None:
    result = validate_reproduction_provenance(_valid_provenance())
    assert result == {"valid": True, "errors": []}


def test_validate_accepts_iso8601_utc_trange() -> None:
    record = _valid_provenance()
    record["event_assumption"]["trange_utc"] = [
        "2018-11-05T00:00:00Z",
        "2018-11-05T01:00:00+00:00",
    ]
    assert validate_reproduction_provenance(record) == {"valid": True, "errors": []}


def test_validate_rejects_missing_required_top_level_keys() -> None:
    record = _valid_provenance()
    del record["data_plan"]
    del record["environment"]
    result = validate_reproduction_provenance(record)
    assert result["valid"] is False
    missing = {e["field"] for e in result["errors"] if e["code"] == "missing_required_key"}
    assert {"data_plan", "environment"} <= missing


def test_validate_rejects_unknown_status_label() -> None:
    record = _valid_provenance()
    record["target"]["status_label"] = "totally_made_up"
    result = validate_reproduction_provenance(record)
    assert result["valid"] is False
    codes = {e["code"] for e in result["errors"]}
    assert "unknown_status_label" in codes


def test_validate_rejects_unknown_run_status() -> None:
    record = _valid_provenance()
    record["status"] = "kinda-worked"
    result = validate_reproduction_provenance(record)
    assert result["valid"] is False
    assert any(e["code"] == "unknown_run_status" for e in result["errors"])


@pytest.mark.parametrize(
    "bad_trange",
    [
        ["2018-11-05/00:00:00"],  # too short
        ["a", "b", "c"],  # too long
        ["", "2018-11-07/00:00:00"],  # empty start
        "2018-11-05/00:00:00",  # not a list
        [1, 2],  # not strings
        ["2018-13-05/00:00:00", "2018-11-07/00:00:00"],  # invalid date
        ["2018-11-07/00:00:00", "2018-11-05/00:00:00"],  # stop before start
        ["2018-11-05/00:00:00", "2018-11-05/00:00:00"],  # zero duration
    ],
)
def test_validate_rejects_malformed_trange(bad_trange) -> None:
    record = _valid_provenance()
    record["event_assumption"]["trange_utc"] = bad_trange
    result = validate_reproduction_provenance(record)
    assert result["valid"] is False
    assert any(e["code"] == "malformed_trange" for e in result["errors"])


def test_validate_rejects_non_object() -> None:
    result = validate_reproduction_provenance("not a dict")
    assert result["valid"] is False
    assert result["errors"][0]["code"] == "not_an_object"


def test_every_allowed_label_validates() -> None:
    for label in ALLOWED_STATUS_LABELS:
        record = _valid_provenance()
        record["target"]["status_label"] = label
        assert validate_reproduction_provenance(record)["valid"] is True
    for status in ALLOWED_RUN_STATUS:
        record = _valid_provenance()
        record["status"] = status
        assert validate_reproduction_provenance(record)["valid"] is True


def test_skill_md_template_labels_match_validator_constants() -> None:
    """Drift guard: the placeholder enums in the SKILL.md provenance template
    must stay in lockstep with the validator's allowed-label constants.

    The SKILL.md JSON block is a human-readable *template* whose ``status_label``
    and ``status`` values are pipe-separated legends (e.g.
    ``"paper_quality | proxy | candidate_interval | partial_success"``), not real
    instance values, so it is not expected to validate clean. Instead we parse
    those legends and assert they enumerate exactly the validator's allowed sets.
    """
    skill = (
        resources.files("spedas_agent_kit.resources")
        .joinpath("skills", "paper-reproduction", "SKILL.md")
        .read_text(encoding="utf-8")
    )
    match = re.search(r"```json\n(.*?)\n```", skill, re.S)
    assert match, "paper-reproduction SKILL.md must contain a fenced json template"
    template = json.loads(match.group(1))

    label_legend = template["target"]["status_label"]
    template_labels = tuple(part.strip() for part in label_legend.split("|"))
    assert template_labels == ALLOWED_STATUS_LABELS

    status_legend = template["status"]
    template_status = tuple(part.strip() for part in status_legend.split("|"))
    assert template_status == ALLOWED_RUN_STATUS

    # And all required top-level keys are present in the template.
    assert set(REQUIRED_TOP_LEVEL_KEYS) <= set(template.keys())


def test_validate_does_not_mutate_input() -> None:
    record = _valid_provenance()
    snapshot = copy.deepcopy(record)
    validate_reproduction_provenance(record)
    assert record == snapshot



def _valid_analysis_bundle_run() -> dict:
    """A minimal, shape-valid analysis-bundle run provenance record."""
    return {
        "schema_version": ANALYSIS_BUNDLE_RUN_SCHEMA_VERSION,
        "created_by": "spedas_agent_kit.create_spedas_analysis_bundle",
        "created_at": "2026-07-01T00:00:00+00:00",
        "study_name": "Example analysis",
        "science_goal": "Validate a solar-wind interval",
        "target": "solar wind",
        "start": "2024-01-01T00:00:00Z",
        "stop": "2024-01-01T00:10:00Z",
        "requested_data_sources": ["cdaweb"],
        "recommended_sources": ["cdaweb"],
        "plan_path": "requests/spedas_plan.json",
        "artifact_dirs": {
            "requests": "requests",
            "data": "data",
            "plots": "plots",
            "provenance": "provenance",
            "notes": "notes",
        },
        "resource_hints": {
            "skill_index_uri": ANALYSIS_BUNDLE_RUN_SKILL_INDEX_URI,
            "provenance_schema_uri": ANALYSIS_BUNDLE_RUN_SCHEMA_URI,
        },
        "tool_calls": [],
        "artifacts": [],
        "caveats": [],
    }


def _materialize_analysis_bundle(tmp_path: Path) -> tuple[Path, dict]:
    """Create the smallest on-disk bundle accepted by the local validator."""
    bundle = tmp_path / "bundle"
    for name in ("requests", "data", "plots", "provenance", "notes"):
        (bundle / name).mkdir(parents=True)
    (bundle / "requests" / "spedas_plan.json").write_text("{}", encoding="utf-8")
    (bundle / "notes" / "artifact.txt").write_text("artifact", encoding="utf-8")
    record = _valid_analysis_bundle_run()
    record["artifacts"] = [{"path": "notes/artifact.txt", "role": "test"}]
    (bundle / "provenance" / "run.json").write_text(
        json.dumps(record), encoding="utf-8"
    )
    return bundle, record


def test_load_analysis_bundle_run_schema_matches_constants() -> None:
    schema = load_analysis_bundle_run_schema()
    assert schema["title"] == "SPEDAS Agent Kit analysis bundle run provenance"
    assert tuple(schema["required"]) == ANALYSIS_BUNDLE_RUN_REQUIRED_TOP_LEVEL_KEYS
    assert schema["properties"]["schema_version"]["enum"] == [
        ANALYSIS_BUNDLE_RUN_SCHEMA_VERSION
    ]
    uri_enum = schema["properties"]["resource_hints"]["properties"][
        "provenance_schema_uri"
    ]["enum"]
    assert uri_enum == [ANALYSIS_BUNDLE_RUN_SCHEMA_URI]
    # plan_path and every artifact_dirs value reference the same bundle-relative
    # path definition, in lockstep with validate_analysis_bundle_run.
    assert schema["properties"]["plan_path"]["$ref"] == "#/definitions/bundleRelativePath"
    assert (
        schema["properties"]["artifact_dirs"]["additionalProperties"]["$ref"]
        == "#/definitions/bundleRelativePath"
    )
    assert schema["properties"]["artifacts"]["items"]["$ref"] == (
        "#/definitions/artifactRecord"
    )
    assert schema["definitions"]["artifactRecord"]["required"] == ["path"]
    assert schema["definitions"]["artifactRecord"]["properties"]["path"]["$ref"] == (
        "#/definitions/bundleRelativePath"
    )


@pytest.mark.parametrize(
    "bad_path",
    [
        "",
        ".",
        "..",
        "   ",
        "/requests/spedas_plan.json",
        "C:\\bundle\\requests\\spedas_plan.json",
        "C:/bundle/requests/spedas_plan.json",
        "\\\\server\\share\\bundle\\requests\\spedas_plan.json",
        "//server/share/bundle/requests/spedas_plan.json",
        "../outside/spedas_plan.json",
        "requests/../../outside/spedas_plan.json",
        # Values only portable after normalization must still be rejected,
        # in lockstep with _portable_relative_path_error.
        "requests\\spedas_plan.json",
        " requests/spedas_plan.json",
        "requests/spedas_plan.json ",
        "requests/./spedas_plan.json",
        "requests//spedas_plan.json",
        "requests/spedas_plan.json/",
    ],
)
def test_packaged_schema_bundle_relative_path_pattern_matches_validator(
    bad_path: str,
) -> None:
    """The packaged schema's ``not``/``anyOf`` patterns must reject exactly the
    same non-portable paths the dependency-free validator rejects, so a
    ``jsonschema``-based caller and the built-in validator agree without
    requiring ``jsonschema`` to be installed for this test to run."""
    schema = load_analysis_bundle_run_schema()
    definition = schema["definitions"]["bundleRelativePath"]
    patterns = [branch["pattern"] for branch in definition["not"]["anyOf"]]
    assert any(re.search(pattern, bad_path) for pattern in patterns), (
        bad_path,
        patterns,
    )
    # Cross-check against the public validator too: every path this test
    # asserts the schema rejects must also be rejected as plan_path by
    # validate_analysis_bundle_run, so the two enforcement paths cannot
    # silently drift apart.
    record = _valid_analysis_bundle_run()
    record["plan_path"] = bad_path
    assert validate_analysis_bundle_run(record)["valid"] is False, bad_path
    artifact_record = _valid_analysis_bundle_run()
    artifact_record["artifacts"] = [{"path": bad_path}]
    assert validate_analysis_bundle_run(artifact_record)["valid"] is False, bad_path


def test_packaged_schema_bundle_relative_path_pattern_accepts_normalized_paths() -> None:
    schema = load_analysis_bundle_run_schema()
    definition = schema["definitions"]["bundleRelativePath"]
    patterns = [branch["pattern"] for branch in definition["not"]["anyOf"]]
    for good_path in (
        "requests/spedas_plan.json",
        "data",
        "provenance/run.json",
        "a/b/c",
        "data/.gitkeep",
    ):
        assert not any(re.search(pattern, good_path) for pattern in patterns), good_path


def test_validate_analysis_bundle_run_accepts_artifact_record_path() -> None:
    record = _valid_analysis_bundle_run()
    record["artifacts"] = [{"path": "notes/artifact.txt", "role": "note"}]
    assert validate_analysis_bundle_run(record) == {"valid": True, "errors": []}


@pytest.mark.parametrize(
    ("artifact", "expected_field", "expected_code"),
    [
        ({}, "artifacts[0].path", "missing_required_key"),
        ({"path": ["notes/artifact.txt"]}, "artifacts[0].path", "wrong_type"),
        ("not-an-object", "artifacts[0]", "wrong_type"),
    ],
)
def test_validate_analysis_bundle_run_rejects_malformed_artifact_record(
    artifact, expected_field: str, expected_code: str
) -> None:
    record = _valid_analysis_bundle_run()
    record["artifacts"] = [artifact]
    result = validate_analysis_bundle_run(record)
    assert result["valid"] is False
    assert result["errors"][0]["field"] == expected_field
    assert result["errors"][0]["code"] == expected_code


def test_validate_analysis_bundle_files_accepts_and_relocates_bundle(tmp_path: Path) -> None:
    bundle, _record = _materialize_analysis_bundle(tmp_path)
    assert validate_analysis_bundle_files(bundle) == {"valid": True, "errors": []}

    relocated = tmp_path / "relocated" / "bundle"
    shutil.copytree(bundle, relocated)
    assert validate_analysis_bundle_files(relocated) == {"valid": True, "errors": []}


def test_validate_analysis_bundle_files_reports_missing_recorded_artifact(
    tmp_path: Path,
) -> None:
    bundle, record = _materialize_analysis_bundle(tmp_path)
    record["artifacts"][0]["path"] = "notes/never-created.txt"
    result = validate_analysis_bundle_files(bundle, record)
    assert result["valid"] is False
    assert any(
        error["field"] == "artifacts[0].path" and error["code"] == "missing_path"
        for error in result["errors"]
    )


def test_validate_analysis_bundle_files_reports_wrong_recorded_kind(
    tmp_path: Path,
) -> None:
    bundle, record = _materialize_analysis_bundle(tmp_path)
    record["artifacts"][0]["path"] = "data"
    result = validate_analysis_bundle_files(bundle, record)
    assert result["valid"] is False
    assert any(
        error["field"] == "artifacts[0].path" and error["code"] == "wrong_kind"
        for error in result["errors"]
    )


def test_validate_analysis_bundle_files_rejects_symlink_escape(tmp_path: Path) -> None:
    bundle, record = _materialize_analysis_bundle(tmp_path)
    outside = tmp_path / "outside-artifact.txt"
    outside.write_text("outside", encoding="utf-8")
    escaped = bundle / "notes" / "escaped.txt"
    try:
        escaped.symlink_to(outside)
    except (NotImplementedError, OSError):
        pytest.skip("symbolic links are unavailable on this filesystem")
    record["artifacts"][0]["path"] = "notes/escaped.txt"
    result = validate_analysis_bundle_files(bundle, record)
    assert result["valid"] is False
    assert any(
        error["field"] == "artifacts[0].path"
        and error["code"] == "path_outside_bundle"
        for error in result["errors"]
    )


def test_validate_analysis_bundle_files_returns_shape_errors_first(tmp_path: Path) -> None:
    bundle, record = _materialize_analysis_bundle(tmp_path)
    record["artifacts"] = [{}]
    result = validate_analysis_bundle_files(bundle, record)
    assert result["valid"] is False
    assert result["errors"] == [
        {
            "field": "artifacts[0].path",
            "code": "missing_required_key",
            "message": "artifacts[0].path is required",
        }
    ]


def test_validate_analysis_bundle_run_accepts_minimal_seed_shape() -> None:
    result = validate_analysis_bundle_run(_valid_analysis_bundle_run())
    assert result == {"valid": True, "errors": []}


def test_validate_analysis_bundle_run_allows_null_planning_fields() -> None:
    record = _valid_analysis_bundle_run()
    record["target"] = None
    record["start"] = None
    record["stop"] = None
    assert validate_analysis_bundle_run(record) == {"valid": True, "errors": []}


def test_validate_analysis_bundle_run_rejects_missing_required_key() -> None:
    record = _valid_analysis_bundle_run()
    del record["plan_path"]
    result = validate_analysis_bundle_run(record)
    assert result["valid"] is False
    assert any(
        e["field"] == "plan_path" and e["code"] == "missing_required_key"
        for e in result["errors"]
    )


def test_validate_analysis_bundle_run_rejects_wrong_schema_version() -> None:
    record = _valid_analysis_bundle_run()
    record["schema_version"] = "old-version"
    result = validate_analysis_bundle_run(record)
    assert result["valid"] is False
    assert any(e["code"] == "wrong_schema_version" for e in result["errors"])


def test_validate_analysis_bundle_run_rejects_wrong_schema_hint() -> None:
    record = _valid_analysis_bundle_run()
    record["resource_hints"]["provenance_schema_uri"] = "spedas-preset://schemas/reproduction_provenance"
    result = validate_analysis_bundle_run(record)
    assert result["valid"] is False
    assert any(
        e["field"] == "resource_hints.provenance_schema_uri"
        and e["code"] == "wrong_resource_hint"
        for e in result["errors"]
    )


@pytest.mark.parametrize("array_key", ["tool_calls", "artifacts", "caveats"])
def test_validate_analysis_bundle_run_rejects_non_array_update_slots(array_key: str) -> None:
    record = _valid_analysis_bundle_run()
    record[array_key] = {"not": "an array"}
    result = validate_analysis_bundle_run(record)
    assert result["valid"] is False
    assert any(
        e["field"] == array_key and e["code"] == "wrong_type"
        for e in result["errors"]
    )


def test_validate_analysis_bundle_run_rejects_missing_artifact_dir() -> None:
    record = _valid_analysis_bundle_run()
    del record["artifact_dirs"]["provenance"]
    result = validate_analysis_bundle_run(record)
    assert result["valid"] is False
    assert any(
        e["field"] == "artifact_dirs.provenance"
        and e["code"] == "missing_required_key"
        for e in result["errors"]
    )
    assert "provenance" in ANALYSIS_BUNDLE_RUN_REQUIRED_ARTIFACT_DIRS


def test_validate_analysis_bundle_run_rejects_path_fields_with_wrong_type() -> None:
    record = _valid_analysis_bundle_run()
    record["plan_path"] = ["requests/spedas_plan.json"]
    record["artifact_dirs"]["data"] = ["data"]
    result = validate_analysis_bundle_run(record)
    assert result["valid"] is False
    assert {"plan_path", "artifact_dirs.data"} <= {
        e["field"] for e in result["errors"] if e["code"] == "wrong_type"
    }


@pytest.mark.parametrize(
    ("bad_path", "expected_code"),
    [
        ("", "empty_or_dot_only_path"),
        (".", "empty_or_dot_only_path"),
        ("..", "empty_or_dot_only_path"),
        ("   ", "empty_or_dot_only_path"),
        ("/requests/spedas_plan.json", "posix_absolute_path"),
        ("C:\\bundle\\requests\\spedas_plan.json", "windows_drive_path"),
        ("C:/bundle/requests/spedas_plan.json", "windows_drive_path"),
        ("\\\\server\\share\\bundle\\requests\\spedas_plan.json", "unc_path"),
        ("//server/share/bundle/requests/spedas_plan.json", "unc_path"),
        ("../outside/spedas_plan.json", "parent_traversal"),
        ("requests/../../outside/spedas_plan.json", "parent_traversal"),
        # Values that are only portable *after* normalization must still be
        # rejected as-is, so callers cannot rely on implicit normalization.
        ("requests\\spedas_plan.json", "non_posix_separator"),
        (" requests/spedas_plan.json", "untrimmed_whitespace"),
        ("requests/spedas_plan.json ", "untrimmed_whitespace"),
        ("requests/./spedas_plan.json", "internal_dot_segment"),
        ("requests//spedas_plan.json", "doubled_or_trailing_separator"),
        ("requests/spedas_plan.json/", "doubled_or_trailing_separator"),
    ],
)
def test_validate_analysis_bundle_run_rejects_non_portable_plan_path(
    bad_path: str, expected_code: str
) -> None:
    record = _valid_analysis_bundle_run()
    record["plan_path"] = bad_path
    result = validate_analysis_bundle_run(record)
    assert result["valid"] is False
    assert any(
        e["field"] == "plan_path" and e["code"] == expected_code
        for e in result["errors"]
    ), result["errors"]


@pytest.mark.parametrize(
    ("bad_path", "expected_code"),
    [
        ("", "empty_or_dot_only_path"),
        ("/data", "posix_absolute_path"),
        ("C:\\bundle\\data", "windows_drive_path"),
        ("\\\\server\\share\\data", "unc_path"),
        ("../data", "parent_traversal"),
        ("data\\nested", "non_posix_separator"),
        (" data", "untrimmed_whitespace"),
        ("data/./nested", "internal_dot_segment"),
        ("data//nested", "doubled_or_trailing_separator"),
        ("data/", "doubled_or_trailing_separator"),
    ],
)
def test_validate_analysis_bundle_run_rejects_non_portable_artifact_dir(
    bad_path: str, expected_code: str
) -> None:
    record = _valid_analysis_bundle_run()
    record["artifact_dirs"]["data"] = bad_path
    result = validate_analysis_bundle_run(record)
    assert result["valid"] is False
    assert any(
        e["field"] == "artifact_dirs.data" and e["code"] == expected_code
        for e in result["errors"]
    ), result["errors"]


@pytest.mark.parametrize(
    ("bad_path", "expected_code"),
    [
        ("/tmp/outside", "posix_absolute_path"),
        ("extra\\nested", "non_posix_separator"),
    ],
)
def test_validate_analysis_bundle_run_rejects_non_portable_extra_artifact_dir_key(
    bad_path: str, expected_code: str
) -> None:
    """Regression for the gap where only the five required artifact_dirs
    names were portability-checked: a caller-appended extra key (beyond
    requests/data/plots/provenance/notes) with a non-portable value must
    still be rejected, matching the schema's ``additionalProperties`` intent
    which already applied ``bundleRelativePath`` to every key."""
    record = _valid_analysis_bundle_run()
    record["artifact_dirs"]["custom_extra"] = bad_path
    result = validate_analysis_bundle_run(record)
    assert result["valid"] is False
    assert any(
        e["field"] == "artifact_dirs.custom_extra" and e["code"] == expected_code
        for e in result["errors"]
    ), result["errors"]


@pytest.mark.parametrize("bad_value", [None, 42])
def test_validate_analysis_bundle_run_rejects_wrong_type_extra_artifact_dir_key(
    bad_value: object,
) -> None:
    record = _valid_analysis_bundle_run()
    record["artifact_dirs"]["custom_extra"] = bad_value
    result = validate_analysis_bundle_run(record)
    assert result["valid"] is False
    assert any(
        e["field"] == "artifact_dirs.custom_extra" and e["code"] == "wrong_type"
        for e in result["errors"]
    ), result["errors"]


def test_validate_analysis_bundle_run_accepts_portable_extra_artifact_dir_key() -> None:
    record = _valid_analysis_bundle_run()
    record["artifact_dirs"]["custom_extra"] = "custom_extra"
    assert validate_analysis_bundle_run(record) == {"valid": True, "errors": []}


def test_validate_analysis_bundle_run_accepts_normalized_relative_paths() -> None:
    record = _valid_analysis_bundle_run()
    record["plan_path"] = "requests/spedas_plan.json"
    record["artifact_dirs"] = {
        "requests": "requests",
        "data": "data",
        "plots": "plots",
        "provenance": "provenance",
        "notes": "notes",
    }
    assert validate_analysis_bundle_run(record) == {"valid": True, "errors": []}


@pytest.mark.parametrize(
    "good_path",
    [
        "requests/spedas_plan.json",
        "data",
        "provenance/run.json",
        "a/b/c",
        "data/.gitkeep",
    ],
)
def test_validate_analysis_bundle_run_accepts_already_normalized_paths(
    good_path: str,
) -> None:
    record = _valid_analysis_bundle_run()
    record["plan_path"] = good_path
    assert validate_analysis_bundle_run(record)["valid"] is True


def test_validate_analysis_bundle_run_rejects_non_object() -> None:
    result = validate_analysis_bundle_run("not a dict")
    assert result["valid"] is False
    assert result["errors"][0]["code"] == "not_an_object"


def test_validate_analysis_bundle_run_does_not_mutate_input() -> None:
    record = _valid_analysis_bundle_run()
    snapshot = copy.deepcopy(record)
    validate_analysis_bundle_run(record)
    assert record == snapshot
