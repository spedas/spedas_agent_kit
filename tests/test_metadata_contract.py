"""Regression tests for the core metadata consistency contract (issue #209, WS-U).

Two surfaces are exercised, both via pure helpers so the tests stay fully
in-memory (no wheel build, no temp dirs, no cleanup primitives):

* a local ``_source_contract`` helper set (tomllib/json/AST over the checked-in
  pyproject.toml, ``__version__``, server.json, and the declared console entry
  point) -- the source contract previously lived in the removed
  ``scripts/validate_plugin_packages.py`` (one-MCP cleanup deleted it, so the
  checks are pinned here instead);
* ``smoke_installed_artifact.check_installed_metadata_contract`` -- the
  *installed-wheel* contract cross-checking the installed distribution
  name/version and imported ``__version__`` against server.json.

A third group (issue #209, WS-Y) pins the *honest Alpha / source-only installation*
contract: the live ``pyproject.toml`` Alpha classifier, and the ``README.md``
status notice, real CI badge, official source-checkout install path, and
source-relative extras. These assertions are pure text/TOML reads over the
checked-in files -- no wheel build, temp dir, subprocess, or network -- and they
reject the old public-index ``pip install spedas-agent-kit...`` command form so
future drift back toward "looks published on PyPI" fails CI.
"""
from __future__ import annotations

import ast
import copy
import json
import re
import sys
from pathlib import Path

import pytest

try:
    import tomllib
except ImportError:  # pragma: no cover - Python < 3.11
    tomllib = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parents[1]

# Put scripts/ on the path the same way an operator running `python scripts/...` would.
_SCRIPTS = ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import smoke_installed_artifact as smoke  # noqa: E402


# --------------------------------------------------------------------------- #
# Source-contract helpers (replaces the deleted scripts/validate_plugin_packages.py).
# --------------------------------------------------------------------------- #


def _load_toml(path: Path) -> dict:
    if tomllib is None:  # pragma: no cover
        raise RuntimeError("tomllib required")
    with open(path, "rb") as fh:
        return tomllib.load(fh)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_init_version(source: str) -> str:
    """Extract ``__version__ = "..."`` statically via AST (no import)."""
    tree = ast.parse(source)
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "__version__"
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            return node.value.value
    raise SystemExit("no __version__ string assignment found")


def _check_core_metadata_contract(*, pyproject: dict, server_manifest: dict, init_version: str) -> list:
    """Return human-readable mismatch messages tying source metadata together."""
    errors: list = []
    project = pyproject.get("project", {})
    dist_name = project.get("name")
    if dist_name != "spedas-agent-kit":
        errors.append("[project].name must be 'spedas-agent-kit'")
    pyproject_version = project.get("version")
    if init_version != "0.1.0":
        errors.append("__version__ must match the release version")
    server_version = server_manifest.get("version")
    if pyproject_version and server_version and pyproject_version != server_version:
        errors.append("server.json top-level version must equal [project].version")
    packages = server_manifest.get("packages", [])
    pypi = next((p for p in packages if p.get("registryType") == "pypi"), None)
    if pypi is None:
        errors.append("server.json declares no pypi package entry")
        return errors
    if pypi.get("identifier") != dist_name:
        errors.append("server.json pypi package identifier must equal [project].name")
    if pypi.get("version") != pyproject_version:
        errors.append("server.json pypi package version must equal [project].version")
    if pypi.get("transport", {}).get("type") != "stdio":
        errors.append("server.json pypi package transport.type must be 'stdio'")
    scripts = project.get("scripts", {})
    if scripts.get("spedas-agent-kit") != "spedas_agent_kit:main":
        errors.append("console script 'spedas-agent-kit' must target spedas_agent_kit:main")
    return errors


def _validate_core_metadata_contract() -> None:
    errors = _check_core_metadata_contract(
        pyproject=_load_toml(ROOT / "pyproject.toml"),
        server_manifest=_load_json(ROOT / "server.json"),
        init_version=_parse_init_version(
            (ROOT / "src" / "spedas_agent_kit" / "__init__.py").read_text(encoding="utf-8")
        ),
    )
    if errors:
        raise SystemExit("; ".join(errors))


# --------------------------------------------------------------------------- #
# Synthetic "good" fixtures -- deep-copied per test before mutation so cases stay
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
    errors = _check_core_metadata_contract(
        pyproject=_load_toml(ROOT / "pyproject.toml"),
        server_manifest=_load_json(ROOT / "server.json"),
        init_version=_parse_init_version(
            (ROOT / "src" / "spedas_agent_kit" / "__init__.py").read_text(encoding="utf-8")
        ),
    )
    assert errors == [], errors


def test_validate_core_metadata_contract_end_to_end_passes():
    # Exercises the real I/O path (tomllib/json/AST) against the checked-in files.
    _validate_core_metadata_contract()  # raises SystemExit on drift


def test_repo_server_metadata_matches_a_wheel_built_from_it():
    server_manifest = _load_json(ROOT / "server.json")
    version = server_manifest["version"]
    errors = smoke.check_installed_metadata_contract(
        dist_name="spedas-agent-kit",
        dist_version=version,
        imported_version=version,
        server_manifest=server_manifest,
    )
    assert errors == [], errors


# --------------------------------------------------------------------------- #
# parse_init_version -- static AST extraction, no import of the package.
# --------------------------------------------------------------------------- #
def test_parse_init_version_reads_string_assignment():
    src = '"""doc"""\n__version__ = "9.9.9"\n\ndef main():\n    return None\n'
    assert _parse_init_version(src) == "9.9.9"


def test_parse_init_version_requires_a_version():
    with pytest.raises(SystemExit):
        _parse_init_version("__all__ = []\n")


