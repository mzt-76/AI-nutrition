"""E2E eval — weekly coaching baseline vs check-in distinction with real LLM.

WHY THIS IS AN EVAL, NOT A TEST
================================
These scenarios involve a real LLM (Haiku 4.5) making decisions:
  - Does the agent call set_baseline (not calculate_weekly_adjustments) for a new user?
  - Does the agent extract weight_kg from natural language for baseline?
  - Does the agent extract optional body composition params for baseline?
  - Does the agent route to calculate_weekly_adjustments for a real weekly check-in?

Outcomes are non-deterministic → scored criteria, not exact assertions.
Run on demand before releases, NOT in CI (slow, costs API credits).

    pytest evals/test_baseline_coaching_e2e.py -m integration -v -s

TEST PERSONA — all required fields defined here, never assumed elsewhere.
=========================================================================
Name:            Marc
Age:             24
Gender:          male
Height:          191 cm
Weight:          86 kg
Activity level:  light (×1.375)
Goal:            muscle gain

Baseline scenario: Marc starts coaching, provides his initial weight (86 kg)
  and optional body comp (22% body fat, 68.5 kg muscle mass).
  → Agent should call set_baseline with weight_kg=86.0

Check-in scenario: Marc reports his week (86.0→86.3 kg, 90% adherence).
  → Agent should call calculate_weekly_adjustments, NOT set_baseline.
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


# ---------------------------------------------------------------------------
# Structured output — text + tool calls
# ---------------------------------------------------------------------------


@dataclass
class AgentResult:
    """Captures both text output and tool call history from an agent run."""

    text: str
    tool_calls: list[dict]  # [{"name": "...", "args": {...}}, ...]


# ---------------------------------------------------------------------------
# Evaluators (reuse patterns from test_profile_caching_e2e.py)
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
                value=True, reason=f"{length} chars >= {self.min_chars}"
            )
        return EvaluationReason(
            value=False,
            reason=f"Response too short: {length} chars < {self.min_chars}",
        )


@dataclass
class ContainsAnyOf(Evaluator):
    """Check that at least one substring appears in the text output."""

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
    """Check that a tool was called with specific argument keys having non-None values."""

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
class SkillScriptRouting(Evaluator):
    """Check that run_skill_script was called with a specific skill+script combination.

    Verifies the agent routed to the correct skill script by inspecting
    the skill_name and script_name arguments of run_skill_script calls.
    """

    expected_skill: str
    expected_script: str
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        for tc in result.tool_calls:
            if tc["name"] != "run_skill_script":
                continue
            args = tc["args"]
            skill = args.get("skill_name", "")
            script = args.get("script_name", "")
            if skill == self.expected_skill and script == self.expected_script:
                return EvaluationReason(
                    value=True,
                    reason=f"Correct routing: {skill}/{script}",
                )
        # Check if wrong script was called
        scripts_called = [
            f"{tc['args'].get('skill_name')}/{tc['args'].get('script_name')}"
            for tc in result.tool_calls
            if tc["name"] == "run_skill_script"
        ]
        return EvaluationReason(
            value=False,
            reason=f"Expected {self.expected_skill}/{self.expected_script}. "
            f"Called: {scripts_called or 'no run_skill_script calls'}",
        )


@dataclass
class ToolNotCalled(Evaluator):
    """Check that a specific skill script was NOT called (negative routing check).

    Used to verify the agent doesn't mistakenly call the wrong script.
    """

    expected_skill: str
    expected_script: str
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        result: AgentResult = ctx.output
        for tc in result.tool_calls:
            if tc["name"] != "run_skill_script":
                continue
            args = tc["args"]
            skill = args.get("skill_name", "")
            script = args.get("script_name", "")
            if skill == self.expected_skill and script == self.expected_script:
                return EvaluationReason(
                    value=False,
                    reason=f"Unwanted script called: {skill}/{script}",
                )
        return EvaluationReason(
            value=True,
            reason=f"Script {self.expected_skill}/{self.expected_script} was NOT called (correct)",
        )


# ---------------------------------------------------------------------------
# Task function — real agent, real Haiku 4.5, captures tool calls
# ---------------------------------------------------------------------------


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
# Scenario 1 — New user baseline recording
#
# User starts coaching and provides their initial weight.
# Agent should call set_baseline (NOT calculate_weekly_adjustments).
# ---------------------------------------------------------------------------


def scenario_1_baseline_weight_only() -> Dataset:
    """Agent records initial baseline with weight when user starts coaching."""
    return Dataset(
        name="scenario_1_baseline_weight_only",
        cases=[
            Case(
                name="new_user_starts_coaching",
                inputs=(
                    "Je commence mon suivi nutritionnel aujourd'hui. "
                    "Mon poids actuel est de 86 kg. "
                    "Enregistre mon poids de départ comme baseline."
                ),
                evaluators=(
                    NoRefusal(),
                    ResponseMinLength(min_chars=50),
                    # CRITICAL: Agent must route to set_baseline
                    SkillScriptRouting(
                        expected_skill="weekly-coaching",
                        expected_script="set_baseline",
                        evaluation_name="baseline_script_called",
                    ),
                    # Agent must NOT call calculate_weekly_adjustments
                    ToolNotCalled(
                        expected_skill="weekly-coaching",
                        expected_script="calculate_weekly_adjustments",
                        evaluation_name="adjustments_not_called",
                    ),
                    # Response should confirm baseline recorded
                    ContainsAnyOf(
                        options=[
                            "baseline",
                            "enregistré",
                            "départ",
                            "initial",
                            "noté",
                            "point de départ",
                        ],
                        evaluation_name="baseline_confirmed",
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=90.0)],
    )


# ---------------------------------------------------------------------------
# Scenario 2 — Baseline with body composition
#
# User provides weight + body fat + muscle mass. Agent should extract
# all optional params and pass them to set_baseline.
# ---------------------------------------------------------------------------


def scenario_2_baseline_with_body_comp() -> Dataset:
    """Agent records baseline with body composition data."""
    return Dataset(
        name="scenario_2_baseline_with_body_composition",
        cases=[
            Case(
                name="weight_and_body_comp",
                inputs=(
                    "C'est mon premier check-in. Voici mes mesures de départ : "
                    "poids 86 kg, taux de graisse corporelle 22%, "
                    "masse musculaire 68.5 kg, tour de taille 88 cm. "
                    "Mesures prises avec ma balance connectée."
                ),
                evaluators=(
                    NoRefusal(),
                    ResponseMinLength(min_chars=50),
                    # Must call set_baseline
                    SkillScriptRouting(
                        expected_skill="weekly-coaching",
                        expected_script="set_baseline",
                        evaluation_name="baseline_script_called",
                    ),
                    # Should pass weight_kg parameter
                    ToolCalledWithArgs(
                        tool_name="run_skill_script",
                        required_args=["parameters"],
                        evaluation_name="parameters_passed",
                    ),
                    # Response should acknowledge body composition
                    ContainsAnyOf(
                        options=[
                            "graisse",
                            "body fat",
                            "composition",
                            "masse musculaire",
                            "muscle",
                            "taille",
                        ],
                        evaluation_name="body_comp_acknowledged",
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=90.0)],
    )


# ---------------------------------------------------------------------------
# Scenario 3 — Regular weekly check-in (NOT baseline)
#
# User reports their weekly feedback with weight_start, weight_end,
# adherence. Agent should call calculate_weekly_adjustments, NOT set_baseline.
# ---------------------------------------------------------------------------


def scenario_3_regular_checkin() -> Dataset:
    """Agent routes to calculate_weekly_adjustments for a real weekly check-in."""
    return Dataset(
        name="scenario_3_regular_weekly_checkin",
        cases=[
            Case(
                name="weekly_feedback_with_adherence",
                inputs=(
                    "Bilan de ma semaine : j'ai commencé à 86.0 kg et fini à 86.3 kg. "
                    "J'ai suivi le plan à 90%, énergie bonne, pas trop de faim. "
                    "Qu'est-ce que tu recommandes ?"
                ),
                evaluators=(
                    NoRefusal(),
                    ResponseMinLength(min_chars=100),
                    # Must call calculate_weekly_adjustments (NOT set_baseline)
                    SkillScriptRouting(
                        expected_skill="weekly-coaching",
                        expected_script="calculate_weekly_adjustments",
                        evaluation_name="adjustments_script_called",
                    ),
                    # Must NOT call set_baseline
                    ToolNotCalled(
                        expected_skill="weekly-coaching",
                        expected_script="set_baseline",
                        evaluation_name="baseline_not_called",
                    ),
                    # Response should contain coaching feedback
                    ContainsAnyOf(
                        options=[
                            "ajustement",
                            "recommand",
                            "semaine",
                            "poids",
                            "progression",
                            "continue",
                        ],
                        evaluation_name="coaching_feedback_given",
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
async def test_scenario_1_baseline_weight_only():
    """E2E: Agent records baseline with weight_kg for new user (real Haiku 4.5)."""
    dataset = scenario_1_baseline_weight_only()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.integration
async def test_scenario_2_baseline_with_body_comp():
    """E2E: Agent records baseline with body composition data (real Haiku 4.5)."""
    dataset = scenario_2_baseline_with_body_comp()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.integration
async def test_scenario_3_regular_checkin():
    """E2E: Agent routes weekly check-in to calculate_weekly_adjustments (real Haiku 4.5)."""
    dataset = scenario_3_regular_checkin()
    report = await dataset.evaluate(task=_run_agent)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"
