"""Tests for src/api.py FastAPI endpoints.

Uses FastAPI TestClient with mocked dependencies.
No real LLM or database calls.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def client():
    """Create a TestClient with mocked global clients and bypassed JWT auth."""
    import src.api as api_module
    from fastapi.testclient import TestClient

    # Mock global clients before creating the test client
    api_module.supabase = MagicMock()
    api_module.title_agent = MagicMock()
    api_module.mem0_client = None  # Disable mem0 for tests

    # Override JWT verification to return a fake authenticated user
    api_module.app.dependency_overrides[api_module.verify_token] = lambda: {
        "id": "user1",
        "email": "test@example.com",
    }

    with TestClient(api_module.app, raise_server_exceptions=False) as c:
        yield c

    # Clean up overrides
    api_module.app.dependency_overrides.clear()


class TestHealthEndpoint:
    """Tests for GET /health."""

    def test_health_returns_200(self, client):
        """Health endpoint should return 200 with status healthy."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "ai-nutrition-api"


class TestConversationsEndpoint:
    """Tests for GET /api/conversations."""

    def test_list_conversations(self, client):
        """Should return conversations for a user."""
        import src.api as api_module

        mock_response = MagicMock()
        mock_response.data = [
            {"id": 1, "session_id": "user1~abc", "title": "Test conv"}
        ]
        # Reset supabase mock to allow deep chaining
        api_module.supabase = MagicMock()
        api_module.supabase.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_response

        response = client.get("/api/conversations?user_id=user1")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["session_id"] == "user1~abc"


class TestAgentEndpoint:
    """Tests for POST /api/agent."""

    def test_rate_limit_exceeded_returns_429(self, client):
        """Should return 429 when rate limit is exceeded."""
        with patch("src.api.check_rate_limit", new_callable=AsyncMock) as mock_rl:
            mock_rl.return_value = (False, "Limite atteinte.")

            response = client.post(
                "/api/agent",
                json={
                    "query": "Hello",
                    "user_id": "user1",
                    "request_id": "req1",
                    "session_id": "user1~existing",
                },
            )

            assert response.status_code == 429
            # Parse NDJSON lines
            lines = response.text.strip().split("\n")
            last_line = json.loads(lines[-1])
            assert last_line["complete"] is True
            assert "limite" in last_line["error"].lower()

    def test_agent_endpoint_accepts_request(self, client):
        """Should accept a valid request and stream a response."""
        with (
            patch("src.api.check_rate_limit", new_callable=AsyncMock) as mock_rl,
            patch("src.api.store_message", new_callable=AsyncMock),
            patch(
                "src.api.fetch_conversation_history", new_callable=AsyncMock
            ) as mock_hist,
            patch("src.api.store_request", new_callable=AsyncMock),
            patch("src.api.agent") as mock_agent,
        ):
            mock_rl.return_value = (True, None)
            mock_hist.return_value = []

            # Mock agent.iter() context manager
            mock_run = AsyncMock()
            mock_run.__aenter__ = AsyncMock(return_value=mock_run)
            mock_run.__aexit__ = AsyncMock(return_value=False)
            mock_run.__aiter__ = AsyncMock(return_value=iter([]))
            mock_run.result = MagicMock()
            mock_run.result.new_messages_json.return_value = b"[]"
            mock_agent.iter.return_value = mock_run

            response = client.post(
                "/api/agent",
                json={
                    "query": "Hello",
                    "user_id": "user1",
                    "request_id": "req1",
                    "session_id": "user1~existing",
                },
            )

            assert response.status_code == 200
            # Should have at least a final chunk
            lines = response.text.strip().split("\n")
            last_line = json.loads(lines[-1])
            assert last_line["complete"] is True

    def test_user_id_mismatch_returns_403(self, client):
        """Should return 403 when user_id doesn't match authenticated user."""
        import src.api as api_module

        # Override verify_token to return a specific user
        api_module.app.dependency_overrides[api_module.verify_token] = lambda: {
            "id": "real-user-uuid"
        }

        response = client.post(
            "/api/agent",
            json={
                "query": "Hello",
                "user_id": "wrong-user-uuid",
                "request_id": "req1",
                "session_id": "test~session",
            },
        )

        assert response.status_code == 403

        # Restore default auth override
        api_module.app.dependency_overrides[api_module.verify_token] = lambda: {
            "id": "user1",
            "email": "test@example.com",
        }

    def test_no_token_returns_401(self, client):
        """Should reject requests without token (auth required)."""
        import src.api as api_module

        # Override verify_token to return None (no token)
        api_module.app.dependency_overrides[api_module.verify_token] = lambda: None

        response = client.post(
            "/api/agent",
            json={
                "query": "Hello",
                "user_id": "cli_user",
                "request_id": "req1",
                "session_id": "cli~session",
            },
        )

        assert response.status_code == 401

        # Restore default auth override
        api_module.app.dependency_overrides[api_module.verify_token] = lambda: {
            "id": "user1",
            "email": "test@example.com",
        }
