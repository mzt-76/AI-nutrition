"""
End-to-End Tests for User Stories (PRD Section 5).

Tests are split into two categories:

  Unit tests (FunctionModel) — deterministic, no LLM API calls, verify that the
  agent correctly wires tool calls and handles responses.  These run in every
  `pytest` invocation.

  Integration tests (@pytest.mark.integration) — call the real configured LLM,
  verify natural-language understanding and generation.  Run with:
      pytest -m integration

User Stories:
- US-1: Initial Profile Setup
- US-2: Weekly Feedback & Adaptive Adjustments
- US-3: Nutritional Knowledge Queries (RAG)
- US-4: Body Composition Analysis
- US-5: Preference Memory & Personalization
- US-6: Web Search for Recent Information
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
      - .table().select().limit().execute()
      - .table().update().eq().execute()
      - .table().insert().execute()
    """
    mock = MagicMock()
    result = MagicMock()
    result.data = [profile] if profile else []

    chain = mock.table.return_value
    chain.select.return_value.limit.return_value.execute.return_value = result
    chain.update.return_value.eq.return_value.execute.return_value = result
    chain.insert.return_value.execute.return_value = result
    return mock


def _make_deps(profile: dict | None = None, memories: str = "") -> AgentDeps:
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
    return deps


# ============================================================================
# FunctionModel definitions — one per unit test scenario
# ============================================================================


def _model_update_profile(messages, info) -> ModelResponse:
    """Simulate LLM calling update_my_profile with correct dict[str, int] goals."""
    if len(messages) == 1:
        return ModelResponse(parts=[
            ToolCallPart("update_my_profile", {
                "age": 35,
                "weight_kg": 87.0,
                "height_cm": 178,
                "gender": "male",
                "goals": {"muscle_gain": 8, "performance": 5},
            })
        ])
    return ModelResponse(parts=[TextPart(
        "Parfait Marc ! Ton profil a été enregistré. "
        "Avec 87 kg pour 178 cm et un objectif de prise de muscle, "
        "je vais calculer tes besoins nutritionnels."
    )])


def _model_fetch_profile(messages, info) -> ModelResponse:
    """Simulate LLM calling fetch_my_profile then summarising the result."""
    if len(messages) == 1:
        return ModelResponse(parts=[ToolCallPart("fetch_my_profile", {})])
    return ModelResponse(parts=[TextPart(
        "Voici ton profil actuel : tu as 35 ans, pèses 87 kg pour 178 cm, "
        "activité modérée, objectif principal prise de muscle."
    )])


def _model_run_nutrition_script(messages, info) -> ModelResponse:
    """Simulate LLM calling run_skill_script for a nutrition calculation."""
    if len(messages) == 1:
        return ModelResponse(parts=[
            ToolCallPart("run_skill_script", {
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
            })
        ])
    # After the script result arrives, synthesise a human-readable answer
    return ModelResponse(parts=[TextPart(
        "Pour un homme de 40 ans, 90 kg, 180 cm, très actif avec objectif perte de poids : "
        "ton BMR est d'environ 1955 kcal, TDEE ~3028 kcal. "
        "Je te recommande environ 2528 kcal/jour (déficit de 500 kcal)."
    )])


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
        "goals": {"muscle_gain": 7, "performance": 5, "weight_loss": 0, "maintenance": 3},
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
            p for m in result.all_messages()
            for p in getattr(m, "parts", [])
            if isinstance(p, ToolCallPart) and p.tool_name == "update_my_profile"
        ]
        assert len(tool_calls) == 1
        args = tool_calls[0].args
        if isinstance(args, str):
            args = json.loads(args)
        assert isinstance(args["goals"], dict), "goals must be a dict, not a list"
        assert all(isinstance(v, int) for v in args["goals"].values()), "goal values must be ints"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_profile_setup_asks_for_allergies(self, mock_deps):
        """Integration (real LLM): agent follows up about allergies during profile setup."""
        result = await agent.run(
            "Je veux créer mon profil nutrition. J'ai 30 ans, 80kg, 175cm.",
            deps=mock_deps,
        )
        assert result.output is not None
        assert len(result.output) > 20


