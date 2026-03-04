"""Eval — does the agent emit well-formed <!--UI:Component:{json}--> markers?

WHY THIS IS AN EVAL, NOT A TEST
================================
This tests whether a real LLM follows the system prompt instructions to emit
UI component markers in the correct format with valid JSON props. The agent
must decide WHEN to emit markers and WHAT data to include — this is
non-deterministic LLM behaviour, not testable with FunctionModel.

Run on demand before releases, NOT in CI.

    pytest evals/test_generative_ui_markers.py -m integration -v

TEST PERSONA
============
Name:            Sophie
Age:             30
Gender:          female
Height:          165 cm
Weight:          62 kg
Activity level:  moderate (×1.55)
Goal:            maintenance

Pre-calculated expected values (Mifflin-St Jeor):
  BMR    = (10×62) + (6.25×165) - (5×30) - 161 = 1341 kcal
  TDEE   = 1341 × 1.55                          = 2079 kcal
  Target = TDEE (maintenance)                    ≈ 2079 kcal
"""

import json
import re
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
from src.ui_components import UI_MARKER_PATTERN, extract_ui_components

# ---------------------------------------------------------------------------
# Test persona
# ---------------------------------------------------------------------------

TEST_USER_PROFILE = {
    "age": 30,
    "gender": "female",
    "height_cm": 165,
    "weight_kg": 62.0,
    "activity_level": "moderate",
    "goal": "maintenance",
    "diet_type": "omnivore",
    "allergies": ["arachides"],
}

EXPECTED_BMR = 1341
EXPECTED_TDEE = 2079

KNOWN_COMPONENTS = {
    "NutritionSummaryCard",
    "MacroGauges",
    "MealCard",
    "DayPlanCard",
    "WeightTrendIndicator",
    "AdjustmentCard",
    "QuickReplyChips",
}


# ---------------------------------------------------------------------------
# Evaluators
# ---------------------------------------------------------------------------


@dataclass
class ContainsUIMarkers(Evaluator):
    """Check that the response contains at least one well-formed UI marker."""

    min_markers: int = 1
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        text = str(ctx.output)
        matches = UI_MARKER_PATTERN.findall(text)
        if len(matches) >= self.min_markers:
            return EvaluationReason(
                value=True,
                reason=f"Found {len(matches)} UI marker(s) (min: {self.min_markers})",
            )
        return EvaluationReason(
            value=False,
            reason=f"Found {len(matches)} UI marker(s), expected at least {self.min_markers}",
        )


@dataclass
class MarkersHaveValidJSON(Evaluator):
    """Check that ALL UI markers in the response have parseable JSON props."""

    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        text = str(ctx.output)
        matches = UI_MARKER_PATTERN.finditer(text)
        total = 0
        invalid = []
        for match in matches:
            total += 1
            component_name = match.group(1)
            json_str = match.group(2)
            try:
                json.loads(json_str)
            except json.JSONDecodeError as e:
                invalid.append(f"{component_name}: {e}")

        if total == 0:
            return EvaluationReason(value=False, reason="No markers found to validate")
        if invalid:
            return EvaluationReason(
                value=False,
                reason=f"{len(invalid)}/{total} markers have invalid JSON: {invalid}",
            )
        return EvaluationReason(
            value=True, reason=f"All {total} markers have valid JSON"
        )


@dataclass
class MarkersUseKnownComponents(Evaluator):
    """Check that all emitted markers use component names from the catalog."""

    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        text = str(ctx.output)
        _, components = extract_ui_components(text)
        if not components:
            return EvaluationReason(value=False, reason="No components extracted")
        unknown = [
            c["component"] for c in components if c["component"] not in KNOWN_COMPONENTS
        ]
        if unknown:
            return EvaluationReason(
                value=False, reason=f"Unknown components: {unknown}"
            )
        return EvaluationReason(
            value=True,
            reason=f"All {len(components)} components are known catalog entries",
        )


@dataclass
class ContainsExpectedComponent(Evaluator):
    """Check that a specific component type appears in the markers."""

    component_name: str
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        text = str(ctx.output)
        _, components = extract_ui_components(text)
        found = [c for c in components if c["component"] == self.component_name]
        if found:
            return EvaluationReason(
                value=True,
                reason=f"{self.component_name} found ({len(found)} instance(s))",
            )
        all_names = [c["component"] for c in components]
        return EvaluationReason(
            value=False,
            reason=f"{self.component_name} not found. Present: {all_names}",
        )


