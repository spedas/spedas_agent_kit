"""Focused tests for the pure helpers in scripts/smoke_installed_analysis.py (#209).

The installed-analysis smoke's real I/O — importing the wheel-installed package,
importing the optional analysis backends, and building the default server — only
happens inside the CI analysis-wheel venv and is not simulated here. What *is*
worth pinning without a wheel build is the pure branching logic the smoke relies
on to stay honest:

* ``source_tree_import_error`` — the installed-vs-source guard. A wrong
  containment check would let a ``src/``-tree import silently pass the
  installed-only witness, defeating its entire purpose.
* ``_missing_analysis_tools`` — the set-difference that decides whether the
  registered surface actually contains every canonical analysis tool.

Both are pure over their arguments, so the "accepts good input" and "rejects the
bad case with a named reason" branches are asserted directly, mirroring the
in-memory style of tests/test_metadata_contract.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

# The smoke lives in scripts/ alongside its siblings; put it on the path the same
# way an operator running `python scripts/...` would (matches test_metadata_contract).
ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import smoke_installed_analysis as smoke  # noqa: E402


# --------------------------------------------------------------------------- #
# source_tree_import_error — installed-vs-source guard.
# --------------------------------------------------------------------------- #
def test_source_tree_guard_skipped_when_no_repo_root():
    # No repo root supplied -> guard disabled, any location is acceptable.
    assert smoke.source_tree_import_error("/anywhere/site-packages/spedas_agent_kit/__init__.py", None) is None


def test_source_tree_guard_accepts_installed_location(tmp_path):
    repo_root = tmp_path / "checkout"
    (repo_root / "src").mkdir(parents=True)
    installed = tmp_path / "venv" / "site-packages" / "spedas_agent_kit" / "__init__.py"
    assert smoke.source_tree_import_error(str(installed), repo_root) is None


def test_source_tree_guard_rejects_source_tree_import(tmp_path):
    repo_root = tmp_path / "checkout"
    src_pkg = repo_root / "src" / "spedas_agent_kit"
    src_pkg.mkdir(parents=True)
    pkg_file = src_pkg / "__init__.py"
    error = smoke.source_tree_import_error(str(pkg_file), repo_root)
    assert error is not None
    # The message must name the offending location so the failure is actionable.
    assert "repository source tree" in error
    assert str(pkg_file.resolve()) in error


def test_source_tree_guard_accepts_sibling_of_src(tmp_path):
    # A path that merely shares a prefix with <repo>/src but is not beneath it
    # (e.g. <repo>/src-build/...) must NOT be rejected: relative_to, not string
    # prefix, decides containment.
    repo_root = tmp_path / "checkout"
    (repo_root / "src").mkdir(parents=True)
    sibling = repo_root / "src-build" / "spedas_agent_kit" / "__init__.py"
    sibling.parent.mkdir(parents=True)
    assert smoke.source_tree_import_error(str(sibling), repo_root) is None


# --------------------------------------------------------------------------- #
# _missing_analysis_tools — canonical-surface completeness check.
# --------------------------------------------------------------------------- #
def test_missing_analysis_tools_empty_when_all_present():
    expected = ("a", "b", "c")
    registered = ["z", "a", "b", "c", "y"]  # superset is fine
    assert smoke._missing_analysis_tools(registered, expected) == []


def test_missing_analysis_tools_reports_absent_in_declared_order():
    expected = ("a", "b", "c", "d")
    registered = ["a", "c"]
    # Preserves the canonical declaration order of the missing names.
    assert smoke._missing_analysis_tools(registered, expected) == ["b", "d"]


def test_missing_analysis_tools_all_absent():
    expected = ("a", "b")
    assert smoke._missing_analysis_tools([], expected) == ["a", "b"]
