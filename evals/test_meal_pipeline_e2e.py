"""E2E eval — Meal-planning pipeline with real LLM + real Supabase.

WHY THIS IS AN EVAL, NOT A TEST
================================
These scenarios involve a real LLM (Haiku 4.5) making decisions:
  - Route to meal-planning skill
  - Extract parameters (num_days, target_calories, etc.) from French NL
  - Select recipes from DB matching user profile (diet, allergens, disliked)
  - Scale portions to macro targets
  - Present results with UI markers

Two real Supabase users with different profiles:

USER A — Loïc (6870a598)
  Age: 24, Male, 191cm, 88kg, moderate activity
  Goals: muscle_gain=10, general_health=8
  Diet: omnivore, no allergies
  Dislikes: fromage, huître, fruits de mer
  Targets: 3334 kcal, 176g protein, 448g carbs, 93g fat
  Cuisines: méditerranéenne, française

USER B — Absolute (5745fc58)
  Age: 24, Male, 191cm, 86kg, light activity
  Goals: muscle_gain=9, performance=5
  Diet: omnivore, allergies=[arachides, cacahuètes]
  Dislikes: fromage, choux de Bruxelles
  Targets: 2964 kcal, 172g protein, 384g carbs, 82g fat
  Cuisines: française, méditerranéenne

    pytest evals/test_meal_pipeline_e2e.py -m integration -v -s
"""

import json
import re
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
# Test user profiles — all required fields (used by evals and fixtures)
# ---------------------------------------------------------------------------

TEST_USER_PROFILE_A = {
    "age": 24,
    "gender": "male",
    "height_cm": 191,
    "weight_kg": 88,
    "activity_level": "moderate",
    "goals": {"muscle_gain": 10, "general_health": 8},
}

TEST_USER_PROFILE_B = {
    "age": 24,
    "gender": "male",
    "height_cm": 191,
    "weight_kg": 86,
    "activity_level": "light",
    "goals": {"muscle_gain": 9, "performance": 5},
}

# ---------------------------------------------------------------------------
# User IDs (real Supabase profiles)
# ---------------------------------------------------------------------------

USER_A_ID = "6870a598-7c9a-4234-a6d7-d20f194bb626"  # Loïc — omnivore, no allergies
USER_B_ID = "5745fc58-9c75-48b1-bc79-12855a8c6021"  # Absolute — peanut allergy

USER_A_TARGETS = {
    "calories": 3334,
    "protein_g": 176,
    "carbs_g": 448,
    "fat_g": 93,
}

USER_B_TARGETS = {
    "calories": 2964,
    "protein_g": 172,
    "carbs_g": 384,
    "fat_g": 82,
}

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
# Structured output
# ---------------------------------------------------------------------------


@dataclass
class AgentResult:
    """Captures text, tool calls, and timing from an agent run."""

    text: str
    tool_calls: list[dict]  # [{"name": "...", "args": {...}}, ...]
    elapsed_seconds: float


# ---------------------------------------------------------------------------
# Evaluators
# ---------------------------------------------------------------------------


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
        result: AgentResult = ctx.output
        text = result.text.lower()
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
        result: AgentResult = ctx.output
        length = len(result.text)
        if length >= self.min_chars:
            return EvaluationReason(
                value=True, reason=f"{length} chars ≥ {self.min_chars}"
            )
        return EvaluationReason(
            value=False, reason=f"Response too short: {length} chars < {self.min_chars}"
        )


@dataclass
class ContainsAnyOf(Evaluator):
    """Check that at least one of the given substrings appears in the output."""

    options: list[str]
    case_sensitive: bool = False
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        haystack = result.text if self.case_sensitive else result.text.lower()
        for option in self.options:
            needle = option if self.case_sensitive else option.lower()
            if needle in haystack:
                return EvaluationReason(value=True, reason=f"Found '{option}'")
        return EvaluationReason(
            value=False,
            reason=f"None of {self.options} found in response",
        )