@dataclass
class TextBeforeMarkers(Evaluator):
    """Check that text explanation appears BEFORE the first UI marker.

    The system prompt requires: text first, markers after.
    """

    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        text = str(ctx.output)
        first_marker = UI_MARKER_PATTERN.search(text)
        if not first_marker:
            return EvaluationReason(value=False, reason="No markers found")
        text_before = text[: first_marker.start()].strip()
        if len(text_before) >= 50:
            return EvaluationReason(
                value=True,
                reason=f"{len(text_before)} chars of text before first marker",
            )
        return EvaluationReason(
            value=False,
            reason=f"Only {len(text_before)} chars before first marker (expected ≥50)",
        )


@dataclass
class PropsContainRealisticNumbers(Evaluator):
    """Check that numeric props in NutritionSummaryCard/MacroGauges are in realistic ranges."""

    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        text = str(ctx.output)
        _, components = extract_ui_components(text)
        issues = []
        for comp in components:
            props = comp["props"]
            name = comp["component"]

            if name == "NutritionSummaryCard":
                bmr = props.get("bmr", 0)
                tdee = props.get("tdee", 0)
                target = props.get("target_calories", 0)
                if not (1000 <= bmr <= 3000):
                    issues.append(f"BMR={bmr} out of range [1000,3000]")
                if not (1200 <= tdee <= 5000):
                    issues.append(f"TDEE={tdee} out of range [1200,5000]")
                if not (1200 <= target <= 5000):
                    issues.append(f"target_calories={target} out of range [1200,5000]")

            if name == "MacroGauges":
                for macro in ["protein_g", "carbs_g", "fat_g"]:
                    val = props.get(macro, 0)
                    if not (20 <= val <= 500):
                        issues.append(f"{macro}={val} out of range [20,500]")

        if not components:
            return EvaluationReason(value=False, reason="No components to check")
        if issues:
            return EvaluationReason(value=False, reason=f"Unrealistic values: {issues}")
        return EvaluationReason(
            value=True, reason="All numeric props in realistic ranges"
        )


# ---------------------------------------------------------------------------
# Task function
# ---------------------------------------------------------------------------


async def _run_agent(message: str) -> str:
    """Run the agent with real LLM and return its text response."""
    deps = create_agent_deps()
    result = await agent.run(message, deps=deps)
    return result.output


# User ID for meal-plan scenarios — needs a real profile in Supabase
# so the meal-planning skill can fetch nutritional targets and generate plans.
MEAL_PLAN_TEST_USER_ID = "6870a598-7c9a-4234-a6d7-d20f194bb626"


async def _run_agent_with_user(message: str) -> str:
    """Run the agent with real LLM and a user_id for skill-dependent scenarios."""
    deps = create_agent_deps(user_id=MEAL_PLAN_TEST_USER_ID)
    result = await agent.run(message, deps=deps)
    return result.output


# ---------------------------------------------------------------------------
# Scenario 1 — Nutrition calculation should emit NutritionSummaryCard + MacroGauges
# ---------------------------------------------------------------------------


