"""Pydantic-evals test suite for skill progressive disclosure system.

Tests skill discovery, loading, content quality, and error handling using
the pydantic-evals framework for structured evaluation.
"""

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import (
    Evaluator,
    EvaluationReason,
    EvaluatorContext,
    IsInstance,
    MaxDuration,
)

from src.skill_loader import SkillLoader
from src.skill_tools import list_skill_files, load_skill, read_skill_file

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = PROJECT_ROOT / "skills"

EXPECTED_SKILLS = {
    "nutrition-calculating",
    "meal-planning",
    "food-tracking",
    "shopping-list",
    "weekly-coaching",
    "knowledge-searching",
    "body-analyzing",
}


@dataclass
class _MockAgentDeps:
    skill_loader: SkillLoader | None = None


class _MockRunContext:
    def __init__(self, deps: _MockAgentDeps) -> None:
        self.deps = deps


def _make_ctx() -> _MockRunContext:
    loader = SkillLoader(SKILLS_DIR)
    loader.discover_skills()
    return _MockRunContext(deps=_MockAgentDeps(skill_loader=loader))


# ---------------------------------------------------------------------------
# Custom evaluators
# ---------------------------------------------------------------------------


@dataclass
class ContainsSubstring(Evaluator):
    """Assert that the output string contains a specific substring."""

    substring: str
    case_sensitive: bool = True
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        output = str(ctx.output)
        target = self.substring
        haystack = output if self.case_sensitive else output.lower()
        needle = target if self.case_sensitive else target.lower()

        if needle in haystack:
            return EvaluationReason(value=True, reason=f"Found '{target}'")
        return EvaluationReason(
            value=False,
            reason=f"'{target}' not found in output ({len(output)} chars)",
        )


@dataclass
class DoesNotContain(Evaluator):
    """Assert that the output string does NOT contain a specific substring."""

    substring: str
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        output = str(ctx.output)
        if self.substring not in output:
            return EvaluationReason(
                value=True, reason=f"'{self.substring}' absent (good)"
            )
        return EvaluationReason(
            value=False,
            reason=f"'{self.substring}' unexpectedly found in output",
        )


@dataclass
class MinLength(Evaluator):
    """Assert that output string meets a minimum length (content quality check)."""

    min_chars: int
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        length = len(str(ctx.output))
        if length >= self.min_chars:
            return EvaluationReason(
                value=True, reason=f"{length} chars >= {self.min_chars}"
            )
        return EvaluationReason(
            value=False,
            reason=f"Output too short: {length} chars < {self.min_chars}",
        )


@dataclass
class NoError(Evaluator):
    """Assert that output does not start with 'Error'."""

    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        output = str(ctx.output)
        if not output.startswith("Error"):
            return EvaluationReason(value=True, reason="No error prefix")
        return EvaluationReason(value=False, reason=f"Error response: {output[:100]}")


@dataclass
class IsError(Evaluator):
    """Assert that output IS an error response."""

    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        output = str(ctx.output)
        if "Error" in output:
            return EvaluationReason(value=True, reason="Got expected error")
        return EvaluationReason(
            value=False, reason=f"Expected error, got: {output[:100]}"
        )


# ---------------------------------------------------------------------------
# Task functions
# ---------------------------------------------------------------------------


async def _load_skill_task(inputs: dict) -> str:
    """Task: load a skill and return its content."""
    ctx = _make_ctx()
    return await load_skill(ctx, inputs["skill_name"])


async def _read_file_task(inputs: dict) -> str:
    """Task: read a reference file from a skill."""
    ctx = _make_ctx()
    return await read_skill_file(ctx, inputs["skill_name"], inputs["file_path"])


async def _list_files_task(inputs: dict) -> str:
    """Task: list files in a skill directory."""
    ctx = _make_ctx()
    return await list_skill_files(
        ctx, inputs["skill_name"], inputs.get("directory", "")
    )


async def _discover_skills_task(inputs: dict) -> dict:
    """Task: discover skills and return metadata."""
    loader = SkillLoader(SKILLS_DIR)
    discovered = loader.discover_skills()
    return {
        "count": len(discovered),
        "names": sorted(s.name for s in discovered),
        "metadata_prompt": loader.get_skill_metadata_prompt(),
    }


# ---------------------------------------------------------------------------
# Eval datasets
# ---------------------------------------------------------------------------