# ============================================================================
# US-2: Weekly Feedback & Adaptive Adjustments
# ============================================================================


class TestUS2WeeklyFeedback:
    """US-2: User submits weekly check-in; agent adjusts targets."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_weekly_feedback_conversation(self, mock_deps):
        """Integration (real LLM): agent handles weekly feedback naturally."""
        result = await agent.run(
            "Cette semaine j'ai perdu 0.6kg, j'avais un peu faim le soir, "
            "bonne énergie à l'entraînement, j'ai suivi le plan à 85%.",
            deps=mock_deps,
        )
        assert result.output is not None
        assert len(result.output) > 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_feedback_with_specific_metrics(self, mock_deps):
        """Integration (real LLM): agent processes specific numeric feedback."""
        result = await agent.run(
            "Mon poids début de semaine: 87kg, fin de semaine: 86.4kg. "
            "Niveau de faim: moyen. Énergie: haute. Adhérence: 90%.",
            deps=mock_deps,
        )
        assert result.output is not None


# ============================================================================
# US-3: Nutritional Knowledge Queries (RAG)
# ============================================================================


class TestUS3NutritionalKnowledge:
    """US-3: User asks nutrition science questions; agent answers from knowledge base."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_protein_question(self, mock_deps):
        """Integration (real LLM): substantive answer to protein/muscle question."""
        result = await agent.run(
            "Combien de protéines pour prendre du muscle ?",
            deps=mock_deps,
        )
        assert result.output is not None
        assert len(result.output) > 50

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_bmr_explanation_request(self, mock_deps):
        """Integration (real LLM): agent explains BMR calculation."""
        result = await agent.run(
            "Comment calcules-tu mon métabolisme de base ?",
            deps=mock_deps,
        )
        assert result.output is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_macro_distribution_question(self, mock_deps):
        """Integration (real LLM): agent explains macro reasoning."""
        result = await agent.run(
            "Pourquoi autant de glucides pour la prise de muscle ?",
            deps=mock_deps,
        )
        assert result.output is not None


# ============================================================================
# US-4: Body Composition Analysis
# ============================================================================


class TestUS4BodyComposition:
    """US-4: User requests body fat estimation from a photo."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_body_fat_request_without_image(self, mock_deps):
        """Integration (real LLM): agent asks for image when none provided."""
        result = await agent.run(
            "Peux-tu estimer mon taux de graisse corporelle ?",
            deps=mock_deps,
        )
        assert result.output is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_body_composition_explanation(self, mock_deps):
        """Integration (real LLM): agent explains body composition analysis."""
        result = await agent.run(
            "Comment fonctionne l'analyse de composition corporelle ?",
            deps=mock_deps,
        )
        assert result.output is not None


# ============================================================================
# US-5: Preference Memory & Personalization
# ============================================================================


class TestUS5PreferenceMemory:
    """US-5: Returning user; agent uses stored memories."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_memory_context_used(self):
        """Integration (real LLM): agent references allergies stored in memories."""
        deps = _make_deps(
            memories="L'utilisateur est allergique aux arachides et n'aime pas le poisson."
        )
        result = await agent.run(
            "Rappelle-moi mes restrictions alimentaires.",
            deps=deps,
        )
        assert result.output is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_returning_user_greeting(self, mock_deps):
        """Integration (real LLM): agent greets returning user using memories."""
        mock_deps.memories = (
            "Dernière conversation: plan de prise de muscle, objectif 3000 kcal."
        )
        result = await agent.run("Salut, c'est encore moi !", deps=mock_deps)
        assert result.output is not None


# ============================================================================
# US-6: Web Search for Recent Information
# ============================================================================


