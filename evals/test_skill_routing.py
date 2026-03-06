"""Eval: skill routing — does the agent pick the right skill for each intent?

Tests that natural language messages are routed to the correct skill
(meal-planning vs food-tracking vs shopping-list). Real LLM decisions.

    pytest evals/test_skill_routing.py -v

TEST PERSONA — required for agent deps.
"""

import json
from dataclasses import dataclass, field

import pytest
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


# ---------------------------------------------------------------------------
# Custom evaluator: check which skill was loaded
# ---------------------------------------------------------------------------


@dataclass
class RoutedToSkill(Evaluator):
    """Check that the agent called load_skill or run_skill_script with the expected skill."""

    expected_skill: str
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        messages = ctx.output.get("messages", [])
        skills_called: list[str] = []

        for msg in messages:
            # Look for tool calls in model requests
            if hasattr(msg, "parts"):
                for part in msg.parts:
                    if hasattr(part, "tool_name") and part.tool_name in (
                        "load_skill",
                        "run_skill_script",
                    ):
                        args = part.args
                        if isinstance(args, str):
                            args = json.loads(args)
                        skill = args.get("skill_name", "")
                        if skill:
                            skills_called.append(skill)

        if self.expected_skill in skills_called:
            return EvaluationReason(
                value=True,
                reason=f"Correctly routed to '{self.expected_skill}' (all skills called: {skills_called})",
            )
        return EvaluationReason(
            value=False,
            reason=f"Expected '{self.expected_skill}', but agent called: {skills_called or 'no skills'}",
        )


@dataclass
class DidNotRoute(Evaluator):
    """Check that the agent did NOT call a specific skill."""

    forbidden_skill: str
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        messages = ctx.output.get("messages", [])
        for msg in messages:
            if hasattr(msg, "parts"):
                for part in msg.parts:
                    if hasattr(part, "tool_name") and part.tool_name in (
                        "load_skill",
                        "run_skill_script",
                    ):
                        args = part.args
                        if isinstance(args, str):
                            args = json.loads(args)
                        if args.get("skill_name") == self.forbidden_skill:
                            return EvaluationReason(
                                value=False,
                                reason=f"Agent incorrectly called '{self.forbidden_skill}'",
                            )
        return EvaluationReason(
            value=True,
            reason=f"'{self.forbidden_skill}' was not called (correct)",
        )


# ---------------------------------------------------------------------------
# Task function — returns messages for inspection
# ---------------------------------------------------------------------------


async def _run_agent_with_messages(message: str) -> dict:
    """Run agent and return both text output and raw messages for routing inspection."""
    deps = create_agent_deps()
    result = await agent.run(message, deps=deps)
    return {
        "text": result.output,
        "messages": list(result.all_messages()),
    }


# ---------------------------------------------------------------------------
# Dataset: 7 routing scenarios
# ---------------------------------------------------------------------------


def skill_routing_dataset() -> Dataset:
    """Dataset: agent routes user intents to the correct skill."""
    return Dataset(
        name="skill_routing",
        cases=[
            # 1. Food logging -> food-tracking
            Case(
                name="food_logging_chicken_rice",
                inputs="j'ai mange 200g de poulet et du riz",
                evaluators=(
                    RoutedToSkill(expected_skill="food-tracking"),
                    DidNotRoute(forbidden_skill="meal-planning"),
                ),
            ),
            # 2. Meal plan -> meal-planning
            Case(
                name="meal_plan_request",
                inputs="fais-moi un plan de repas pour la semaine",
                evaluators=(
                    RoutedToSkill(expected_skill="meal-planning"),
                    DidNotRoute(forbidden_skill="food-tracking"),
                ),
            ),
            # 3. Shopping list -> shopping-list
            Case(
                name="shopping_list_request",
                inputs="genere ma liste de courses pour cette semaine",
                evaluators=(
                    RoutedToSkill(expected_skill="shopping-list"),
                    DidNotRoute(forbidden_skill="meal-planning"),
                ),
            ),
            # 4. View existing plan -> meal-planning (fetch_stored_meal_plan)
            Case(
                name="view_existing_plan",
                inputs="montre-moi mon plan de lundi",
                evaluators=(
                    RoutedToSkill(expected_skill="meal-planning"),
                    DidNotRoute(forbidden_skill="shopping-list"),
                ),
            ),
            # 5. Breakfast logging -> food-tracking
            Case(
                name="food_logging_breakfast",
                inputs="j'ai pris un cafe et un croissant ce matin",
                evaluators=(
                    RoutedToSkill(expected_skill="food-tracking"),
                    DidNotRoute(forbidden_skill="meal-planning"),
                ),
            ),
            # 6. Recipe request -> meal-planning
            Case(
                name="recipe_request",
                inputs="je veux une recette de risotto",
                evaluators=(
                    RoutedToSkill(expected_skill="meal-planning"),
                    DidNotRoute(forbidden_skill="food-tracking"),
                ),
            ),
            # 7. What to buy -> shopping-list
            Case(
                name="what_to_buy",
                inputs="qu'est-ce que je dois acheter ?",
                evaluators=(
                    RoutedToSkill(expected_skill="shopping-list"),
                    DidNotRoute(forbidden_skill="meal-planning"),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=60.0)],
    )


# ---------------------------------------------------------------------------
# Pytest
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_skill_routing_eval():
    """Eval: agent routes 7 user intents to the correct skill."""
    dataset = skill_routing_dataset()
    report = await dataset.evaluate(task=_run_agent_with_messages)
    report.print()
    # Evals are scored, not hard-asserted — but flag if most fail
    failure_rate = len(report.failures) / len(report.cases)
    assert failure_rate <= 0.3, (
        f"Too many routing failures: {len(report.failures)}/{len(report.cases)} "
        f"({[f.name for f in report.failures]})"
    )
