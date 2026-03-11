"""
Basic agent tests — deterministic only (no real LLM calls).

Real LLM API compatibility tests are in evals/test_agent_e2e.py.
"""

from src.agent import create_agent_deps


class TestAgentDependencies:
    """Test that agent dependencies are properly initialized."""

    def test_create_agent_deps_returns_valid_object(self):
        """Test that create_agent_deps() returns a valid AgentDeps object."""
        deps = create_agent_deps()

        # Check critical attributes exist
        assert hasattr(deps, "supabase"), "AgentDeps should have supabase client"
        assert hasattr(
            deps, "embedding_client"
        ), "AgentDeps should have embedding client"
        assert hasattr(deps, "http_client"), "AgentDeps should have HTTP client"

        # Check clients are not None
        assert deps.supabase is not None, "Supabase client should be initialized"
        assert (
            deps.embedding_client is not None
        ), "Embedding client should be initialized"
        assert deps.http_client is not None, "HTTP client should be initialized"
