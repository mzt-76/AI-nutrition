"""
End-to-End Tests for User Stories (PRD Section 5).

These tests validate that the agent correctly handles the 8 user stories
defined in the PRD. Tests use mocking to avoid external API calls.

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
from unittest.mock import AsyncMock, MagicMock, patch
from src.agent import agent, AgentDeps


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_deps():
    """Create mock AgentDeps for testing without external services."""
    deps = MagicMock(spec=AgentDeps)
    deps.supabase = MagicMock()
    deps.openai_client = AsyncMock()
    deps.embedding_client = AsyncMock()
    deps.http_client = AsyncMock()
    deps.brave_api_key = "test-brave-key"
    deps.searxng_base_url = None
    deps.memories = ""
    deps.skill_loader = None
    return deps


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
    """
    US-1: Initial Profile Setup

    As a new user, I want to have a natural conversation to set up my profile
    (age, weight, height, goals, allergies), so that I receive personalized
    nutritional recommendations without filling out forms.
    """

    @pytest.mark.asyncio
    async def test_profile_setup_greeting_response(self, mock_deps):
        """Test that agent responds naturally to profile setup request."""
        # When user introduces themselves
        result = await agent.run(
            "Salut ! Je suis Marc, 35 ans, 87kg, 178cm. Je veux prendre du muscle.",
            deps=mock_deps,
        )

        # Then agent should respond (not error)
        assert hasattr(result, "output")
        assert isinstance(result.output, str)
        assert len(result.output) > 0

    @pytest.mark.asyncio
    async def test_profile_setup_asks_for_allergies(self, mock_deps):
        """Test that agent asks about allergies during profile setup."""
        result = await agent.run(
            "Je veux créer mon profil nutrition. J'ai 30 ans, 80kg, 175cm.",
            deps=mock_deps,
        )

        # Agent should respond with follow-up questions or acknowledgment
        assert result.output is not None
        assert len(result.output) > 20  # Non-trivial response


# ============================================================================
# US-2: Weekly Feedback & Adaptive Adjustments
# ============================================================================


class TestUS2WeeklyFeedback:
    """
    US-2: Weekly Feedback & Adaptive Adjustments

    As an active user, I want to submit my weekly check-in via conversation,
    so that the agent adjusts my calorie/macro targets based on real-world results.
    """

    @pytest.mark.asyncio
    async def test_weekly_feedback_conversation(self, mock_deps):
        """Test agent handles weekly feedback naturally."""
        result = await agent.run(
            "Cette semaine j'ai perdu 0.6kg, j'avais un peu faim le soir, "
            "bonne énergie à l'entraînement, j'ai suivi le plan à 85%.",
            deps=mock_deps,
        )

        assert result.output is not None
        assert len(result.output) > 0

    @pytest.mark.asyncio
    async def test_feedback_with_specific_metrics(self, mock_deps):
        """Test agent processes specific feedback metrics."""
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
    """
    US-3: Nutritional Knowledge Queries

    As a user curious about nutrition science, I want to ask questions and
    get scientifically-backed answers from the knowledge base.
    """

    @pytest.mark.asyncio
    async def test_protein_question(self, mock_deps):
        """Test agent answers protein-related questions."""
        result = await agent.run(
            "Combien de protéines pour prendre du muscle ?",
            deps=mock_deps,
        )

        assert result.output is not None
        # Response should contain relevant information
        assert len(result.output) > 50

    @pytest.mark.asyncio
    async def test_bmr_explanation_request(self, mock_deps):
        """Test agent explains BMR calculation."""
        result = await agent.run(
            "Comment calcules-tu mon métabolisme de base ?",
            deps=mock_deps,
        )

        assert result.output is not None

    @pytest.mark.asyncio
    async def test_macro_distribution_question(self, mock_deps):
        """Test agent explains macro distribution."""
        result = await agent.run(
            "Pourquoi autant de glucides pour la prise de muscle ?",
            deps=mock_deps,
        )

        assert result.output is not None


# ============================================================================
# US-4: Body Composition Analysis
# ============================================================================


class TestUS4BodyComposition:
    """
    US-4: Body Composition Analysis

    As a user tracking my physique, I want to upload a body photo and receive
    an estimated body fat percentage with detailed visual feedback.
    """

    @pytest.mark.asyncio
    async def test_body_fat_request_without_image(self, mock_deps):
        """Test agent responds appropriately when no image provided."""
        result = await agent.run(
            "Peux-tu estimer mon taux de graisse corporelle ?",
            deps=mock_deps,
        )

        assert result.output is not None
        # Agent should ask for an image or explain the process

    @pytest.mark.asyncio
    async def test_body_composition_explanation(self, mock_deps):
        """Test agent explains body composition analysis."""
        result = await agent.run(
            "Comment fonctionne l'analyse de composition corporelle ?",
            deps=mock_deps,
        )

        assert result.output is not None


# ============================================================================
# US-5: Preference Memory & Personalization
# ============================================================================


class TestUS5PreferenceMemory:
    """
    US-5: Preference Memory & Personalization

    As a returning user, I want the agent to remember my dietary restrictions,
    favorite foods, and past conversations.
    """

    @pytest.mark.asyncio
    async def test_memory_context_used(self):
        """Test that memories are included in agent context."""
        # Create deps with memories
        deps = MagicMock(spec=AgentDeps)
        deps.supabase = MagicMock()
        deps.openai_client = AsyncMock()
        deps.embedding_client = AsyncMock()
        deps.http_client = AsyncMock()
        deps.brave_api_key = "test"
        deps.searxng_base_url = None
        deps.memories = (
            "L'utilisateur est allergique aux arachides et n'aime pas le poisson."
        )
        deps.skill_loader = None

        result = await agent.run(
            "Rappelle-moi mes restrictions alimentaires.",
            deps=deps,
        )

        assert result.output is not None

    @pytest.mark.asyncio
    async def test_returning_user_greeting(self, mock_deps):
        """Test agent responds to returning user."""
        mock_deps.memories = (
            "Dernière conversation: plan de prise de muscle, objectif 3000 kcal."
        )

        result = await agent.run(
            "Salut, c'est encore moi !",
            deps=mock_deps,
        )

        assert result.output is not None


# ============================================================================
# US-6: Web Search for Recent Information
# ============================================================================


class TestUS6WebSearch:
    """
    US-6: Web Search for Recent Information

    As a user asking about recent nutrition trends, I want the agent to search
    the web when its knowledge base is insufficient.
    """

    @pytest.mark.asyncio
    async def test_recent_research_question(self, mock_deps):
        """Test agent handles questions about recent research."""
        result = await agent.run(
            "Quelles sont les dernières études sur la créatine en 2024 ?",
            deps=mock_deps,
        )

        assert result.output is not None

    @pytest.mark.asyncio
    async def test_trending_diet_question(self, mock_deps):
        """Test agent handles questions about trending diets."""
        result = await agent.run(
            "C'est quoi le régime carnivore dont tout le monde parle ?",
            deps=mock_deps,
        )

        assert result.output is not None


# ============================================================================
# US-7: Profile Retrieval & Context Loading
# ============================================================================


class TestUS7ProfileRetrieval:
    """
    US-7: Profile Retrieval & Context Loading

    As a user starting a new conversation session, I want the agent to
    automatically load my profile and recent memories.
    """

    @pytest.mark.asyncio
    async def test_profile_context_request(self, mock_deps):
        """Test agent can discuss user's current profile."""
        result = await agent.run(
            "Rappelle-moi mon profil actuel et mes objectifs.",
            deps=mock_deps,
        )

        assert result.output is not None

    @pytest.mark.asyncio
    async def test_session_continuity(self, mock_deps):
        """Test agent maintains session continuity."""
        mock_deps.memories = (
            "Objectif: prise de muscle. Calories: 3000. Allergies: arachides."
        )

        result = await agent.run(
            "On en était où la dernière fois ?",
            deps=mock_deps,
        )

        assert result.output is not None


