"""Focused unit tests for the source-checkout install guidance helper (#209).

The helper (:mod:`spedas_agent_kit.installation`) is the single source of truth
for every user-visible runtime install directive. These tests pin the three
shapes callers use — base, a single extra, and combined extras — plus the
source-only-Alpha framing, and assert the helper never renders the misleading
public-index ``pip install spedas-agent-kit[...]`` command form.
"""
from __future__ import annotations

import re

from spedas_agent_kit import installation


# The prohibited command form (same shape the metadata anti-drift contract bans):
# a `pip`/`pip3 install` directive naming the distribution, tolerating quotes, the
# hyphen/underscore spellings, and any option flags (e.g. `-U`, `--upgrade`)
# between `install` and the distribution so no cosmetic variant slips through. The
# helper must never emit it; the checkout-relative `python -m pip install '.[...]'`
# is the correct form.
MISLEADING_PIP_INSTALL = re.compile(
    r"""pip3?\s+install\s+(?:-{1,2}\S+\s+)*["']?spedas[-_]agent[-_]kit""",
    re.IGNORECASE,
)


def test_misleading_pip_install_regex_shape():
    # Cosmetic variants of the misleading public-index command must all match...
    for text in (
        "pip install spedas-agent-kit",
        "pip install 'spedas-agent-kit[analysis]'",
        'pip3 install "spedas_agent_kit[hapi]"',
        "PIP INSTALL SPEDAS-AGENT-KIT",
        # Flags/options between `install` and the distribution.
        "pip install -U 'spedas-agent-kit[analysis]'",
        'pip install --upgrade "spedas_agent_kit[analysis]"',
    ):
        assert MISLEADING_PIP_INSTALL.search(text), text
    # ...while allowed identifier/checkout forms must not.
    for text in (
        "spedas-agent-kit[analysis]",
        "python -m pip install .",
        "python -m pip install '.[hapi,fdsn]'",
    ):
        assert MISLEADING_PIP_INSTALL.search(text) is None, text


def test_source_install_command_base():
    assert installation.source_install_command() == "python -m pip install ."
    assert installation.source_install_command(None) == "python -m pip install ."


def test_source_install_command_single_extra():
    assert installation.source_install_command("analysis") == (
        "python -m pip install '.[analysis]'"
    )
    # An iterable of one behaves like the string form.
    assert installation.source_install_command(["hapi"]) == (
        "python -m pip install '.[hapi]'"
    )


def test_source_install_command_combined_extras():
    assert installation.source_install_command(["hapi", "fdsn"]) == (
        "python -m pip install '.[hapi,fdsn]'"
    )


def test_install_hint_states_source_only_alpha_and_checkout_path():
    hint = installation.install_hint("analysis")
    # Source-only Alpha, explicitly not on PyPI.
    assert "Source-only Alpha" in hint
    assert "not published on PyPI" in hint
    # Names the official clone URL and the docs anchor.
    assert installation.REPO_GIT_URL in hint
    assert installation.INSTALL_DOCS_URL in hint
    # Carries the correct checkout-relative command for the requested extra.
    assert "python -m pip install '.[analysis]'" in hint


def test_install_hint_base_has_no_extra_brackets():
    hint = installation.install_hint()
    assert "python -m pip install ." in hint
    assert "'.[" not in hint


def test_missing_backend_message_names_identifier_and_command():
    message = installation.missing_backend_message("hapi")
    # Plain identifier of the extra (allowed) is present for readers/tests...
    assert "spedas-agent-kit[hapi]" in message
    # ...alongside the correct checkout-relative command.
    assert "python -m pip install '.[hapi]'" in message


def test_helper_never_emits_public_index_install_command():
    rendered = [
        installation.install_hint(),
        installation.install_hint("analysis"),
        installation.install_hint(["hapi", "fdsn"]),
        installation.missing_backend_message("analysis"),
        installation.missing_backend_message("fdsn"),
        installation.source_install_command(),
        installation.source_install_command("mcp"),
    ]
    for text in rendered:
        assert MISLEADING_PIP_INSTALL.search(text) is None, text
