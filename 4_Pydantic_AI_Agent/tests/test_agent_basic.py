"""
Basic agent tests to prevent API breakage.

These tests ensure the agent's core functionality works and catch
breaking changes in dependencies like Pydantic AI.
"""

import pytest
from agent import agent, create_agent_deps


class TestAgentBasicFunctionality:
    """Test basic agent operations to catch API changes."""

    @pytest.mark.asyncio
    async def test_agent_returns_result_with_data_attribute(self):
        """
        Test that agent.run() returns a result with .data attribute.

        This test catches breaking changes in Pydantic AI's API
        (e.g., .output renamed to .data).
        """
        deps = create_agent_deps()

        result = await agent.run(
            "Dis-moi bonjour en une phrase",
            deps=deps
        )

        # CRITICAL: Test that result has .data attribute
        assert hasattr(result, 'data'), (
            "AgentRunResult should have 'data' attribute. "
            "If this fails, check Pydantic AI version and API changes."
        )

        # Test that .data returns a string
        assert isinstance(result.data, str), (
            f"result.data should be string, got {type(result.data)}"
        )

        # Test that response is not empty
        assert len(result.data) > 0, "Agent response should not be empty"

    @pytest.mark.asyncio
    async def test_agent_does_not_have_output_attribute(self):
        """
        Test that agent.run() result does NOT have .output attribute.

        This ensures we're not using the deprecated API.
        """
        deps = create_agent_deps()

        result = await agent.run(
            "Réponds juste 'OK'",
            deps=deps
        )

        # Ensure old API (.output) is NOT present
        assert not hasattr(result, 'output'), (
            "AgentRunResult should NOT have 'output' attribute. "
            "This is the old Pydantic AI API. Use 'data' instead."
        )


class TestAgentDependencies:
    """Test that agent dependencies are properly initialized."""

    def test_create_agent_deps_returns_valid_object(self):
        """Test that create_agent_deps() returns a valid AgentDeps object."""
        deps = create_agent_deps()

        # Check critical attributes exist
        assert hasattr(deps, 'supabase'), "AgentDeps should have supabase client"
        assert hasattr(deps, 'embedding_client'), "AgentDeps should have embedding client"
        assert hasattr(deps, 'http_client'), "AgentDeps should have HTTP client"

        # Check clients are not None
        assert deps.supabase is not None, "Supabase client should be initialized"
        assert deps.embedding_client is not None, "Embedding client should be initialized"
        assert deps.http_client is not None, "HTTP client should be initialized"
