"""E2E eval — tracker meal details + meal_structure routing.

WHY THIS IS AN EVAL, NOT A TEST
================================
These scenarios involve a real LLM (Haiku 4.5) making decisions:
  - Does the agent return individual food items when asked "what did I eat?"
  - Does the agent pass meal_structure="3_consequent_meals" when user says "no snacks"?

Outcomes are non-deterministic → scored criteria, not exact assertions.
Run on demand before releases, NOT in CI (slow, costs API credits).

    pytest evals/test_tracker_details_and_meal_structure_e2e.py -m integration -v -s

TEST PERSONA — all required fields defined here, never assumed elsewhere.
=========================================================================
Name:            Marc
Age:             24
Gender:          male
Height:          191 cm
Weight:          86 kg
Activity level:  active (×1.725) — above 2500 kcal threshold
Goal:            muscle gain
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
    "activity_level": "active",
    "goal": "muscle_gain",
    "diet_type": "omnivore",
    "allergies": [],
}

# Real Supabase user for DB operations (meuzeretl@gmail.com — prod)
TEST_USER_ID = "0fdc6878-7384-4ca6-a92b-f26dbe4d0dfc"


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
class ScriptParamsMealStructure(Evaluator):
    """Check that meal_structure parameter matches the expected value."""

    expected_value: str
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        for tc in result.tool_calls:
            if tc["name"] != "run_skill_script":
                continue
            args = tc["args"]
            if args.get("skill_name") != "meal-planning":
                continue
            params = args.get("parameters", {})
            if isinstance(params, str):
                try:
                    params = json.loads(params)
                except json.JSONDecodeError:
                    continue
            meal_structure = params.get("meal_structure", "")
            if meal_structure == self.expected_value:
                return EvaluationReason(
                    value=True,
                    reason=f"meal_structure='{meal_structure}' matches expected",
                )
            if meal_structure:
                return EvaluationReason(
                    value=False,
                    reason=f"meal_structure='{meal_structure}' != '{self.expected_value}'",
                )
        return EvaluationReason(
            value=False,
            reason="meal_structure not found in any meal-planning call",
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
# Scenario 1 — Tracker returns meal details
#
# User asks "what did I eat this morning?" — agent should call
# get_daily_summary and include individual food items in response.
# ---------------------------------------------------------------------------


def scenario_1_tracker_meal_details() -> Dataset:
    """Agent returns detailed food items when asked about a specific meal."""
    return Dataset(
        name="scenario_1_tracker_meal_details",
        cases=[
            Case(
                name="what_did_i_eat_today",
                inputs=(
                    "Qu'est-ce que j'ai mangé aujourd'hui ? "
                    "Donne-moi le détail de chaque repas avec les aliments."
                ),
                evaluators=(
                    NoRefusal(),
                    SkillScriptRouting(
                        expected_skill="food-tracking",
                        expected_script="get_daily_summary",
                        evaluation_name="routes_to_get_daily_summary",
                    ),
                    # Response should mention specific food items, not just totals
                    ContainsAnyOf(
                        options=[
                            "petit-déjeuner",
                            "petit-dej",
                            "petit déjeuner",
                            "déjeuner",
                            "dîner",
                            "diner",
                            "kcal",
                            "calories",
                        ],
                        evaluation_name="mentions_meals",
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=90.0)],
    )


# ---------------------------------------------------------------------------
# Scenario 2 — Meal structure: 3 meals, no snacks
#
# User asks for a plan with "3 repas sans collation" — agent should pass
# meal_structure="3_consequent_meals" to generate_week_plan.
# ---------------------------------------------------------------------------


def scenario_2_meal_structure_no_snack() -> Dataset:
    """Agent passes meal_structure=3_consequent_meals when user says no snack."""
    return Dataset(
        name="scenario_2_meal_structure_no_snack",
        cases=[
            Case(
                name="three_meals_no_snack_explicit",
                inputs=(
                    "Génère mon plan repas pour demain sans me poser de questions. "
                    "3 repas principaux, pas de collation."
                ),
                evaluators=(
                    NoRefusal(),
                    SkillScriptRouting(
                        expected_skill="meal-planning",
                        expected_script="generate_week_plan",
                        evaluation_name="routes_to_generate_week_plan",
                    ),
                    ScriptParamsMealStructure(
                        expected_value="3_consequent_meals",
                        evaluation_name="passes_3_consequent_meals",
                    ),
                ),
            ),
            Case(
                name="remove_snack_french",
                inputs=(
                    "Fais-moi un plan pour demain, juste 3 repas sans collation. "
                    "Pas de questions, lance directement."
                ),
                evaluators=(
                    NoRefusal(),
                    SkillScriptRouting(
                        expected_skill="meal-planning",
                        expected_script="generate_week_plan",
                        evaluation_name="routes_to_generate_week_plan",
                    ),
                    ScriptParamsMealStructure(
                        expected_value="3_consequent_meals",
                        evaluation_name="passes_3_consequent_meals",
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=120.0)],
    )


# ---------------------------------------------------------------------------
# Pytest test functions — marked integration (excluded from CI)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_scenario_1_tracker_meal_details():
    """E2E: Agent returns meal details from tracker (real Haiku 4.5)."""
    dataset = scenario_1_tracker_meal_details()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.integration
async def test_scenario_2_meal_structure_no_snack():
    """E2E: Agent passes meal_structure=3_consequent_meals when no snack requested."""
    dataset = scenario_2_meal_structure_no_snack()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"
