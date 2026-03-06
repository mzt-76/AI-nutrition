"""E2E eval — recipe → shopping list routing with real LLM.

WHY THIS IS AN EVAL, NOT A TEST
================================
These scenarios involve a real LLM making routing decisions:
  - Scenario 1: custom recipe request → agent calls generate_custom_recipe (not free text)
                 then "liste de courses" → agent calls generate_from_recipes with recipe_id
  - Scenario 2: weekly shopping list → agent calls generate_shopping_list (regression check)

Outcomes are non-deterministic -> scored criteria, not exact assertions.
Run on demand before releases, NOT in CI.

    pytest evals/test_recipe_shopping_list_routing.py -m integration -v -s

TEST PERSONA — Marc (same as test_recipe_shopping_e2e.py)
=========================================================================
Name:            Marc
Age:             24
Gender:          male
Height:          191 cm
Weight:          86 kg
Activity level:  light (x1.375)
Goal:            muscle gain

This user has meal plans in DB (week_start 2026-02-23).
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
# Test persona
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

TEST_USER_ID = "5745fc58-9c75-48b1-bc79-12855a8c6021"


# ---------------------------------------------------------------------------
# Structured output
# ---------------------------------------------------------------------------


@dataclass
class AgentResult:
    text: str
    tool_calls: list[dict]


# ---------------------------------------------------------------------------
# Evaluators
# ---------------------------------------------------------------------------


@dataclass
class ToolWasCalled(Evaluator):
    tool_name: str
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        if not isinstance(ctx.output, AgentResult):
            return EvaluationReason(value=False, reason="Output is not AgentResult")
        called = [tc["name"] for tc in ctx.output.tool_calls]
        if self.tool_name in called:
            return EvaluationReason(value=True, reason=f"'{self.tool_name}' was called")
        return EvaluationReason(
            value=False, reason=f"'{self.tool_name}' not in calls: {called}"
        )


@dataclass
class ToolCalledWithArgs(Evaluator):
    tool_name: str
    required_args: dict
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        if not isinstance(ctx.output, AgentResult):
            return EvaluationReason(value=False, reason="Output is not AgentResult")
        last_mismatch: str | None = None
        for tc in ctx.output.tool_calls:
            if tc["name"] == self.tool_name:
                args = tc["args"]
                missing = []
                for key, expected in self.required_args.items():
                    actual = args.get(key)
                    if actual != expected:
                        missing.append(f"{key}: expected={expected}, got={actual}")
                if not missing:
                    return EvaluationReason(
                        value=True,
                        reason=f"'{self.tool_name}' called with correct args",
                    )
                last_mismatch = f"'{self.tool_name}' args mismatch: {missing}"
        called = [tc["name"] for tc in ctx.output.tool_calls]
        if last_mismatch:
            return EvaluationReason(value=False, reason=last_mismatch)
        return EvaluationReason(
            value=False, reason=f"'{self.tool_name}' never called. Called: {called}"
        )


@dataclass
class ToolCalledWithArgContaining(Evaluator):
    """Check a tool was called and one of its args contains a substring."""

    tool_name: str
    arg_name: str
    substring: str
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        if not isinstance(ctx.output, AgentResult):
            return EvaluationReason(value=False, reason="Output is not AgentResult")
        for tc in ctx.output.tool_calls:
            if tc["name"] == self.tool_name:
                val = tc["args"].get(self.arg_name, "")
                val_str = json.dumps(val) if not isinstance(val, str) else val
                if self.substring in val_str:
                    return EvaluationReason(
                        value=True,
                        reason=f"'{self.arg_name}' contains '{self.substring}'",
                    )
        return EvaluationReason(
            value=False,
            reason=f"'{self.tool_name}' not called with '{self.substring}' in '{self.arg_name}'",
        )


@dataclass
class NoRefusal(Evaluator):
    evaluation_name: str | None = field(default=None)

    _REFUSAL_PHRASES = [
        "je ne peux pas",
        "je suis incapable",
        "impossible de",
        "i cannot",
        "i'm unable",
    ]

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        text = (
            ctx.output.text.lower()
            if isinstance(ctx.output, AgentResult)
            else str(ctx.output).lower()
        )
        for phrase in self._REFUSAL_PHRASES:
            if phrase in text:
                return EvaluationReason(value=False, reason=f"Refusal: '{phrase}'")
        return EvaluationReason(value=True, reason="No refusal")


# ---------------------------------------------------------------------------
# Task function — multi-turn conversation
# ---------------------------------------------------------------------------


async def _run_agent_multi_turn(messages: list[str]) -> AgentResult:
    """Run multiple user messages in a single conversation, accumulating tool calls."""
    deps = create_agent_deps(user_id=TEST_USER_ID)
    all_tool_calls: list[dict] = []
    message_history = None
    result = None
    seen_tool_ids: set[str] = set()

    for msg in messages:
        result = await agent.run(msg, deps=deps, message_history=message_history)
        message_history = result.all_messages()
        for m in message_history:
            for part in getattr(m, "parts", []):
                if isinstance(part, ToolCallPart):
                    if part.tool_call_id in seen_tool_ids:
                        continue
                    seen_tool_ids.add(part.tool_call_id)
                    args = part.args
                    if isinstance(args, str):
                        args = json.loads(args)
                    all_tool_calls.append({"name": part.tool_name, "args": args})

    return AgentResult(text=result.output if result else "", tool_calls=all_tool_calls)


async def _run_single_turn(message: str) -> AgentResult:
    """Run a single user message."""
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
# Scenario 1 — Custom recipe then shopping list for that recipe
# ---------------------------------------------------------------------------


def scenario_1_recipe_then_shopping_list() -> Dataset:
    """Agent generates a custom recipe, then shopping list from its recipe_id."""
    return Dataset(
        name="scenario_1_recipe_then_shopping_list",
        cases=[
            Case(
                name="chicken_recipe_then_shopping",
                inputs=[
                    "Fais-moi une recette de poulet grille pour le dejeuner, environ 500 kcal.",
                    "Fais-moi la liste de courses pour cette recette.",
                ],
                evaluators=(
                    NoRefusal(),
                    # Turn 1: must call generate_custom_recipe (not improvise)
                    ToolCalledWithArgs(
                        tool_name="run_skill_script",
                        required_args={
                            "skill_name": "meal-planning",
                            "script_name": "generate_custom_recipe",
                        },
                        evaluation_name="uses_generate_custom_recipe",
                    ),
                    # Turn 2: must call generate_from_recipes (not generate_shopping_list)
                    ToolCalledWithArgs(
                        tool_name="run_skill_script",
                        required_args={
                            "skill_name": "shopping-list",
                            "script_name": "generate_from_recipes",
                        },
                        evaluation_name="uses_generate_from_recipes",
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=180.0)],
    )


# ---------------------------------------------------------------------------
# Scenario 2 — Weekly shopping list (regression)
# ---------------------------------------------------------------------------


def scenario_2_weekly_shopping_list() -> Dataset:
    """Agent generates a shopping list from existing weekly meal plan."""
    return Dataset(
        name="scenario_2_weekly_shopping_list_regression",
        cases=[
            Case(
                name="weekly_plan_shopping",
                inputs="Fais-moi la liste de courses pour mon plan de la semaine du 2026-02-23.",
                evaluators=(
                    NoRefusal(),
                    ToolWasCalled(tool_name="load_skill"),
                    ToolCalledWithArgs(
                        tool_name="run_skill_script",
                        required_args={
                            "skill_name": "shopping-list",
                            "script_name": "generate_shopping_list",
                        },
                        evaluation_name="uses_generate_shopping_list",
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=120.0)],
    )


# ---------------------------------------------------------------------------
# Pytest — marked integration
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_scenario_1_recipe_then_shopping():
    """E2E: Custom recipe → shopping list routing uses generate_from_recipes."""
    dataset = scenario_1_recipe_then_shopping_list()
    report = await dataset.evaluate(task=_run_agent_multi_turn)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.integration
async def test_scenario_2_weekly_shopping_regression():
    """E2E: Weekly shopping list still routes to generate_shopping_list."""
    dataset = scenario_2_weekly_shopping_list()
    report = await dataset.evaluate(task=_run_single_turn)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"