# --------------------------------------------------------------------------- #
# Source contract mismatch cases -- each must fail and name its surface.
# --------------------------------------------------------------------------- #
def _core_errors(*, pyproject=None, server=None, init_version="0.1.0"):
    return _check_core_metadata_contract(
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


# --------------------------------------------------------------------------- #
# Honest Alpha / source-only installation contract (issue #209, WS-Y).
# --------------------------------------------------------------------------- #
ALPHA_CLASSIFIER = "Development Status :: 3 - Alpha"

CI_BADGE_SVG = (
    "https://github.com/spedas/spedas_agent_kit/actions/workflows/ci.yml/badge.svg"
)
CI_WORKFLOW_URL = (
    "https://github.com/spedas/spedas_agent_kit/actions/workflows/ci.yml"
)

OFFICIAL_CLONE_CMD = "git clone https://github.com/spedas/spedas_agent_kit.git"
SOURCE_INSTALL_COMMANDS = (
    "python -m pip install .",
    "python -m pip install '.[mcp]'",
)

MISLEADING_PIP_INSTALL = re.compile(
    r"""pip3?\s+install\s+(?:-{1,2}\S+\s+)*["']?spedas[-_]agent[-_]kit""",
    re.IGNORECASE,
)


def _pyproject_classifiers() -> list:
    return _load_toml(ROOT / "pyproject.toml")["project"]["classifiers"]


def _readme_text() -> str:
    return (ROOT / "README.md").read_text(encoding="utf-8")


def test_pyproject_still_declares_alpha_development_status():
    assert ALPHA_CLASSIFIER in _pyproject_classifiers(), _pyproject_classifiers()


def test_readme_states_alpha_source_only_pypi_notice():
    readme = _readme_text()
    assert ALPHA_CLASSIFIER in readme
    assert "not published on PyPI" in readme
    assert "pre-1.0" in readme


def test_readme_ties_status_notice_to_authoritative_alpha_metadata():
    assert ALPHA_CLASSIFIER in _pyproject_classifiers()
    assert ALPHA_CLASSIFIER in _readme_text()


def test_readme_has_real_ci_badge_only():
    readme = _readme_text()
    assert CI_BADGE_SVG in readme
    assert CI_WORKFLOW_URL in readme
    assert "img.shields.io/pypi" not in readme
    assert "pypi.org/project/spedas-agent-kit" not in readme


def test_readme_documents_official_source_checkout_install_path():
    readme = _readme_text()
    assert OFFICIAL_CLONE_CMD in readme
    for command in SOURCE_INSTALL_COMMANDS:
        assert command in readme, command


def test_readme_rejects_misleading_public_index_install_command():
    readme = _readme_text()
    hits = MISLEADING_PIP_INSTALL.findall(readme)
    assert hits == [], f"misleading public-index install command present: {hits}"


# --------------------------------------------------------------------------- #
# Runtime Python source may not emit the public-index command form either.
# --------------------------------------------------------------------------- #
RUNTIME_PKG = ROOT / "src" / "spedas_agent_kit"


def _runtime_python_sources() -> list:
    return sorted(RUNTIME_PKG.rglob("*.py"))


def test_runtime_python_sources_exist_to_scan():
    sources = _runtime_python_sources()
    names = {p.name for p in sources}
    assert {"__init__.py", "server.py", "workflows.py", "installation.py"} <= names, names


def test_runtime_python_sources_reject_public_index_install_command():
    offenders = {}
    for path in _runtime_python_sources():
        hits = MISLEADING_PIP_INSTALL.findall(path.read_text(encoding="utf-8"))
        if hits:
            offenders[str(path.relative_to(ROOT))] = hits
    assert offenders == {}, (
        "runtime source emits the public-index install command form; route it "
        f"through spedas_agent_kit.installation instead: {offenders}"
    )


def _string_constants(tree: ast.AST) -> list:
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


def test_runtime_ast_string_constants_reject_public_index_install_command():
    offenders = {}
    for path in _runtime_python_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        hits = [s for s in _string_constants(tree) if MISLEADING_PIP_INSTALL.search(s)]
        if hits:
            offenders[str(path.relative_to(ROOT))] = hits
    assert offenders == {}, (
        "a runtime string constant renders the public-index install command form "
        "(possibly split across adjacent literals); route it through "
        f"spedas_agent_kit.installation instead: {offenders}"
    )


MISLEADING_VARIANTS_THAT_MUST_MATCH = (
    "pip install spedas-agent-kit",
    "pip install spedas-agent-kit[analysis]",
    "pip install 'spedas-agent-kit[analysis]'",
    'pip install "spedas-agent-kit[hapi]"',
    "pip3 install spedas-agent-kit",
    "pip install spedas_agent_kit",  # underscore distribution spelling
    "PIP INSTALL SPEDAS-AGENT-KIT",  # case-insensitive
    "pip install -U 'spedas-agent-kit[analysis]'",
    'pip install --upgrade "spedas_agent_kit[analysis]"',
    "pip3 install -U --no-cache-dir spedas-agent-kit[analysis]",
)
ALLOWED_FORMS_THAT_MUST_NOT_MATCH = (
    "spedas-agent-kit[analysis]",  # plain identifier mention
    "python -m pip install .",  # checkout-relative base
    "python -m pip install '.[mcp]'",  # checkout-relative extra
)


def test_misleading_pip_install_regex_catches_all_cosmetic_variants():
    for text in MISLEADING_VARIANTS_THAT_MUST_MATCH:
        assert MISLEADING_PIP_INSTALL.search(text), text


def test_misleading_pip_install_regex_allows_identifier_and_checkout_forms():
    for text in ALLOWED_FORMS_THAT_MUST_NOT_MATCH:
        assert MISLEADING_PIP_INSTALL.search(text) is None, text
