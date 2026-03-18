"""E2E eval — get_user_favorites and remove_favorite_recipe routing.

WHY THIS IS AN EVAL, NOT A TEST
================================
These scenarios involve a real LLM making routing decisions:
  - Does the agent call get_user_favorites when asked to list favorites?
  - Does it pass name filter when the user asks for a specific recipe?
  - Does it call remove_favorite_recipe when asked to delete?

Outcomes are non-deterministic → scored criteria, not exact assertions.
Run on demand before releases, NOT in CI.

    pytest evals/test_favorites_management_e2e.py -m integration -v -s

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
# Evaluators (reuse patterns from test_add_favorite_routing_e2e.py)
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
# Scenario 1 — List all favorites
# ---------------------------------------------------------------------------


def scenario_1_list_favorites() -> Dataset:
    """User asks to see their favorite recipes → get_user_favorites."""
    return Dataset(
        name="scenario_1_list_favorites",
        cases=[
            Case(
                name="list_favorites_fr",
                inputs="Montre-moi mes recettes favorites",
                evaluators=(
                    NoRefusal(evaluation_name="no_refusal"),
                    ScriptWasCalled(
                        script_name="get_user_favorites",
                        evaluation_name="correct_script",
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=60.0)],
    )


# ---------------------------------------------------------------------------
# Scenario 2 — Search favorite by name
# ---------------------------------------------------------------------------


def scenario_2_search_favorite_by_name() -> Dataset:
    """User asks for a specific favorite by name → get_user_favorites with name param."""
    return Dataset(
        name="scenario_2_search_favorite_by_name",
        cases=[
            Case(
                name="search_favorite_poulet",
                inputs="Est-ce que tu peux retrouver ma recette de poulet dans mes favoris ?",
                evaluators=(
                    NoRefusal(evaluation_name="no_refusal"),
                    ScriptWasCalled(
                        script_name="get_user_favorites",
                        evaluation_name="correct_script",
                    ),
                    ScriptCalledWithParam(
                        script_name="get_user_favorites",
                        param_key="name",
                        evaluation_name="has_name_param",
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=60.0)],
    )


# ---------------------------------------------------------------------------
# Scenario 3 — Remove a favorite by name
# ---------------------------------------------------------------------------


def scenario_3_remove_favorite() -> Dataset:
    """User asks to remove a favorite → remove_favorite_recipe."""
    return Dataset(
        name="scenario_3_remove_favorite",
        cases=[
            Case(
                name="remove_favorite_by_name",
                inputs="Supprime la recette poulet grillé de mes favoris",
                evaluators=(
                    NoRefusal(evaluation_name="no_refusal"),
                    ScriptWasCalled(
                        script_name="remove_favorite_recipe",
                        evaluation_name="correct_script",
                    ),
                    ScriptCalledWithParam(
                        script_name="remove_favorite_recipe",
                        param_key="recipe_name",
                        evaluation_name="has_recipe_name",
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=60.0)],
    )


# ---------------------------------------------------------------------------
# Pytest functions
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_scenario_1_list_favorites():
    """Eval: 'mes recettes favorites' routes to get_user_favorites."""
    dataset = scenario_1_list_favorites()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.integration
async def test_scenario_2_search_favorite_by_name():
    """Eval: 'retrouver ma recette de poulet' routes with name param."""
    dataset = scenario_2_search_favorite_by_name()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.integration
async def test_scenario_3_remove_favorite():
    """Eval: 'supprime de mes favoris' routes to remove_favorite_recipe."""
    dataset = scenario_3_remove_favorite()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"
