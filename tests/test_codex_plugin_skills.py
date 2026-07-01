from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGED_SKILLS = ROOT / "src" / "spedas_agent_kit" / "resources" / "skills"
CODEX_SKILLS = ROOT / ".agents" / "plugins" / "spedas-codex" / "skills"


def _skill_names(path: Path) -> set[str]:
    return {p.name for p in path.iterdir() if p.is_dir() and (p / "SKILL.md").is_file()}


def test_codex_plugin_skills_match_packaged_resource_copies():
    packaged = _skill_names(PACKAGED_SKILLS)
    codex = _skill_names(CODEX_SKILLS)

    assert codex == packaged
    for name in sorted(packaged):
        assert (CODEX_SKILLS / name / "SKILL.md").read_text(encoding="utf-8") == (
            PACKAGED_SKILLS / name / "SKILL.md"
        ).read_text(encoding="utf-8")
