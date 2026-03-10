"""E2E eval — MILP per-ingredient optimizer (v2f) regression check.

WHY THIS IS AN EVAL, NOT A TEST
================================
These scenarios involve a real LLM (Haiku 4.5) making decisions:
  - Route to meal-planning skill with correct parameters
  - Generate a day plan that goes through the MILP optimizer
  - Produce macros coherent with targets (calories, protein, fat, carbs)
  - Present results as text summaries with plan link

The v2f change replaces the LP v1 (1 scale factor per recipe) with a MILP
(1 variable per ingredient). This eval checks that:
  1. Plans still generate successfully (no MILP crashes/infeasibility)
  2. Macro precision is maintained or improved
  3. The pipeline completes within time limits

Two user profiles tested (real Supabase users):

USER A — Loïc (6870a598) — Muscle gain, HIGH cal
  Targets: 3334 kcal, 176g protein, 448g carbs, 93g fat
  Diet: omnivore, no allergies, dislikes fromage/huître/fruits de mer

USER B — Absolute (5745fc58) — Muscle gain, MODERATE cal
  Targets: 2964 kcal, 172g protein, 384g carbs, 82g fat
  Diet: omnivore, allergies=[arachides, cacahuètes], dislikes fromage

    pytest evals/test_milp_optimizer_e2e.py -m integration -v -s
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
class NumberInRange(Evaluator):
    min_val: float
    max_val: float
    label: str = ""
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        clean = re.sub(r"[*_`#|]", "", result.text)
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
class SmallNumberInRange(Evaluator):
    """Like NumberInRange but matches 2-5 digit numbers (for fat/small values)."""

    min_val: float
    max_val: float
    label: str = ""
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        clean = re.sub(r"[*_`#|]", "", result.text)
        clean = re.sub(r"(\d)\s+(\d)", r"\1\2", clean)
        numbers = [
            float(n.replace(",", "."))
            for n in re.findall(r"\b\d{2,5}(?:[.,]\d+)?\b", clean)
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
class ContainsAnyOf(Evaluator):
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
class ToolWasCalled(Evaluator):
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
            reason=f"Tool '{self.tool_name}' NOT called. Called: {called}",
        )


@dataclass
class HasPlanLink(Evaluator):
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        md_links = re.findall(r"\[.*?\]\(/plans/[a-f0-9-]+\)", result.text)
        bare_links = re.findall(r"/plans/[a-f0-9-]+", result.text)
        if md_links:
            return EvaluationReason(
                value=True, reason=f"Markdown plan link found: {md_links[0]}"
            )
        if bare_links:
            return EvaluationReason(
                value=True, reason=f"Bare plan link found: {bare_links[0]}"
            )
        return EvaluationReason(value=False, reason="No /plans/ link found in response")


@dataclass
class PipelineTiming(Evaluator):
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
    expected_types: list[str]
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        text_lower = result.text.lower()
        found = [mt for mt in self.expected_types if mt.lower() in text_lower]
        missing = [mt for mt in self.expected_types if mt.lower() not in text_lower]
        if not missing:
            return EvaluationReason(value=True, reason=f"All meal types found: {found}")
        return EvaluationReason(value=False, reason=f"Missing meal types: {missing}")


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
# Scenario 1 — Basic plan generation with MILP optimizer
# User A, 1 day — checks that the pipeline completes, macros in range,
# plan link present, no crashes from the new optimizer.
# ---------------------------------------------------------------------------


def scenario_1_milp_basic_plan() -> Dataset:
    """MILP optimizer produces a valid 1-day plan with macros in target range."""
    return Dataset(
        name="scenario_1_milp_basic_plan",
        cases=[
            Case(
                name="one_day_milp_plan_user_a",
                inputs=(
                    "Génère-moi un plan repas pour aujourd'hui, go. "
                    "Utilise mon profil pour les cibles."
                ),
                evaluators=(
                    NoRefusal(evaluation_name="no_refusal"),
                    ResponseMinLength(min_chars=200, evaluation_name="response_length"),
                    ToolWasCalled(
                        tool_name="run_skill_script",
                        evaluation_name="skill_script_called",
                    ),
                    HasPlanLink(evaluation_name="plan_link_present"),
                    # Calories: 3334 ± 20%
                    NumberInRange(
                        min_val=USER_A_TARGETS["calories"] * 0.80,
                        max_val=USER_A_TARGETS["calories"] * 1.20,
                        label="Daily calories",
                        evaluation_name="calories_in_range",
                    ),
                    # Protein: 176g ± 25%
                    NumberInRange(
                        min_val=USER_A_TARGETS["protein_g"] * 0.75,
                        max_val=USER_A_TARGETS["protein_g"] * 1.25,
                        label="Daily protein",
                        evaluation_name="protein_in_range",
                    ),
                    # Meal types present
                    HasMealTypesInSummary(
                        expected_types=["Petit-déjeuner", "Déjeuner", "Dîner"],
                        evaluation_name="meal_types_present",
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
# Scenario 2 — Macro precision with allergen user
# User B (peanut allergy), 1 day — MILP should produce macros in range
# despite tighter recipe pool (allergen-filtered).
# ---------------------------------------------------------------------------


def scenario_2_milp_allergen_user() -> Dataset:
    """MILP handles allergen-restricted user with good macro precision."""
    return Dataset(
        name="scenario_2_milp_allergen_user",
        cases=[
            Case(
                name="one_day_milp_plan_user_b",
                inputs=(
                    "Fais-moi un plan repas pour demain, go. "
                    "Mon profil contient mes cibles nutritionnelles."
                ),
                evaluators=(
                    NoRefusal(evaluation_name="no_refusal"),
                    ResponseMinLength(min_chars=200, evaluation_name="response_length"),
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
                    HasPlanLink(evaluation_name="plan_link_present"),
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
# Scenario 3 — Low-fat target plan
# User A overrides fat target to low value — MILP should reduce fat
# sources (oils, cheese) while maintaining protein.
# This is the KEY behavior change from v2f: per-ingredient scaling
# can reduce oil independently from chicken, unlike v1's uniform scaling.
# ---------------------------------------------------------------------------


def scenario_3_milp_low_fat() -> Dataset:
    """MILP reduces fat effectively when user requests low-fat plan."""
    return Dataset(
        name="scenario_3_milp_low_fat",
        cases=[
            Case(
                name="low_fat_plan_fat_reduced",
                inputs=(
                    "Génère-moi un plan repas pour 1 jour avec des macros spécifiques : "
                    "2500 kcal, 160g protéines, 50g lipides, 350g glucides. "
                    "Je veux un plan faible en gras. Go."
                ),
                evaluators=(
                    NoRefusal(evaluation_name="no_refusal"),
                    ResponseMinLength(min_chars=200, evaluation_name="response_length"),
                    ToolWasCalled(
                        tool_name="run_skill_script",
                        evaluation_name="skill_script_called",
                    ),
                    # Calories in range (2500 ± 20%)
                    NumberInRange(
                        min_val=2000,
                        max_val=3000,
                        label="Daily calories",
                        evaluation_name="calories_in_range",
                    ),
                    # Protein should still be high (160g ± 25%)
                    NumberInRange(
                        min_val=120,
                        max_val=200,
                        label="Daily protein",
                        evaluation_name="protein_maintained",
                    ),
                    # Fat should be low — reported in text
                    # 50g target ± 40% (tolerant range since MILP may not hit exactly)
                    # Use SmallNumberInRange since fat <100 → only 2 digits
                    SmallNumberInRange(
                        min_val=30,
                        max_val=90,
                        label="Daily fat",
                        evaluation_name="fat_reduced",
                    ),
                    HasPlanLink(evaluation_name="plan_link_present"),
                    # Should mention recipe/meal keywords
                    ContainsAnyOf(
                        options=[
                            "petit-déjeuner",
                            "déjeuner",
                            "dîner",
                            "repas",
                            "recette",
                        ],
                        evaluation_name="meal_keywords_present",
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
async def test_scenario_1_milp_basic_plan():
    """E2E: MILP optimizer produces valid 1-day plan for User A (real Haiku 4.5)."""
    dataset = scenario_1_milp_basic_plan()
    report = await dataset.evaluate(task=_run_agent_user_a)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.integration
async def test_scenario_2_milp_allergen_user():
    """E2E: MILP optimizer handles allergen-restricted user (real Haiku 4.5)."""
    dataset = scenario_2_milp_allergen_user()
    report = await dataset.evaluate(task=_run_agent_user_b)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.integration
async def test_scenario_3_milp_low_fat():
    """E2E: MILP reduces fat while maintaining protein for low-fat request (real Haiku 4.5)."""
    dataset = scenario_3_milp_low_fat()
    report = await dataset.evaluate(task=_run_agent_user_a)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"
