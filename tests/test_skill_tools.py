"""Tests for skill progressive disclosure tools (load, read, list)."""

import pytest
from pathlib import Path
from dataclasses import dataclass

from src.skill_loader import SkillLoader
from src.skill_tools import load_skill, read_skill_file, list_skill_files


@dataclass
class MockAgentDeps:
    """Minimal mock of AgentDeps for skill tool testing."""

    skill_loader: SkillLoader | None = None


class MockRunContext:
    """Mock RunContext for testing skill tools."""

    def __init__(self, deps: MockAgentDeps) -> None:
        self.deps = deps


@pytest.fixture
def skills_dir(tmp_path: Path) -> Path:
    """Create a temporary skills directory with a test skill."""
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()

    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: test-skill\n"
        "description: A test skill.\n"
        "---\n\n"
        "# Test Skill\n\n"
        "Step 1: Do something.\n"
        "Step 2: Do something else.\n\n"
        "See `references/details.md` for more info.\n",
        encoding="utf-8",
    )

    refs_dir = skill_dir / "references"
    refs_dir.mkdir()
    (refs_dir / "details.md").write_text(
        "# Details\n\nDetailed reference content.\n",
        encoding="utf-8",
    )
    (refs_dir / "extra.md").write_text(
        "# Extra\n\nExtra reference.\n",
        encoding="utf-8",
    )

    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "helper.py").write_text(
        "# Helper script\nprint('hello')\n",
        encoding="utf-8",
    )

    return tmp_path


@pytest.fixture
def loaded_ctx(skills_dir: Path) -> MockRunContext:
    """Create a mock context with initialized skill loader."""
    loader = SkillLoader(skills_dir)
    loader.discover_skills()
    deps = MockAgentDeps(skill_loader=loader)
    return MockRunContext(deps=deps)


@pytest.fixture
def empty_ctx() -> MockRunContext:
    """Create a mock context without skill loader."""
    deps = MockAgentDeps(skill_loader=None)
    return MockRunContext(deps=deps)


class TestLoadSkill:
    """Test load_skill tool (Level 2 progressive disclosure)."""

    @pytest.mark.asyncio
    async def test_loads_skill_body(self, loaded_ctx: MockRunContext) -> None:
        """Returns SKILL.md body without YAML frontmatter."""
        result = await load_skill(loaded_ctx, "test-skill")

        assert "# Test Skill" in result
        assert "Step 1: Do something." in result
        # Should NOT contain frontmatter
        assert "name: test-skill" not in result
        assert "---" not in result

    @pytest.mark.asyncio
    async def test_skill_not_found(self, loaded_ctx: MockRunContext) -> None:
        """Returns error with available skills when skill not found."""
        result = await load_skill(loaded_ctx, "nonexistent")

        assert "Error" in result
        assert "nonexistent" in result
        assert "test-skill" in result  # lists available skills

    @pytest.mark.asyncio
    async def test_skill_loader_not_initialized(
        self, empty_ctx: MockRunContext
    ) -> None:
        """Returns error when skill_loader is None."""
        result = await load_skill(empty_ctx, "test-skill")

        assert "Error" in result
        assert "not initialized" in result


class TestReadSkillFile:
    """Test read_skill_file tool (Level 3 progressive disclosure)."""

    @pytest.mark.asyncio
    async def test_reads_reference_file(self, loaded_ctx: MockRunContext) -> None:
        """Reads a reference file from within the skill directory."""
        result = await read_skill_file(
            loaded_ctx, "test-skill", "references/details.md"
        )

        assert "# Details" in result
        assert "Detailed reference content." in result

    @pytest.mark.asyncio
    async def test_reads_script_file(self, loaded_ctx: MockRunContext) -> None:
        """Reads a script file from within the skill directory."""
        result = await read_skill_file(loaded_ctx, "test-skill", "scripts/helper.py")

        assert "Helper script" in result

    @pytest.mark.asyncio
    async def test_file_not_found(self, loaded_ctx: MockRunContext) -> None:
        """Returns error when file doesn't exist."""
        result = await read_skill_file(
            loaded_ctx, "test-skill", "references/missing.md"
        )

        assert "Error" in result
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_directory_traversal_blocked(
        self, loaded_ctx: MockRunContext
    ) -> None:
        """Prevents directory traversal attacks."""
        result = await read_skill_file(loaded_ctx, "test-skill", "../../etc/passwd")

        assert "Error" in result
        assert "denied" in result.lower() or "invalid" in result.lower()

    @pytest.mark.asyncio
    async def test_skill_not_found(self, loaded_ctx: MockRunContext) -> None:
        """Returns error when skill doesn't exist."""
        result = await read_skill_file(loaded_ctx, "nonexistent", "file.md")

        assert "Error" in result
        assert "nonexistent" in result


