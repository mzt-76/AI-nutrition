"""E2E eval — Add favorite recipe to daily food tracker.

WHY THIS IS AN EVAL, NOT A TEST
================================
This tests a multi-step LLM workflow:
  1. Agent routes to get_user_favorites (meal-planning skill)
  2. Agent extracts ingredients from the favorite
  3. Agent routes to log_food_entries (food-tracking skill) with decomposed ingredients
  4. Agent does NOT log the recipe name as a single opaque item

Outcomes are non-deterministic → scored criteria, not exact assertions.
Run on demand before releases, NOT in CI.

    pytest evals/test_favorite_to_tracker_e2e.py -m integration -v -s

TEST PERSONA — Marc (real user in DB with favorites)
=====================================================
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
class LogFoodHasMultipleItems(Evaluator):
    """Check that log_food_entries was called with >1 items (decomposed ingredients)."""

    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        for tc in result.tool_calls:
            if tc["name"] != "run_skill_script":
                continue
            if tc["args"].get("script_name") != "log_food_entries":
                continue
            params = tc["args"].get("parameters", {})
            items = params.get("items", [])
            if len(items) > 1:
                names = [i.get("name", "?") for i in items]
                return EvaluationReason(
                    value=True,
                    reason=f"log_food_entries called with {len(items)} items: {names}",
                )
            if len(items) == 1:
                return EvaluationReason(
                    value=False,
                    reason=f"log_food_entries called with only 1 item: {items[0].get('name', '?')} — recipe was not decomposed",
                )
        return EvaluationReason(
            value=False,
            reason="log_food_entries was not called at all",
        )


@dataclass
class BothSkillsUsed(Evaluator):
    """Check that both meal-planning and food-tracking skills were loaded."""

    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        skills_loaded = set()
        for tc in result.tool_calls:
            if tc["name"] == "load_skill":
                skills_loaded.add(tc["args"].get("skill_name", ""))
            elif tc["name"] == "run_skill_script":
                skills_loaded.add(tc["args"].get("skill_name", ""))
        has_mp = "meal-planning" in skills_loaded
        has_ft = "food-tracking" in skills_loaded
        if has_mp and has_ft:
            return EvaluationReason(
                value=True, reason=f"Both skills used: {skills_loaded}"
            )
        missing = []
        if not has_mp:
            missing.append("meal-planning")
        if not has_ft:
            missing.append("food-tracking")
        return EvaluationReason(
            value=False, reason=f"Missing skills: {missing}. Loaded: {skills_loaded}"
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
# Scenario — Add favorite to tracker
# ---------------------------------------------------------------------------


def scenario_favorite_to_tracker() -> Dataset:
    """User asks to add a favorite recipe to today's tracker.

    Expected flow:
    1. load_skill('meal-planning') + get_user_favorites(name='poulet')
    2. load_skill('food-tracking') + log_food_entries(items=[decomposed ingredients])
    """
    return Dataset(
        name="favorite_to_tracker",
        cases=[
            Case(
                name="add_favorite_poulet_to_tracker",
                inputs="Ajoute ma recette favorite de poulet grillé à mon suivi du jour pour le déjeuner",
                evaluators=(
                    NoRefusal(evaluation_name="no_refusal"),
                    BothSkillsUsed(evaluation_name="both_skills_used"),
                    ScriptWasCalled(
                        script_name="get_user_favorites",
                        evaluation_name="fetched_favorites",
                    ),
                    ScriptWasCalled(
                        script_name="log_food_entries",
                        evaluation_name="logged_food",
                    ),
                    LogFoodHasMultipleItems(
                        evaluation_name="ingredients_decomposed",
                    ),
                ),
            ),
            Case(
                name="add_favorite_generic_to_tracker",
                inputs="Mets mon favori dans mon suivi d'aujourd'hui",
                evaluators=(
                    NoRefusal(evaluation_name="no_refusal"),
                    ScriptWasCalled(
                        script_name="get_user_favorites",
                        evaluation_name="fetched_favorites",
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=120.0)],
    )


# ---------------------------------------------------------------------------
# Pytest entry points
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_favorite_to_tracker():
    """Eval: 'ajoute ma recette favorite au suivi' → full cross-skill flow."""
    dataset = scenario_favorite_to_tracker()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"
