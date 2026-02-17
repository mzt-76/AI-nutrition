"""Tests for skill loader - discovery, metadata parsing, and prompt generation."""

import pytest
from pathlib import Path

from src.skill_loader import SkillLoader, SkillMetadata


@pytest.fixture
def skills_dir(tmp_path: Path) -> Path:
    """Create a temporary skills directory with test skills."""
    # Valid skill
    valid_skill = tmp_path / "test-skill"
    valid_skill.mkdir()
    (valid_skill / "SKILL.md").write_text(
        "---\n"
        "name: test-skill\n"
        "description: A test skill for unit testing.\n"
        "---\n\n"
        "# Test Skill\n\n"
        "These are the instructions.\n",
        encoding="utf-8",
    )
    (valid_skill / "references").mkdir()
    (valid_skill / "references" / "guide.md").write_text(
        "# Guide\n\nReference content here.\n",
        encoding="utf-8",
    )

    # Second valid skill
    second_skill = tmp_path / "another-skill"
    second_skill.mkdir()
    (second_skill / "SKILL.md").write_text(
        "---\n"
        "name: another-skill\n"
        "description: Another skill for testing.\n"
        "version: 2.0.0\n"
        "---\n\n"
        "# Another Skill\n\n"
        "More instructions.\n",
        encoding="utf-8",
    )

    # Invalid skill (no frontmatter)
    invalid_skill = tmp_path / "bad-skill"
    invalid_skill.mkdir()
    (invalid_skill / "SKILL.md").write_text(
        "# No Frontmatter\n\nThis should be skipped.\n",
        encoding="utf-8",
    )

    # Invalid skill (missing required fields)
    incomplete_skill = tmp_path / "incomplete-skill"
    incomplete_skill.mkdir()
    (incomplete_skill / "SKILL.md").write_text(
        "---\n" "name: incomplete-skill\n" "---\n\n" "# Missing description field\n",
        encoding="utf-8",
    )

    # Directory without SKILL.md (should be ignored)
    no_skill_md = tmp_path / "no-skill-md"
    no_skill_md.mkdir()
    (no_skill_md / "README.md").write_text("Not a skill.\n", encoding="utf-8")

    return tmp_path


class TestSkillDiscovery:
    """Test skill discovery from filesystem."""

    def test_discovers_valid_skills(self, skills_dir: Path) -> None:
        """Discovers skills with valid SKILL.md and YAML frontmatter."""
        loader = SkillLoader(skills_dir)
        discovered = loader.discover_skills()

        assert len(discovered) == 2
        names = {s.name for s in discovered}
        assert names == {"another-skill", "test-skill"}

    def test_skips_invalid_frontmatter(self, skills_dir: Path) -> None:
        """Skips skills without valid YAML frontmatter."""
        loader = SkillLoader(skills_dir)
        loader.discover_skills()

        assert "bad-skill" not in loader.skills

    def test_skips_incomplete_frontmatter(self, skills_dir: Path) -> None:
        """Skips skills missing required fields (name or description)."""
        loader = SkillLoader(skills_dir)
        loader.discover_skills()

        assert "incomplete-skill" not in loader.skills

    def test_skips_directories_without_skill_md(self, skills_dir: Path) -> None:
        """Ignores directories that don't contain SKILL.md."""
        loader = SkillLoader(skills_dir)
        loader.discover_skills()

        assert "no-skill-md" not in loader.skills

    def test_handles_missing_skills_directory(self, tmp_path: Path) -> None:
        """Returns empty list when skills directory doesn't exist."""
        loader = SkillLoader(tmp_path / "nonexistent")
        discovered = loader.discover_skills()

        assert discovered == []
        assert len(loader.skills) == 0

    def test_registers_skills_by_name(self, skills_dir: Path) -> None:
        """Skills are accessible by name after discovery."""
        loader = SkillLoader(skills_dir)
        loader.discover_skills()

        assert "test-skill" in loader.skills
        assert (
            loader.skills["test-skill"].description == "A test skill for unit testing."
        )

    def test_parses_version(self, skills_dir: Path) -> None:
        """Parses optional version field from frontmatter."""
        loader = SkillLoader(skills_dir)
        loader.discover_skills()

        assert loader.skills["another-skill"].version == "2.0.0"
        assert loader.skills["test-skill"].version == "1.0.0"  # default

    def test_stores_skill_path(self, skills_dir: Path) -> None:
        """Stores the path to the skill directory."""
        loader = SkillLoader(skills_dir)
        loader.discover_skills()

        assert loader.skills["test-skill"].skill_path == skills_dir / "test-skill"


class TestSkillMetadataPrompt:
    """Test system prompt generation from skill metadata."""

    def test_generates_metadata_prompt(self, skills_dir: Path) -> None:
        """Generates formatted metadata for system prompt injection."""
        loader = SkillLoader(skills_dir)
        loader.discover_skills()

        prompt = loader.get_skill_metadata_prompt()

        assert "**test-skill**" in prompt
        assert "A test skill for unit testing." in prompt
        assert "**another-skill**" in prompt

    def test_returns_message_when_no_skills(self, tmp_path: Path) -> None:
        """Returns informative message when no skills are available."""
        loader = SkillLoader(tmp_path / "nonexistent")
        loader.discover_skills()

        prompt = loader.get_skill_metadata_prompt()
        assert "Aucun skill" in prompt


class TestRealSkillsDiscovery:
    """Test discovery of actual project skills."""

    def test_discovers_project_skills(self) -> None:
        """Discovers all skills in the project's skills/ directory."""
        project_root = Path(__file__).resolve().parent.parent
        skills_dir = project_root / "skills"

        loader = SkillLoader(skills_dir)
        discovered = loader.discover_skills()

        # Should find at least our 5 new skills + skill-creator
        assert len(discovered) >= 6

        expected_skills = {
            "nutrition-calculating",
            "meal-planning",
            "weekly-coaching",
            "knowledge-searching",
            "body-analyzing",
            "skill-creator",
        }
        actual_skills = {s.name for s in discovered}
        assert expected_skills.issubset(
            actual_skills
        ), f"Missing skills: {expected_skills - actual_skills}"

    def test_all_skills_have_descriptions(self) -> None:
        """All project skills have non-empty descriptions."""
        project_root = Path(__file__).resolve().parent.parent
        skills_dir = project_root / "skills"

        loader = SkillLoader(skills_dir)
        loader.discover_skills()

        for name, skill in loader.skills.items():
            assert skill.description, f"Skill '{name}' has empty description"
            assert (
                len(skill.description) > 10
            ), f"Skill '{name}' description too short: {skill.description}"