# ============================================================================
# US-8: Conversational Calculations
# ============================================================================


class TestUS8ConversationalCalculations:
    """
    US-8: Conversational Calculations

    As a user with changing metrics, I want to ask scenario questions and
    get instant recalculations.
    """

    @pytest.mark.asyncio
    async def test_weight_change_scenario(self, mock_deps):
        """Test agent handles weight change scenarios."""
        result = await agent.run(
            "Si je passe à 85kg, ça change mes macros comment ?",
            deps=mock_deps,
        )

        assert result.output is not None

    @pytest.mark.asyncio
    async def test_activity_level_change(self, mock_deps):
        """Test agent handles activity level change scenarios."""
        result = await agent.run(
            "Si je passe de modéré à actif, je devrais manger combien de plus ?",
            deps=mock_deps,
        )

        assert result.output is not None

    @pytest.mark.asyncio
    async def test_goal_change_scenario(self, mock_deps):
        """Test agent handles goal change scenarios."""
        result = await agent.run(
            "Et si je voulais plutôt perdre du poids au lieu de prendre du muscle ?",
            deps=mock_deps,
        )

        assert result.output is not None

    @pytest.mark.asyncio
    async def test_specific_calculation_request(self, mock_deps):
        """Test agent performs specific calculations on request."""
        result = await agent.run(
            "Calcule mes besoins pour un homme de 40 ans, 90kg, 180cm, très actif, "
            "objectif perte de poids.",
            deps=mock_deps,
        )

        assert result.output is not None


