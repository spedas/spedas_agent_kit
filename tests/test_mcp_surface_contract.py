"""Tests for the MCP surface contract checker and its checked-in snapshots.

Two layers are exercised on purpose:

* Pure-logic unit tests build synthetic listing objects and assert the
  canonicalization, deterministic ordering, noise exclusion, diff rendering, and
  update/check behavior directly -- no server, no snapshot files.
* One real-stdio integration test per profile launches the actual MCP server and
  asserts the live, canonicalized surface equals the committed snapshot. That is
  what prevents this suite from merely testing the checker against itself: the
  pure tests pin the transform, the integration tests pin the transform *against
  the real server and the committed contract*.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# The checker lives in scripts/ (alongside the sibling smokes); put it on the
# path the same way an operator running `python scripts/...` would.
_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import check_mcp_surface_contract as contract  # noqa: E402
from spedas_agent_kit.optional_backends import ANALYSIS_TOOL_NAMES  # noqa: E402

# Sentinel so fixtures can distinguish "argument not supplied" (use the default
# non-null block) from an explicit ``None`` (assert the block is elided).
_MISSING = object()


# --------------------------------------------------------------------------- #
# Synthetic fixtures: shaped like mcp `.model_dump(mode="json", by_alias=True)`
# output -- note the real wire key is `_meta`, not `meta` -- with deliberately
# injected noise fields the contract must drop.
# --------------------------------------------------------------------------- #

def _tool_dump(name="demo_tool", description="Summary line.", *, surface="primary", required=None, annotations=_MISSING, meta=_MISSING):
    return {
        "name": name,
        "title": None,
        "description": description,
        "inputSchema": {
            "type": "object",
            "title": f"{name}Arguments",
            "properties": {"a": {"type": "string"}, "b": {"type": "integer"}},
            "required": list(required if required is not None else ["a"]),
        },
        "outputSchema": {"type": "object", "properties": {"result": {"type": "string"}}, "required": ["result"]},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "title": None} if annotations is _MISSING else annotations,
        # Real MCP wire key (serialization alias of the SDK's `meta` field):
        "_meta": {"surface": surface} if meta is _MISSING else meta,
        # Noise that must NOT survive canonicalization:
        "icons": None,
        "execution": None,
    }


def _resource_dump(uri="spedas-skill://index", name="idx", *, annotations=None, meta=_MISSING):
    return {
        "uri": uri,
        "name": name,
        "title": "A Title",
        "description": "A resource description.",
        "mimeType": "text/markdown",
        "_meta": {"surface": "spedas_skill", "kind": "index"} if meta is _MISSING else meta,
        # Optional annotation block; None by default so it is elided.
        "annotations": annotations,
        # Noise that must NOT survive canonicalization:
        "size": 12345,
        "icons": None,
    }


def _template_dump(uri_template="spedas-skill://skills/{name}", name="skill", *, annotations=None, meta=_MISSING):
    return {
        "uriTemplate": uri_template,
        "name": name,
        "title": "A Template",
        "description": "A template description.",
        "mimeType": "text/markdown",
        "_meta": {"surface": "spedas_skill"} if meta is _MISSING else meta,
        "annotations": annotations,
        "icons": None,
    }


def _prompt_dump(name="demo_prompt", *, meta=_MISSING):
    return {
        "name": name,
        "title": None,
        "description": "A prompt description.",
        "arguments": [{"name": "arg", "description": "an arg", "required": True}],
        "_meta": {"surface": "spedas_prompt"} if meta is _MISSING else meta,
        "icons": None,
    }


# --------------------------------------------------------------------------- #
# Text normalization (the cross-Python-version guarantee).
# --------------------------------------------------------------------------- #

def test_norm_text_collapses_indented_and_dedented_docstrings():
    """A <=3.12 (indented) and a 3.13+ (dedented) docstring must normalize equal.

    This is the property that lets a single snapshot satisfy the whole CI Python
    matrix; it is asserted directly rather than by running two interpreters.
    """
    pre_313 = "Summary.\n\n        Detail line one.\n        Detail line two.\n        "
    post_313 = "Summary.\n\nDetail line one.\nDetail line two."
    assert contract._norm_text(pre_313) == contract._norm_text(post_313)
    assert contract._norm_text(pre_313) == "Summary.\n\nDetail line one.\nDetail line two."
    assert contract._norm_text(None) is None


# --------------------------------------------------------------------------- #
# Canonicalization / noise exclusion.
# --------------------------------------------------------------------------- #

def test_canonicalize_tool_keeps_only_allowlisted_fields():
    view = contract.canonicalize_tool(_tool_dump(required=["a", "b"]))
    assert set(view) == set(contract._TOOL_CORE) | {"annotations", "_meta"}
    # Transport/presentation noise dropped.
    assert "icons" not in view
    assert "execution" not in view
    # Contract essentials retained, including required.
    assert view["name"] == "demo_tool"
    assert view["inputSchema"]["required"] == ["a", "b"]
    # The real wire key is `_meta`, never the SDK-internal `meta`.
    assert view["_meta"] == {"surface": "primary"}
    assert "meta" not in view
    assert view["annotations"]["readOnlyHint"] is True


def test_canonicalize_tool_normalizes_description_whitespace():
    dump = _tool_dump(description="Summary.\n\n        Indented detail.\n        ")
    assert contract.canonicalize_tool(dump)["description"] == "Summary.\n\nIndented detail."


def test_canonicalize_resource_excludes_size_and_coerces_uri():
    view = contract.canonicalize_resource(_resource_dump())
    # Default fixture has null annotations -> elided; _meta present under wire key.
    assert set(view) == set(contract._RESOURCE_CORE) | {"_meta"}
    assert "size" not in view  # populated byte size is runtime noise
    assert "icons" not in view
    assert "annotations" not in view  # None optional block elided
    assert "meta" not in view and view["_meta"] == {"surface": "spedas_skill", "kind": "index"}
    assert isinstance(view["uri"], str)
    assert view["uri"] == "spedas-skill://index"


def test_nonnull_resource_annotations_survive_but_null_is_elided():
    kept = contract.canonicalize_resource(_resource_dump(annotations={"audience": ["user"], "priority": 0.5}))
    assert kept["annotations"] == {"audience": ["user"], "priority": 0.5}
    elided = contract.canonicalize_resource(_resource_dump(annotations=None))
    assert "annotations" not in elided


def test_nonnull_template_annotations_survive_but_null_is_elided():
    kept = contract.canonicalize_resource_template(_template_dump(annotations={"audience": ["assistant"]}))
    assert kept["annotations"] == {"audience": ["assistant"]}
    assert isinstance(kept["uriTemplate"], str)
    elided = contract.canonicalize_resource_template(_template_dump(annotations=None))
    assert "annotations" not in elided


def test_prompt_preserves_nonnull_meta_under_wire_key_but_elides_null():
    kept = contract.canonicalize_prompt(_prompt_dump(meta={"surface": "spedas_prompt"}))
    assert kept["_meta"] == {"surface": "spedas_prompt"}
    assert "meta" not in kept
    assert kept["arguments"] == [{"name": "arg", "description": "an arg", "required": True}]
    elided = contract.canonicalize_prompt(_prompt_dump(meta=None))
    assert "_meta" not in elided


# --------------------------------------------------------------------------- #
# Snapshot assembly: ordering, analysis filtering, empty collections.
# --------------------------------------------------------------------------- #

def test_build_profile_snapshot_filters_optional_analysis_tools():
    analysis_name = ANALYSIS_TOOL_NAMES[0]
    tools = [_tool_dump(name="browse_data_sources"), _tool_dump(name=analysis_name, surface="advanced")]
    snap = contract.build_profile_snapshot("base", {}, tools, [], [], [])
    names = [t["name"] for t in snap["tools"]]
    assert analysis_name not in names
    assert names == ["browse_data_sources"]
    assert snap["excludes_optional_analysis_tools"] is True


def test_build_profile_snapshot_orders_deterministically_regardless_of_input_order():
    tools = [_tool_dump(name="zeta"), _tool_dump(name="alpha"), _tool_dump(name="mu")]
    resources = [_resource_dump(uri="spedas-skill://z"), _resource_dump(uri="spedas-skill://a")]
    forward = contract.build_profile_snapshot("base", {}, tools, resources, [], [])
    shuffled = contract.build_profile_snapshot(
        "base", {}, list(reversed(tools)), list(reversed(resources)), [], []
    )
    assert [t["name"] for t in forward["tools"]] == ["alpha", "mu", "zeta"]
    assert [r["uri"] for r in forward["resources"]] == ["spedas-skill://a", "spedas-skill://z"]
    # Input order must not affect the rendered bytes at all.
    assert contract.render_snapshot(forward) == contract.render_snapshot(shuffled)


def test_build_profile_snapshot_emits_explicit_empty_prompts_and_templates():
    snap = contract.build_profile_snapshot("base", {}, [_tool_dump()], [], [], [])
    assert snap["prompts"] == []
    assert snap["resource_templates"] == []
    assert snap["env"] == {}


def test_env_flags_are_recorded_per_profile():
    snap = contract.build_profile_snapshot(
        "compat", {"SPEDAS_AGENT_KIT_COMPAT_TOOLS": "1"}, [_tool_dump()], [], [], []
    )
    assert snap["env"] == {"SPEDAS_AGENT_KIT_COMPAT_TOOLS": "1"}
    assert snap["profile"] == "compat"


# --------------------------------------------------------------------------- #
# Rendering + diff.
# --------------------------------------------------------------------------- #

def test_render_snapshot_is_sorted_newline_terminated_and_idempotent():
    snap = contract.build_profile_snapshot("base", {}, [_tool_dump(name="b"), _tool_dump(name="a")], [], [], [])
    text = contract.render_snapshot(snap)
    assert text.endswith("\n")
    # Recursively key-sorted: re-dumping the parsed structure yields the same bytes.
    assert contract.render_snapshot(json.loads(text)) == text
    # Top-level keys sorted.
    assert list(json.loads(text).keys()) == sorted(json.loads(text).keys())


def test_diff_snapshots_produces_readable_unified_diff():
    base = contract.build_profile_snapshot("base", {}, [_tool_dump(description="Old.")], [], [], [])
    drifted = contract.build_profile_snapshot("base", {}, [_tool_dump(description="New.")], [], [], [])
    diff = contract.diff_snapshots(
        contract.render_snapshot(base), contract.render_snapshot(drifted), "base.json"
    )
    assert "--- base.json (checked-in)" in diff
    assert "+++ base.json (live)" in diff
    assert "@@" in diff
    assert '-      "description": "Old."' in diff
    assert '+      "description": "New."' in diff
    # Identical snapshots produce no diff.
    assert contract.diff_snapshots(contract.render_snapshot(base), contract.render_snapshot(base), "base.json") == ""


# --------------------------------------------------------------------------- #
# Update / check behavior, driven through the real `_run` with a stubbed capture
# so no server is launched. This pins the maintainer workflow: update writes the
# named file, a re-check passes, and post-drift check fails with a diff.
# --------------------------------------------------------------------------- #

@pytest.fixture
def _isolated_snapshots(tmp_path, monkeypatch):
    monkeypatch.setattr(contract, "SNAPSHOT_DIR", tmp_path)
    return tmp_path


def _stub_capture(monkeypatch, snapshot):
    monkeypatch.setattr(contract, "capture_profile", lambda profile, module="spedas_agent_kit": (snapshot, []))


def test_update_then_check_roundtrip(_isolated_snapshots, monkeypatch):
    snap = contract.build_profile_snapshot("base", {}, [_tool_dump()], [_resource_dump()], [], [])
    _stub_capture(monkeypatch, snap)

    ok, reports = contract._run(["base"], update=True, module="m")
    assert ok is True
    written = (_isolated_snapshots / "base.json").read_text(encoding="utf-8")
    assert written == contract.render_snapshot(snap)
    assert reports[0]["created"] is True

    ok, reports = contract._run(["base"], update=False, module="m")
    assert ok is True
    assert reports[0]["matched"] is True
    assert "diff" not in reports[0]


def test_check_fails_with_diff_after_drift(_isolated_snapshots, monkeypatch):
    original = contract.build_profile_snapshot("base", {}, [_tool_dump(description="Old.")], [], [], [])
    _stub_capture(monkeypatch, original)
    contract._run(["base"], update=True, module="m")

    drifted = contract.build_profile_snapshot("base", {}, [_tool_dump(description="New.")], [], [], [])
    _stub_capture(monkeypatch, drifted)
    ok, reports = contract._run(["base"], update=False, module="m")

    assert ok is False
    assert reports[0]["matched"] is False
    assert '-      "description": "Old."' in reports[0]["diff"]
    assert '+      "description": "New."' in reports[0]["diff"]


def test_check_reports_missing_snapshot(_isolated_snapshots, monkeypatch):
    snap = contract.build_profile_snapshot("base", {}, [_tool_dump()], [], [], [])
    _stub_capture(monkeypatch, snap)
    ok, reports = contract._run(["base"], update=False, module="m")
    assert ok is False
    assert reports[0]["missing"] is True


def test_update_refuses_in_ci(monkeypatch, capsys):
    monkeypatch.setenv("CI", "true")
    # The CI guard returns before any capture, so no stub/server is needed.
    assert contract.main(["--update"]) == 2
    assert "Refusing to --update" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# Capture hygiene: the cache root is unique and NOT created (and never deleted).
# --------------------------------------------------------------------------- #

def test_cache_root_is_unique_and_uncreated():
    import tempfile as _tempfile

    a = contract._cache_root("base")
    b = contract._cache_root("base")
    assert a != b  # PID + random keeps launches from colliding
    assert not a.exists() and not b.exists()  # never created by the checker
    assert str(a).startswith(_tempfile.gettempdir())
    assert "base" in a.name


# --------------------------------------------------------------------------- #
# Integration: real stdio surface vs. committed snapshot, one per profile.
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("profile", sorted(contract.PROFILES))
def test_live_surface_matches_checked_in_snapshot(profile):
    """The real server's canonicalized surface equals the committed snapshot.

    Analysis tools are filtered by the checker, so this passes whether or not the
    optional [analysis] extra is installed in the interpreter running the test.
    """
    path = contract.snapshot_path(profile)
    assert path.exists(), f"missing committed snapshot for profile {profile!r}: {path}"
    snapshot, _filtered = contract.capture_profile(profile)
    live_text = contract.render_snapshot(snapshot)
    expected_text = path.read_text(encoding="utf-8")
    if live_text != expected_text:
        diff = contract.diff_snapshots(expected_text, live_text, path.name)
        pytest.fail(
            f"live MCP surface drifted from {path}. Refresh with "
            f"`python scripts/check_mcp_surface_contract.py --update` if intentional.\n{diff}"
        )
