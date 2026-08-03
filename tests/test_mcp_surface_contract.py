"""Tests for the MCP surface contract checker (issue #209 Workstream J).

Runs the real checker against the checked-in snapshots so accidental drift in
the advertised tool/resource/prompt surface fails CI -- the same gate the CI
step runs -- plus focused unit tests of the canonicalization helpers and the
removal of the dead datasource profile.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKER = REPO_ROOT / "scripts" / "check_mcp_surface_contract.py"
SNAPSHOT_DIR = REPO_ROOT / "tests" / "contracts" / "mcp_surface"


def test_contract_check_passes_against_checked_in_snapshots() -> None:
    """The live MCP surface must match the checked-in contract snapshots."""
    result = subprocess.run(
        [sys.executable, str(CHECKER), "--check"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, (
        "MCP surface contract check failed:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_base_and_compat_snapshots_present() -> None:
    """The two live profiles must have checked-in snapshots."""
    assert (SNAPSHOT_DIR / "base.json").exists()
    assert (SNAPSHOT_DIR / "compat.json").exists()


def test_datasource_profile_removed_with_dead_gate() -> None:
    """The HAPI/FDSN datasource gate is dead; no snapshot may remain."""
    assert not (SNAPSHOT_DIR / "datasource.json").exists()


def _load_checker() -> types.ModuleType:
    """Import the checker script as a module (it lives outside the package)."""
    # The checker imports its sibling ``_smoke_runtime`` helper, so scripts/
    # must be importable (running the script directly puts it on sys.path).
    scripts_dir = REPO_ROOT / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    spec = importlib.util.spec_from_file_location("check_mcp_surface_contract", CHECKER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_checker_no_longer_tracks_datasource_profile() -> None:
    """The dead SPEDAS_AGENT_KIT_DATASOURCE_TOOLS gate must be gone."""
    checker = _load_checker()
    assert "datasource" not in checker.PROFILES
    assert "SPEDAS_AGENT_KIT_DATASOURCE_TOOLS" not in checker._GATE_FLAGS
    assert set(checker.PROFILES) == {"base", "compat"}


def test_canonicalize_tool_projects_core_fields() -> None:
    """Tool canonicalization keeps stable core fields and drops transport noise."""
    checker = _load_checker()
    view = checker.canonicalize_tool(
        {
            "name": "sample_tool",
            "title": "Sample",
            "description": "\n    A tool\n    description\n    ",
            "inputSchema": {"type": "object"},
            "outputSchema": {"type": "object"},
            "annotations": {"readOnlyHint": True},
            "icons": "ignored-transport-field",
        }
    )
    assert view["name"] == "sample_tool"
    # inspect.cleandoc dedents and strips a docstring-style description
    assert view["description"] == "A tool\ndescription"
    assert "icons" not in view


def test_canonicalize_resource_drops_null_metadata_blocks() -> None:
    """Optional metadata blocks are captured only when present."""
    checker = _load_checker()
    view = checker.canonicalize_resource(
        {
            "uri": "spedas://v1/sample",
            "name": "sample",
            "title": "Sample",
            "description": "desc",
            "mimeType": "application/json",
            "annotations": None,
            "_meta": None,
        }
    )
    assert "annotations" not in view
    assert "_meta" not in view