def skill_loading_dataset() -> Dataset:
    """Dataset: loading each skill returns valid content without frontmatter."""
    cases = [
        Case(
            name=f"load_{skill_name}",
            inputs={"skill_name": skill_name},
            evaluators=(
                NoError(),
                MinLength(min_chars=100),
                ContainsSubstring(substring="## Quand utiliser"),
                ContainsSubstring(substring="outil", case_sensitive=False),
            ),
        )
        for skill_name in sorted(EXPECTED_SKILLS)
    ]

    return Dataset(
        name="skill_loading",
        cases=cases,
        evaluators=[IsInstance(type_name="str"), MaxDuration(seconds=2.0)],
    )


def skill_error_handling_dataset() -> Dataset:
    """Dataset: error cases return helpful error messages."""
    return Dataset(
        name="skill_error_handling",
        cases=[
            Case(
                name="load_nonexistent_skill",
                inputs={"skill_name": "nonexistent"},
                evaluators=(
                    IsError(),
                    ContainsSubstring(substring="nonexistent"),
                    ContainsSubstring(substring="meal-planning"),
                ),
            ),
            Case(
                name="read_file_nonexistent_skill",
                inputs={"skill_name": "nonexistent", "file_path": "any.md"},
                evaluators=(IsError(), ContainsSubstring(substring="nonexistent")),
            ),
            Case(
                name="read_file_missing_file",
                inputs={
                    "skill_name": "meal-planning",
                    "file_path": "references/missing.md",
                },
                evaluators=(
                    IsError(),
                    ContainsSubstring(substring="not found", case_sensitive=False),
                ),
            ),
            Case(
                name="read_file_directory_traversal",
                inputs={"skill_name": "meal-planning", "file_path": "../../etc/passwd"},
                evaluators=(IsError(),),
            ),
            Case(
                name="list_files_directory_traversal",
                inputs={"skill_name": "meal-planning", "directory": "../../"},
                evaluators=(IsError(),),
            ),
        ],
    )


def reference_file_loading_dataset() -> Dataset:
    """Dataset: reference files load correctly with expected content."""
    return Dataset(
        name="reference_file_loading",
        cases=[
            Case(
                name="read_nutrition_formulas",
                inputs={
                    "skill_name": "nutrition-calculating",
                    "file_path": "references/formulas.md",
                },
                evaluators=(
                    NoError(),
                    MinLength(min_chars=100),
                    ContainsSubstring(substring="Mifflin", case_sensitive=False),
                ),
            ),
            Case(
                name="read_meal_presentation",
                inputs={
                    "skill_name": "meal-planning",
                    "file_path": "references/presentation_format.md",
                },
                evaluators=(NoError(), MinLength(min_chars=100)),
            ),
            Case(
                name="read_allergen_families",
                inputs={
                    "skill_name": "meal-planning",
                    "file_path": "references/allergen_families.md",
                },
                evaluators=(
                    NoError(),
                    ContainsSubstring(substring="arachides", case_sensitive=False),
                ),
            ),
            Case(
                name="read_red_flag_protocol",
                inputs={
                    "skill_name": "weekly-coaching",
                    "file_path": "references/red_flag_protocol.md",
                },
                evaluators=(
                    NoError(),
                    ContainsSubstring(substring="CRITICAL"),
                    ContainsSubstring(substring="WARNING"),
                ),
            ),
            Case(
                name="read_shopping_list_format",
                inputs={
                    "skill_name": "meal-planning",
                    "file_path": "references/shopping_list_format.md",
                },
                evaluators=(NoError(), MinLength(min_chars=50)),
            ),
        ],
        evaluators=[IsInstance(type_name="str"), MaxDuration(seconds=0.5)],
    )


def skill_discovery_dataset() -> Dataset:
    """Dataset: skill discovery finds all expected skills with valid metadata."""

    @dataclass
    class DiscoverCountCheck(Evaluator):
        min_count: int = 6
        evaluation_name: str | None = field(default=None)

        def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
            count = ctx.output.get("count", 0) if isinstance(ctx.output, dict) else 0
            if count >= self.min_count:
                return EvaluationReason(value=True, reason=f"Found {count} skills")
            return EvaluationReason(
                value=False,
                reason=f"Expected >= {self.min_count} skills, got {count}",
            )

    @dataclass
    class AllExpectedSkills(Evaluator):
        expected: list = field(default_factory=lambda: sorted(EXPECTED_SKILLS))
        evaluation_name: str | None = field(default=None)

        def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
            names = (
                set(ctx.output.get("names", []))
                if isinstance(ctx.output, dict)
                else set()
            )
            missing = set(self.expected) - names
            if not missing:
                return EvaluationReason(value=True, reason="All expected skills found")
            return EvaluationReason(value=False, reason=f"Missing skills: {missing}")

    @dataclass
    class MetadataPromptHasSkills(Evaluator):
        evaluation_name: str | None = field(default=None)

        def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
            prompt = (
                ctx.output.get("metadata_prompt", "")
                if isinstance(ctx.output, dict)
                else ""
            )
            missing = [s for s in EXPECTED_SKILLS if f"**{s}**" not in prompt]
            if not missing:
                return EvaluationReason(
                    value=True, reason="All skills in metadata prompt"
                )
            return EvaluationReason(
                value=False,
                reason=f"Missing from metadata prompt: {missing}",
            )

    return Dataset(
        name="skill_discovery",
        cases=[
            Case(
                name="discover_all_project_skills",
                inputs={},
                evaluators=(
                    DiscoverCountCheck(min_count=8),
                    AllExpectedSkills(),
                    MetadataPromptHasSkills(),
                ),
            ),
        ],
        evaluators=[IsInstance(type_name="dict"), MaxDuration(seconds=2.0)],
    )


