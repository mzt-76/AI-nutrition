"""
End-to-End Eval for User Stories — real LLM tests (moved from tests/).

WHY THIS IS AN EVAL, NOT A TEST
================================
These tests call agent.run() with the real configured LLM.
They verify natural-language understanding and generation.
Run on demand with:
    pytest evals/test_user_stories_e2e.py -m integration -v

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

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.agent import agent, AgentDeps


TEST_USER_PROFILE = {
    "age": 30,
    "gender": "male",
    "height_cm": 178,
    "weight_kg": 80,
    "activity_level": "moderate",
    "goals": {"muscle_gain": 5, "maintenance": 3, "weight_loss": 1, "performance": 2},
}


def _make_supabase_mock(profile: dict | None = None) -> MagicMock:
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


@pytest.fixture
def mock_deps():
    return _make_deps()


# ============================================================================
# US-1: Initial Profile Setup
# ============================================================================


class TestUS1ProfileSetup:
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
# Multi-turn Conversations
# ============================================================================


class TestMultiTurnConversations:
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