def scenario_1_nutrition_markers_dataset() -> Dataset:
    """Agent emits UI markers when calculating nutritional needs."""
    msg = (
        "J'ai 30 ans, je suis une femme, je mesure 165cm, je pèse 62kg, "
        "activité modérée, mon objectif est le maintien, allergie aux arachides. "
        "Calcule mes besoins nutritionnels."
    )
    return Dataset(
        name="scenario_1_nutrition_ui_markers",
        cases=[
            Case(
                name="nutrition_calc_emits_markers",
                inputs=msg,
                evaluators=(
                    ContainsUIMarkers(min_markers=1),
                    MarkersHaveValidJSON(),
                    MarkersUseKnownComponents(),
                    ContainsExpectedComponent(component_name="NutritionSummaryCard"),
                    ContainsExpectedComponent(component_name="MacroGauges"),
                    TextBeforeMarkers(),
                    PropsContainRealisticNumbers(),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=90.0)],
    )


# ---------------------------------------------------------------------------
# Scenario 2 — Plain question should NOT emit markers
# ---------------------------------------------------------------------------


@dataclass
class NoUIMarkers(Evaluator):
    """Check that the response does NOT contain any UI markers."""

    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        text = str(ctx.output)
        matches = UI_MARKER_PATTERN.findall(text)
        if not matches:
            return EvaluationReason(value=True, reason="No UI markers (correct)")
        return EvaluationReason(
            value=False,
            reason=f"Found {len(matches)} unexpected UI marker(s)",
        )


def scenario_2_no_markers_for_simple_question() -> Dataset:
    """Agent does NOT emit markers for conversational questions without data."""
    msg = "Qu'est-ce que les protéines et pourquoi sont-elles importantes ?"
    return Dataset(
        name="scenario_2_no_markers_simple_question",
        cases=[
            Case(
                name="knowledge_question_no_markers",
                inputs=msg,
                evaluators=(NoUIMarkers(),),
            ),
        ],
        evaluators=[MaxDuration(seconds=60.0)],
    )


# ---------------------------------------------------------------------------
# Scenario 3 — QuickReplyChips for follow-up suggestions
# ---------------------------------------------------------------------------


def scenario_3_quick_reply_chips_dataset() -> Dataset:
    """Agent includes QuickReplyChips for follow-up suggestions after calculations."""
    msg = (
        "J'ai 30 ans, femme, 165cm, 62kg, activité modérée, maintien. "
        "Calcule mes besoins et propose-moi des actions de suivi."
    )
    return Dataset(
        name="scenario_3_quick_reply_chips",
        cases=[
            Case(
                name="follow_up_chips_emitted",
                inputs=msg,
                evaluators=(
                    ContainsUIMarkers(min_markers=1),
                    MarkersHaveValidJSON(),
                    ContainsExpectedComponent(component_name="QuickReplyChips"),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=90.0)],
    )


# ---------------------------------------------------------------------------
# Scenario 4 — Meal plan should emit DayPlanCard with valid meal structure
# ---------------------------------------------------------------------------


@dataclass
class DayPlanCardHasValidMeals(Evaluator):
    """Check that DayPlanCard markers contain well-structured meals array.

    Each meal must have: meal_type, recipe_name, calories, macros.
    """

    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        text = str(ctx.output)
        _, components = extract_ui_components(text)
        day_cards = [c for c in components if c["component"] == "DayPlanCard"]
        if not day_cards:
            return EvaluationReason(value=False, reason="No DayPlanCard found")

        issues = []
        total_meals = 0
        for card in day_cards:
            props = card["props"]
            if "day_name" not in props:
                issues.append("Missing day_name")
            if "meals" not in props or not isinstance(props.get("meals"), list):
                issues.append("Missing or invalid meals array")
                continue
            if "totals" not in props:
                issues.append("Missing totals")

            for i, meal in enumerate(props["meals"]):
                total_meals += 1
                for required in ["meal_type", "recipe_name", "calories", "macros"]:
                    if required not in meal:
                        issues.append(
                            f"Meal {i} in {props.get('day_name', '?')}: missing '{required}'"
                        )
                if "macros" in meal:
                    macros = meal["macros"]
                    for macro_key in ["protein_g", "carbs_g", "fat_g"]:
                        if macro_key not in macros:
                            issues.append(f"Meal {i} macros: missing '{macro_key}'")

        if issues:
            return EvaluationReason(value=False, reason=f"Structure issues: {issues}")
        return EvaluationReason(
            value=True,
            reason=f"{len(day_cards)} DayPlanCard(s) with {total_meals} total meals, all valid",
        )


@dataclass
class DayPlanCardCaloriesRealistic(Evaluator):
    """Check that DayPlanCard totals.calories is in a realistic range."""

    min_cal: int = 1200
    max_cal: int = 4000
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        text = str(ctx.output)
        _, components = extract_ui_components(text)
        day_cards = [c for c in components if c["component"] == "DayPlanCard"]
        if not day_cards:
            return EvaluationReason(value=False, reason="No DayPlanCard found")

        issues = []
        for card in day_cards:
            totals = card["props"].get("totals", {})
            cal = totals.get("calories", 0)
            day = card["props"].get("day_name", "?")
            if not (self.min_cal <= cal <= self.max_cal):
                issues.append(
                    f"{day}: totals.calories={cal} outside [{self.min_cal},{self.max_cal}]"
                )

        if issues:
            return EvaluationReason(value=False, reason=f"Unrealistic: {issues}")
        return EvaluationReason(
            value=True,
            reason=f"All {len(day_cards)} day(s) have realistic calorie totals",
        )


def scenario_4_meal_plan_emits_dayplancard() -> Dataset:
    """Agent emits DayPlanCard markers when generating a meal plan.

    Uses _run_agent_with_user so the skill can fetch the user profile from DB.
    """
    msg = (
        "Génère-moi un plan repas pour aujourd'hui. "
        "Pas de préférence particulière, 3 repas simples. Go !"
    )
    return Dataset(
        name="scenario_4_meal_plan_dayplancard",
        cases=[
            Case(
                name="meal_plan_emits_dayplancard",
                inputs=msg,
                evaluators=(
                    ContainsUIMarkers(min_markers=1),
                    MarkersHaveValidJSON(),
                    MarkersUseKnownComponents(),
                    ContainsExpectedComponent(component_name="DayPlanCard"),
                    DayPlanCardHasValidMeals(),
                    DayPlanCardCaloriesRealistic(min_cal=1500, max_cal=4000),
                    TextBeforeMarkers(),
                    ContainsExpectedComponent(component_name="QuickReplyChips"),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=120.0)],
    )


# ---------------------------------------------------------------------------
# Scenario 5 — Meal plan link to /plans/{id}
# ---------------------------------------------------------------------------


@dataclass
class ContainsPlanLink(Evaluator):
    """Check that the response contains a link to /plans/{meal_plan_id}."""

    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        text = str(ctx.output)
        if re.search(r"/plans/[a-f0-9-]+", text):
            return EvaluationReason(value=True, reason="Found /plans/{id} link")
        return EvaluationReason(
            value=False,
            reason="No /plans/{id} link found in response",
        )


def scenario_5_meal_plan_contains_link() -> Dataset:
    """Agent includes a link to the visual meal plan page.

    Uses _run_agent_with_user so the skill can fetch the user profile from DB.
    """
    msg = "Génère un plan repas pour 1 jour. Pas de préférence. Lance !"
    return Dataset(
        name="scenario_5_meal_plan_link",
        cases=[
            Case(
                name="plan_link_present",
                inputs=msg,
                evaluators=(
                    ContainsUIMarkers(min_markers=1),
                    ContainsExpectedComponent(component_name="DayPlanCard"),
                    ContainsPlanLink(),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=120.0)],
    )


# ---------------------------------------------------------------------------
# Pytest entrypoints
# ---------------------------------------------------------------------------


def _print_report_details(report) -> None:
    """Print detailed assertion results and the raw agent output for analysis."""
    for case in report.cases:
        print(f"\n--- Case: {case.name} ---")
        print(f"  Assertions: {case.assertions}")
        print(f"  Metrics: {case.metrics}")
        print("\n  === AGENT OUTPUT (first 3000 chars) ===")
        output_str = str(case.output)
        print(output_str[:3000])
        if len(output_str) > 3000:
            print(f"  ... ({len(output_str)} chars total, truncated)")
        print("  === END OUTPUT ===\n")


@pytest.mark.integration
async def test_scenario_1_nutrition_markers():
    dataset = scenario_1_nutrition_markers_dataset()
    report = await dataset.evaluate(_run_agent)
    report.print()
    _print_report_details(report)


@pytest.mark.integration
async def test_scenario_2_no_markers_simple_question():
    dataset = scenario_2_no_markers_for_simple_question()
    report = await dataset.evaluate(_run_agent)
    report.print()
    _print_report_details(report)


@pytest.mark.integration
async def test_scenario_3_quick_reply_chips():
    dataset = scenario_3_quick_reply_chips_dataset()
    report = await dataset.evaluate(_run_agent)
    report.print()
    _print_report_details(report)


@pytest.mark.integration
async def test_scenario_4_meal_plan_dayplancard():
    dataset = scenario_4_meal_plan_emits_dayplancard()
    report = await dataset.evaluate(_run_agent_with_user)
    report.print()
    _print_report_details(report)


@pytest.mark.integration
async def test_scenario_5_meal_plan_link():
    dataset = scenario_5_meal_plan_contains_link()
    report = await dataset.evaluate(_run_agent_with_user)
    report.print()
    _print_report_details(report)