def file_listing_dataset() -> Dataset:
    """Dataset: list_skill_files returns complete file listings."""
    return Dataset(
        name="file_listing",
        cases=[
            Case(
                name="list_meal_planning_all_files",
                inputs={"skill_name": "meal-planning"},
                evaluators=(
                    NoError(),
                    ContainsSubstring(substring="SKILL.md"),
                    ContainsSubstring(substring="presentation_format.md"),
                    ContainsSubstring(substring="allergen_families.md"),
                ),
            ),
            Case(
                name="list_meal_planning_references_only",
                inputs={"skill_name": "meal-planning", "directory": "references"},
                evaluators=(
                    NoError(),
                    ContainsSubstring(substring="presentation_format.md"),
                    DoesNotContain(substring="SKILL.md"),
                ),
            ),
            Case(
                name="list_weekly_coaching_files",
                inputs={"skill_name": "weekly-coaching"},
                evaluators=(
                    NoError(),
                    ContainsSubstring(substring="red_flag_protocol.md"),
                ),
            ),
        ],
        evaluators=[IsInstance(type_name="str"), MaxDuration(seconds=0.5)],
    )


# ---------------------------------------------------------------------------
# Pytest test functions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skill_loading_eval():
    """Eval: All 6 skills load correctly with valid content."""
    dataset = skill_loading_dataset()
    report = await dataset.evaluate(task=_load_skill_task)
    report.print()
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.asyncio
async def test_skill_error_handling_eval():
    """Eval: Error cases produce helpful error messages."""
    dataset = skill_error_handling_dataset()

    async def _dispatch(inputs: dict) -> str:
        if "file_path" in inputs:
            return await _read_file_task(inputs)
        if "directory" in inputs:
            return await _list_files_task(inputs)
        return await _load_skill_task(inputs)

    report = await dataset.evaluate(task=_dispatch)
    report.print()
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.asyncio
async def test_reference_file_loading_eval():
    """Eval: Reference files load with correct content."""
    dataset = reference_file_loading_dataset()
    report = await dataset.evaluate(task=_read_file_task)
    report.print()
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.asyncio
async def test_skill_discovery_eval():
    """Eval: Skill discovery finds all expected skills with metadata."""
    dataset = skill_discovery_dataset()
    report = await dataset.evaluate(task=_discover_skills_task)
    report.print()
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.asyncio
async def test_file_listing_eval():
    """Eval: File listing returns complete, correct listings."""
    dataset = file_listing_dataset()
    report = await dataset.evaluate(task=_list_files_task)
    report.print()
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    async def run_all_evals():
        """Run all eval suites and print reports."""
        datasets = [
            ("Skill Discovery", skill_discovery_dataset(), _discover_skills_task),
            ("Skill Loading", skill_loading_dataset(), _load_skill_task),
            ("Reference Files", reference_file_loading_dataset(), _read_file_task),
            ("File Listing", file_listing_dataset(), _list_files_task),
        ]

        for name, dataset, task in datasets:
            print(f"\n{'='*60}")
            print(f"  {name}")
            print(f"{'='*60}")
            report = await dataset.evaluate(task=task)
            report.print()

        # Error handling needs a dispatcher
        print(f"\n{'='*60}")
        print("  Error Handling")
        print(f"{'='*60}")

        async def _dispatch(inputs: dict) -> str:
            if "file_path" in inputs:
                return await _read_file_task(inputs)
            if "directory" in inputs:
                return await _list_files_task(inputs)
            return await _load_skill_task(inputs)

        dataset = skill_error_handling_dataset()
        report = await dataset.evaluate(task=_dispatch)
        report.print()

    asyncio.run(run_all_evals())
