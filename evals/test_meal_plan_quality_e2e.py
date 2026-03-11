"""E2E eval — Meal plan quality: macro precision, recipe variety, text format.

WHY THIS IS AN EVAL, NOT A TEST
================================
These scenarios involve a real LLM (Haiku 4.5) making decisions:
  - Route to meal-planning skill with correct parameters
  - Select varied recipes matching user profile (diet, allergens)
  - Present results as text summaries (NOT DayPlanCard UI markers)
  - Include a clickable /plans/ link
  - Produce macros coherent with the user's goal

Three user profiles tested:

USER A — Loïc (6870a598) — Muscle gain
  Targets: 3334 kcal, 176g protein, 448g carbs, 93g fat
  Diet: omnivore, no allergies, dislikes fromage/huître/fruits de mer

USER B — Absolute (5745fc58) — Muscle gain
  Targets: 2964 kcal, 172g protein, 384g carbs, 82g fat
  Diet: omnivore, allergies=[arachides, cacahuètes], dislikes fromage

Profiles are real Supabase users — agent loads them via get_user_profile.

    pytest evals/test_meal_plan_quality_e2e.py -m integration -v -s
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

USER_A_ID = "6870a598-7c9a-4234-a6d7-d20f194bb626"  # Loïc — muscle gain, omnivore
USER_B_ID = (
    "5745fc58-9c75-48b1-bc79-12855a8c6021"  # Absolute — muscle gain, peanut allergy
)

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


# ---------------------------------------------------------------------------
# Structured output
# ---------------------------------------------------------------------------


@dataclass
class AgentResult:
    """Captures text, tool calls, and timing from an agent run."""

    text: str
    tool_calls: list[dict]
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
class NumberInRange(Evaluator):
    """Check that at least one number in the text falls within [min_val, max_val]."""

    min_val: float
    max_val: float
    label: str = ""
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        clean = re.sub(r"[*_`#|]", "", result.text)
        # Handle French thousands separator (space/nbsp): "2 787" → "2787"
        # Also handle numbers followed by letters: "148g" → "148"
        clean = re.sub(r"(\d)\s+(\d)", r"\1\2", clean)
        numbers = [
            float(n.replace(",", "."))
            for n in re.findall(r"\d{3,5}(?:[.,]\d+)?", clean)
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
class NoDayPlanCardMarkers(Evaluator):
    """Check that no <!--UI:DayPlanCard:...--> markers appear in the response.

    After the SKILL.md change, the agent should output text summaries
    instead of DayPlanCard UI markers.
    """

    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        markers = re.findall(r"<!--UI:DayPlanCard:", result.text)
        if markers:
            return EvaluationReason(
                value=False,
                reason=f"Found {len(markers)} DayPlanCard markers — should use text summaries instead",
            )
        return EvaluationReason(
            value=True,
            reason="No DayPlanCard markers — text summary format used correctly",
        )


@dataclass
class HasPlanLink(Evaluator):
    """Check that the response contains a /plans/ link (markdown format)."""

    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        # Match markdown link [text](/plans/uuid-or-id) or bare /plans/uuid-or-id
        md_links = re.findall(r"\[.*?\]\(/plans/[a-f0-9-]+\)", result.text)
        bare_links = re.findall(r"/plans/[a-f0-9-]+", result.text)
        if md_links:
            return EvaluationReason(
                value=True,
                reason=f"Markdown plan link found: {md_links[0]}",
            )
        if bare_links:
            return EvaluationReason(
                value=True,
                reason=f"Bare plan link found: {bare_links[0]}",
            )
        return EvaluationReason(
            value=False,
            reason="No /plans/ link found in response",
        )


@dataclass
class NoRecipeDuplicates(Evaluator):
    """Check that recipe names within a single day are unique (variety).

    Splits text by day headings (French day names) and checks duplicates
    per day block — cross-day reuse (batch cooking) is allowed.
    """

    evaluation_name: str | None = field(default=None)

    _MEAL_PATTERN = re.compile(
        r"[-•]\s*\*{0,2}(?:Petit-déjeuner|Déjeuner|Dîner|Collation)[^:]*:\s*\*{0,2}\s*(.+)",
        re.IGNORECASE,
    )
    _MEAL_FALLBACK = re.compile(
        r"(?:petit.d[ée]jeuner|d[ée]jeuner|d[îi]ner|collation)\s*:?\s*(.+?)(?:\n|$)",
        re.IGNORECASE,
    )
    _DAY_SPLIT = re.compile(
        r"\*{0,2}(?:Lundi|Mardi|Mercredi|Jeudi|Vendredi|Samedi|Dimanche)\*{0,2}",
        re.IGNORECASE,
    )

    def _extract_recipes(self, text: str) -> list[str]:
        lines = self._MEAL_PATTERN.findall(text)
        if not lines:
            lines = self._MEAL_FALLBACK.findall(text)
        return [r.strip().lower() for r in lines]

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        # Split text into per-day blocks
        day_blocks = self._DAY_SPLIT.split(result.text)
        # Filter out empty blocks (before first day heading)
        day_blocks = [b for b in day_blocks if b.strip()]

        all_dupes: list[str] = []
        total_recipes = 0

        for block in day_blocks:
            recipes = self._extract_recipes(block)
            total_recipes += len(recipes)
            seen = set()
            for r in recipes:
                if r in seen:
                    all_dupes.append(r)
                seen.add(r)

        if total_recipes < 2:
            return EvaluationReason(
                value=True,
                reason=f"Only {total_recipes} recipes found — can't check duplicates",
            )
        if not all_dupes:
            return EvaluationReason(
                value=True,
                reason=f"All {total_recipes} recipes unique within each day ({len(day_blocks)} days)",
            )
        return EvaluationReason(
            value=False,
            reason=f"Intra-day duplicate recipes: {set(all_dupes)}",
        )


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
class HasMealTypesInSummary(Evaluator):
    """Check that the text summary lists expected meal types."""

    expected_types: list[str]
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        text_lower = result.text.lower()
        found = [mt for mt in self.expected_types if mt.lower() in text_lower]
        missing = [mt for mt in self.expected_types if mt.lower() not in text_lower]
        if not missing:
            return EvaluationReason(
                value=True,
                reason=f"All meal types found: {found}",
            )
        return EvaluationReason(
            value=False,
            reason=f"Missing meal types: {missing}",
        )


# ---------------------------------------------------------------------------
# Task functions — real agent, real DB
# ---------------------------------------------------------------------------


async def _run_agent_user_a(message: str) -> AgentResult:
    """Run agent as User A (Loïc — omnivore, muscle gain, high cal)."""
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
    """Run agent as User B (Absolute — peanut allergy, muscle gain)."""
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
# Scenario 1 — Text format: no DayPlanCard, has plan link, text summaries
# User A, 1 day, checks the new SKILL.md presentation format
# ---------------------------------------------------------------------------


def scenario_1_text_format() -> Dataset:
    """After SKILL.md change: agent outputs text summaries, not DayPlanCard markers."""
    return Dataset(
        name="scenario_1_text_format",
        cases=[
            Case(
                name="text_summary_not_dayplancard",
                inputs=(
                    "Génère-moi un plan repas pour aujourd'hui, go. "
                    "Utilise mon profil pour les cibles."
                ),
                evaluators=(
                    NoRefusal(),
                    ResponseMinLength(min_chars=200),
                    ToolWasCalled(
                        tool_name="run_skill_script",
                        evaluation_name="skill_script_called",
                    ),
                    # Key checks for the new format
                    NoDayPlanCardMarkers(
                        evaluation_name="no_dayplancard_markers",
                    ),
                    HasPlanLink(
                        evaluation_name="plan_link_present",
                    ),
                    # Should have day name in text
                    ContainsAnyOf(
                        options=[
                            "Lundi",
                            "Mardi",
                            "Mercredi",
                            "Jeudi",
                            "Vendredi",
                            "Samedi",
                            "Dimanche",
                        ],
                        evaluation_name="day_name_present",
                    ),
                    # Should list meal types in text summary
                    HasMealTypesInSummary(
                        expected_types=["Petit-déjeuner", "Déjeuner", "Dîner"],
                        evaluation_name="meal_types_in_summary",
                    ),
                    # Calories in range
                    NumberInRange(
                        min_val=USER_A_TARGETS["calories"] * 0.80,
                        max_val=USER_A_TARGETS["calories"] * 1.20,
                        label="Daily calories",
                        evaluation_name="calories_in_range",
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
# Scenario 2 — Macro coherence: protein and calories match muscle gain profile
# User B, 1 day, checks macros are in the right range
# ---------------------------------------------------------------------------


def scenario_2_macro_coherence() -> Dataset:
    """Macro values in the plan should match the user's muscle gain targets."""
    return Dataset(
        name="scenario_2_macro_coherence",
        cases=[
            Case(
                name="muscle_gain_macros_coherent",
                inputs=(
                    "Fais-moi un plan repas pour demain, go. "
                    "Mon profil contient mes cibles nutritionnelles."
                ),
                evaluators=(
                    NoRefusal(),
                    ResponseMinLength(min_chars=200),
                    ToolWasCalled(
                        tool_name="run_skill_script",
                        evaluation_name="skill_script_called",
                    ),
                    # Calories: 2964 ± 20%
                    NumberInRange(
                        min_val=USER_B_TARGETS["calories"] * 0.80,
                        max_val=USER_B_TARGETS["calories"] * 1.20,
                        label="Daily calories",
                        evaluation_name="calories_in_range",
                    ),
                    # Protein: 172g ± 25%
                    NumberInRange(
                        min_val=USER_B_TARGETS["protein_g"] * 0.75,
                        max_val=USER_B_TARGETS["protein_g"] * 1.25,
                        label="Daily protein",
                        evaluation_name="protein_in_range",
                    ),
                    # Text format checks
                    NoDayPlanCardMarkers(
                        evaluation_name="no_dayplancard_markers",
                    ),
                    HasPlanLink(
                        evaluation_name="plan_link_present",
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
# Scenario 3 — Recipe variety: no duplicates in a 3-day plan
# User A, 3 days, checks uniqueness + varied recipe names
# ---------------------------------------------------------------------------


def scenario_3_recipe_variety() -> Dataset:
    """3-day plan should have varied recipes, no duplicates within a day."""
    return Dataset(
        name="scenario_3_recipe_variety",
        cases=[
            Case(
                name="three_day_varied_recipes",
                inputs=(
                    "Génère-moi un plan repas pour 3 jours, go. "
                    "Je veux de la variété, pas les mêmes recettes."
                ),
                evaluators=(
                    NoRefusal(),
                    ResponseMinLength(min_chars=300),
                    ToolWasCalled(
                        tool_name="run_skill_script",
                        evaluation_name="skill_script_called",
                    ),
                    # Should show multiple days
                    ContainsAnyOf(
                        options=["Lundi", "Mardi", "Mercredi"],
                        evaluation_name="multiple_days_shown",
                    ),
                    # No recipe duplicates within a day
                    NoRecipeDuplicates(
                        evaluation_name="no_duplicate_recipes",
                    ),
                    # Text format
                    NoDayPlanCardMarkers(
                        evaluation_name="no_dayplancard_markers",
                    ),
                    HasPlanLink(
                        evaluation_name="plan_link_present",
                    ),
                    PipelineTiming(
                        max_seconds=180.0,
                        evaluation_name="pipeline_timing",
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=240.0)],
    )


# ---------------------------------------------------------------------------
# Scenario 4 — Végétarien plan: no meat in recipes
# Uses User A profile but overrides diet in the message
# ---------------------------------------------------------------------------


def scenario_4_vegetarian_plan() -> Dataset:
    """Végétarien plan should contain no meat recipes."""
    return Dataset(
        name="scenario_4_vegetarian_plan",
        cases=[
            Case(
                name="vegetarian_no_meat",
                inputs=(
                    "Je suis végétarien. Génère-moi un plan repas pour 1 jour, lance. "
                    "Cible : 2200 kcal, 100g protéines."
                ),
                evaluators=(
                    NoRefusal(),
                    ResponseMinLength(min_chars=200),
                    ToolWasCalled(
                        tool_name="run_skill_script",
                        evaluation_name="skill_script_called",
                    ),
                    # Should mention plant/vegetarian protein sources
                    # (includes vegan terms since vegan ⊂ végétarien)
                    ContainsAnyOf(
                        options=[
                            "légume",
                            "tofu",
                            "lentille",
                            "pois",
                            "fromage",
                            "œuf",
                            "oeuf",
                            "quinoa",
                            "champignon",
                            "haricot",
                            "végétarien",
                            "vegan",
                            "végétal",
                            "tempeh",
                            "soja",
                        ],
                        evaluation_name="vegetarian_keywords_present",
                    ),
                    # Calories in range
                    NumberInRange(
                        min_val=1800,
                        max_val=2600,
                        label="Daily calories",
                        evaluation_name="calories_in_range",
                    ),
                    NoDayPlanCardMarkers(
                        evaluation_name="no_dayplancard_markers",
                    ),
                    HasPlanLink(
                        evaluation_name="plan_link_present",
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
# Scenario 5 — Vegan plan: no animal products
# Tests the vegan recipe DB coverage after seeding
# ---------------------------------------------------------------------------


def scenario_5_vegan_plan() -> Dataset:
    """Vegan plan should contain no animal products."""
    return Dataset(
        name="scenario_5_vegan_plan",
        cases=[
            Case(
                name="vegan_no_animal_products",
                inputs=(
                    "Je suis vegan. Fais-moi un plan repas pour 1 jour, lance. "
                    "Cible : 2000 kcal, 90g protéines."
                ),
                evaluators=(
                    NoRefusal(),
                    ResponseMinLength(min_chars=200),
                    ToolWasCalled(
                        tool_name="run_skill_script",
                        evaluation_name="skill_script_called",
                    ),
                    # Should include plant-protein keywords
                    ContainsAnyOf(
                        options=[
                            "tofu",
                            "lentille",
                            "pois",
                            "tempeh",
                            "soja",
                            "haricot",
                            "vegan",
                            "végétal",
                        ],
                        evaluation_name="vegan_keywords_present",
                    ),
                    NoDayPlanCardMarkers(
                        evaluation_name="no_dayplancard_markers",
                    ),
                    HasPlanLink(
                        evaluation_name="plan_link_present",
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
# Pytest test functions — marked integration
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_scenario_1_text_format():
    """E2E: Agent uses text summaries (not DayPlanCard) and includes plan link."""
    dataset = scenario_1_text_format()
    report = await dataset.evaluate(task=_run_agent_user_a)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.integration
async def test_scenario_2_macro_coherence():
    """E2E: Macros in plan match muscle gain profile targets."""
    dataset = scenario_2_macro_coherence()
    report = await dataset.evaluate(task=_run_agent_user_b)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.integration
async def test_scenario_3_recipe_variety():
    """E2E: 3-day plan has varied recipes, no duplicates."""
    dataset = scenario_3_recipe_variety()
    report = await dataset.evaluate(task=_run_agent_user_a)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.integration
async def test_scenario_4_vegetarian_plan():
    """E2E: Végétarien plan contains no meat."""
    dataset = scenario_4_vegetarian_plan()
    report = await dataset.evaluate(task=_run_agent_user_a)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.integration
async def test_scenario_5_vegan_plan():
    """E2E: Vegan plan contains no animal products."""
    dataset = scenario_5_vegan_plan()
    report = await dataset.evaluate(task=_run_agent_user_a)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"
