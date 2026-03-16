"""E2E eval — add_favorite_recipe routing and favorite-before-plan flow.

WHY THIS IS AN EVAL, NOT A TEST
================================
These scenarios involve a real LLM making routing decisions:
  - Does the agent call add_favorite_recipe when asked to save a recipe?
  - When asked for a plan with a custom recipe, does the agent favorite first?

Outcomes are non-deterministic → scored criteria, not exact assertions.
Run on demand before releases, NOT in CI.

    pytest evals/test_add_favorite_routing_e2e.py -m integration -v -s

TEST PERSONA — Marc (real user in DB)
======================================
User ID:         5745fc58-9c75-48b1-bc79-12855a8c6021
"""

import json
import time
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
# Test persona
# ---------------------------------------------------------------------------

TEST_USER_ID = "5745fc58-9c75-48b1-bc79-12855a8c6021"

TEST_USER_PROFILE = {
    "age": 24,
    "gender": "male",
    "height_cm": 191,
    "weight_kg": 86.0,
    "activity_level": "light",
    "goal": "muscle_gain",
    "diet_type": "omnivore",
    "allergies": ["arachides", "cacahuètes"],
    "disliked_foods": ["fromage", "choux de Bruxelles"],
    "preferred_cuisines": ["française", "méditerranéenne"],
}

# A recipe known to exist in the DB (seeded, OFF-validated)
# We use a real recipe_id from the recipes table to test add_favorite_recipe
KNOWN_RECIPE_NAME = "Blanc de poulet grillé, riz basmati et légumes colorés"


# ---------------------------------------------------------------------------
# Structured output
# ---------------------------------------------------------------------------


@dataclass
class AgentResult:
    text: str
    tool_calls: list[dict]
    elapsed_seconds: float = 0.0

    def __str__(self) -> str:
        return self.text


# ---------------------------------------------------------------------------
# Evaluators
# ---------------------------------------------------------------------------


@dataclass
class NoRefusal(Evaluator):
    """Check the agent did not refuse the task."""

    evaluation_name: str | None = field(default=None)

    _REFUSAL_PHRASES = [
        "je ne peux pas",
        "je suis incapable",
        "désolé, je ne",
        "impossible de",
        "i cannot",
        "i'm unable",
    ]

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        text = str(ctx.output).lower()
        for phrase in self._REFUSAL_PHRASES:
            if phrase in text:
                return EvaluationReason(
                    value=False, reason=f"Refusal detected: '{phrase}'"
                )
        return EvaluationReason(value=True, reason="No refusal detected")


@dataclass
class ScriptWasCalled(Evaluator):
    """Check that a specific script_name was passed to run_skill_script."""

    script_name: str
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        scripts_called = [
            tc["args"].get("script_name", "")
            for tc in result.tool_calls
            if tc["name"] == "run_skill_script"
        ]
        if self.script_name in scripts_called:
            return EvaluationReason(
                value=True,
                reason=f"Script '{self.script_name}' was called (all: {scripts_called})",
            )
        return EvaluationReason(
            value=False,
            reason=f"Script '{self.script_name}' not called. Called: {scripts_called}",
        )


@dataclass
class ScriptCalledWithParam(Evaluator):
    """Check that a script was called with a specific parameter key present."""

    script_name: str
    param_key: str
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        for tc in result.tool_calls:
            if tc["name"] != "run_skill_script":
                continue
            if tc["args"].get("script_name") != self.script_name:
                continue
            params = tc["args"].get("parameters", {})
            if self.param_key in params:
                return EvaluationReason(
                    value=True,
                    reason=f"'{self.script_name}' called with '{self.param_key}': {params[self.param_key]}",
                )
        return EvaluationReason(
            value=False,
            reason=f"'{self.script_name}' not called with param '{self.param_key}'",
        )


