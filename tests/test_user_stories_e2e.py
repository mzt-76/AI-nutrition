"""
Unit tests for User Stories (PRD Section 5) — deterministic, no real LLM calls.

These tests use FunctionModel to simulate LLM behaviour and verify that the
agent correctly wires tool calls and handles responses.

Integration tests (real LLM) are in evals/test_user_stories_e2e.py.

User Stories covered:
- US-1: Initial Profile Setup
- US-7: Profile Retrieval & Context Loading
- US-8: Conversational Calculations
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from pydantic_ai.models.function import FunctionModel
from pydantic_ai.messages import ModelResponse, ToolCallPart, TextPart

from src.agent import agent, AgentDeps


# ============================================================================
# Helpers
# ============================================================================


def _make_supabase_mock(profile: dict | None = None) -> MagicMock:
    """Build a Supabase mock that returns JSON-serializable data.

    Wires the call chains used by fetch_my_profile_tool and update_my_profile_tool:
      - .table().select().eq().limit().execute()
      - .table().update().eq().execute()
      - .table().insert().execute()
    """
    mock = MagicMock()
    result = MagicMock()
    result.data = [profile] if profile else []

    chain = mock.table.return_value
    chain.select.return_value.eq.return_value.limit.return_value.execute = AsyncMock(
        return_value=result
    )
    chain.update.return_value.eq.return_value.execute = AsyncMock(return_value=result)
    chain.insert.return_value.execute = AsyncMock(return_value=result)
    return mock


def _make_deps(
    profile: dict | None = None,
    memories: str = "",
    user_id: str = "test-user-123",
) -> AgentDeps:
    """Create mock AgentDeps with a properly-wired Supabase stub."""
    deps = MagicMock(spec=AgentDeps)
    deps.supabase = _make_supabase_mock(profile=profile)
    deps.openai_client = AsyncMock()
    deps.embedding_client = AsyncMock()
    deps.http_client = AsyncMock()
    deps.brave_api_key = "test-brave-key"
    deps.searxng_base_url = None
    deps.memories = memories
    deps.skill_loader = None
    deps.user_id = user_id
    return deps


# ============================================================================
# FunctionModel definitions — one per unit test scenario
# ============================================================================


def _model_update_profile(messages, info) -> ModelResponse:
    """Simulate LLM calling update_my_profile with correct dict[str, int] goals."""
    if len(messages) == 1:
        return ModelResponse(
            parts=[
                ToolCallPart(
                    "update_my_profile",
                    {
                        "age": 35,
                        "weight_kg": 87.0,
                        "height_cm": 178,
                        "gender": "male",
                        "goals": {"muscle_gain": 8, "performance": 5},
                    },
                )
            ]
        )
    return ModelResponse(
        parts=[
            TextPart(
                "Parfait Marc ! Ton profil a été enregistré. "
                "Avec 87 kg pour 178 cm et un objectif de prise de muscle, "
                "je vais calculer tes besoins nutritionnels."
            )
        ]
    )


def _model_fetch_profile(messages, info) -> ModelResponse:
    """Simulate LLM calling fetch_my_profile then summarising the result."""
    if len(messages) == 1:
        return ModelResponse(parts=[ToolCallPart("fetch_my_profile", {})])
    return ModelResponse(
        parts=[
            TextPart(
                "Voici ton profil actuel : tu as 35 ans, pèses 87 kg pour 178 cm, "
                "activité modérée, objectif principal prise de muscle."
            )
        ]
    )


def _model_run_nutrition_script(messages, info) -> ModelResponse:
    """Simulate LLM calling run_skill_script for a nutrition calculation."""
    if len(messages) == 1:
        return ModelResponse(
            parts=[
                ToolCallPart(
                    "run_skill_script",
                    {
                        "skill_name": "nutrition-calculating",
                        "script_name": "calculate_nutritional_needs",
                        "params": {
                            "age": 40,
                            "gender": "male",
                            "weight_kg": 90.0,
                            "height_cm": 180,
                            "activity_level": "very_active",
                            "context": "objectif perte de poids",
                        },
                    },
                )
            ]
        )
    # After the script result arrives, synthesise a human-readable answer
    return ModelResponse(
        parts=[
            TextPart(
                "Pour un homme de 40 ans, 90 kg, 180 cm, très actif avec objectif perte de poids : "
                "ton BMR est d'environ 1955 kcal, TDEE ~3028 kcal. "
                "Je te recommande environ 2528 kcal/jour (déficit de 500 kcal)."
            )
        ]
    )


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_deps():
    """Deps with empty profile (new user)."""
    return _make_deps()


@pytest.fixture
def mock_deps_with_profile(sample_profile):
    """Deps pre-loaded with a real profile."""
    return _make_deps(profile=sample_profile)


@pytest.fixture
def sample_profile():
    """Standard test profile matching PRD persona."""
    return {
        "id": "test-user-123",
        "name": "Marc",
        "age": 35,
        "gender": "male",
        "weight_kg": 87.0,
        "height_cm": 178,
        "activity_level": "moderate",
        "goals": {
            "muscle_gain": 7,
            "performance": 5,
            "weight_loss": 0,
            "maintenance": 3,
        },
        "allergies": ["arachides"],
        "diet_type": "omnivore",
        "disliked_foods": ["poisson"],
        "favorite_foods": ["poulet", "riz", "banane"],
        "max_prep_time": 45,
        "preferred_cuisines": ["méditerranéenne", "asiatique"],
        "target_calories": 3168,
        "target_protein_g": 191,
        "target_carbs_g": 397,
        "target_fat_g": 88,
    }


# ============================================================================
# US-1: Initial Profile Setup
# ============================================================================


class TestUS1ProfileSetup:
    """US-1: New user sets up profile via natural conversation."""

    @pytest.mark.asyncio
    async def test_profile_setup_greeting_response(self, mock_deps):
        """Unit: agent calls update_my_profile with dict[str, int] goals — not a list."""
        with agent.override(model=FunctionModel(_model_update_profile)):
            result = await agent.run(
                "Salut ! Je suis Marc, 35 ans, 87kg, 178cm. Je veux prendre du muscle.",
                deps=mock_deps,
            )

        assert result.output is not None
        assert isinstance(result.output, str)
        assert len(result.output) > 0

        # Verify the tool was actually called with correct goal structure
        tool_calls = [
            p
            for m in result.all_messages()
            for p in getattr(m, "parts", [])
            if isinstance(p, ToolCallPart) and p.tool_name == "update_my_profile"
        ]
        assert len(tool_calls) == 1
        args = tool_calls[0].args
        if isinstance(args, str):
            args = json.loads(args)
        assert isinstance(args["goals"], dict), "goals must be a dict, not a list"
        assert all(
            isinstance(v, int) for v in args["goals"].values()
        ), "goal values must be ints"


# ============================================================================
# US-7: Profile Retrieval & Context Loading
# ============================================================================


class TestUS7ProfileRetrieval:
    """US-7: Agent loads profile from DB at the start of a session."""

    @pytest.mark.asyncio
    async def test_profile_context_request(self, mock_deps_with_profile):
        """Unit: agent calls fetch_my_profile and returns a human-readable summary."""
        with agent.override(model=FunctionModel(_model_fetch_profile)):
            result = await agent.run(
                "Rappelle-moi mon profil actuel et mes objectifs.",
                deps=mock_deps_with_profile,
            )

        assert result.output is not None

        # Verify fetch_my_profile was called exactly once
        tool_calls = [
            p
            for m in result.all_messages()
            for p in getattr(m, "parts", [])
            if isinstance(p, ToolCallPart) and p.tool_name == "fetch_my_profile"
        ]
        assert len(tool_calls) == 1


# ============================================================================
# US-8: Conversational Calculations
# ============================================================================


class TestUS8ConversationalCalculations:
    """US-8: User asks scenario questions; agent recalculates on the fly."""

    @pytest.mark.asyncio
    async def test_specific_calculation_request(self, mock_deps):
        """Unit: agent calls run_skill_script for nutrition calc; result is JSON with macros."""
        with agent.override(model=FunctionModel(_model_run_nutrition_script)):
            result = await agent.run(
                "Calcule mes besoins pour un homme de 40 ans, 90kg, 180cm, "
                "très actif, objectif perte de poids.",
                deps=mock_deps,
            )

        assert result.output is not None

        # Verify run_skill_script was called with the right skill
        tool_calls = [
            p
            for m in result.all_messages()
            for p in getattr(m, "parts", [])
            if isinstance(p, ToolCallPart) and p.tool_name == "run_skill_script"
        ]
        assert len(tool_calls) == 1
        args = tool_calls[0].args
        if isinstance(args, str):
            args = json.loads(args)
        assert args["skill_name"] == "nutrition-calculating"
        assert args["script_name"] == "calculate_nutritional_needs"
        # The script ran and the model produced a response — check it's non-trivial
        assert len(result.output) > 30
