"""Tests for dataset-catalog coverage rendering (GitHub issue #138).

Covers two concerns:
  1. Missing/empty start or stop dates must not render as malformed
     ``Coverage:  to `` strings; unknown coverage is shown explicitly.
  2. Slash-containing PDS3 IDs (e.g. Juno ``JNO-E/J/SS...``) must be
     preserved verbatim in the rendered catalog.
"""

from spedas_agent_kit.backends.cdaweb.catalog import observatory_to_markdown
from spedas_agent_kit.backends.pds.catalog import mission_to_markdown


# --- PDS backend -----------------------------------------------------------


def _pds_mission(datasets: dict) -> dict:
    return {"instruments": {"INST": {"datasets": datasets}}}


def test_pds_empty_start_and_stop_renders_unknown():
    md = mission_to_markdown(
        _pds_mission({"DS1": {"description": "d", "start_date": "", "stop_date": ""}})
    )
    assert "Coverage:  to " not in md
    assert "Coverage: unknown" in md


def test_pds_missing_keys_renders_unknown():
    md = mission_to_markdown(_pds_mission({"DS1": {"description": "d"}}))
    assert "Coverage:  to " not in md
    assert "Coverage: unknown" in md


def test_pds_partial_coverage_uses_unknown_placeholder():
    md = mission_to_markdown(
        _pds_mission({"DS1": {"description": "d", "start_date": "2010", "stop_date": ""}})
    )
    assert "Coverage:  to " not in md
    assert "2010" in md
    assert "unknown" in md


def test_pds_valid_coverage_unchanged():
    md = mission_to_markdown(
        _pds_mission(
            {"DS1": {"description": "d", "start_date": "2010", "stop_date": "2020"}}
        )
    )
    assert "Coverage: 2010 to 2020" in md


def test_pds_preserves_slash_containing_juno_id():
    ds_id = "JNO-E/J/SS-JADE-3-CALIBRATED-V1.0"
    md = mission_to_markdown(
        _pds_mission({ds_id: {"description": "Juno JADE", "start_date": "2011"}})
    )
    assert ds_id in md


# --- CDAWeb backend --------------------------------------------------------


def _cdaweb_obs(datasets: dict) -> dict:
    return {"instruments": {"inst": {"name": "Inst", "datasets": datasets}}}


def test_cdaweb_empty_start_and_stop_renders_unknown():
    md = observatory_to_markdown(
        _cdaweb_obs({"DS1": {"description": "d", "start_date": "", "stop_date": ""}})
    )
    assert "Coverage:  to " not in md
    assert "Coverage: unknown" in md


def test_cdaweb_missing_keys_renders_unknown():
    md = observatory_to_markdown(_cdaweb_obs({"DS1": {"description": "d"}}))
    assert "Coverage:  to " not in md
    assert "Coverage: unknown" in md


def test_cdaweb_valid_coverage_unchanged():
    md = observatory_to_markdown(
        _cdaweb_obs(
            {
                "DS1": {
                    "description": "d",
                    "start_date": "2010-01-01T00:00:00.000Z",
                    "stop_date": "2020-12-31T00:00:00.000Z",
                }
            }
        )
    )
    assert "Coverage: 2010-01-01 to 2020-12-31" in md
