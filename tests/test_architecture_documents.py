"""Architecture-document validation for the ANATOMY/CONTRACT distributed systems.

Validates, with no third-party dependencies (no PyYAML):

- every ANATOMY.md / CONTRACT.md under the repo has parseable YAML frontmatter;
- `related_files` entries are repo-relative, duplicate-free, and resolve to real files;
- co-located ANATOMY.md / CONTRACT.md pairs list each other (reciprocal);
- the root CONTRACT.md lists every governed child CONTRACT.md exactly once;
- every governed child has `root_contract: CONTRACT.md` and a paired ANATOMY.md.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

ANATOMY_FILES = sorted(REPO_ROOT.rglob("ANATOMY.md"))
CONTRACT_FILES = sorted(REPO_ROOT.rglob("CONTRACT.md"))


# ---------------------------------------------------------------------------
# Minimal YAML frontmatter parser (no PyYAML dependency, CI-safe)
# ---------------------------------------------------------------------------

def parse_frontmatter(text: str) -> dict[str, object] | None:
    """Parse the leading YAML frontmatter block of a markdown document.

    Supports the subset used by this repo's architecture documents: simple
    ``key: value`` scalars, ``key: |`` block scalars, and ``key:`` followed by
    a ``- item`` list. Returns None when the document has no frontmatter or
    the block is malformed.
    """
    if not text.startswith("---"):
        return None
    lines = text.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        return None
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return None

    data: dict[str, object] = {}
    fm_lines = lines[1:end]
    i = 0
    while i < len(fm_lines):
        line = fm_lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in line:
            i += 1
            continue
        key, _, rest = line.partition(":")
        key = key.strip()
        rest = rest.strip()
        if not key:
            i += 1
            continue
        if rest == "|":
            # Block scalar: consume following indented/blank lines.
            i += 1
            block: list[str] = []
            while i < len(fm_lines):
                cur = fm_lines[i]
                if cur.strip() == "" or cur.startswith("  ") or cur.startswith("\t"):
                    block.append(cur)
                    i += 1
                else:
                    break
            data[key] = "\n".join(
                b[2:] if b.startswith("  ") else b for b in block
            )
        elif rest.startswith("- "):
            # Inline list start (rare); consume following list items.
            items = [rest[2:].strip()]
            i += 1
            while i < len(fm_lines) and fm_lines[i].strip().startswith("- "):
                items.append(fm_lines[i].strip()[2:].strip())
                i += 1
            data[key] = items
        elif rest == "":
            # List on following lines.
            i += 1
            items: list[str] = []
            while i < len(fm_lines) and fm_lines[i].strip().startswith("- "):
                items.append(fm_lines[i].strip()[2:].strip())
                i += 1
            data[key] = items
        else:
            data[key] = _coerce_scalar(rest)
            i += 1
    return data


def _coerce_scalar(value: str) -> object:
    """Coerce simple YAML scalars: integers and booleans."""
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if value in ("true", "True"):
        return True
    if value in ("false", "False"):
        return False
    return value


def _frontmatter(path: Path) -> dict[str, object]:
    data = parse_frontmatter(path.read_text(encoding="utf-8"))
    assert data is not None, f"{path} has no parseable YAML frontmatter"
    return data


def _related_files(path: Path) -> list[str]:
    data = _frontmatter(path)
    related = data.get("related_files")
    assert isinstance(related, list) and related, (
        f"{path} frontmatter must have a non-empty related_files list"
    )
    assert all(isinstance(item, str) and item.strip() for item in related), (
        f"{path} related_files must contain only non-empty strings"
    )
    return related


def _rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


# ---------------------------------------------------------------------------
# Discovery sanity
# ---------------------------------------------------------------------------


def test_expected_document_set():
    expected = [
        "ANATOMY.md",
        "CONTRACT.md",
        "src/spedas_agent_kit/ANATOMY.md",
        "src/spedas_agent_kit/CONTRACT.md",
        "src/spedas_agent_kit/backends/ANATOMY.md",
        "src/spedas_agent_kit/backends/CONTRACT.md",
        "src/spedas_agent_kit/resources/ANATOMY.md",
        "src/spedas_agent_kit/resources/CONTRACT.md",
    ]
    assert sorted(_rel(p) for p in ANATOMY_FILES + CONTRACT_FILES) == sorted(expected)


# ---------------------------------------------------------------------------
# Frontmatter shape
# ---------------------------------------------------------------------------


def test_all_documents_have_parseable_frontmatter():
    for path in ANATOMY_FILES + CONTRACT_FILES:
        _frontmatter(path)


def test_anatomy_frontmatter_keys():
    for path in ANATOMY_FILES:
        data = _frontmatter(path)
        assert "related_files" in data and isinstance(data["related_files"], list)
        maintenance = data.get("maintenance")
        assert isinstance(maintenance, str) and maintenance.strip(), (
            f"{path} frontmatter must have a non-empty maintenance block"
        )


def test_contract_frontmatter_keys():
    for path in CONTRACT_FILES:
        data = _frontmatter(path)
        name = data.get("name")
        assert isinstance(name, str) and name.strip(), f"{path} must have a name"
        version = data.get("contract_version")
        assert isinstance(version, int) and version >= 1, (
            f"{path} contract_version must be a positive integer"
        )
        assert "related_files" in data and isinstance(data["related_files"], list)
        maintenance = data.get("maintenance")
        assert isinstance(maintenance, str) and maintenance.strip(), (
            f"{path} frontmatter must have a non-empty maintenance block"
        )


def test_root_contract_has_no_root_contract_key():
    root = REPO_ROOT / "CONTRACT.md"
    data = _frontmatter(root)
    assert "root_contract" not in data, "root CONTRACT.md must omit root_contract"


def test_governed_children_point_back_to_root_contract():
    root = REPO_ROOT / "CONTRACT.md"
    children = [p for p in CONTRACT_FILES if p != root]
    assert children, "expected at least one governed child contract"
    for path in children:
        data = _frontmatter(path)
        assert data.get("root_contract") == "CONTRACT.md", (
            f"{path} root_contract must be the literal path CONTRACT.md"
        )


# ---------------------------------------------------------------------------
# related_files graph
# ---------------------------------------------------------------------------


def test_related_files_are_repo_relative_duplicate_free_and_resolve():
    for path in ANATOMY_FILES + CONTRACT_FILES:
        related = _related_files(path)
        assert len(related) == len(set(related)), f"duplicate related_files in {path}"
        for entry in related:
            assert not entry.startswith("/"), f"{path}: {entry!r} is absolute"
            parts = Path(entry).parts
            assert "." not in parts and ".." not in parts, (
                f"{path}: {entry!r} must not contain . or .. segments"
            )
            target = REPO_ROOT / entry
            assert target.is_file(), f"{path}: related_files {entry!r} does not resolve"


def test_paired_anatomy_contract_are_reciprocal():
    paired_dirs = {p.parent for p in ANATOMY_FILES} & {p.parent for p in CONTRACT_FILES}
    assert paired_dirs, "expected at least one directory with both ANATOMY.md and CONTRACT.md"
    for directory in sorted(paired_dirs):
        ana_path = directory / "ANATOMY.md"
        con_path = directory / "CONTRACT.md"
        assert _rel(con_path) in _related_files(ana_path), (
            f"{_rel(ana_path)} must list its paired {_rel(con_path)}"
        )
        assert _rel(ana_path) in _related_files(con_path), (
            f"{_rel(con_path)} must list its paired {_rel(ana_path)}"
        )


def test_root_contract_lists_every_governed_child_exactly_once():
    root = REPO_ROOT / "CONTRACT.md"
    children = sorted(p for p in CONTRACT_FILES if p != root)
    related = _related_files(root)
    for child in children:
        rel = _rel(child)
        assert related.count(rel) == 1, (
            f"root CONTRACT.md must list governed child {rel} exactly once"
        )


def test_every_governed_child_has_paired_anatomy():
    root = REPO_ROOT / "CONTRACT.md"
    for path in CONTRACT_FILES:
        if path == root:
            continue
        paired = path.parent / "ANATOMY.md"
        assert paired.is_file(), f"{_rel(path)} has no co-located ANATOMY.md"
        assert _rel(paired) in _related_files(path), (
            f"{_rel(path)} must list its paired {_rel(paired)}"
        )


def test_anatomy_notes_have_no_empty_stub_sections():
    required_sections = [
        "## Components",
        "## Connections",
        "## Composition",
        "## State",
        "## Notes",
    ]
    for path in ANATOMY_FILES:
        text = path.read_text(encoding="utf-8")
        for section in required_sections:
            assert section in text, f"{_rel(path)} missing body section {section}"
        # No section may be immediately followed by the next section heading
        # (an empty stub): there must be at least one non-heading line between
        # consecutive headings.
        lines = text.splitlines()
        for idx, line in enumerate(lines):
            if line.startswith("## "):
                rest = lines[idx + 1 :]
                if rest and rest[0].startswith("#"):
                    pytest.fail(f"{_rel(path)}: empty stub section {line!r}")
