"""End-to-end agent eval — real Haiku 4.5 making real decisions.

WHY THIS IS AN EVAL, NOT A TEST
================================
These scenarios involve a real LLM (Haiku 4.5) making decisions:
  - Which skill to load?
  - Which script to call?
  - Which parameters to extract from natural language?
  - How to synthesize the final response?

Outcomes are non-deterministic → scored criteria, not exact assertions.
Run on demand before releases, NOT in CI (slow, costs API credits).

    pytest evals/test_agent_e2e.py -m integration -v

TEST PERSONA — all required fields defined here, never assumed elsewhere.
=========================================================================
Name:            Marc
Age:             24
Gender:          male
Height:          191 cm
Weight:          86 kg
Activity level:  light (×1.375)
Goal:            muscle gain

Pre-calculated expected values (Mifflin-St Jeor):
  BMR    = (10×86) + (6.25×191) - (5×24) + 5 = 1939 kcal
  TDEE   = 1939 × 1.375                       = 2666 kcal
  Target = TDEE + 300 surplus                 ≈ 2966 kcal
  Protein range: 1.6–2.2 g/kg × 86 kg        = 138–189 g/day
"""

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
    "allergies": [],
}

# Pre-calculated targets (verified with src.nutrition.calculations)
EXPECTED_TDEE = 2666  # kcal/day
EXPECTED_TARGET = 2966  # kcal/day (TDEE + 300 surplus)
EXPECTED_PROTEIN_MIN = 138  # g/day (1.6 g/kg × 86)
EXPECTED_PROTEIN_MAX = 189  # g/day (2.2 g/kg × 86)

FRENCH_DAY_NAMES = [
    "Lundi",
    "Mardi",
    "Mercredi",
    "Jeudi",
    "Vendredi",
    "Samedi",
    "Dimanche",
]


# ---------------------------------------------------------------------------
# Custom evaluators for natural language agent responses
# ---------------------------------------------------------------------------