@dataclass
class RecipeDataExcludes(Evaluator):
    """Check that forbidden terms don't appear in recipe data (UI markers).

    Only checks inside <!--UI:DayPlanCard:{...}--> JSON, not in the agent's
    explanatory text (where it may say "I excluded X" which would false-positive).
    Falls back to checking ingredient lists in the full text if no UI markers found.
    """

    forbidden: list[str]
    exceptions: list[str] = field(default_factory=list)
    evaluation_name: str | None = field(default=None)

    def _is_exception(self, text: str, word: str) -> bool:
        """Check if a match is actually a compound exception (e.g. fromage blanc)."""
        for exc in self.exceptions:
            if exc.lower() in text:
                return True
        return False

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        # Extract recipe data from UI markers
        ui_matches = re.findall(
            r"<!--UI:DayPlanCard:(\{.*?\})-->", result.text, re.DOTALL
        )
        if ui_matches:
            # Check inside the JSON recipe data only
            for ui_json in ui_matches:
                try:
                    data = json.loads(ui_json)
                    meals = data.get("meals", [])
                    for meal in meals:
                        ingredients_str = " ".join(meal.get("ingredients", [])).lower()
                        recipe_name = meal.get("recipe_name", "").lower()
                        check_text = f"{recipe_name} {ingredients_str}"
                        for word in self.forbidden:
                            if word.lower() in check_text and not self._is_exception(
                                check_text, word
                            ):
                                return EvaluationReason(
                                    value=False,
                                    reason=f"Forbidden '{word}' in recipe: {meal.get('recipe_name', '?')}",
                                )
                except json.JSONDecodeError:
                    continue
            return EvaluationReason(
                value=True,
                reason=f"No {self.forbidden} found in recipe data",
            )
        # Fallback: no UI markers, check full text (less precise)
        haystack = result.text.lower()
        for word in self.forbidden:
            if word.lower() in haystack and not self._is_exception(haystack, word):
                return EvaluationReason(
                    value=False,
                    reason=f"Forbidden '{word}' found in text (no UI markers to inspect)",
                )
        return EvaluationReason(
            value=True,
            reason=f"No {self.forbidden} found in response",
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
                value=True,
                reason=f"Tool '{self.tool_name}' was called",
            )
        return EvaluationReason(
            value=False,
            reason=f"Tool '{self.tool_name}' NOT called. Called: {called}",
        )


@dataclass
class ToolCalledWithArgs(Evaluator):
    """Check that a tool was called with specific argument values."""

    tool_name: str
    required_args: dict
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        for tc in result.tool_calls:
            if tc["name"] != self.tool_name:
                continue
            args = tc["args"]
            missing = {}
            for key, expected in self.required_args.items():
                actual = args.get(key)
                if str(actual) != str(expected):
                    missing[key] = f"expected={expected}, got={actual}"
            if not missing:
                return EvaluationReason(
                    value=True,
                    reason=f"Tool '{self.tool_name}' called with correct args",
                )
            return EvaluationReason(
                value=False,
                reason=f"Arg mismatch: {missing}",
            )
        return EvaluationReason(
            value=False,
            reason=f"Tool '{self.tool_name}' was never called",
        )


@dataclass
class NumberInRange(Evaluator):
    """Check that at least one number in the text falls within [min_val, max_val]."""

    min_val: float
    max_val: float
    label: str = ""
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        clean = re.sub(r"[*_`#|]", "", result.text)
        numbers = [
            float(n.replace(",", "."))
            for n in re.findall(r"\b\d{3,5}(?:[.,]\d+)?\b", clean)
        ]
        in_range = [n for n in numbers if self.min_val <= n <= self.max_val]
        if in_range:
            return EvaluationReason(
                value=True,
                reason=f"{self.label or 'Number'} found: {in_range[0]} ∈ [{self.min_val}, {self.max_val}]",
            )
        return EvaluationReason(
            value=False,
            reason=f"No number in [{self.min_val}, {self.max_val}]. Found: {numbers[:8]}",
        )


@dataclass
class ContainsAllDays(Evaluator):
    """Check that all 7 French day names appear (full week plan)."""

    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        missing = [day for day in FRENCH_DAY_NAMES if day not in result.text]
        if not missing:
            return EvaluationReason(value=True, reason="All 7 days present")
        return EvaluationReason(value=False, reason=f"Missing days: {missing}")


@dataclass
class PipelineTiming(Evaluator):
    """Check total execution time is within bounds."""

    max_seconds: float
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        if result.elapsed_seconds <= self.max_seconds:
            return EvaluationReason(
                value=True,
                reason=f"Completed in {result.elapsed_seconds:.1f}s ≤ {self.max_seconds}s",
            )
        return EvaluationReason(
            value=False,
            reason=f"Too slow: {result.elapsed_seconds:.1f}s > {self.max_seconds}s",
        )


