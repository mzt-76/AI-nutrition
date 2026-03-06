"""E2E eval — get_daily_summary routing via agent with real LLM.

WHY THIS IS AN EVAL, NOT A TEST
================================
These scenarios involve a real LLM (Haiku 4.5) making decisions:
  - Does the agent route "combien il me reste" to food-tracking/get_daily_summary?
  - Does the agent use the summary data to give concrete macro advice?
  - Does the agent call get_daily_summary BEFORE suggesting foods to fill the gap?

Outcomes are non-deterministic → scored criteria, not exact assertions.
Run on demand before releases, NOT in CI (slow, costs API credits).

    pytest evals/test_daily_summary_e2e.py -m integration -v -s

TEST PERSONA — all required fields defined here, never assumed elsewhere.
=========================================================================
Name:            Marc
Age:             24
Gender:          male
Height:          191 cm
Weight:          86 kg
Activity level:  light (×1.375)
Goal:            muscle gain

Uses the same real Supabase user as food_logging evals so the script
can query daily_food_log and user_profiles.
"""

import json
from dataclasses import dataclass, field

import pytest
from pydantic_ai.messages import ToolCallPart
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import (
    Evaluator,
    EvaluationReason,
    EvaluatorContext,
    MaxDuration,
)

from src.agent import agent, create_agent_deps

# ---------------------------------------------------------------------------
# Test persona — single source of truth
# ---------------------------------------------------------------------------

TEST_USER_PROFILE = {
    "age": 24,
    "gender": "male",
    "height_cm": 191,
    "weight_kg": 86.0,
    "activity_level": "light",
    "goal": "muscle_gain",
    "diet_type": "omnivore",
    "allergies": [],
}

# Real Supabase user for DB operations
TEST_USER_ID = "5745fc58-9c75-48b1-bc79-12855a8c6021"


# ---------------------------------------------------------------------------
# Structured output — text + tool calls
# ---------------------------------------------------------------------------


@dataclass
class AgentResult:
    """Captures both text output and tool call history from an agent run."""

    text: str
    tool_calls: list[dict]  # [{"name": "...", "args": {...}}, ...]


# ---------------------------------------------------------------------------
# Evaluators
# ---------------------------------------------------------------------------


@dataclass
class NoRefusal(Evaluator):
    """Check the agent did not refuse or say it cannot help."""

    evaluation_name: str | None = field(default=None)

    _REFUSAL_PHRASES = [
        "je ne peux pas",
        "je suis incapable",
        "impossible de",
        "i cannot",
        "i'm unable",
    ]

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        text = result.text.lower()
        for phrase in self._REFUSAL_PHRASES:
            if phrase in text:
                return EvaluationReason(
                    value=False, reason=f"Refusal detected: '{phrase}'"
                )
        return EvaluationReason(value=True, reason="No refusal detected")


@dataclass
class ContainsAnyOf(Evaluator):
    """Check that at least one substring appears in the text output."""

    options: list[str]
    case_sensitive: bool = False
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        haystack = result.text if self.case_sensitive else result.text.lower()
        for option in self.options:
            needle = option if self.case_sensitive else option.lower()
            if needle in haystack:
                return EvaluationReason(value=True, reason=f"Found '{option}'")
        return EvaluationReason(
            value=False,
            reason=f"None of {self.options} found in response",
        )


@dataclass
class ResponseMinLength(Evaluator):
    """Check the response is substantive."""

    min_chars: int
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        length = len(result.text)
        if length >= self.min_chars:
            return EvaluationReason(
                value=True, reason=f"{length} chars >= {self.min_chars}"
            )
        return EvaluationReason(
            value=False,
            reason=f"Response too short: {length} chars < {self.min_chars}",
        )


@dataclass
class SkillScriptRouting(Evaluator):
    """Check that run_skill_script was called with a specific skill+script."""

    expected_skill: str
    expected_script: str
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        for tc in result.tool_calls:
            if tc["name"] != "run_skill_script":
                continue
            args = tc["args"]
            skill = args.get("skill_name", "")
            script = args.get("script_name", "")
            if skill == self.expected_skill and script == self.expected_script:
                return EvaluationReason(
                    value=True,
                    reason=f"Correct routing: {skill}/{script}",
                )
        scripts_called = [
            f"{tc['args'].get('skill_name')}/{tc['args'].get('script_name')}"
            for tc in result.tool_calls
            if tc["name"] == "run_skill_script"
        ]
        return EvaluationReason(
            value=False,
            reason=f"Expected {self.expected_skill}/{self.expected_script}. "
            f"Called: {scripts_called or 'no run_skill_script calls'}",
        )


