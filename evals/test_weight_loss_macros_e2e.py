"""E2E eval — weight_loss macros (fat 25%, high protein) with real LLM.

WHY THIS IS AN EVAL, NOT A TEST
================================
These scenarios involve a real LLM (Haiku 4.5) making decisions:
  - Does the agent calculate correct macros for weight_loss?
  - Does the agent produce a meal plan with appropriate deficit?

All existing evals test muscle_gain (Marc 24M). This eval covers weight_loss,
verifying fat at 25% and elevated protein (2.3-3.1 g/kg) per calculations.py.

Outcomes are non-deterministic -> scored criteria, not exact assertions.
Run on demand before releases, NOT in CI (slow, costs API credits).

    pytest evals/test_weight_loss_macros_e2e.py -m integration -v -s

TEST PERSONA — Sophie (all required fields)
=============================================
Name:            Sophie
Age:             30
Gender:          female
Height:          165 cm
Weight:          62 kg
Activity level:  moderate (x1.55)
Goal:            weight_loss

Pre-calculated expected values (Mifflin-St Jeor):
  BMR    = (10x62) + (6.25x165) - (5x30) - 161 = 1290 kcal
  TDEE   = 1290 x 1.55                          = 2000 kcal
  Target = TDEE - 400 deficit                   ~= 1600 kcal (>= 1200 floor)

  Fat @ 25% of target: 1600 x 0.25 / 9         ~= 44g (range: 35-55g)
  Protein: 2.3-3.1 g/kg x 62                    = 143-192g (range: 130-200g)
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


# --- Test persona (single source of truth) ---
TEST_USER_PROFILE = {
    "age": 30,
    "gender": "female",
    "height_cm": 165,
    "weight_kg": 62.0,
    "activity_level": "moderate",
    "goals": "weight_loss",
    "diet_type": "omnivore",
    "allergies": [],
    "disliked_foods": [],
    "preferred_cuisines": ["française", "méditerranéenne"],
    "max_prep_time": 30,
}

# --- Pre-calculated expected values ---
EXPECTED_BMR = 1290
EXPECTED_TDEE = 2000
EXPECTED_TARGET = 1600  # TDEE - 400
EXPECTED_FAT_MIN = 35   # tolerant lower bound
EXPECTED_FAT_MAX = 55   # tolerant upper bound
EXPECTED_PROTEIN_MIN = 130  # tolerant lower bound
EXPECTED_PROTEIN_MAX = 200  # tolerant upper bound


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
                reason=f"{self.label or 'Number'} found in range: {in_range[0]} in [{self.min_val}, {self.max_val}]",
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
                value=True, reason=f"{length} chars >= {self.min_chars}"
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
class SkillScriptRouting(Evaluator):
    """Check the agent routed to the expected skill and script."""

    skill_name: str
    script_name: str | None = None
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        if not isinstance(ctx.output, AgentResult):
            return EvaluationReason(value=False, reason="Output is not AgentResult")
        for tc in ctx.output.tool_calls:
            if tc["name"] == "run_skill_script":
                args = tc["args"]
                skill = args.get("skill_name", "")
                script = args.get("script_name", "")
                if self.skill_name in skill:
                    if self.script_name is None or self.script_name in script:
                        return EvaluationReason(
                            value=True,
                            reason=f"Routed to {skill}/{script}",
                        )
        called = [
            f"{tc['args'].get('skill_name', '?')}/{tc['args'].get('script_name', '?')}"
            for tc in ctx.output.tool_calls
            if tc["name"] == "run_skill_script"
        ]
        return EvaluationReason(
            value=False,
            reason=f"Expected {self.skill_name}/{self.script_name}, got: {called}",
        )


# --- Task function ---
async def _run_agent(message: str) -> AgentResult:
    """Run the agent with real Haiku 4.5 and return text + tool calls."""
    deps = create_agent_deps()
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
# Scenario 1 — Weight loss macro calculation
# Expected: calories ~1400-1800, fat ~35-55g (25%), protein ~130-200g
# ---------------------------------------------------------------------------


def scenario_1_weight_loss_calculation() -> Dataset:
    """Agent calculates correct macros for weight_loss goal."""
    msg = (
        "J'ai 30 ans, femme, 165cm, 62kg, activite moderee, "
        "objectif perte de poids. Omnivore, pas d'allergies, "
        "pas d'aliments detestes, cuisine francaise, 30 min max. "
        "Calcule mes besoins nutritionnels avec les macros detailles "
        "(proteines, glucides, lipides en grammes). "
        "Ne pose pas de questions, calcule directement."
    )
    return Dataset(
        name="scenario_1_weight_loss_calc",
        cases=[
            Case(
                name="weight_loss_macros",
                inputs=msg,
                evaluators=(
                    NoRefusal(),
                    ResponseMinLength(min_chars=200),
                    SkillScriptRouting(
                        skill_name="nutrition-calculating",
                        script_name="calculate_nutritional_needs",
                        evaluation_name="routes_to_nutrition_skill",
                    ),
                    NumberInRange(
                        min_val=1400,
                        max_val=1800,
                        label="Calories (kcal)",
                        evaluation_name="calories_in_deficit_range",
                    ),
                    NumberInRange(
                        min_val=EXPECTED_FAT_MIN,
                        max_val=EXPECTED_FAT_MAX,
                        label="Fat (g)",
                        evaluation_name="fat_at_25pct",
                    ),
                    NumberInRange(
                        min_val=EXPECTED_PROTEIN_MIN,
                        max_val=EXPECTED_PROTEIN_MAX,
                        label="Protein (g)",
                        evaluation_name="protein_elevated",
                    ),
                    ContainsAnyOf(
                        options=["perte", "deficit", "poids", "weight loss"],
                        evaluation_name="mentions_weight_loss",
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=90.0)],
    )


# ---------------------------------------------------------------------------
# Scenario 2 — Meal plan with weight loss deficit
# Expected: agent generates a plan (no refusal), routes to meal-planning
# ---------------------------------------------------------------------------


def scenario_2_weight_loss_meal_plan() -> Dataset:
    """Agent generates a day meal plan for weight_loss with deficit."""
    msg = (
        "Je suis une femme de 30 ans, 165cm, 62kg, activite moderee, "
        "objectif perte de poids. "
        "Genere un plan repas pour une journee avec un deficit calorique "
        "adapte a la perte de poids."
    )
    return Dataset(
        name="scenario_2_weight_loss_plan",
        cases=[
            Case(
                name="weight_loss_day_plan",
                inputs=msg,
                evaluators=(
                    NoRefusal(),
                    ResponseMinLength(min_chars=300),
                    ToolWasCalled(
                        tool_name="run_skill_script",
                        evaluation_name="skill_script_called",
                    ),
                    ContainsAnyOf(
                        options=["repas", "dejeuner", "diner", "petit-dejeuner", "déjeuner", "dîner"],
                        evaluation_name="has_meal_types",
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
async def test_scenario_1_weight_loss_calculation():
    """E2E: Agent calculates correct weight_loss macros (real Haiku 4.5)."""
    dataset = scenario_1_weight_loss_calculation()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.integration
async def test_scenario_2_weight_loss_meal_plan():
    """E2E: Agent generates weight_loss meal plan with deficit (real Haiku 4.5)."""
    dataset = scenario_2_weight_loss_meal_plan()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"