@dataclass
class HasUIMarkers(Evaluator):
    """Check that the response contains generative UI markers (<!--UI:...-->)."""

    min_markers: int = 1
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        markers = re.findall(r"<!--UI:\w+:", result.text)
        count = len(markers)
        if count >= self.min_markers:
            return EvaluationReason(
                value=True,
                reason=f"Found {count} UI markers (≥ {self.min_markers})",
            )
        return EvaluationReason(
            value=False,
            reason=f"Only {count} UI markers, expected ≥ {self.min_markers}",
        )


# ---------------------------------------------------------------------------
# Task functions — real agent, real DB
# ---------------------------------------------------------------------------


async def _run_agent_user_a(message: str) -> AgentResult:
    """Run agent as User A (Loïc — omnivore, no allergies, dislikes fromage)."""
    deps = create_agent_deps(user_id=USER_A_ID)
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


async def _run_agent_user_b(message: str) -> AgentResult:
    """Run agent as User B (Absolute — peanut allergy, dislikes fromage)."""
    deps = create_agent_deps(user_id=USER_B_ID)
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
# Scenario 1 — User A: 1-day meal plan (omnivore, no allergies, high cal)
# Target: 3334 kcal, pipeline should pick DB recipes, scale portions,
#         show meals with macros, no fromage/fruits de mer in recipes
# ---------------------------------------------------------------------------


