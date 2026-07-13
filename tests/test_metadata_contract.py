"""Regression tests for the core metadata consistency contract (issue #209, WS-U).

Two surfaces are exercised, both via pure helpers so the tests stay fully
in-memory (no wheel build, no temp dirs, no cleanup primitives):

* ``validate_plugin_packages.check_core_metadata_contract`` — the *source*
  contract cross-checking pyproject, the package ``__version__``, server.json,
  and the declared console entry point. Run in the base CI ``test`` lane by
  ``scripts/validate_plugin_packages.py``.
* ``smoke_installed_artifact.check_installed_metadata_contract`` — the
  *installed-wheel* contract cross-checking the installed distribution
  name/version and imported ``__version__`` against server.json. Run in the CI
  ``wheel`` lane by ``scripts/smoke_installed_artifact.py``.

Each helper returns a list of human-readable mismatch messages (empty == OK), so
the "current metadata passes" and "stale metadata fails with a named field" cases
are both asserted directly.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# The validators live in scripts/ (alongside the sibling smokes); put them on the
# path the same way an operator running `python scripts/...` would.
_SCRIPTS = ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import smoke_installed_artifact as smoke  # noqa: E402
import validate_plugin_packages as validate  # noqa: E402


# --------------------------------------------------------------------------- #
# Synthetic "good" fixtures — deep-copied per test before mutation so cases stay
# independent. Shaped like the parsed pyproject/server.json structures.
# --------------------------------------------------------------------------- #
GOOD_PYPROJECT = {
    "project": {
        "name": "spedas-agent-kit",
        "version": "0.1.0",
        "scripts": {"spedas-agent-kit": "spedas_agent_kit:main"},
    }
}
GOOD_SERVER = {
    "version": "0.1.0",
    "packages": [
        {
            "registryType": "pypi",
            "identifier": "spedas-agent-kit",
            "version": "0.1.0",
            "transport": {"type": "stdio"},
        }
    ],
}


def _pyproject() -> dict:
    return copy.deepcopy(GOOD_PYPROJECT)


def _server() -> dict:
    return copy.deepcopy(GOOD_SERVER)


# --------------------------------------------------------------------------- #
# The live repository metadata must pass both contracts as-is.
# --------------------------------------------------------------------------- #
def test_repo_source_metadata_satisfies_core_contract():
    pyproject = validate.load_toml(ROOT / "pyproject.toml")
    server_manifest = validate.load_json(ROOT / "server.json")
    init_version = validate.parse_init_version(
        (ROOT / "src" / "spedas_agent_kit" / "__init__.py").read_text(encoding="utf-8")
    )
    errors = validate.check_core_metadata_contract(
        pyproject=pyproject,
        server_manifest=server_manifest,
        init_version=init_version,
    )
    assert errors == [], errors


def test_validate_core_metadata_contract_end_to_end_passes():
    # Exercises the real I/O path (tomllib/json/AST) against the checked-in files.
    validate.validate_core_metadata_contract()  # raises SystemExit on drift


def test_repo_server_metadata_matches_a_wheel_built_from_it():
    # Simulate the installed wheel agreeing with the current server.json: the
    # distribution + imported __version__ equal server.json's declared version.
    server_manifest = validate.load_json(ROOT / "server.json")
    version = server_manifest["version"]
    errors = smoke.check_installed_metadata_contract(
        dist_name="spedas-agent-kit",
        dist_version=version,
        imported_version=version,
        server_manifest=server_manifest,
    )
    assert errors == [], errors


# --------------------------------------------------------------------------- #
# parse_init_version — static AST extraction, no import of the package.
# --------------------------------------------------------------------------- #
def test_parse_init_version_reads_string_assignment():
    src = '"""doc"""\n__version__ = "9.9.9"\n\ndef main():\n    return None\n'
    assert validate.parse_init_version(src) == "9.9.9"


def test_parse_init_version_requires_a_version():
    with pytest.raises(SystemExit):
        validate.parse_init_version("__all__ = []\n")


# --------------------------------------------------------------------------- #
# Source contract mismatch cases — each must fail and name its surface.
# --------------------------------------------------------------------------- #
def _core_errors(*, pyproject=None, server=None, init_version="0.1.0"):
    return validate.check_core_metadata_contract(
        pyproject=pyproject if pyproject is not None else _pyproject(),
        server_manifest=server if server is not None else _server(),
        init_version=init_version,
    )


def test_core_contract_good_inputs_pass():
    assert _core_errors() == []


def test_core_contract_flags_package_rename():
    pyproject = _pyproject()
    pyproject["project"]["name"] = "spedas-agent-kit-fork"
    errors = _core_errors(pyproject=pyproject)
    assert any("[project].name" in e for e in errors), errors


def test_core_contract_flags_init_version_drift():
    errors = _core_errors(init_version="0.2.0")
    assert any("__version__" in e for e in errors), errors


def test_core_contract_flags_pyproject_version_drift_against_server():
    pyproject = _pyproject()
    pyproject["project"]["version"] = "0.2.0"
    # init still 0.1.0 and server still 0.1.0 -> both drift from the new source truth
    errors = _core_errors(pyproject=pyproject, init_version="0.2.0")
    assert any("server.json top-level version" in e for e in errors), errors


def test_core_contract_flags_server_top_version_drift():
    server = _server()
    server["version"] = "0.9.9"
    errors = _core_errors(server=server)
    assert any("server.json top-level version" in e for e in errors), errors


def test_core_contract_flags_server_package_version_drift():
    server = _server()
    server["packages"][0]["version"] = "0.9.9"
    errors = _core_errors(server=server)
    assert any("pypi package version" in e for e in errors), errors


def test_core_contract_flags_server_identifier_drift():
    server = _server()
    server["packages"][0]["identifier"] = "some-other-dist"
    errors = _core_errors(server=server)
    assert any("identifier" in e for e in errors), errors


def test_core_contract_flags_non_stdio_transport():
    server = _server()
    server["packages"][0]["transport"] = {"type": "http"}
    errors = _core_errors(server=server)
    assert any("transport.type" in e for e in errors), errors


def test_core_contract_flags_missing_pypi_package():
    server = _server()
    server["packages"] = []
    errors = _core_errors(server=server)
    assert any("no pypi package entry" in e for e in errors), errors


def test_core_contract_flags_wrong_console_target():
    pyproject = _pyproject()
    pyproject["project"]["scripts"]["spedas-agent-kit"] = "spedas_agent_kit:other"
    errors = _core_errors(pyproject=pyproject)
    assert any("console" in e.lower() for e in errors), errors


def test_core_contract_flags_missing_console_script():
    pyproject = _pyproject()
    pyproject["project"]["scripts"] = {}
    errors = _core_errors(pyproject=pyproject)
    assert any("console script" in e for e in errors), errors


# --------------------------------------------------------------------------- #
# Installed-wheel contract mismatch cases.
# --------------------------------------------------------------------------- #
def _installed_errors(*, dist_name="spedas-agent-kit", dist_version="0.1.0",
                      imported_version="0.1.0", server=None):
    return smoke.check_installed_metadata_contract(
        dist_name=dist_name,
        dist_version=dist_version,
        imported_version=imported_version,
        server_manifest=server if server is not None else _server(),
    )


def test_installed_contract_good_inputs_pass():
    assert _installed_errors() == []


def test_installed_contract_flags_distribution_rename():
    errors = _installed_errors(dist_name="spedas-agent-kit-fork")
    assert any("distribution name" in e for e in errors), errors


def test_installed_contract_flags_imported_version_drift():
    # Built wheel (pyproject-driven) at 0.1.0 but __init__.__version__ stale at 0.0.9.
    errors = _installed_errors(imported_version="0.0.9")
    assert any("__version__" in e for e in errors), errors


def test_installed_contract_flags_server_top_version_drift():
    server = _server()
    server["version"] = "0.0.9"
    errors = _installed_errors(server=server)
    assert any("server.json top-level version" in e for e in errors), errors


def test_installed_contract_flags_server_identifier_drift():
    server = _server()
    server["packages"][0]["identifier"] = "some-other-dist"
    errors = _installed_errors(server=server)
    assert any("identifier" in e for e in errors), errors


def test_installed_contract_flags_server_package_version_drift():
    server = _server()
    server["packages"][0]["version"] = "0.0.9"
    errors = _installed_errors(server=server)
    assert any("pypi package version" in e for e in errors), errors