@dataclass
class ScriptCalledBefore(Evaluator):
    """Check that script A was called before script B (ordering matters)."""

    first_script: str
    second_script: str
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        script_order = [
            tc["args"].get("script_name", "")
            for tc in result.tool_calls
            if tc["name"] == "run_skill_script"
        ]
        try:
            idx_first = script_order.index(self.first_script)
            idx_second = script_order.index(self.second_script)
        except ValueError:
            missing = []
            if self.first_script not in script_order:
                missing.append(self.first_script)
            if self.second_script not in script_order:
                missing.append(self.second_script)
            return EvaluationReason(
                value=False,
                reason=f"Missing scripts: {missing}. Called: {script_order}",
            )

        if idx_first < idx_second:
            return EvaluationReason(
                value=True,
                reason=f"'{self.first_script}' (#{idx_first}) called before '{self.second_script}' (#{idx_second})",
            )
        return EvaluationReason(
            value=False,
            reason=f"Wrong order: '{self.first_script}' (#{idx_first}) after '{self.second_script}' (#{idx_second})",
        )


@dataclass
class ResponseMinLength(Evaluator):
    """Check the response is substantive."""

    min_chars: int
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        length = len(str(ctx.output))
        if length >= self.min_chars:
            return EvaluationReason(
                value=True, reason=f"{length} chars ≥ {self.min_chars}"
            )
        return EvaluationReason(
            value=False,
            reason=f"Response too short: {length} chars < {self.min_chars}",
        )


# ---------------------------------------------------------------------------
# Task function
# ---------------------------------------------------------------------------


async def _run_agent(message: str) -> AgentResult:
    """Run agent as the test user."""
    deps = create_agent_deps(user_id=TEST_USER_ID)
    t0 = time.monotonic()
    result = await agent.run(message, deps=deps)
    elapsed = time.monotonic() - t0

    tool_calls = []
    for msg in result.all_messages():
        for part in getattr(msg, "parts", []):
            if isinstance(part, ToolCallPart):
                args = part.args
                if isinstance(args, str):
                    args = json.loads(args)
                tool_calls.append({"name": part.tool_name, "args": args})

    return AgentResult(
        text=result.output, tool_calls=tool_calls, elapsed_seconds=elapsed
    )


async def _run_agent_multi_turn(messages: str) -> AgentResult:
    """Run agent with multi-turn conversation (messages separated by |||).

    Simulates: user says message 1, then message 2, etc.
    Only the last turn's tool calls and text are captured for evaluation.
    """
    turns = [m.strip() for m in messages.split("|||")]
    deps = create_agent_deps(user_id=TEST_USER_ID)

    all_tool_calls: list[dict] = []
    message_history = None
    text = ""
    t0 = time.monotonic()

    for turn in turns:
        result = await agent.run(turn, deps=deps, message_history=message_history)
        message_history = list(result.all_messages())
        text = result.output

        for msg in result.new_messages():
            for part in getattr(msg, "parts", []):
                if isinstance(part, ToolCallPart):
                    args = part.args
                    if isinstance(args, str):
                        args = json.loads(args)
                    all_tool_calls.append({"name": part.tool_name, "args": args})

    elapsed = time.monotonic() - t0
    return AgentResult(text=text, tool_calls=all_tool_calls, elapsed_seconds=elapsed)


# ---------------------------------------------------------------------------
# Scenario 1 — Direct "ajouter en favoris" routing
# Agent should route to meal-planning skill, add_favorite_recipe script
# ---------------------------------------------------------------------------


