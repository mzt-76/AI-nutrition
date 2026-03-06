"""E2E eval — food logging via agent + log_food_entries script with real LLM.

WHY THIS IS AN EVAL, NOT A TEST
================================
These scenarios involve a real LLM (Haiku 4.5) making decisions:
  - Does the agent route food logging to food-tracking/log_food_entries?
  - Does the agent extract ingredient names, quantities, and units from NL?
  - Does the agent decompose composite dishes into individual ingredients?
  - Does the agent pass the correct meal_type and log_date?

Outcomes are non-deterministic → scored criteria, not exact assertions.
Run on demand before releases, NOT in CI (slow, costs API credits).

    pytest evals/test_food_logging_e2e.py -m integration -v -s

TEST PERSONA — all required fields defined here, never assumed elsewhere.
=========================================================================
Name:            Marc
Age:             24
Gender:          male
Height:          191 cm
Weight:          86 kg
Activity level:  light (×1.375)
Goal:            muscle gain

Food logging scenarios:
  1. Simple ingredients with explicit quantities → direct log
  2. Composite dish (recipe name) → agent decomposes into ingredients → log
  3. Meal type inference from context (petit-dej vs dejeuner vs diner)

NOTE: These evals use create_agent_deps(user_id=...) with a real Supabase
user so the skill script can insert into daily_food_log.
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
class ScriptParamsContainItems(Evaluator):
    """Check that run_skill_script parameters contain an 'items' list with >= min_count entries."""

    min_count: int
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        for tc in result.tool_calls:
            if tc["name"] != "run_skill_script":
                continue
            params = tc["args"].get("parameters", {})
            if isinstance(params, str):
                try:
                    params = json.loads(params)
                except json.JSONDecodeError:
                    continue
            items = params.get("items", [])
            if len(items) >= self.min_count:
                names = [it.get("name", "?") for it in items]
                return EvaluationReason(
                    value=True,
                    reason=f"Found {len(items)} items: {names}",
                )
        return EvaluationReason(
            value=False,
            reason=f"Expected >= {self.min_count} items in parameters. "
            f"Check run_skill_script calls.",
        )


@dataclass
class ScriptParamsMealType(Evaluator):
    """Check that the meal_type parameter matches one of the expected values."""

    expected_types: list[str]
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        for tc in result.tool_calls:
            if tc["name"] != "run_skill_script":
                continue
            params = tc["args"].get("parameters", {})
            if isinstance(params, str):
                try:
                    params = json.loads(params)
                except json.JSONDecodeError:
                    continue
            meal_type = params.get("meal_type", "")
            if meal_type in self.expected_types:
                return EvaluationReason(
                    value=True,
                    reason=f"meal_type='{meal_type}' matches expected {self.expected_types}",
                )
        return EvaluationReason(
            value=False,
            reason=f"meal_type not in {self.expected_types}",
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
# Scenario 1 — Simple food logging with explicit quantities
#
# User says "200g de poulet et 150g de riz" with SUIVI RAPIDE prefix.
# Agent should route to food-tracking/log_food_entries with 2 items.
# ---------------------------------------------------------------------------


def scenario_1_simple_food_logging() -> Dataset:
    """Agent logs simple ingredients with explicit quantities."""
    return Dataset(
        name="scenario_1_simple_food_logging",
        cases=[
            Case(
                name="chicken_and_rice_explicit",
                inputs=(
                    "[SUIVI RAPIDE - date: 2026-03-05] L'utilisateur déclare avoir mangé : "
                    '"200g de poulet grillé et 150g de riz basmati". '
                    "Enregistre ces aliments dans le journal du 2026-03-05. "
                    "Réponds uniquement par une confirmation courte."
                ),
                evaluators=(
                    NoRefusal(),
                    # Must route to log_food_entries
                    SkillScriptRouting(
                        expected_skill="meal-planning",
                        expected_script="log_food_entries",
                        evaluation_name="routes_to_log_food_entries",
                    ),
                    # Must pass >= 2 items
                    ScriptParamsContainItems(
                        min_count=2,
                        evaluation_name="extracts_2_items",
                    ),
                    # Response should confirm logging
                    ContainsAnyOf(
                        options=[
                            "enregistré",
                            "ajouté",
                            "noté",
                            "journal",
                            "kcal",
                            "calories",
                            "poulet",
                            "logged",
                        ],
                        evaluation_name="confirms_logging",
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=90.0)],
    )


# ---------------------------------------------------------------------------
# Scenario 2 — Composite dish decomposition
#
# User says "pâtes carbonara" — agent must decompose into individual
# ingredients (pâtes, lardons, oeuf, crème, parmesan) before calling
# log_food_entries. The script only handles simple ingredients.
# ---------------------------------------------------------------------------


def scenario_2_composite_dish_decomposition() -> Dataset:
    """Agent decomposes a composite dish into individual ingredients before logging."""
    return Dataset(
        name="scenario_2_composite_dish_decomposition",
        cases=[
            Case(
                name="pates_carbonara_decomposed",
                inputs=(
                    "[SUIVI RAPIDE - date: 2026-03-05] L'utilisateur déclare avoir mangé : "
                    '"des pâtes carbonara". '
                    "Enregistre ces aliments dans le journal du 2026-03-05. "
                    "Réponds uniquement par une confirmation courte."
                ),
                evaluators=(
                    NoRefusal(),
                    # Must route to log_food_entries
                    SkillScriptRouting(
                        expected_skill="meal-planning",
                        expected_script="log_food_entries",
                        evaluation_name="routes_to_log_food_entries",
                    ),
                    # Must decompose into >= 3 ingredients (pâtes + lardons/bacon + at least 1 more)
                    ScriptParamsContainItems(
                        min_count=3,
                        evaluation_name="decomposes_into_ingredients",
                    ),
                    # Response should mention some of the ingredients or macros
                    ContainsAnyOf(
                        options=[
                            "enregistré",
                            "ajouté",
                            "noté",
                            "kcal",
                            "calories",
                            "pâtes",
                            "carbonara",
                        ],
                        evaluation_name="confirms_logging",
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=90.0)],
    )


# ---------------------------------------------------------------------------
# Scenario 3 — Meal type inference from context
#
# User mentions breakfast food in morning context → agent should set
# meal_type to "petit-dejeuner" (not default "dejeuner").
# ---------------------------------------------------------------------------


def scenario_3_meal_type_inference() -> Dataset:
    """Agent infers the correct meal_type from contextual clues."""
    return Dataset(
        name="scenario_3_meal_type_inference",
        cases=[
            Case(
                name="breakfast_context",
                inputs=(
                    "[SUIVI RAPIDE - date: 2026-03-05] L'utilisateur déclare avoir mangé : "
                    '"2 oeufs brouillés et une tartine de pain complet pour mon petit-déjeuner". '
                    "Enregistre ces aliments dans le journal du 2026-03-05. "
                    "Réponds uniquement par une confirmation courte."
                ),
                evaluators=(
                    NoRefusal(),
                    SkillScriptRouting(
                        expected_skill="meal-planning",
                        expected_script="log_food_entries",
                        evaluation_name="routes_to_log_food_entries",
                    ),
                    # Should set meal_type to petit-dejeuner
                    ScriptParamsMealType(
                        expected_types=["petit-dejeuner"],
                        evaluation_name="infers_breakfast_meal_type",
                    ),
                    # Should extract >= 2 items (oeufs + pain)
                    ScriptParamsContainItems(
                        min_count=2,
                        evaluation_name="extracts_items",
                    ),
                ),
            ),
            Case(
                name="dinner_context",
                inputs=(
                    "[SUIVI RAPIDE - date: 2026-03-05] L'utilisateur déclare avoir mangé : "
                    '"une salade et un steak pour le dîner". '
                    "Enregistre ces aliments dans le journal du 2026-03-05. "
                    "Réponds uniquement par une confirmation courte."
                ),
                evaluators=(
                    NoRefusal(),
                    SkillScriptRouting(
                        expected_skill="meal-planning",
                        expected_script="log_food_entries",
                        evaluation_name="routes_to_log_food_entries",
                    ),
                    ScriptParamsMealType(
                        expected_types=["diner"],
                        evaluation_name="infers_dinner_meal_type",
                    ),
                    ScriptParamsContainItems(
                        min_count=2,
                        evaluation_name="extracts_items",
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
async def test_scenario_1_simple_food_logging():
    """E2E: Agent logs simple ingredients via log_food_entries (real Haiku 4.5)."""
    dataset = scenario_1_simple_food_logging()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.integration
async def test_scenario_2_composite_dish_decomposition():
    """E2E: Agent decomposes composite dish into ingredients (real Haiku 4.5)."""
    dataset = scenario_2_composite_dish_decomposition()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.integration
async def test_scenario_3_meal_type_inference():
    """E2E: Agent infers meal_type from context clues (real Haiku 4.5)."""
    dataset = scenario_3_meal_type_inference()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"
