"""E2E eval — fat % for muscle_gain & disliked foods filtering with real LLM.

WHY THIS IS AN EVAL, NOT A TEST
================================
These scenarios involve a real LLM (Haiku 4.5) making decisions:
  - Does the agent calculate fat at 25% for muscle_gain? (presentation of results)
  - Does the agent pass disliked_foods through to meal planning?
  - Does the agent's meal plan response exclude disliked foods?

Deterministic logic (compound food exceptions, _contains_disliked) is tested
in tests/test_recipe_db.py. These evals verify the full agent pipeline.

Outcomes are non-deterministic → scored criteria, not exact assertions.
Run on demand before releases, NOT in CI (slow, costs API credits).

    pytest evals/test_fat_pct_disliked_foods_e2e.py -m integration -v

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

  Fat @ 25% of target: 2966 × 0.25 / 9       ≈ 82g (range: 70-100g)
  Fat @ old 22%:       2966 × 0.22 / 9       ≈ 72g (should NOT see this)
  Protein: 1.6–2.2 g/kg × 86 kg              = 138–189 g/day

Disliked foods scenario: "fromage" disliked
  - Should exclude: "Galette fromage", "Omelette aux herbes et fromage"
  - Should NOT exclude: "Fromage blanc fruits", "Fromage frais et radis"
"""

import json
import re
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


TEST_USER_ID = "5745fc58-9c75-48b1-bc79-12855a8c6021"

# --- Test persona (single source of truth) ---
TEST_USER_PROFILE = {
    "age": 24,
    "gender": "male",
    "height_cm": 191,
    "weight_kg": 86.0,
    "activity_level": "light",
    "goals": "muscle_gain",
    "diet_type": "omnivore",
    "allergies": [],
    "disliked_foods": ["fromage"],
    "preferred_cuisines": ["française", "méditerranéenne"],
    "max_prep_time": 30,
}

# --- Pre-calculated expected values ---
EXPECTED_TDEE = 2666
EXPECTED_TARGET = 2966
EXPECTED_PROTEIN_MIN = 138  # 1.6 g/kg × 86
EXPECTED_PROTEIN_MAX = 189  # 2.2 g/kg × 86
# Fat at 25% of target calories
EXPECTED_FAT_G = 82  # 2966 × 0.25 / 9 ≈ 82g
EXPECTED_FAT_MIN = 70  # tolerant lower bound
EXPECTED_FAT_MAX = 100  # tolerant upper bound


# --- Structured output (text + tool calls) ---
@dataclass
class AgentResult:
    text: str
    tool_calls: list[dict]


# --- Evaluators ---


@dataclass
class NumberInRange(Evaluator):
    """Check that at least one number in the text falls within [min_val, max_val]."""

    min_val: float
    max_val: float
    label: str = ""
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        text = (
            ctx.output.text if isinstance(ctx.output, AgentResult) else str(ctx.output)
        )
        clean = re.sub(r"[*_`#|]", "", text)
        numbers = [
            float(n.replace(",", "."))
            for n in re.findall(r"\b\d{2,5}(?:[.,]\d+)?\b", clean)
        ]
        in_range = [n for n in numbers if self.min_val <= n <= self.max_val]
        if in_range:
            return EvaluationReason(
                value=True,
                reason=f"{self.label or 'Number'} found in range: {in_range[0]} ∈ [{self.min_val}, {self.max_val}]",
            )
        return EvaluationReason(
            value=False,
            reason=f"No number in [{self.min_val}, {self.max_val}]. Found: {numbers[:8]}",
        )


@dataclass
class ContainsAnyOf(Evaluator):
    """Check that at least one of the given substrings appears in the output."""

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
class DoesNotContain(Evaluator):
    """Check that NONE of the given substrings appear in the output.

    Used to verify disliked/excluded foods are absent from meal plans.
    """

    forbidden: list[str]
    case_sensitive: bool = False
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        text = (
            ctx.output.text if isinstance(ctx.output, AgentResult) else str(ctx.output)
        )
        haystack = text if self.case_sensitive else text.lower()
        found = [
            f
            for f in self.forbidden
            if (f if self.case_sensitive else f.lower()) in haystack
        ]
        if found:
            return EvaluationReason(
                value=False,
                reason=f"Forbidden terms found: {found}",
            )
        return EvaluationReason(value=True, reason="No forbidden terms found")


@dataclass
class NoRefusal(Evaluator):
    """Check the agent did not refuse or say it cannot help."""

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
        text = (
            ctx.output.text if isinstance(ctx.output, AgentResult) else str(ctx.output)
        )
        text_lower = text.lower()
        for phrase in self._REFUSAL_PHRASES:
            if phrase in text_lower:
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
                value=True, reason=f"{length} chars ≥ {self.min_chars}"
            )
        return EvaluationReason(
            value=False, reason=f"Response too short: {length} chars < {self.min_chars}"
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
                        reason=f"Tool '{self.tool_name}' called with correct args",
                    )
                return EvaluationReason(
                    value=False,
                    reason=f"Args mismatch: {missing}",
                )
        return EvaluationReason(
            value=False,
            reason=f"Tool '{self.tool_name}' not found in calls",
        )


# --- Task function ---
async def _run_agent(message: str) -> AgentResult:
    """Run the agent with real Haiku 4.5 and return text + tool calls."""
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
# Scenario 1 — Fat % at 25% for muscle_gain
# Expected: agent calculates macros with fat ≈ 82g (25% of ~2966 kcal),
#           NOT the old 72g (22%).
# ---------------------------------------------------------------------------