def scenario_1_save_favorite_routing() -> Dataset:
    """User explicitly asks to save/favorite a recipe → add_favorite_recipe."""
    return Dataset(
        name="scenario_1_save_favorite_routing",
        cases=[
            Case(
                name="save_recipe_fr",
                inputs=(
                    "Sauvegarde cette recette en favori : "
                    "recipe_id = '11111111-1111-1111-1111-111111111111'"
                ),
                evaluators=(
                    NoRefusal(evaluation_name="no_refusal"),
                    ScriptWasCalled(
                        script_name="add_favorite_recipe",
                        evaluation_name="correct_script",
                    ),
                    ScriptCalledWithParam(
                        script_name="add_favorite_recipe",
                        param_key="recipe_id",
                        evaluation_name="has_recipe_id",
                    ),
                ),
            ),
            Case(
                name="add_to_favorites_fr",
                inputs=(
                    "Ajoute en favoris la recette avec l'id "
                    "'22222222-2222-2222-2222-222222222222', "
                    "c'est ma recette d'escalope maison"
                ),
                evaluators=(
                    NoRefusal(evaluation_name="no_refusal"),
                    ScriptWasCalled(
                        script_name="add_favorite_recipe",
                        evaluation_name="correct_script",
                    ),
                    ScriptCalledWithParam(
                        script_name="add_favorite_recipe",
                        param_key="recipe_id",
                        evaluation_name="has_recipe_id",
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=60.0)],
    )


# ---------------------------------------------------------------------------
# Scenario 2 — Multi-turn: generate custom recipe, then plan with it
# Agent should favorite the recipe BEFORE generating the plan
# ---------------------------------------------------------------------------


def scenario_2_favorite_then_plan() -> Dataset:
    """User generates a custom recipe, then asks for a plan using it.

    Expected flow:
    1. Turn 1: generate_custom_recipe → returns recipe with id
    2. Turn 2: add_favorite_recipe(recipe_id) THEN generate_week_plan(custom_requests)
    """
    return Dataset(
        name="scenario_2_favorite_then_plan",
        cases=[
            Case(
                name="custom_recipe_then_plan",
                inputs=(
                    "Crée-moi une recette de poulet tikka masala pour le déjeuner"
                    "|||"
                    "Parfait ! Maintenant fais-moi un plan pour demain avec cette recette au déjeuner. "
                    "Lance directement sans poser de questions."
                ),
                evaluators=(
                    NoRefusal(evaluation_name="no_refusal"),
                    ScriptWasCalled(
                        script_name="generate_custom_recipe",
                        evaluation_name="custom_recipe_generated",
                    ),
                    ScriptWasCalled(
                        script_name="add_favorite_recipe",
                        evaluation_name="favorite_added",
                    ),
                    ScriptWasCalled(
                        script_name="generate_week_plan",
                        evaluation_name="plan_generated",
                    ),
                    ScriptCalledBefore(
                        first_script="add_favorite_recipe",
                        second_script="generate_week_plan",
                        evaluation_name="favorite_before_plan",
                    ),
                    ResponseMinLength(
                        min_chars=200,
                        evaluation_name="substantive_response",
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=300.0)],
    )


# ---------------------------------------------------------------------------
# Scenario 3 — Routing does NOT trigger add_favorite for unrelated requests
# ---------------------------------------------------------------------------


def scenario_3_no_false_positive() -> Dataset:
    """Normal meal plan request should NOT trigger add_favorite_recipe."""
    return Dataset(
        name="scenario_3_no_false_positive",
        cases=[
            Case(
                name="normal_plan_no_favorite",
                inputs=(
                    "Génère mon plan repas pour demain, 3 repas. "
                    "Lance directement sans questions."
                ),
                evaluators=(
                    NoRefusal(evaluation_name="no_refusal"),
                    ScriptWasCalled(
                        script_name="generate_week_plan",
                        evaluation_name="plan_generated",
                    ),
                    _ScriptNotCalled(
                        script_name="add_favorite_recipe",
                        evaluation_name="no_false_favorite",
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=180.0)],
    )


@dataclass
class _ScriptNotCalled(Evaluator):
    """Check that a specific script was NOT called."""

    script_name: str
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        scripts_called = [
            tc["args"].get("script_name", "")
            for tc in result.tool_calls
            if tc["name"] == "run_skill_script"
        ]
        if self.script_name not in scripts_called:
            return EvaluationReason(
                value=True,
                reason=f"'{self.script_name}' correctly not called (called: {scripts_called})",
            )
        return EvaluationReason(
            value=False,
            reason=f"'{self.script_name}' was incorrectly called",
        )


# ---------------------------------------------------------------------------
# Pytest functions
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_scenario_1_save_favorite_routing():
    """Eval: 'sauvegarder en favori' routes to add_favorite_recipe."""
    dataset = scenario_1_save_favorite_routing()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.integration
async def test_scenario_2_favorite_then_plan():
    """Eval: custom recipe → favorite → plan (correct ordering)."""
    dataset = scenario_2_favorite_then_plan()
    report = await dataset.evaluate(task=_run_agent_multi_turn)
    report.print(include_input=True, include_output=True)
    # Multi-turn is harder — allow partial success
    failure_rate = len(report.failures) / max(len(report.cases), 1)
    assert failure_rate <= 0.5, (
        f"Too many failures: {len(report.failures)}/{len(report.cases)} "
        f"({[f.name for f in report.failures]})"
    )


@pytest.mark.integration
async def test_scenario_3_no_false_positive():
    """Eval: normal plan request does NOT trigger add_favorite_recipe."""
    dataset = scenario_3_no_false_positive()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"