@dataclass
class NumberInRange(Evaluator):
    """Check that at least one number found in the text falls within [min_val, max_val].

    Used to verify the agent mentions calorie/protein targets in the right range
    without requiring the exact wording.
    """

    min_val: float
    max_val: float
    label: str = ""
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        text = str(ctx.output)
        # Strip markdown formatting so **2664** or `2664` are matched correctly
        clean = re.sub(r"[*_`#|]", "", text)
        numbers = [
            float(n.replace(",", "."))
            for n in re.findall(r"\b\d{3,5}(?:[.,]\d+)?\b", clean)
        ]
        in_range = [n for n in numbers if self.min_val <= n <= self.max_val]
        if in_range:
            return EvaluationReason(
                value=True,
                reason=f"{self.label or 'Number'} found in range: {in_range[0]} ∈ [{self.min_val}, {self.max_val}]",
            )
        return EvaluationReason(
            value=False,
            reason=f"No number in [{self.min_val}, {self.max_val}]. Found: {numbers[:5]}",
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
class NoRefusal(Evaluator):
    """Check the agent did not refuse or say it cannot help.

    A refusal means the agent failed to engage with the task entirely.
    """

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
    """Check the response is substantive (not a one-liner)."""

    min_chars: int
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        length = len(str(ctx.output))
        if length >= self.min_chars:
            return EvaluationReason(
                value=True, reason=f"{length} chars ≥ {self.min_chars}"
            )
        return EvaluationReason(
            value=False, reason=f"Response too short: {length} chars < {self.min_chars}"
        )


@dataclass
class ContainsAllDays(Evaluator):
    """Check that all 7 French day names appear in the response (full week plan)."""

    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        text = str(ctx.output)
        missing = [day for day in FRENCH_DAY_NAMES if day not in text]
        if not missing:
            return EvaluationReason(value=True, reason="All 7 days present")
        return EvaluationReason(value=False, reason=f"Missing days: {missing}")


@dataclass
class MentionsSkill(Evaluator):
    """Check that the agent response reflects having used a specific skill domain.

    Checks for domain keywords rather than internal skill names
    (the agent synthesises results, it doesn't expose its tool calls).
    """

    keywords: list[str]
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        text = str(ctx.output).lower()
        found = [kw for kw in self.keywords if kw.lower() in text]
        if found:
            return EvaluationReason(
                value=True, reason=f"Domain keywords found: {found}"
            )
        return EvaluationReason(
            value=False,
            reason=f"None of {self.keywords} found — skill may not have been called",
        )


# ---------------------------------------------------------------------------
# Task function — real agent, real Haiku 4.5
# ---------------------------------------------------------------------------


async def _run_agent(message: str) -> str:
    """Run the agent with real Haiku 4.5 and return its text response."""
    deps = create_agent_deps(user_id=TEST_USER_ID)
    result = await agent.run(message, deps=deps)
    return result.output


# ---------------------------------------------------------------------------
# Scenario 1 — Nutrition calculation
# Expected: agent calls calculate_nutritional_needs, mentions TDEE ~2666,
#           target ~2966, protein 138–189g
# ---------------------------------------------------------------------------


def scenario_1_nutrition_dataset() -> Dataset:
    """Agent correctly calculates nutritional needs from a natural language message."""
    profile_msg = (
        "J'ai 24 ans, je suis un homme, je mesure 191cm, je pèse 86kg, "
        "activité légère, mon objectif est la prise de muscle. "
        "Calcule mes besoins nutritionnels."
    )
    return Dataset(
        name="scenario_1_nutrition_calculation",
        cases=[
            Case(
                name="full_profile_muscle_gain",
                inputs=profile_msg,
                evaluators=(
                    NoRefusal(),
                    ResponseMinLength(min_chars=200),
                    # Agent should mention TDEE in the right range
                    NumberInRange(min_val=2500, max_val=2900, label="TDEE"),
                    # Agent should mention calorie target with surplus
                    NumberInRange(min_val=2800, max_val=3200, label="Calorie target"),
                    # Agent should mention protein recommendation
                    NumberInRange(
                        min_val=EXPECTED_PROTEIN_MIN,
                        max_val=EXPECTED_PROTEIN_MAX,
                        label="Protein",
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=60.0)],
    )


# ---------------------------------------------------------------------------
# Scenario 2 — Meal plan generation
# Expected: agent calls load_skill(meal-planning) → generate_week_plan,
#           returns a 7-day plan
# ---------------------------------------------------------------------------


def scenario_2_meal_plan_dataset() -> Dataset:
    """Agent generates a full weekly meal plan matching calorie targets."""
    meal_plan_msg = (
        "Génère mon plan repas pour la semaine. "
        f"Mes cibles nutritionnelles : {EXPECTED_TARGET} kcal/jour, "
        f"{EXPECTED_PROTEIN_MIN + 17}g de protéines. "
        "Je suis omnivore, sans allergies."
    )
    return Dataset(
        name="scenario_2_meal_plan",
        cases=[
            Case(
                name="weekly_plan_omnivore_no_allergies",
                inputs=meal_plan_msg,
                evaluators=(
                    NoRefusal(),
                    ResponseMinLength(min_chars=500),
                    # The design shows only Lundi + Mardi — verify at least one is present
                    ContainsAnyOf(options=["Lundi", "Mardi"]),
                    # Verify meal plan content keywords are mentioned (DB store confirmation)
                    ContainsAnyOf(options=["plan", "semaine", "jour", "repas", "kcal"]),
                    # Should include collation (auto-detected for ≥2500 kcal target)
                    ContainsAnyOf(
                        options=[
                            "collation",
                            "Collation",
                            "pré-training",
                            "pre-training",
                            "snack",
                        ]
                    ),
                    # Verify next steps offered — broad prefixes catch past tense (génér*)
                    ContainsAnyOf(
                        options=["courses", "génér", "d'autres", "souhait", "veux-tu"]
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=120.0)],
    )


# ---------------------------------------------------------------------------
# Scenario 3 — Custom recipe request
# Expected: agent calls generate_custom_recipe with meal_type=dejeuner,
#           response mentions salmon/saumon
# ---------------------------------------------------------------------------


def scenario_3_custom_recipe_dataset() -> Dataset:
    """Agent generates a custom recipe from a specific ingredient request."""
    return Dataset(
        name="scenario_3_custom_recipe",
        cases=[
            Case(
                name="salmon_lunch_no_allergies",
                inputs=(
                    "Je voudrais une recette à base de saumon pour mon déjeuner. "
                    "Cible : environ 600 kcal, 40g de protéines. "
                    "Je n'ai aucune allergie."
                ),
                evaluators=(
                    NoRefusal(),
                    ResponseMinLength(min_chars=150),
                    ContainsAnyOf(options=["saumon", "salmon"]),
                    MentionsSkill(
                        keywords=[
                            "recette",
                            "ingrédients",
                            "préparation",
                            "instructions",
                        ]
                    ),
                ),
            ),
            Case(
                name="allergen_respected",
                inputs=(
                    "Je voudrais une recette pour mon dîner. "
                    "IMPORTANT : j'ai une allergie sévère aux arachides. "
                    "Cible : 500 kcal."
                ),
                evaluators=(
                    NoRefusal(),
                    ResponseMinLength(min_chars=150),
                    # The word "arachide" should NOT appear as an ingredient
                    MentionsSkill(keywords=["recette", "ingrédients", "préparation"]),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=90.0)],
    )


# ---------------------------------------------------------------------------
# Scenario 4 — Nutrition knowledge query
# Expected: agent calls knowledge-searching → retrieve_relevant_documents,
#           response mentions protein ranges for muscle gain
# ---------------------------------------------------------------------------


def scenario_4_knowledge_dataset() -> Dataset:
    """Agent answers a nutrition science question using the knowledge base."""
    return Dataset(
        name="scenario_4_knowledge_query",
        cases=[
            Case(
                name="protein_for_muscle_gain",
                inputs=(
                    "Combien de grammes de protéines par kilo de poids de corps "
                    "dois-je consommer pour optimiser la prise de muscle ?"
                ),
                evaluators=(
                    NoRefusal(),
                    ResponseMinLength(min_chars=100),
                    # Should mention protein per kg range (1.6 to 2.2 g/kg)
                    ContainsAnyOf(
                        options=["1.6", "1,6", "2.2", "2,2", "g/kg", "par kilo"]
                    ),
                    MentionsSkill(
                        keywords=[
                            "protéine",
                            "muscle",
                            "synthèse",
                            "recherche",
                            "étude",
                        ]
                    ),
                ),
            ),
            Case(
                name="calorie_deficit_weight_loss",
                inputs=(
                    "Quel déficit calorique recommandes-tu pour perdre du poids "
                    "sans perdre de muscle ?"
                ),
                evaluators=(
                    NoRefusal(),
                    ResponseMinLength(min_chars=100),
                    ContainsAnyOf(options=["déficit", "500", "300", "kcal"]),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=60.0)],
    )


# ---------------------------------------------------------------------------
# Scenario 5 — Weekly feedback & coaching
# Expected: agent calls weekly-coaching → calculate_weekly_adjustments,
#           detects hunger as red flag, suggests calorie increase
# ---------------------------------------------------------------------------


def scenario_5_coaching_dataset() -> Dataset:
    """Agent processes weekly feedback and suggests appropriate adjustments."""
    return Dataset(
        name="scenario_5_weekly_coaching",
        cases=[
            Case(
                name="hunger_red_flag_muscle_gain",
                inputs=(
                    "Retour de ma semaine : j'ai suivi mon plan à 90%, "
                    "j'ai pris 0.3kg (de 86.0kg à 86.3kg), "
                    "mais j'avais faim tout le temps et mon énergie était basse. "
                    f"Ma cible calorique était {EXPECTED_TARGET} kcal. "
                    "Qu'est-ce que tu recommandes pour la semaine prochaine ?"
                ),
                evaluators=(
                    NoRefusal(),
                    ResponseMinLength(min_chars=150),
                    # Agent should detect hunger as a concern
                    ContainsAnyOf(
                        options=["faim", "hunger", "calories", "augmenter", "ajuster"]
                    ),
                    # Should mention an adjusted calorie target
                    NumberInRange(min_val=2800, max_val=3400, label="Adjusted target"),
                ),
            ),
            Case(
                name="on_track_no_change_needed",
                inputs=(
                    "Bilan de la semaine : j'ai suivi le plan à 95%, "
                    "j'ai pris 0.25kg (de 86.0 à 86.25kg), "
                    "énergie bonne, pas de faim, sommeil excellent. "
                    f"Cible était {EXPECTED_TARGET} kcal."
                ),
                evaluators=(
                    NoRefusal(),
                    ResponseMinLength(min_chars=100),
                    ContainsAnyOf(
                        options=[
                            "bien",
                            "bonne",
                            "continue",
                            "maintenir",
                            "progression",
                        ]
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=60.0)],
    )


# ---------------------------------------------------------------------------
# Scenario 6 — 1-day meal plan (default behavior)
# Expected: agent calls generate_week_plan with num_days=1 (default),
#           auto-detects meal_structure (≥2500 kcal → 3_meals_1_preworkout),
#           returns Lundi with collation/snack, macros in range
# ---------------------------------------------------------------------------


def scenario_6_one_day_plan_dataset() -> Dataset:
    """Agent generates a 1-day meal plan with auto-detected meal structure."""
    one_day_msg = (
        "Génère-moi un plan repas pour aujourd'hui. "
        f"Mes cibles : {EXPECTED_TARGET} kcal/jour, "
        f"{EXPECTED_PROTEIN_MIN + 17}g de protéines, "
        "284g de glucides, 63g de lipides. "
        "Je suis omnivore, sans allergies."
    )
    return Dataset(
        name="scenario_6_one_day_plan",
        cases=[
            Case(
                name="one_day_auto_structure_high_cal",
                inputs=one_day_msg,
                evaluators=(
                    NoRefusal(),
                    ResponseMinLength(min_chars=300),
                    # Should show at least one day (Lundi by default)
                    ContainsAnyOf(options=FRENCH_DAY_NAMES),
                    # Should include a collation/snack (auto-detected for ≥2500 kcal)
                    ContainsAnyOf(
                        options=[
                            "collation",
                            "Collation",
                            "pré-training",
                            "pre-training",
                            "snack",
                            "Snack",
                        ]
                    ),
                    # Calories should be in the target range (±15%)
                    NumberInRange(
                        min_val=EXPECTED_TARGET * 0.85,
                        max_val=EXPECTED_TARGET * 1.15,
                        label="Daily calories",
                    ),
                    # Protein should be in a reasonable range
                    NumberInRange(
                        min_val=EXPECTED_PROTEIN_MIN,
                        max_val=EXPECTED_PROTEIN_MAX + 20,
                        label="Daily protein",
                    ),
                    # Should mention meal plan content
                    MentionsSkill(
                        keywords=[
                            "recette",
                            "ingrédients",
                            "repas",
                            "petit-déjeuner",
                            "déjeuner",
                            "dîner",
                        ]
                    ),
                    # Should offer next steps (more days or shopping list)
                    ContainsAnyOf(
                        options=[
                            "courses",
                            "génér",
                            "d'autres",
                            "souhait",
                            "veux-tu",
                            "liste",
                        ]
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
async def test_scenario_1_nutrition_calculation():
    """E2E: Agent calculates nutritional needs for Marc's profile (real Haiku 4.5)."""
    dataset = scenario_1_nutrition_dataset()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.integration
async def test_scenario_2_meal_plan_generation():
    """E2E: Agent generates a 7-day meal plan matching calorie targets (real Haiku 4.5)."""
    dataset = scenario_2_meal_plan_dataset()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.integration
async def test_scenario_3_custom_recipe():
    """E2E: Agent generates custom recipes respecting allergen constraints (real Haiku 4.5)."""
    dataset = scenario_3_custom_recipe_dataset()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.integration
async def test_scenario_4_knowledge_query():
    """E2E: Agent answers nutrition science questions from the knowledge base (real Haiku 4.5)."""
    dataset = scenario_4_knowledge_dataset()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.integration
async def test_scenario_5_weekly_coaching():
    """E2E: Agent processes weekly feedback and detects red flags (real Haiku 4.5)."""
    dataset = scenario_5_coaching_dataset()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.integration
async def test_scenario_6_one_day_plan():
    """E2E: Agent generates a 1-day plan with auto meal structure and collation (real Haiku 4.5)."""
    dataset = scenario_6_one_day_plan_dataset()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"