@dataclass
class MentionsMacroNumbers(Evaluator):
    """Check that the response mentions concrete macro numbers (not just vague advice).

    Looks for patterns like "750 kcal", "55g de protéines", etc. — evidence
    the agent actually used the summary data rather than improvising.
    """

    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        text = result.text.lower()
        # Look for number + unit patterns that indicate macro data
        macro_keywords = ["kcal", "calories", "protéine", "glucide", "lipide", "g"]
        import re

        numbers = re.findall(r"\d+", text)
        has_numbers = len(numbers) >= 2  # At least 2 numbers (consumed + remaining)
        has_units = any(kw in text for kw in macro_keywords)
        if has_numbers and has_units:
            return EvaluationReason(
                value=True,
                reason=f"Found {len(numbers)} numbers with macro units",
            )
        return EvaluationReason(
            value=False,
            reason=f"Expected concrete macro numbers. Numbers found: {numbers[:5]}, "
            f"units found: {[kw for kw in macro_keywords if kw in text]}",
        )


# ---------------------------------------------------------------------------
# Task function — real agent, real Haiku 4.5, captures tool calls
# ---------------------------------------------------------------------------


async def _run_agent(message: str) -> AgentResult:
    """Run the agent with real Haiku 4.5 and return text + tool calls."""
    deps = create_agent_deps(user_id=TEST_USER_ID)
    result = await agent.run(message, deps=deps)

    tool_calls = []
    for msg in result.all_messages():
        for part in getattr(msg, "parts", []):
            if isinstance(part, ToolCallPart):
                args = part.args
                if isinstance(args, str):
                    args = json.loads(args)
                tool_calls.append({"name": part.tool_name, "args": args})

    return AgentResult(text=result.output, tool_calls=tool_calls)


# ---------------------------------------------------------------------------
# Scenario 1 — "Combien il me reste ?" → get_daily_summary
#
# User asks how many calories remain today. Agent should call
# get_daily_summary and respond with concrete consumed/remaining numbers.
# ---------------------------------------------------------------------------


def scenario_1_remaining_calories() -> Dataset:
    """Agent fetches daily summary when asked about remaining calories."""
    return Dataset(
        name="scenario_1_remaining_calories",
        cases=[
            Case(
                name="how_many_calories_left",
                inputs=("Combien de calories il me reste aujourd'hui ?"),
                evaluators=(
                    NoRefusal(),
                    SkillScriptRouting(
                        expected_skill="food-tracking",
                        expected_script="get_daily_summary",
                        evaluation_name="routes_to_get_daily_summary",
                    ),
                    MentionsMacroNumbers(
                        evaluation_name="mentions_concrete_numbers",
                    ),
                    ContainsAnyOf(
                        options=["reste", "consommé", "objectif", "cible", "restant"],
                        evaluation_name="mentions_remaining_concept",
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=90.0)],
    )


# ---------------------------------------------------------------------------
# Scenario 2 — "Que me conseilles-tu pour finir mon quota ?" → get_daily_summary first
#
# User asks for food suggestions to fill the gap. Agent should first call
# get_daily_summary to know the gap, then suggest foods accordingly.
# ---------------------------------------------------------------------------


def scenario_2_fill_the_gap_advice() -> Dataset:
    """Agent fetches summary first, then suggests foods to fill the gap."""
    return Dataset(
        name="scenario_2_fill_the_gap_advice",
        cases=[
            Case(
                name="suggest_foods_for_remaining",
                inputs=(
                    "Que me conseilles-tu pour finir mon quota calorique aujourd'hui ?"
                ),
                evaluators=(
                    NoRefusal(),
                    SkillScriptRouting(
                        expected_skill="food-tracking",
                        expected_script="get_daily_summary",
                        evaluation_name="fetches_summary_first",
                    ),
                    ResponseMinLength(
                        min_chars=100,
                        evaluation_name="substantive_advice",
                    ),
                    ContainsAnyOf(
                        options=[
                            "reste",
                            "manque",
                            "restant",
                            "compléter",
                            "atteindre",
                            "objectif",
                        ],
                        evaluation_name="references_remaining_gap",
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=90.0)],
    )


# ---------------------------------------------------------------------------
# Pytest test functions — marked integration (excluded from CI)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_scenario_1_remaining_calories():
    """E2E: Agent routes 'combien il me reste' to get_daily_summary (real Haiku 4.5)."""
    dataset = scenario_1_remaining_calories()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.integration
async def test_scenario_2_fill_the_gap_advice():
    """E2E: Agent fetches summary then suggests foods to fill gap (real Haiku 4.5)."""
    dataset = scenario_2_fill_the_gap_advice()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"
