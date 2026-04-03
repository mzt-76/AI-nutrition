"""E2E eval — Delete food entry from daily tracker via chat.

WHY THIS IS AN EVAL, NOT A TEST
================================
These scenarios involve a real LLM making decisions:
  - Does the agent route to delete_food_entry when asked to remove an entry?
  - Does it extract food_name / meal_type correctly from natural language?
  - Does it handle ambiguity (multiple matches) gracefully?

Outcomes are non-deterministic → scored criteria, not exact assertions.
Run on demand before releases, NOT in CI.

    pytest evals/test_delete_food_entry_e2e.py -m integration -v -s

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
}


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
        "pas de fonction",
        "pas de script",
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
class SkillWasLoaded(Evaluator):
    """Check that food-tracking skill was loaded."""

    skill_name: str
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        for tc in result.tool_calls:
            if (
                tc["name"] == "load_skill"
                and tc["args"].get("skill_name") == self.skill_name
            ):
                return EvaluationReason(
                    value=True, reason=f"Skill '{self.skill_name}' was loaded"
                )
            if (
                tc["name"] == "run_skill_script"
                and tc["args"].get("skill_name") == self.skill_name
            ):
                return EvaluationReason(
                    value=True,
                    reason=f"Skill '{self.skill_name}' used via run_skill_script",
                )
        return EvaluationReason(
            value=False, reason=f"Skill '{self.skill_name}' was never loaded"
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


# ---------------------------------------------------------------------------
# Scenario 1 — Delete by food name
# ---------------------------------------------------------------------------


def scenario_1_delete_by_name() -> Dataset:
    """User asks to delete a specific food from today's tracker."""
    return Dataset(
        name="scenario_1_delete_by_name",
        cases=[
            Case(
                name="delete_riz_from_dejeuner",
                inputs="Supprime le riz de mon déjeuner d'aujourd'hui",
                evaluators=(
                    NoRefusal(evaluation_name="no_refusal"),
                    SkillWasLoaded(
                        skill_name="food-tracking",
                        evaluation_name="skill_loaded",
                    ),
                    ScriptWasCalled(
                        script_name="delete_food_entry",
                        evaluation_name="correct_script",
                    ),
                    ScriptCalledWithParam(
                        script_name="delete_food_entry",
                        param_key="food_name",
                        evaluation_name="has_food_name",
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=90.0)],
    )


# ---------------------------------------------------------------------------
# Scenario 2 — Delete with generic phrasing
# ---------------------------------------------------------------------------


def scenario_2_delete_generic() -> Dataset:
    """User asks to remove/delete an entry using varied phrasing."""
    return Dataset(
        name="scenario_2_delete_generic",
        cases=[
            Case(
                name="enleve_oeufs_petit_dej",
                inputs="Enlève les oeufs de mon petit-déjeuner",
                evaluators=(
                    NoRefusal(evaluation_name="no_refusal"),
                    ScriptWasCalled(
                        script_name="delete_food_entry",
                        evaluation_name="correct_script",
                    ),
                    ScriptCalledWithParam(
                        script_name="delete_food_entry",
                        param_key="food_name",
                        evaluation_name="has_food_name",
                    ),
                ),
            ),
            Case(
                name="retire_du_suivi",
                inputs="Retire le poulet grillé de mon suivi du jour",
                evaluators=(
                    NoRefusal(evaluation_name="no_refusal"),
                    ScriptWasCalled(
                        script_name="delete_food_entry",
                        evaluation_name="correct_script",
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=90.0)],
    )


# ---------------------------------------------------------------------------
# Pytest entry points
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_scenario_1_delete_by_name():
    """Eval: 'supprime le riz' routes to delete_food_entry with food_name."""
    dataset = scenario_1_delete_by_name()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.integration
async def test_scenario_2_delete_generic():
    """Eval: varied delete phrasings route to delete_food_entry."""
    dataset = scenario_2_delete_generic()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"
