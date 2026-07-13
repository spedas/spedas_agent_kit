"""Canonical source-checkout installation guidance (issue #209).

The kit's 0.1.0 is a source-only Alpha: it is **not published on PyPI**, so any
runtime message that pointed a user at a public-index install of the
distribution named an install command that cannot work. This module is the
single source of truth for the *correct* guidance — clone the official
repository and install from the checked-out working tree — so every
user-visible runtime hint renders the same, honest instructions.

Design contract:

- **Dependency-free and import-side-effect-free.** Pure string builders over
  module constants; importing this module never imports a backend, touches the
  filesystem, or reads the environment. Safe to import from the package
  ``__init__``'s error path and from optional/lazy backends alike.
- **No publication guessing.** There is deliberately no ``_ON_PYPI`` flag,
  future-release branch, or public-index command generator here. The kit is
  source-only until an authorized release contract says otherwise; this module
  only renders the source-checkout path the README documents and CI validates.
- **Extras stay checkout-relative.** Optional extras are rendered as identifiers
  of *this* checkout (``'.[analysis]'``), never as a public-index distribution
  (``spedas-agent-kit[analysis]`` as a ``pip install`` target).
"""
from __future__ import annotations

from collections.abc import Iterable

#: Official source repository (clone target).
REPO_GIT_URL = "https://github.com/spedas/spedas_agent_kit.git"
#: Anchor to the README installation section documenting this exact path.
INSTALL_DOCS_URL = "https://github.com/spedas/spedas_agent_kit#installation"
#: Distribution name, used only for plain identifier mentions of extras — never
#: as a ``pip install`` target (the kit is not on a public index).
DISTRIBUTION_NAME = "spedas-agent-kit"


def _normalized_extras(extras: str | Iterable[str] | None) -> list[str]:
    """Return a clean list of extra names from ``str``/iterable/``None`` input."""
    if extras is None:
        return []
    if isinstance(extras, str):
        candidates = [extras]
    else:
        candidates = list(extras)
    return [part.strip() for part in candidates if part and part.strip()]


def source_install_command(extras: str | Iterable[str] | None = None) -> str:
    """Render the checkout-relative ``pip install`` command.

    ``extras=None`` → ``python -m pip install .`` (base). A single extra or an
    iterable of extras → ``python -m pip install '.[analysis]'`` /
    ``'.[hapi,fdsn]'``. The command is always relative to the current working
    tree (``.``), so it only works when run *from the cloned checkout* — which is
    exactly the documented, CI-validated path.
    """
    names = _normalized_extras(extras)
    if not names:
        return "python -m pip install ."
    return f"python -m pip install '.[{','.join(names)}]'"


def extras_identifier(extras: str | Iterable[str]) -> str:
    """Plain ``spedas-agent-kit[analysis]`` identifier for descriptive prose.

    This is an *identifier* of the optional extra, not a runnable install
    command; callers embed it in messages that separately point at
    :func:`source_install_command` for the actual command to run.
    """
    names = _normalized_extras(extras)
    joined = ",".join(names)
    return f"{DISTRIBUTION_NAME}[{joined}]"


def install_hint(extras: str | Iterable[str] | None = None) -> str:
    """One-line install hint for a runtime payload/error ``install_hint`` field.

    Names the source-only Alpha status, the official clone URL, the correct
    checkout-relative command, and the documentation anchor, so a user who hits
    the hint can install the (base or extra) capability without ever reaching for
    a public index that has no release.
    """
    command = source_install_command(extras)
    return (
        f"Source-only Alpha (not published on PyPI): clone {REPO_GIT_URL}, then "
        f"from the checkout run `{command}`. See {INSTALL_DOCS_URL}."
    )


def missing_backend_message(extras: str | Iterable[str]) -> str:
    """Fuller guidance for a missing optional backend's error message.

    Includes the plain ``spedas-agent-kit[extra]`` identifier (so callers/tests
    can refer to the extra by name) alongside the checkout-relative command and
    the source-only Alpha framing.
    """
    identifier = extras_identifier(extras)
    return (
        f"This capability needs the optional {identifier} extra. "
        f"{install_hint(extras)}"
    )