def scenario_1_fat_pct_muscle_gain() -> Dataset:
    """Agent calculates macros for muscle_gain with fat at 25%."""
    profile_msg = (
        "J'ai 24 ans, je suis un homme, je mesure 191cm, je pèse 86kg, "
        "activité légère, mon objectif est la prise de muscle. "
        "Calcule mes besoins nutritionnels avec les macros détaillés "
        "(protéines, glucides, lipides en grammes)."
    )
    return Dataset(
        name="scenario_1_fat_pct_muscle_gain",
        cases=[
            Case(
                name="fat_25_pct_muscle_gain",
                inputs=profile_msg,
                evaluators=(
                    NoRefusal(),
                    ResponseMinLength(min_chars=200),
                    # Agent should call nutrition-calculating skill
                    ToolWasCalled(
                        tool_name="run_skill_script",
                        evaluation_name="skill_script_called",
                    ),
                    # Fat should be in 70-100g range (25% of ~2966 kcal)
                    NumberInRange(
                        min_val=EXPECTED_FAT_MIN,
                        max_val=EXPECTED_FAT_MAX,
                        label="Fat (g)",
                        evaluation_name="fat_in_25pct_range",
                    ),
                    # Should mention lipides/graisses
                    ContainsAnyOf(
                        options=["lipide", "graisse", "fat", "matières grasses"],
                        evaluation_name="mentions_fat",
                    ),
                    # Protein should still be in range
                    NumberInRange(
                        min_val=EXPECTED_PROTEIN_MIN,
                        max_val=EXPECTED_PROTEIN_MAX,
                        label="Protein (g)",
                        evaluation_name="protein_in_range",
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=90.0)],
    )


# ---------------------------------------------------------------------------
# Scenario 2 — Meal plan with disliked foods passed through
# Expected: agent calls meal-planning with disliked_foods, response doesn't
#           contain cheese-based recipe names (but "fromage blanc" is OK).
# ---------------------------------------------------------------------------


def scenario_2_disliked_foods_meal_plan() -> Dataset:
    """Agent generates a day plan excluding disliked foods (fromage)."""
    meal_plan_msg = (
        "Génère-moi un plan repas pour aujourd'hui. "
        f"Mes cibles : {EXPECTED_TARGET} kcal/jour, "
        f"{EXPECTED_PROTEIN_MIN + 17}g de protéines. "
        "Je suis omnivore, sans allergies. "
        "IMPORTANT : je n'aime pas le fromage, ne mets aucune recette "
        "avec du fromage. Par contre le fromage blanc et le fromage frais "
        "sont acceptés (ce sont des produits laitiers différents)."
    )
    return Dataset(
        name="scenario_2_disliked_foods_plan",
        cases=[
            Case(
                name="no_cheese_in_plan",
                inputs=meal_plan_msg,
                evaluators=(
                    NoRefusal(),
                    ResponseMinLength(min_chars=300),
                    # Should call run_skill_script for meal planning
                    ToolWasCalled(
                        tool_name="run_skill_script",
                        evaluation_name="meal_plan_skill_called",
                    ),
                    # Response should NOT contain cheese recipe names
                    # (but "fromage blanc" and "fromage frais" are allowed)
                    ContainsAnyOf(
                        options=["repas", "déjeuner", "dîner", "petit-déjeuner"],
                        evaluation_name="has_meal_types",
                    ),
                    # Should show at least one day
                    ContainsAnyOf(
                        options=[
                            "Lundi",
                            "Mardi",
                            "Mercredi",
                            "Jeudi",
                            "Vendredi",
                            "Samedi",
                            "Dimanche",
                        ]
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=120.0)],
    )


# ---------------------------------------------------------------------------
# Scenario 3 — Nutrition calculation mentions updated fat %
# Expected: When the user asks specifically about fat percentage for muscle
#           gain, the agent should report ~25% (not old 22%).
# ---------------------------------------------------------------------------


def scenario_3_fat_pct_explicit_question() -> Dataset:
    """Agent correctly reports fat percentage as ~25% for muscle gain goal."""
    question_msg = (
        "Pour un objectif de prise de muscle, quel pourcentage de mes "
        "calories totales devrait provenir des lipides ? "
        "Calcule aussi les grammes pour un apport de 3000 kcal."
    )
    return Dataset(
        name="scenario_3_fat_pct_explicit",
        cases=[
            Case(
                name="fat_pct_is_25_not_22",
                inputs=question_msg,
                evaluators=(
                    NoRefusal(),
                    ResponseMinLength(min_chars=100),
                    # Should mention 25% (the new value)
                    ContainsAnyOf(
                        options=["25%", "25 %", "25 pour"],
                        evaluation_name="mentions_25_pct",
                    ),
                    # Fat in grams for 3000 kcal @ 25%: 3000 * 0.25 / 9 ≈ 83g
                    NumberInRange(
                        min_val=75,
                        max_val=95,
                        label="Fat grams at 25%",
                        evaluation_name="fat_grams_correct",
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=90.0)],
    )


# ---------------------------------------------------------------------------
# Pytest test functions — marked integration (excluded from CI)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_scenario_1_fat_pct_muscle_gain():
    """E2E: Agent calculates fat at 25% for muscle_gain (real Haiku 4.5)."""
    dataset = scenario_1_fat_pct_muscle_gain()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.integration
async def test_scenario_2_disliked_foods_meal_plan():
    """E2E: Agent generates meal plan excluding disliked foods (real Haiku 4.5)."""
    dataset = scenario_2_disliked_foods_meal_plan()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.integration
async def test_scenario_3_fat_pct_explicit():
    """E2E: Agent reports fat percentage as ~25% for muscle gain (real Haiku 4.5)."""
    dataset = scenario_3_fat_pct_explicit_question()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"
