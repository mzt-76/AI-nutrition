"""Unit tests for src/db_utils.py.

Deterministic tests with mocked Supabase client. No LLM calls.
"""

from unittest.mock import MagicMock

import pytest

from src.db_utils import (
    check_rate_limit,
    convert_history_to_pydantic_format,
    generate_session_id,
    store_message,
    store_request,
)


class TestGenerateSessionId:
    """Tests for session ID generation."""

    def test_format_contains_user_id_and_separator(self):
        """Session ID must follow {user_id}~{random} format."""
        session_id = generate_session_id("user123")
        assert "~" in session_id
        prefix, suffix = session_id.split("~", 1)
        assert prefix == "user123"
        assert len(suffix) == 10

    def test_random_part_is_alphanumeric_lowercase(self):
        """Random suffix should be lowercase alphanumeric."""
        session_id = generate_session_id("test")
        suffix = session_id.split("~")[1]
        assert suffix.isalnum()
        assert suffix == suffix.lower()

    def test_unique_across_calls(self):
        """Two calls should produce different session IDs."""
        id1 = generate_session_id("user1")
        id2 = generate_session_id("user1")
        assert id1 != id2


class TestCheckRateLimit:
    """Tests for rate limiting."""

    @pytest.mark.asyncio
    async def test_under_limit_returns_true(self):
        """User under rate limit should be allowed."""
        mock_supabase = MagicMock()
        mock_response = MagicMock()
        mock_response.count = 3

        mock_supabase.table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value = mock_response

        result = await check_rate_limit(mock_supabase, "user1", rate_limit=10)
        assert result is True

    @pytest.mark.asyncio
    async def test_over_limit_returns_false(self):
        """User over rate limit should be blocked."""
        mock_supabase = MagicMock()
        mock_response = MagicMock()
        mock_response.count = 15

        mock_supabase.table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value = mock_response

        result = await check_rate_limit(mock_supabase, "user1", rate_limit=10)
        assert result is False

    @pytest.mark.asyncio
    async def test_error_allows_request(self):
        """On error, should allow request (fail open)."""
        mock_supabase = MagicMock()
        mock_supabase.table.side_effect = Exception("DB down")

        result = await check_rate_limit(mock_supabase, "user1")
        assert result is True


class TestStoreMessage:
    """Tests for message storage."""

    @pytest.mark.asyncio
    async def test_inserts_basic_message(self):
        """Should insert a message with type and content."""
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.insert.return_value.execute.return_value = (
            MagicMock(data=[{"id": 1}])
        )

        await store_message(
            mock_supabase,
            session_id="test~abc123",
            message_type="human",
            content="Hello",
        )

        mock_supabase.table.assert_called_with("messages")
        call_args = mock_supabase.table.return_value.insert.call_args[0][0]
        assert call_args["session_id"] == "test~abc123"
        assert call_args["message"]["type"] == "human"
        assert call_args["message"]["content"] == "Hello"

    @pytest.mark.asyncio
    async def test_includes_message_data_when_provided(self):
        """Should include message_data as decoded string."""
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.insert.return_value.execute.return_value = (
            MagicMock(data=[{"id": 1}])
        )

        await store_message(
            mock_supabase,
            session_id="test~abc",
            message_type="ai",
            content="Response",
            message_data=b'[{"kind": "response"}]',
        )

        call_args = mock_supabase.table.return_value.insert.call_args[0][0]
        assert call_args["message_data"] == '[{"kind": "response"}]'


class TestConvertHistoryToPydanticFormat:
    """Tests for history conversion."""

    def test_skips_messages_without_message_data(self):
        """Messages without message_data should be skipped."""
        history = [
            {"id": 1, "message": {"type": "human", "content": "Hi"}},
            {"id": 2, "message": {"type": "ai", "content": "Hello"}},
        ]
        result = convert_history_to_pydantic_format(history)
        assert result == []

    def test_empty_history_returns_empty(self):
        """Empty history should return empty list."""
        result = convert_history_to_pydantic_format([])
        assert result == []

    def test_skips_invalid_message_data(self):
        """Invalid message_data should be skipped with warning."""
        history = [
            {"id": 1, "message_data": "not valid json for pydantic"},
        ]
        result = convert_history_to_pydantic_format(history)
        assert result == []


class TestStoreRequest:
    """Tests for request storage."""

    @pytest.mark.asyncio
    async def test_stores_request_data(self):
        """Should insert request with id, user_id, query, and timestamp."""
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.insert.return_value.execute.return_value = (
            MagicMock(data=[{"id": "req1"}])
        )

        await store_request(mock_supabase, "req1", "user1", "What is protein?")

        mock_supabase.table.assert_called_with("requests")
        call_args = mock_supabase.table.return_value.insert.call_args[0][0]
        assert call_args["id"] == "req1"
        assert call_args["user_id"] == "user1"
        assert call_args["user_query"] == "What is protein?"
        assert "timestamp" in call_args

    @pytest.mark.asyncio
    async def test_error_does_not_raise(self):
        """Errors should be logged, not raised."""
        mock_supabase = MagicMock()
        mock_supabase.table.side_effect = Exception("DB error")

        # Should not raise
        await store_request(mock_supabase, "req1", "user1", "test")