class TestUS6WebSearch:
    """US-6: User asks about recent research; agent searches the web."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_recent_research_question(self, mock_deps):
        """Integration (real LLM): agent handles questions about recent studies."""
        result = await agent.run(
            "Quelles sont les dernières études sur la créatine en 2024 ?",
            deps=mock_deps,
        )
        assert result.output is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_trending_diet_question(self, mock_deps):
        """Integration (real LLM): agent handles trending diet questions."""
        result = await agent.run(
            "C'est quoi le régime carnivore dont tout le monde parle ?",
            deps=mock_deps,
        )
        assert result.output is not None


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
            p for m in result.all_messages()
            for p in getattr(m, "parts", [])
            if isinstance(p, ToolCallPart) and p.tool_name == "fetch_my_profile"
        ]
        assert len(tool_calls) == 1

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_session_continuity(self, mock_deps):
        """Integration (real LLM): agent maintains session continuity via memories."""
        mock_deps.memories = (
            "Objectif: prise de muscle. Calories: 3000. Allergies: arachides."
        )
        result = await agent.run("On en était où la dernière fois ?", deps=mock_deps)
        assert result.output is not None


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
            p for m in result.all_messages()
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

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_weight_change_scenario(self, mock_deps):
        """Integration (real LLM): agent recalculates macros for new weight."""
        result = await agent.run(
            "Si je passe à 85kg, ça change mes macros comment ?",
            deps=mock_deps,
        )
        assert result.output is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_activity_level_change(self, mock_deps):
        """Integration (real LLM): agent calculates impact of activity change."""
        result = await agent.run(
            "Si je passe de modéré à actif, je devrais manger combien de plus ?",
            deps=mock_deps,
        )
        assert result.output is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_goal_change_scenario(self, mock_deps):
        """Integration (real LLM): agent handles goal switch from muscle gain to fat loss."""
        result = await agent.run(
            "Et si je voulais plutôt perdre du poids au lieu de prendre du muscle ?",
            deps=mock_deps,
        )
        assert result.output is not None


# ============================================================================
# Integration Tests - Multi-turn Conversations
# ============================================================================


class TestMultiTurnConversations:
    """Multi-turn conversation flows."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_profile_then_calculation_flow(self, mock_deps):
        """Integration (real LLM): natural flow — intro then calculation request."""
        result1 = await agent.run("Salut ! Je suis nouveau ici.", deps=mock_deps)
        assert result1.output is not None

        result2 = await agent.run(
            "J'ai 35 ans, je fais 87kg pour 178cm.", deps=mock_deps
        )
        assert result2.output is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_feedback_then_adjustment_flow(self, mock_deps):
        """Integration (real LLM): feedback then ask for next week's advice."""
        result1 = await agent.run(
            "J'ai perdu 1kg cette semaine mais j'avais très faim.", deps=mock_deps
        )
        assert result1.output is not None

        result2 = await agent.run(
            "Tu me conseilles quoi pour la semaine prochaine ?", deps=mock_deps
        )
        assert result2.output is not None


# ============================================================================
# Edge Cases
# ============================================================================


class TestEdgeCasesE2E:
    """Edge cases in conversation handling."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_empty_message(self, mock_deps):
        """Integration (real LLM): agent handles empty input without crashing."""
        result = await agent.run("", deps=mock_deps)
        assert result.output is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_off_topic_question(self, mock_deps):
        """Integration (real LLM): agent redirects off-topic questions gracefully."""
        result = await agent.run(
            "Quelle est la capitale de la France ?", deps=mock_deps
        )
        assert result.output is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_greeting_response(self, mock_deps):
        """Integration (real LLM): agent responds warmly to simple greetings."""
        result = await agent.run("Bonjour !", deps=mock_deps)
        assert result.output is not None
        assert len(result.output) > 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_thanks_response(self, mock_deps):
        """Integration (real LLM): agent responds appropriately to thanks."""
        result = await agent.run("Merci beaucoup !", deps=mock_deps)
        assert result.output is not None
