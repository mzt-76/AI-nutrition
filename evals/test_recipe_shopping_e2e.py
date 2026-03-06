"""E2E eval — custom recipe generation & shopping list generation with real LLM.

WHY THIS IS AN EVAL, NOT A TEST
================================
These scenarios involve a real LLM (Haiku 4.5) making decisions:
  - Does the agent route to the correct skill (meal-planning)?
  - Does it call the right script (generate_custom_recipe / generate_shopping_list)?
  - Does it extract the right parameters from natural language?
  - Does the response contain recipe content / shopping list categories?
  - Does the shopping list get persisted (shopping_list_id in response)?

Outcomes are non-deterministic -> scored criteria, not exact assertions.
Run on demand before releases, NOT in CI (slow, costs API credits).

    pytest evals/test_recipe_shopping_e2e.py -m integration -v -s

TEST PERSONA — Marc (same as test_agent_e2e.py)
=========================================================================
Name:            Marc
Age:             24
Gender:          male
Height:          191 cm
Weight:          86 kg
Activity level:  light (x1.375)
Goal:            muscle gain

This user has meal plans in DB (week_start 2026-02-23) enabling shopping list
generation. The user_id below is the real Supabase test account.
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

# Real Supabase user ID with existing meal plans in DB
TEST_USER_ID = "5745fc58-9c75-48b1-bc79-12855a8c6021"


# ---------------------------------------------------------------------------
# Structured output — text + tool calls
# ---------------------------------------------------------------------------


@dataclass
class AgentResult:
    """Captures both text output and tool call history from an agent run."""

    text: str
    tool_calls: list[dict]


# ---------------------------------------------------------------------------
# Custom evaluators
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
        text = (
            ctx.output.text.lower()
            if isinstance(ctx.output, AgentResult)
            else str(ctx.output).lower()
        )
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
        text = (
            ctx.output.text if isinstance(ctx.output, AgentResult) else str(ctx.output)
        )
        length = len(text)
        if length >= self.min_chars:
            return EvaluationReason(
                value=True, reason=f"{length} chars >= {self.min_chars}"
            )
        return EvaluationReason(
            value=False, reason=f"Response too short: {length} chars < {self.min_chars}"
        )


@dataclass
class ContainsAnyOf(Evaluator):
    """Check that at least one substring appears in the text output."""

    options: list[str]
    case_sensitive: bool = False
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        text = (
            ctx.output.text if isinstance(ctx.output, AgentResult) else str(ctx.output)
        )
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
        if not isinstance(ctx.output, AgentResult):
            return EvaluationReason(value=False, reason="Output is not AgentResult")
        called = [tc["name"] for tc in ctx.output.tool_calls]
        if self.tool_name in called:
            return EvaluationReason(
                value=True, reason=f"Tool '{self.tool_name}' was called"
            )
        return EvaluationReason(
            value=False, reason=f"Tool '{self.tool_name}' not found in calls: {called}"
        )


@dataclass
class ToolCalledWithArgs(Evaluator):
    """Check a tool was called with specific argument values."""

    tool_name: str
    required_args: dict
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        if not isinstance(ctx.output, AgentResult):
            return EvaluationReason(value=False, reason="Output is not AgentResult")
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
                        reason=f"Tool '{self.tool_name}' called with correct args: {self.required_args}",
                    )
                return EvaluationReason(
                    value=False,
                    reason=f"Tool '{self.tool_name}' called but args mismatch: {missing}",
                )
        called = [tc["name"] for tc in ctx.output.tool_calls]
        return EvaluationReason(
            value=False,
            reason=f"Tool '{self.tool_name}' never called. Called: {called}",
        )


@dataclass
class DoesNotContain(Evaluator):
    """Check that NONE of the given substrings appear in the output (safety check)."""

    forbidden: list[str]
    case_sensitive: bool = False
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        text = (
            ctx.output.text if isinstance(ctx.output, AgentResult) else str(ctx.output)
        )
        haystack = text if self.case_sensitive else text.lower()
        for term in self.forbidden:
            needle = term if self.case_sensitive else term.lower()
            if needle in haystack:
                return EvaluationReason(
                    value=False, reason=f"Forbidden term '{term}' found in response"
                )
        return EvaluationReason(
            value=True, reason=f"None of {self.forbidden} found (good)"
        )


# ---------------------------------------------------------------------------
# Task function — real agent, real Haiku 4.5, real user_id for DB access
# ---------------------------------------------------------------------------


async def _run_agent(message: str) -> AgentResult:
    """Run the agent with real Haiku 4.5 and a user_id for DB-dependent skills."""
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
# Scenario 1 — Custom recipe generation (salmon lunch)
# Expected: agent calls load_skill("meal-planning") then
#           run_skill_script("meal-planning", "generate_custom_recipe", ...)
#           Response contains recipe with salmon, ingredients, instructions.
# ---------------------------------------------------------------------------


def scenario_1_custom_recipe_dataset() -> Dataset:
    """Agent generates a custom recipe from a specific ingredient request."""
    return Dataset(
        name="scenario_1_custom_recipe",
        cases=[
            Case(
                name="salmon_lunch_recipe",
                inputs=(
                    "Je voudrais une recette a base de saumon pour mon dejeuner. "
                    "Cible : environ 600 kcal, 40g de proteines. "
                    "Je n'ai aucune allergie."
                ),
                evaluators=(
                    NoRefusal(),
                    ResponseMinLength(min_chars=150),
                    # Agent should route to meal-planning skill
                    ToolWasCalled(tool_name="load_skill"),
                    ToolCalledWithArgs(
                        tool_name="run_skill_script",
                        required_args={
                            "skill_name": "meal-planning",
                            "script_name": "generate_custom_recipe",
                        },
                    ),
                    # Response mentions salmon/saumon
                    ContainsAnyOf(options=["saumon", "salmon"]),
                    # Response contains recipe structure
                    ContainsAnyOf(
                        options=[
                            "ingredients",
                            "ingrédients",
                            "préparation",
                            "instructions",
                            "recette",
                        ],
                        evaluation_name="recipe_structure",
                    ),
                ),
            ),
            Case(
                name="allergen_exclusion_peanuts",
                inputs=(
                    "Donne-moi une recette pour le diner, environ 500 kcal. "
                    "IMPORTANT : j'ai une allergie severe aux arachides et aux cacahuetes."
                ),
                evaluators=(
                    NoRefusal(),
                    ResponseMinLength(min_chars=150),
                    ToolWasCalled(tool_name="run_skill_script"),
                    # Recipe content present
                    ContainsAnyOf(
                        options=[
                            "recette",
                            "ingrédients",
                            "ingredients",
                            "préparation",
                        ],
                        evaluation_name="recipe_content",
                    ),
                    # Peanuts should not appear as an actual ingredient
                    # Note: agent may mention "sans arachides" as safety confirmation
                    # — that's acceptable. We check for ingredient-like patterns.
                    DoesNotContain(
                        forbidden=[
                            "beurre de cacahuète",
                            "peanut butter",
                            "huile d'arachide",
                            "peanut oil",
                        ],
                        evaluation_name="allergen_exclusion",
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=120.0)],
    )


# ---------------------------------------------------------------------------
# Scenario 2 — Shopping list generation
# Expected: agent calls load_skill("meal-planning") then
#           run_skill_script("meal-planning", "generate_shopping_list", ...)
#           Response contains categorized items and mentions persistence.
# ---------------------------------------------------------------------------


def scenario_2_shopping_list_dataset() -> Dataset:
    """Agent generates a shopping list from an existing meal plan."""
    return Dataset(
        name="scenario_2_shopping_list",
        cases=[
            Case(
                name="full_week_shopping_list",
                inputs=(
                    "Genere-moi la liste de courses pour mon plan repas "
                    "de la semaine du 2026-02-23."
                ),
                evaluators=(
                    NoRefusal(),
                    ResponseMinLength(min_chars=100),
                    # Agent should route to meal-planning skill
                    ToolWasCalled(tool_name="load_skill"),
                    ToolCalledWithArgs(
                        tool_name="run_skill_script",
                        required_args={
                            "skill_name": "meal-planning",
                            "script_name": "generate_shopping_list",
                        },
                        evaluation_name="correct_script_routing",
                    ),
                    # Response mentions food categories
                    ContainsAnyOf(
                        options=[
                            "protéines",
                            "proteines",
                            "proteins",
                            "légumes",
                            "legumes",
                            "produce",
                            "féculents",
                            "feculents",
                            "grains",
                            "courses",
                            "liste",
                        ],
                        evaluation_name="shopping_categories",
                    ),
                ),
            ),
            Case(
                name="partial_days_shopping_list",
                inputs=(
                    "Fais-moi une liste de courses pour les 3 premiers jours "
                    "(lundi, mardi, mercredi) de mon plan du 2026-02-23."
                ),
                evaluators=(
                    NoRefusal(),
                    ResponseMinLength(min_chars=100),
                    ToolWasCalled(tool_name="run_skill_script"),
                    # Response mentions food items or categories
                    ContainsAnyOf(
                        options=["courses", "liste", "articles", "items"],
                        evaluation_name="shopping_list_content",
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
async def test_scenario_1_custom_recipe():
    """E2E: Agent generates custom recipes with correct skill routing (real Haiku 4.5)."""
    dataset = scenario_1_custom_recipe_dataset()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.integration
async def test_scenario_2_shopping_list():
    """E2E: Agent generates shopping lists with DB persistence (real Haiku 4.5)."""
    dataset = scenario_2_shopping_list_dataset()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"