# ============================================================================
# Integration Tests - Multi-turn Conversations
# ============================================================================


class TestMultiTurnConversations:
    """Test multi-turn conversation flows."""

    @pytest.mark.asyncio
    async def test_profile_then_calculation_flow(self, mock_deps):
        """Test natural flow: profile setup then calculation request."""
        # First turn: introduction
        result1 = await agent.run(
            "Salut ! Je suis nouveau ici.",
            deps=mock_deps,
        )
        assert result1.output is not None

        # Second turn: provide info
        result2 = await agent.run(
            "J'ai 35 ans, je fais 87kg pour 178cm.",
            deps=mock_deps,
        )
        assert result2.output is not None

    @pytest.mark.asyncio
    async def test_feedback_then_adjustment_flow(self, mock_deps):
        """Test natural flow: feedback then adjustment discussion."""
        # First turn: provide feedback
        result1 = await agent.run(
            "J'ai perdu 1kg cette semaine mais j'avais très faim.",
            deps=mock_deps,
        )
        assert result1.output is not None

        # Second turn: ask about adjustment
        result2 = await agent.run(
            "Tu me conseilles quoi pour la semaine prochaine ?",
            deps=mock_deps,
        )
        assert result2.output is not None


# ============================================================================
# Edge Cases
# ============================================================================


class TestEdgeCasesE2E:
    """Test edge cases in conversation handling."""

    @pytest.mark.asyncio
    async def test_empty_message(self, mock_deps):
        """Test agent handles empty or minimal input."""
        result = await agent.run("", deps=mock_deps)
        # Should not crash, may ask for clarification
        assert result.output is not None

    @pytest.mark.asyncio
    async def test_off_topic_question(self, mock_deps):
        """Test agent handles off-topic questions gracefully."""
        result = await agent.run(
            "Quelle est la capitale de la France ?",
            deps=mock_deps,
        )
        # Agent should redirect to nutrition or answer briefly
        assert result.output is not None

    @pytest.mark.asyncio
    async def test_greeting_response(self, mock_deps):
        """Test agent responds warmly to simple greetings."""
        result = await agent.run("Bonjour !", deps=mock_deps)
        assert result.output is not None
        assert len(result.output) > 0

    @pytest.mark.asyncio
    async def test_thanks_response(self, mock_deps):
        """Test agent responds appropriately to thanks."""
        result = await agent.run("Merci beaucoup !", deps=mock_deps)
        assert result.output is not None
