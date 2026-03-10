"""E2E eval — Favorites integration in meal-planning pipeline.

WHY THIS IS AN EVAL, NOT A TEST
================================
These scenarios involve a real LLM (Haiku 4.5) making decisions:
  - Does the agent route to the meal-planning skill?
  - When a user requests a favorite recipe by name, does the pipeline use the
    saved favorite instead of generating a new one via LLM?
  - Does the pipeline complete successfully with favorites enabled?

Outcomes are non-deterministic → scored criteria, not exact assertions.
Run on demand before releases, NOT in CI (slow, costs API credits).

    pytest evals/test_favorites_meal_planning_e2e.py -m integration -v -s

TEST PERSONA — Marc (real user in DB with favorites)
=====================================================
User ID:         5745fc58-9c75-48b1-bc79-12855a8c6021
Age:             24
Gender:          male
Height:          191 cm
Weight:          86 kg
Activity level:  light (×1.375)
Goal:            muscle gain
Diet:            omnivore
Allergies:       arachides, cacahuètes
Favorites:
  - "Blanc de poulet grillé, riz basmati et légumes colorés"
  - "Escalope de Poulet Panée Croustante, Sauce Citron-Miel et Légumes Rôtis"

Niveau 1 (implicit): Favorite recipes get a 0.15 scoring bonus in
  score_recipe_variety(), making them surface more often in plans.
  Difficult to assert deterministically — we verify the plan completes.

Niveau 2 (explicit): When user requests a recipe by name matching a
  favorite, the pipeline returns the saved favorite instead of calling LLM.
  We check the response mentions the favorite recipe name.
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
# Test persona — single source of truth
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

# Favorite recipes (must exist in DB for this user)
FAVORITE_RECIPE_1 = "Blanc de poulet grillé, riz basmati et légumes colorés"
FAVORITE_RECIPE_2 = (
    "Escalope de Poulet Panée Croustante, Sauce Citron-Miel et Légumes Rôtis"
)


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


@dataclass
class ContainsAnyOf(Evaluator):
    """Check that at least one of the given substrings appears in the output."""

    options: list[str]
    case_sensitive: bool = False
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        text = str(ctx.output)
        haystack = text if self.case_sensitive else text.lower()
        for option in self.options:
            needle = option if self.case_sensitive else option.lower()
            if needle in haystack:
                return EvaluationReason(value=True, reason=f"Found '{option}'")
        return EvaluationReason(
            value=False,
            reason=f"None of {self.options} found in response",
        )


@dataclass
class ToolWasCalled(Evaluator):
    """Check that a specific tool was called during the agent run."""

    tool_name: str
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        called = [tc["name"] for tc in result.tool_calls]
        if self.tool_name in called:
            return EvaluationReason(
                value=True, reason=f"Tool '{self.tool_name}' was called"
            )
        return EvaluationReason(
            value=False,
            reason=f"Tool '{self.tool_name}' not called. Called: {called}",
        )


@dataclass
class ResponseContainsFavorite(Evaluator):
    """Check that the response mentions at least one favorite recipe name.

    Uses partial matching — the agent may abbreviate or rephrase the name.
    We check for key distinctive words from the recipe name.
    """

    favorite_keywords: list[list[str]]  # list of keyword sets, one per favorite
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        text = str(ctx.output).lower()
        for i, keywords in enumerate(self.favorite_keywords):
            if all(kw.lower() in text for kw in keywords):
                return EvaluationReason(
                    value=True,
                    reason=f"Favorite #{i + 1} found via keywords {keywords}",
                )
        return EvaluationReason(
            value=False,
            reason=f"No favorite recipe keywords found in response. "
            f"Checked: {self.favorite_keywords}",
        )


# ---------------------------------------------------------------------------
# Task function — real agent, real DB, real user with favorites
# ---------------------------------------------------------------------------


async def _run_agent(message: str) -> AgentResult:
    """Run agent as the test user who has favorite recipes."""
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
# Scenario 1 — Niveau 1 (implicit): Plan completes with favorites enabled
# The favorite scoring boost is internal — we verify the pipeline runs
# successfully and produces a meal plan. Logs will show fav_bonus values.
# ---------------------------------------------------------------------------


def scenario_1_implicit_favorite_boost() -> Dataset:
    """Agent generates a 1-day plan for a user with favorites — pipeline completes."""
    return Dataset(
        name="scenario_1_implicit_favorite_boost",
        cases=[
            Case(
                name="1day_plan_with_favorites",
                inputs=(
                    "Génère mon plan repas pour demain sans me poser de questions. "
                    "3 repas : petit-déjeuner, déjeuner, dîner. "
                    "Pas de collation. Lance directement."
                ),
                evaluators=(
                    NoRefusal(evaluation_name="no_refusal"),
                    ResponseMinLength(
                        min_chars=200,
                        evaluation_name="substantive_response",
                    ),
                    ToolWasCalled(
                        tool_name="run_skill_script",
                        evaluation_name="skill_called",
                    ),
                    ContainsAnyOf(
                        options=[
                            "petit-déjeuner",
                            "déjeuner",
                            "dîner",
                            "kcal",
                            "calories",
                        ],
                        evaluation_name="meal_plan_content",
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=180.0)],
    )


# ---------------------------------------------------------------------------
# Scenario 2 — Niveau 2 (explicit): User requests a favorite by name
# The pipeline should find the saved favorite instead of LLM-generating.
# We check the response mentions the favorite recipe.
# ---------------------------------------------------------------------------


def scenario_2_explicit_favorite_request() -> Dataset:
    """User requests their favorite 'poulet grillé riz basmati' by name."""
    return Dataset(
        name="scenario_2_explicit_favorite_request",
        cases=[
            Case(
                name="custom_request_matches_favorite",
                inputs=(
                    "Génère mon plan repas pour demain sans me poser de questions. "
                    "3 repas : petit-déjeuner, déjeuner, dîner. "
                    "Pour le déjeuner je veux mon blanc de poulet grillé riz basmati. "
                    "Le reste c'est au choix, lance directement."
                ),
                evaluators=(
                    NoRefusal(evaluation_name="no_refusal"),
                    ResponseMinLength(
                        min_chars=200,
                        evaluation_name="substantive_response",
                    ),
                    ToolWasCalled(
                        tool_name="run_skill_script",
                        evaluation_name="skill_called",
                    ),
                    ResponseContainsFavorite(
                        favorite_keywords=[
                            ["poulet", "grillé", "riz", "basmati"],
                        ],
                        evaluation_name="favorite_recipe_used",
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=180.0)],
    )


# ---------------------------------------------------------------------------
# Pytest functions
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_scenario_1_implicit_favorite_boost():
    dataset = scenario_1_implicit_favorite_boost()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.integration
async def test_scenario_2_explicit_favorite_request():
    dataset = scenario_2_explicit_favorite_request()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"
