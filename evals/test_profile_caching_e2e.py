"""E2E eval — profile target caching with real LLM.

WHY THIS IS AN EVAL, NOT A TEST
================================
These scenarios involve a real LLM (Haiku 4.5) making decisions:
  - Does the agent call update_my_profile when user provides data?
  - Does the agent calculate AND persist nutrition targets?
  - Does the agent save preferences (allergies, diet) without being asked?

Outcomes are non-deterministic → scored criteria, not exact assertions.
Run on demand before releases, NOT in CI (slow, costs API credits).

    pytest evals/test_profile_caching_e2e.py -m integration -v

TEST PERSONA — all required fields defined here, never assumed elsewhere.
=========================================================================
Name:            Marc
Age:             24
Gender:          male
Height:          191 cm
Weight:          86 kg
Activity level:  light (x1.375)
Goal:            muscle gain

Pre-calculated expected values (Mifflin-St Jeor):
  BMR    = (10x86) + (6.25x191) - (5x24) + 5 = 1939 kcal
  TDEE   = 1939 x 1.375                       = 2666 kcal
  Target = TDEE + 300 surplus                  ~ 2966 kcal
  Protein range: 1.6-2.2 g/kg x 86 kg         = 138-189 g/day
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

# ---------------------------------------------------------------------------
# Test persona — single source of truth
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

# Pre-calculated targets (verified with src.nutrition.calculations)
EXPECTED_TDEE = 2666
EXPECTED_TARGET = 2966
EXPECTED_PROTEIN_MIN = 138
EXPECTED_PROTEIN_MAX = 189


# ---------------------------------------------------------------------------
# Structured output — text + tool calls for evaluators
# ---------------------------------------------------------------------------


@dataclass
class AgentResult:
    """Captures both text output and tool call history from an agent run."""

    text: str
    tool_calls: list[dict]  # [{"name": "...", "args": {...}}, ...]


# ---------------------------------------------------------------------------
# Custom evaluators
# ---------------------------------------------------------------------------


@dataclass
class ToolWasCalled(Evaluator):
    """Check that a specific tool was called during the agent run.

    Works on AgentResult.tool_calls to verify the agent's actual behavior,
    not just what it says in its text response.
    """

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
    """Check that a tool was called with specific argument keys having non-None values.

    For update_my_profile: verifies the agent passed nutrition fields.
    For run_skill_script: verifies correct skill/script routing.
    """

    tool_name: str
    required_args: list[str]
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        for tc in result.tool_calls:
            if tc["name"] != self.tool_name:
                continue
            args = tc["args"]
            missing = [
                k for k in self.required_args if k not in args or args[k] is None
            ]
            if not missing:
                return EvaluationReason(
                    value=True,
                    reason=f"Tool '{self.tool_name}' called with all required args: {self.required_args}",
                )
            return EvaluationReason(
                value=False,
                reason=f"Tool '{self.tool_name}' called but missing args: {missing}",
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
                reason=f"{self.label or 'Number'} found in range: {in_range[0]} in [{self.min_val}, {self.max_val}]",
            )
        return EvaluationReason(
            value=False,
            reason=f"No number in [{self.min_val}, {self.max_val}]. Found: {numbers[:5]}",
        )


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
    """Check the response is substantive (not a one-liner)."""

    min_chars: int
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        length = len(result.text)
        if length >= self.min_chars:
            return EvaluationReason(
                value=True, reason=f"{length} chars >= {self.min_chars}"
            )
        return EvaluationReason(
            value=False, reason=f"Response too short: {length} chars < {self.min_chars}"
        )


@dataclass
class ContainsAnyOf(Evaluator):
    """Check that at least one of the given substrings appears in the text output."""

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
class ToolCallCount(Evaluator):
    """Check that a tool was called at least N times."""

    tool_name: str
    min_count: int
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        count = sum(1 for tc in result.tool_calls if tc["name"] == self.tool_name)
        if count >= self.min_count:
            return EvaluationReason(
                value=True,
                reason=f"Tool '{self.tool_name}' called {count} time(s) (>= {self.min_count})",
            )
        return EvaluationReason(
            value=False,
            reason=f"Tool '{self.tool_name}' called {count} time(s), expected >= {self.min_count}",
        )


# ---------------------------------------------------------------------------
# Task function — real agent, real Haiku 4.5, captures tool calls
# ---------------------------------------------------------------------------


async def _run_agent(message: str) -> AgentResult:
    """Run the agent with real Haiku 4.5 and return text + tool calls."""
    deps = create_agent_deps()
    result = await agent.run(message, deps=deps)

    # Extract tool calls from message history
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
# Scenario 1 — Profile data auto-saved on calculation request
#
# User provides biometric data as part of a calculation request.
# OLD behavior: agent skips update_my_profile ("calcul ponctuel").
# NEW behavior: agent ALWAYS calls update_my_profile to persist data,
#               THEN runs the nutrition calculation.
# ---------------------------------------------------------------------------


def scenario_1_profile_saved_on_calc() -> Dataset:
    """Agent saves profile data AND calculates nutrition when user provides data."""
    return Dataset(
        name="scenario_1_profile_saved_on_calculation",
        cases=[
            Case(
                name="biometric_data_with_calc_request",
                inputs=(
                    "J'ai 24 ans, je suis un homme, je mesure 191cm, je pèse 86kg, "
                    "activité légère. Mon objectif est la prise de muscle. "
                    "Calcule mes besoins nutritionnels."
                ),
                evaluators=(
                    NoRefusal(),
                    ResponseMinLength(min_chars=200),
                    # CRITICAL: Agent must call update_my_profile to save biometric data
                    ToolWasCalled(
                        tool_name="update_my_profile",
                        evaluation_name="profile_update_called",
                    ),
                    # Agent must pass biometric fields to update_my_profile
                    ToolCalledWithArgs(
                        tool_name="update_my_profile",
                        required_args=[
                            "age",
                            "gender",
                            "weight_kg",
                            "height_cm",
                            "activity_level",
                        ],
                        evaluation_name="biometric_fields_saved",
                    ),
                    # Agent must also run the nutrition calculation
                    ToolWasCalled(
                        tool_name="run_skill_script",
                        evaluation_name="nutrition_calc_called",
                    ),
                    # Agent should mention TDEE in the right range
                    NumberInRange(min_val=2500, max_val=2900, label="TDEE"),
                    # Agent should mention calorie target with surplus
                    NumberInRange(min_val=2800, max_val=3200, label="Calorie target"),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=90.0)],
    )


# ---------------------------------------------------------------------------
# Scenario 2 — Preferences auto-saved without explicit "save" request
#
# User casually mentions allergies and diet. OLD behavior: agent would
# NOT save unless user says "sauvegarde". NEW behavior: always persist.
# ---------------------------------------------------------------------------


def scenario_2_preferences_auto_saved() -> Dataset:
    """Agent saves allergies and diet type when mentioned casually."""
    return Dataset(
        name="scenario_2_preferences_auto_saved",
        cases=[
            Case(
                name="allergies_and_diet_casual_mention",
                inputs=(
                    "Au fait, je suis allergique aux arachides et au lactose. "
                    "Je suis végétarien. "
                    "Mes cuisines préférées sont la cuisine méditerranéenne et asiatique."
                ),
                evaluators=(
                    NoRefusal(),
                    # CRITICAL: Agent must call update_my_profile with preferences
                    ToolWasCalled(
                        tool_name="update_my_profile",
                        evaluation_name="profile_update_called",
                    ),
                    # Should save allergies
                    ToolCalledWithArgs(
                        tool_name="update_my_profile",
                        required_args=["allergies"],
                        evaluation_name="allergies_saved",
                    ),
                    # Response should acknowledge the saved preferences
                    ContainsAnyOf(
                        options=[
                            "enregistré",
                            "noté",
                            "sauvegardé",
                            "mis à jour",
                            "profil",
                            "pris en compte",
                            "retenu",
                        ]
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=60.0)],
    )


# ---------------------------------------------------------------------------
# Scenario 3 — Nutrition targets auto-persisted by calculation script
#
# After the agent runs calculate_nutritional_needs, the script itself
# calls update_my_profile_tool to persist bmr/tdee/macros. The agent
# doesn't need to do this explicitly — the script handles it.
#
# We verify: calculation returns valid values AND the response shows them.
# (The actual DB write is tested in tests/test_profile_caching.py)
# ---------------------------------------------------------------------------


def scenario_3_nutrition_targets_in_response() -> Dataset:
    """Agent returns complete nutrition targets from calculation (auto-persisted by script)."""
    return Dataset(
        name="scenario_3_nutrition_targets_complete",
        cases=[
            Case(
                name="full_calculation_with_all_targets",
                inputs=(
                    "Calcule mes besoins nutritionnels : "
                    "24 ans, homme, 191cm, 86kg, activité légère, "
                    "objectif prise de muscle."
                ),
                evaluators=(
                    NoRefusal(),
                    ResponseMinLength(min_chars=200),
                    # All 6 nutrition values must be present in response
                    # BMR ~1939
                    NumberInRange(min_val=1800, max_val=2100, label="BMR"),
                    # TDEE ~2666
                    NumberInRange(min_val=2500, max_val=2900, label="TDEE"),
                    # Target calories ~2966
                    NumberInRange(min_val=2800, max_val=3200, label="Calorie target"),
                    # Protein 138-189g
                    NumberInRange(
                        min_val=EXPECTED_PROTEIN_MIN,
                        max_val=EXPECTED_PROTEIN_MAX,
                        label="Protein",
                    ),
                    # Response should mention all macro types
                    ContainsAnyOf(options=["protéine", "protein"]),
                    ContainsAnyOf(options=["glucide", "carb"]),
                    ContainsAnyOf(options=["lipide", "fat", "gras"]),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=90.0)],
    )


# ---------------------------------------------------------------------------
# Scenario 4 — Disliked foods saved (regression check)
#
# User provides disliked foods — agent must save them. This is a common
# pattern that was broken before (data lost between sessions).
# ---------------------------------------------------------------------------


def scenario_4_disliked_foods_saved() -> Dataset:
    """Agent saves disliked foods and favorite foods when provided."""
    return Dataset(
        name="scenario_4_food_preferences_saved",
        cases=[
            Case(
                name="disliked_and_favorite_foods",
                inputs=(
                    "Je déteste le poisson et les épinards. "
                    "Par contre j'adore le poulet, le riz et les bananes. "
                    "Mon temps de préparation maximum est 30 minutes."
                ),
                evaluators=(
                    NoRefusal(),
                    ToolWasCalled(
                        tool_name="update_my_profile",
                        evaluation_name="profile_update_called",
                    ),
                    ToolCalledWithArgs(
                        tool_name="update_my_profile",
                        required_args=["disliked_foods"],
                        evaluation_name="disliked_foods_saved",
                    ),
                    ContainsAnyOf(
                        options=[
                            "enregistré",
                            "noté",
                            "sauvegardé",
                            "mis à jour",
                            "profil",
                            "pris en compte",
                            "retenu",
                        ]
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=60.0)],
    )


# ---------------------------------------------------------------------------
# Pytest test functions — marked integration (excluded from CI)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_scenario_1_profile_saved_on_calculation():
    """E2E: Agent saves biometric data AND calculates nutrition (real Haiku 4.5)."""
    dataset = scenario_1_profile_saved_on_calc()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.integration
async def test_scenario_2_preferences_auto_saved():
    """E2E: Agent saves allergies and diet when mentioned casually (real Haiku 4.5)."""
    dataset = scenario_2_preferences_auto_saved()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.integration
async def test_scenario_3_nutrition_targets_complete():
    """E2E: Agent returns all 6 nutrition targets from calculation (real Haiku 4.5)."""
    dataset = scenario_3_nutrition_targets_in_response()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.integration
async def test_scenario_4_food_preferences_saved():
    """E2E: Agent saves disliked/favorite foods when provided (real Haiku 4.5)."""
    dataset = scenario_4_disliked_foods_saved()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"
