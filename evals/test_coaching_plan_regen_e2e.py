"""E2E eval — weekly coaching adjustments → meal plan re-generation with real LLM.

WHY THIS IS AN EVAL, NOT A TEST
================================
These scenarios involve a real LLM making multi-turn decisions:
  - Turn 1: Agent receives weekly feedback → calls calculate_weekly_adjustments
  - Turn 2: Agent is asked to regenerate meal plan with adjusted targets
           → calls generate_week_plan with NEW calorie/macro targets

Outcomes are non-deterministic → scored criteria, not exact assertions.
Run on demand before releases, NOT in CI (slow, costs API credits).

    pytest evals/test_coaching_plan_regen_e2e.py -m integration -v -s

TEST PERSONA — Marc (real user in Supabase with meal plans)
=========================================================================
Name:            Marc
Age:             24
Gender:          male
Height:          191 cm
Weight:          86 kg
Activity level:  light (x1.375)
Goal:            muscle gain
Original target: ~2966 kcal

Pre-calculated expected adjustments (from src.nutrition.adjustments):
  If adherence=90%, weight_start=86.0, weight_end=86.3 (gain +0.3 kg/wk)
  and user reports hunger → expect calorie increase (~100-300 kcal)
  New target should be in range 3000-3300 kcal
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

TEST_USER_ID = "5745fc58-9c75-48b1-bc79-12855a8c6021"


# ---------------------------------------------------------------------------
# Structured output
# ---------------------------------------------------------------------------


@dataclass
class AgentResult:
    text: str
    tool_calls: list[dict]


# ---------------------------------------------------------------------------
# Evaluators
# ---------------------------------------------------------------------------


@dataclass
class NoRefusal(Evaluator):
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
                return EvaluationReason(value=False, reason=f"Refusal: '{phrase}'")
        return EvaluationReason(value=True, reason="No refusal")


@dataclass
class SkillScriptRouting(Evaluator):
    """Check run_skill_script was called with specific skill+script."""

    expected_skill: str
    expected_script: str
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        if not isinstance(ctx.output, AgentResult):
            return EvaluationReason(value=False, reason="Output is not AgentResult")
        for tc in ctx.output.tool_calls:
            if tc["name"] != "run_skill_script":
                continue
            args = tc["args"]
            if (
                args.get("skill_name") == self.expected_skill
                and args.get("script_name") == self.expected_script
            ):
                return EvaluationReason(
                    value=True,
                    reason=f"Correct routing: {self.expected_skill}/{self.expected_script}",
                )
        scripts_called = [
            f"{tc['args'].get('skill_name')}/{tc['args'].get('script_name')}"
            for tc in ctx.output.tool_calls
            if tc["name"] == "run_skill_script"
        ]
        return EvaluationReason(
            value=False,
            reason=f"Expected {self.expected_skill}/{self.expected_script}. "
            f"Called: {scripts_called or 'none'}",
        )


@dataclass
class ContainsAnyOf(Evaluator):
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
            value=False, reason=f"None of {self.options} found in response"
        )


@dataclass
class ResponseMinLength(Evaluator):
    min_chars: int
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        text = (
            ctx.output.text if isinstance(ctx.output, AgentResult) else str(ctx.output)
        )
        if len(text) >= self.min_chars:
            return EvaluationReason(
                value=True, reason=f"{len(text)} chars >= {self.min_chars}"
            )
        return EvaluationReason(
            value=False, reason=f"Too short: {len(text)} < {self.min_chars}"
        )


# ---------------------------------------------------------------------------
# Task functions
# ---------------------------------------------------------------------------


async def _run_agent_multi_turn(messages: list[str]) -> AgentResult:
    """Run multiple user messages in sequence, preserving conversation history."""
    deps = create_agent_deps(user_id=TEST_USER_ID)
    all_tool_calls: list[dict] = []
    message_history = None
    result = None
    seen_tool_ids: set[str] = set()

    for msg in messages:
        result = await agent.run(msg, deps=deps, message_history=message_history)
        message_history = result.all_messages()
        for m in message_history:
            for part in getattr(m, "parts", []):
                if isinstance(part, ToolCallPart):
                    if part.tool_call_id in seen_tool_ids:
                        continue
                    seen_tool_ids.add(part.tool_call_id)
                    args = part.args
                    if isinstance(args, str):
                        args = json.loads(args)
                    all_tool_calls.append({"name": part.tool_name, "args": args})

    return AgentResult(text=result.output if result else "", tool_calls=all_tool_calls)


# ---------------------------------------------------------------------------
# Scenario 1 — Coaching check-in → re-generate meal plan
#
# Turn 1: User provides weekly feedback → calculate_weekly_adjustments
# Turn 2: User asks for new plan with adjusted targets → generate_week_plan
# ---------------------------------------------------------------------------


def scenario_1_coaching_then_plan_regen() -> Dataset:
    """Agent adjusts targets from coaching, then generates updated meal plan."""
    return Dataset(
        name="scenario_1_coaching_then_plan_regen",
        cases=[
            Case(
                name="coaching_adjustments_flow_to_plan",
                inputs=[
                    (
                        "Bilan de ma semaine : poids debut 86.0 kg, poids fin 86.3 kg. "
                        "J'ai suivi le plan a 90%, bonne energie mais j'avais faim "
                        "entre les repas. Ma cible etait 2966 kcal."
                    ),
                    (
                        "Regenere mon plan repas pour la semaine prochaine "
                        "avec les nouvelles cibles que tu viens de calculer."
                    ),
                ],
                evaluators=(
                    NoRefusal(),
                    # Turn 1: must call calculate_weekly_adjustments
                    SkillScriptRouting(
                        expected_skill="weekly-coaching",
                        expected_script="calculate_weekly_adjustments",
                        evaluation_name="coaching_adjustments_called",
                    ),
                    # Turn 2: must call generate_week_plan
                    SkillScriptRouting(
                        expected_skill="meal-planning",
                        expected_script="generate_week_plan",
                        evaluation_name="week_plan_generated",
                    ),
                    # Response should mention calorie/macro adjustments
                    ContainsAnyOf(
                        options=[
                            "kcal",
                            "calories",
                            "ajust",
                            "augment",
                            "nouveau",
                            "plan",
                        ],
                        evaluation_name="mentions_adjusted_targets",
                    ),
                    ResponseMinLength(
                        min_chars=100,
                        evaluation_name="substantive_response",
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=180.0)],
    )


# ---------------------------------------------------------------------------
# Pytest — marked integration
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_scenario_1_coaching_then_plan_regen():
    """E2E: Coaching adjustments → plan regeneration with updated targets."""
    dataset = scenario_1_coaching_then_plan_regen()
    report = await dataset.evaluate(task=_run_agent_multi_turn)
    report.print(include_input=True, include_output=True)
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"