class TestListSkillFiles:
    """Test list_skill_files tool (resource discovery)."""

    @pytest.mark.asyncio
    async def test_lists_all_files(self, loaded_ctx: MockRunContext) -> None:
        """Lists all files in a skill directory."""
        result = await list_skill_files(loaded_ctx, "test-skill")

        assert "SKILL.md" in result
        assert "references/details.md" in result
        assert "references/extra.md" in result
        assert "scripts/helper.py" in result

    @pytest.mark.asyncio
    async def test_lists_subdirectory(self, loaded_ctx: MockRunContext) -> None:
        """Lists files in a specific subdirectory."""
        result = await list_skill_files(loaded_ctx, "test-skill", "references")

        assert "details.md" in result
        assert "extra.md" in result
        # Should not list files outside the subdirectory
        assert "helper.py" not in result

    @pytest.mark.asyncio
    async def test_skill_not_found(self, loaded_ctx: MockRunContext) -> None:
        """Returns error when skill doesn't exist."""
        result = await list_skill_files(loaded_ctx, "nonexistent")

        assert "Error" in result
        assert "nonexistent" in result

    @pytest.mark.asyncio
    async def test_directory_traversal_blocked(
        self, loaded_ctx: MockRunContext
    ) -> None:
        """Prevents directory traversal in directory parameter."""
        result = await list_skill_files(loaded_ctx, "test-skill", "../../")

        assert "Error" in result
        assert "denied" in result.lower() or "invalid" in result.lower()

    @pytest.mark.asyncio
    async def test_skill_loader_not_initialized(
        self, empty_ctx: MockRunContext
    ) -> None:
        """Returns error when skill_loader is None."""
        result = await list_skill_files(empty_ctx, "test-skill")

        assert "Error" in result
        assert "not initialized" in result


class TestLoadSkillViaAgent:
    """Test that agent's load_skill wrapper works correctly."""

    @pytest.mark.asyncio
    async def test_load_skill_returns_content(self, loaded_ctx: MockRunContext) -> None:
        """Agent load_skill returns skill body content."""
        from src.agent import load_skill as agent_load_skill

        result = await agent_load_skill(loaded_ctx, "test-skill")

        assert "# Test Skill" in result
        assert "Step 1: Do something." in result

    @pytest.mark.asyncio
    async def test_failed_load_returns_error(self, loaded_ctx: MockRunContext) -> None:
        """Failed load_skill returns error message."""
        from src.agent import load_skill as agent_load_skill

        result = await agent_load_skill(loaded_ctx, "nonexistent")

        assert "Error" in result


class TestSkillScriptsImportable:
    """Verify all migrated skill scripts have execute() function."""

    def test_skill_scripts_importable(self) -> None:
        """All migrated skill scripts export async execute() function."""
        import importlib.util
        import inspect

        scripts = [
            ("nutrition-calculating", "calculate_nutritional_needs"),
            ("knowledge-searching", "retrieve_relevant_documents"),
            ("knowledge-searching", "web_search"),
            ("body-analyzing", "image_analysis"),
            ("weekly-coaching", "calculate_weekly_adjustments"),
        ]
        for skill, script in scripts:
            path = Path(f"skills/{skill}/scripts/{script}.py")
            assert path.exists(), f"Script not found: {path}"
            spec = importlib.util.spec_from_file_location("test_mod", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            assert hasattr(mod, "execute"), f"{skill}/{script} missing execute()"
            assert inspect.iscoroutinefunction(
                mod.execute
            ), f"{skill}/{script} execute() should be async"
