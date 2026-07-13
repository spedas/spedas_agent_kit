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

A third group (issue #209, WS-Y) pins the *honest Alpha / source-only installation*
contract: the live ``pyproject.toml`` Alpha classifier, and the ``README.md``
status notice, real CI badge, official source-checkout install path, and
source-relative extras. These assertions are pure text/TOML reads over the
checked-in files — no wheel build, temp dir, subprocess, or network — and they
reject the old public-index ``pip install spedas-agent-kit...`` command form so
future drift back toward "looks published on PyPI" fails CI.
"""
from __future__ import annotations

import ast
import copy
import re
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


# --------------------------------------------------------------------------- #
# Honest Alpha / source-only installation contract (issue #209, WS-Y).
#
# Pure reads over the checked-in pyproject.toml and README.md — no build, temp
# dir, subprocess, or network. These tie the README's "not on PyPI / install from
# source" story to the authoritative Alpha metadata and reject the old public
# index command form so the README cannot silently drift back toward implying a
# published PyPI release.
# --------------------------------------------------------------------------- #
ALPHA_CLASSIFIER = "Development Status :: 3 - Alpha"

# The real CI workflow badge/target on the official repo (.github/workflows/ci.yml
# on spedas/spedas_agent_kit). No PyPI/version badge exists because no release does.
CI_BADGE_SVG = (
    "https://github.com/spedas/spedas_agent_kit/actions/workflows/ci.yml/badge.svg"
)
CI_WORKFLOW_URL = (
    "https://github.com/spedas/spedas_agent_kit/actions/workflows/ci.yml"
)

# The supported source-checkout install path: clone the official repo + install
# from the working tree, base and per-extra (issue #209 WS-Y). Extra names stay as
# identifiers of *this* checkout ('.[extra]'), never a public-index distribution.
OFFICIAL_CLONE_CMD = "git clone https://github.com/spedas/spedas_agent_kit.git"
SOURCE_INSTALL_COMMANDS = (
    "python -m pip install .",
    "python -m pip install '.[analysis]'",
    "python -m pip install '.[hapi]'",
    "python -m pip install '.[fdsn]'",
    "python -m pip install '.[hapi,fdsn]'",
)

# The misleading public-index command form this slice removed. Match only the
# *command* (a `pip`/`pip3 install` directive naming the distribution, optionally
# quoted, flagged, and with an extra), so plain identifier mentions like
# `spedas-agent-kit[hapi]` and the source-relative `python -m pip install .` /
# `'.[analysis]'` commands do not trip it. Tolerates the pip3 spelling,
# single/double quotes, the hyphen/underscore distribution spellings, and any
# short/long option flags between `install` and the distribution (e.g. `-U`,
# `--upgrade`) so drift cannot sneak back in under a cosmetic variant.
MISLEADING_PIP_INSTALL = re.compile(
    r"""pip3?\s+install\s+(?:-{1,2}\S+\s+)*["']?spedas[-_]agent[-_]kit""",
    re.IGNORECASE,
)


def _pyproject_classifiers() -> list:
    pyproject = validate.load_toml(ROOT / "pyproject.toml")
    return pyproject["project"]["classifiers"]


def _readme_text() -> str:
    return (ROOT / "README.md").read_text(encoding="utf-8")


def test_pyproject_still_declares_alpha_development_status():
    # Authoritative Alpha metadata the README notice/tests are pinned against.
    assert ALPHA_CLASSIFIER in _pyproject_classifiers(), _pyproject_classifiers()


def test_readme_states_alpha_source_only_pypi_notice():
    readme = _readme_text()
    # The above-the-fold notice must make the Alpha, not-on-PyPI, pre-1.0 status
    # explicit so a new researcher cannot mistake this for a published release.
    assert ALPHA_CLASSIFIER in readme
    assert "not published on PyPI" in readme
    assert "pre-1.0" in readme


def test_readme_ties_status_notice_to_authoritative_alpha_metadata():
    # The status the README advertises must be the status pyproject declares.
    assert ALPHA_CLASSIFIER in _pyproject_classifiers()
    assert ALPHA_CLASSIFIER in _readme_text()


def test_readme_has_real_ci_badge_only():
    readme = _readme_text()
    # The one badge added targets the real CI workflow (badge image + link).
    assert CI_BADGE_SVG in readme
    assert CI_WORKFLOW_URL in readme
    # Guard against re-introducing fake PyPI/version/release badges for a package
    # that is not published: no shields.io PyPI badge, no pypi.org badge target.
    assert "img.shields.io/pypi" not in readme
    assert "pypi.org/project/spedas-agent-kit" not in readme


def test_readme_documents_official_source_checkout_install_path():
    readme = _readme_text()
    # Official clone + install-from-checkout base and per-extra commands are all
    # present and runnable from the repository working tree.
    assert OFFICIAL_CLONE_CMD in readme
    for command in SOURCE_INSTALL_COMMANDS:
        assert command in readme, command


def test_readme_rejects_misleading_public_index_install_command():
    # The old `pip install spedas-agent-kit[...]` command form must be gone so the
    # README never again implies a public-index (PyPI) install. Identifier
    # mentions of the extra names are still allowed; only the command form fails.
    readme = _readme_text()
    hits = MISLEADING_PIP_INSTALL.findall(readme)
    assert hits == [], f"misleading public-index install command present: {hits}"


# --------------------------------------------------------------------------- #
# Runtime Python source may not emit the public-index command form either
# (issue #209 slice #8). Every user-visible runtime install directive must route
# through spedas_agent_kit.installation, which renders the source-checkout path
# (`python -m pip install '.[...]'`). Plain `spedas-agent-kit[extra]` identifiers
# and checkout-relative commands are allowed; the `pip install spedas-agent-kit`
# command form is not, so runtime guidance cannot drift back toward a package
# that is not published.
# --------------------------------------------------------------------------- #
RUNTIME_PKG = ROOT / "src" / "spedas_agent_kit"


def _runtime_python_sources() -> list:
    return sorted(RUNTIME_PKG.rglob("*.py"))


def test_runtime_python_sources_exist_to_scan():
    # Guard against a silently-empty scan (e.g. wrong ROOT): the package ships
    # source, so the glob must find the known command producers.
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
    """Every ``str`` constant in the module (stdlib AST, no import/execution).

    The parser folds *adjacent* string literals into a single ``ast.Constant``,
    so a command literal split across source lines (e.g. ``"pip install -U "``
    ``"'spedas-agent-kit[analysis]'"``) is reconciled into one rendered value the
    regex can catch — which the raw line-by-line scan misses.
    """
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


def test_runtime_ast_string_constants_reject_public_index_install_command():
    # Scans rendered string constants (concatenation-aware) so split-literal
    # command forms — like the pre-fix fieldmodels backend_outdated message —
    # cannot evade the raw-source scan. Deterministic, stdlib-only, no execution.
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


# Pin the *shape* of the anti-drift pattern so a future edit cannot silently
# weaken it back to only matching a single cosmetic spelling. Every cosmetic
# variant of the misleading public-index command must still be caught, and every
# allowed form (plain identifier, checkout-relative command) must still pass.
MISLEADING_VARIANTS_THAT_MUST_MATCH = (
    "pip install spedas-agent-kit",
    "pip install spedas-agent-kit[analysis]",
    "pip install 'spedas-agent-kit[analysis]'",
    'pip install "spedas-agent-kit[hapi]"',
    "pip3 install spedas-agent-kit",
    "pip install spedas_agent_kit",  # underscore distribution spelling
    "PIP INSTALL SPEDAS-AGENT-KIT",  # case-insensitive
    # Flags/options between `install` and the distribution (the exact pre-fix
    # fieldmodels offender and its long-option twin).
    "pip install -U 'spedas-agent-kit[analysis]'",
    'pip install --upgrade "spedas_agent_kit[analysis]"',
    "pip3 install -U --no-cache-dir spedas-agent-kit[analysis]",
)
ALLOWED_FORMS_THAT_MUST_NOT_MATCH = (
    "spedas-agent-kit[analysis]",  # plain identifier mention
    "python -m pip install .",  # checkout-relative base
    "python -m pip install '.[analysis]'",  # checkout-relative extra
    "python -m pip install '.[hapi,fdsn]'",
)


def test_misleading_pip_install_regex_catches_all_cosmetic_variants():
    for text in MISLEADING_VARIANTS_THAT_MUST_MATCH:
        assert MISLEADING_PIP_INSTALL.search(text), text


def test_misleading_pip_install_regex_allows_identifier_and_checkout_forms():
    for text in ALLOWED_FORMS_THAT_MUST_NOT_MATCH:
        assert MISLEADING_PIP_INSTALL.search(text) is None, text
