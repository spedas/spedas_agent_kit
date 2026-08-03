"""Packaged SPEDAS skill catalog helpers.

The Agent Kit ships shared, runtime-neutral SPEDAS skills inside the Python
package so thin wrappers (Claude Code, Codex, OpenCode, etc.) can reuse one
canonical skill surface.  This module keeps the catalog logic dependency-free so
base MCP installs can expose those skills as MCP resources without pulling in a
YAML parser.
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from typing import Any

SPEDAS_SKILL_INDEX_URI = "spedas-skill://index"
SPEDAS_SKILL_URI_PREFIX = "spedas-skill://skills/"
_SKILL_ROOT = "skills"


@dataclass(frozen=True)
class PackagedSkill:
    """Metadata for one packaged SPEDAS Agent Kit skill."""

    name: str
    description: str
    resource_uri: str


def _strip_yaml_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Parse the small YAML-frontmatter subset used by bundled SKILL.md files."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    block: list[str] = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        block.append(line.rstrip("\n"))
    else:
        return {}

    data: dict[str, str] = {}
    i = 0
    while i < len(block):
        raw = block[i]
        if not raw.strip() or raw.lstrip().startswith("#") or ":" not in raw:
            i += 1
            continue
        key, value = raw.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value in {"|", ">"}:
            folded = value == ">"
            collected: list[str] = []
            i += 1
            while i < len(block):
                continuation = block[i]
                if continuation and not continuation.startswith((" ", "\t")):
                    break
                collected.append(continuation.strip())
                i += 1
            if folded:
                data[key] = " ".join(part for part in collected if part).strip()
            else:
                data[key] = "\n".join(collected).strip()
            continue
        data[key] = _strip_yaml_scalar(value)
        i += 1
    return data


def _skills_root() -> Any:
    return resources.files("spedas_agent_kit.resources").joinpath(_SKILL_ROOT)


def _skill_path(name: str) -> Any:
    if not name or "/" in name or "\\" in name or name in {".", ".."}:
        raise KeyError(name)
    return _skills_root().joinpath(name, "SKILL.md")


def list_packaged_skills() -> list[PackagedSkill]:
    """Return metadata for every bundled SPEDAS skill, sorted by skill name."""
    root = _skills_root()
    skills: list[PackagedSkill] = []
    for entry in root.iterdir():
        if not entry.is_dir():
            continue
        skill_file = entry.joinpath("SKILL.md")
        if not skill_file.is_file():
            continue
        text = skill_file.read_text(encoding="utf-8")
        frontmatter = _parse_frontmatter(text)
        name = frontmatter.get("name") or entry.name
        description = frontmatter.get("description") or "Packaged SPEDAS Agent Kit skill."
        skills.append(
            PackagedSkill(
                name=name,
                description=" ".join(description.split()),
                resource_uri=f"{SPEDAS_SKILL_URI_PREFIX}{name}",
            )
        )
    return sorted(skills, key=lambda item: item.name)


def read_packaged_skill(name: str) -> str:
    """Read one bundled skill by frontmatter/directory name."""
    for skill in list_packaged_skills():
        if skill.name == name:
            return _skill_path(skill.name).read_text(encoding="utf-8")
    raise KeyError(name)


def render_skill_index_markdown() -> str:
    """Render a compact MCP-resource index for bundled SPEDAS skills."""
    skills = list_packaged_skills()
    lines = [
        "# SPEDAS Agent Kit packaged skills",
        "",
        (
            "These runtime-neutral skills ship inside `spedas_agent_kit` and are "
            "also exposed by the MCP server as read-only resources. Use "
            "`list_resources` to discover them and `read_resource` on the "
            "individual URI to load the full `SKILL.md`."
        ),
        "",
        f"Skill count: {len(skills)}",
        "",
    ]
    for skill in skills:
        lines.append(f"- `{skill.name}` — `{skill.resource_uri}` — {skill.description}")
    lines.append("")
    return "\n".join(lines)