def scenario_1_user_a_one_day() -> Dataset:
    """User A requests a 1-day meal plan — high cal omnivore, dislikes fromage."""
    return Dataset(
        name="scenario_1_user_a_one_day",
        cases=[
            Case(
                name="one_day_high_cal_omnivore",
                inputs=(
                    "Génère-moi un plan repas pour aujourd'hui. "
                    "Utilise mon profil pour les cibles."
                ),
                evaluators=(
                    NoRefusal(),
                    ResponseMinLength(min_chars=300),
                    # Must call the right tools
                    ToolWasCalled(
                        tool_name="run_skill_script",
                        evaluation_name="skill_script_called",
                    ),
                    # Should show at least one day
                    ContainsAnyOf(
                        options=FRENCH_DAY_NAMES,
                        evaluation_name="day_name_present",
                    ),
                    # Calories in the target range (±20% tolerance)
                    NumberInRange(
                        min_val=USER_A_TARGETS["calories"] * 0.80,
                        max_val=USER_A_TARGETS["calories"] * 1.20,
                        label="Daily calories",
                        evaluation_name="calories_in_range",
                    ),
                    # Protein in range
                    NumberInRange(
                        min_val=USER_A_TARGETS["protein_g"] * 0.75,
                        max_val=USER_A_TARGETS["protein_g"] * 1.30,
                        label="Daily protein",
                        evaluation_name="protein_in_range",
                    ),
                    # Should mention meal types
                    ContainsAnyOf(
                        options=[
                            "petit-déjeuner",
                            "déjeuner",
                            "dîner",
                            "Petit",
                            "Déjeuner",
                            "Dîner",
                        ],
                        evaluation_name="meal_types_mentioned",
                    ),
                    # Disliked food exclusion: no cheese (but fromage blanc is OK)
                    RecipeDataExcludes(
                        forbidden=[
                            "gruyère",
                            "emmental",
                            "parmesan",
                            "mozzarella",
                            "feta",
                            "comté",
                            "cheddar",
                            "chèvre",
                        ],
                        exceptions=["fromage blanc", "fromage frais"],
                        evaluation_name="no_cheese_in_recipes",
                    ),
                    # Pipeline should complete within 120s
                    PipelineTiming(
                        max_seconds=120.0,
                        evaluation_name="pipeline_timing",
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=180.0)],
    )


# ---------------------------------------------------------------------------
# Scenario 2 — User B: 1-day plan (peanut allergy — safety critical)
# Target: 2964 kcal, NO arachides/cacahuètes in any recipe
# ---------------------------------------------------------------------------


def scenario_2_user_b_allergen_safety() -> Dataset:
    """User B requests a 1-day plan — peanut allergy must be respected."""
    return Dataset(
        name="scenario_2_user_b_allergen_safety",
        cases=[
            Case(
                name="one_day_peanut_allergy",
                inputs=(
                    "Fais-moi un plan repas pour demain. "
                    "Mon profil contient mes allergies, respecte-les."
                ),
                evaluators=(
                    NoRefusal(),
                    ResponseMinLength(min_chars=300),
                    ToolWasCalled(
                        tool_name="run_skill_script",
                        evaluation_name="skill_script_called",
                    ),
                    # CRITICAL: no peanut-related terms
                    RecipeDataExcludes(
                        forbidden=[
                            "arachide",
                            "cacahuète",
                            "cacahuete",
                            "peanut",
                            "beurre de cacahuète",
                        ],
                        evaluation_name="no_peanut_allergen",
                    ),
                    # Calories in range
                    NumberInRange(
                        min_val=USER_B_TARGETS["calories"] * 0.80,
                        max_val=USER_B_TARGETS["calories"] * 1.20,
                        label="Daily calories",
                        evaluation_name="calories_in_range",
                    ),
                    # Disliked foods excluded too (fromage blanc is OK)
                    RecipeDataExcludes(
                        forbidden=[
                            "gruyère",
                            "emmental",
                            "parmesan",
                            "mozzarella",
                            "feta",
                            "chèvre",
                            "choux de bruxelles",
                        ],
                        exceptions=["fromage blanc", "fromage frais"],
                        evaluation_name="no_disliked_foods",
                    ),
                    PipelineTiming(
                        max_seconds=120.0,
                        evaluation_name="pipeline_timing",
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=180.0)],
    )


# ---------------------------------------------------------------------------
# Scenario 3 — User A: 7-day week plan (full pipeline stress test)
# All 7 days present, variety across days, macros mentioned, timing
# ---------------------------------------------------------------------------


def scenario_3_user_a_week_plan() -> Dataset:
    """User A requests a full 7-day plan — pipeline must handle all days."""
    return Dataset(
        name="scenario_3_user_a_week_plan",
        cases=[
            Case(
                name="full_week_plan_omnivore",
                inputs=(
                    "Génère mon plan repas pour la semaine complète (7 jours). "
                    "Utilise mon profil. Assure la variété des recettes."
                ),
                evaluators=(
                    NoRefusal(),
                    ResponseMinLength(min_chars=500),
                    ToolWasCalled(
                        tool_name="run_skill_script",
                        evaluation_name="skill_script_called",
                    ),
                    # All 7 French day names
                    ContainsAllDays(evaluation_name="all_7_days_present"),
                    # Calories should appear in the right range
                    NumberInRange(
                        min_val=USER_A_TARGETS["calories"] * 0.80,
                        max_val=USER_A_TARGETS["calories"] * 1.20,
                        label="Daily calories",
                        evaluation_name="calories_in_range",
                    ),
                    # Meal content keywords
                    ContainsAnyOf(
                        options=["recette", "repas", "ingrédients", "kcal", "calories"],
                        evaluation_name="meal_content_keywords",
                    ),
                    # Disliked food exclusion (fromage blanc is OK)
                    RecipeDataExcludes(
                        forbidden=[
                            "gruyère",
                            "emmental",
                            "parmesan",
                            "mozzarella",
                            "feta",
                            "chèvre",
                            "huître",
                            "fruits de mer",
                        ],
                        exceptions=["fromage blanc", "fromage frais"],
                        evaluation_name="no_disliked_foods",
                    ),
                    # 7-day plan should complete within 5 min
                    PipelineTiming(
                        max_seconds=300.0,
                        evaluation_name="pipeline_timing_week",
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=360.0)],
    )


# ---------------------------------------------------------------------------
# Pytest test functions — marked integration
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_scenario_1_user_a_one_day():
    """E2E: User A (omnivore, high cal) — 1-day plan with disliked food exclusion."""
    dataset = scenario_1_user_a_one_day()
    report = await dataset.evaluate(task=_run_agent_user_a)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.integration
async def test_scenario_2_user_b_allergen_safety():
    """E2E: User B (peanut allergy) — 1-day plan with allergen exclusion."""
    dataset = scenario_2_user_b_allergen_safety()
    report = await dataset.evaluate(task=_run_agent_user_b)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.integration
async def test_scenario_3_user_a_week_plan():
    """E2E: User A — full 7-day plan, variety, timing, disliked food exclusion."""
    dataset = scenario_3_user_a_week_plan()
    report = await dataset.evaluate(task=_run_agent_user_a)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"
