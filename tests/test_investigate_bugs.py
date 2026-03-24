"""Tests for scripts/investigate_bugs.py — data fetcher for bug investigation.

All external APIs (Langfuse, Supabase) are mocked. CI-safe.
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from scripts.investigate_bugs import (
    _extract_observation_errors,
    _truncate,
    build_report,
    fetch_conversation_context,
    fetch_error_traces,
    fetch_recent_conversations,
    fetch_trace_by_session,
)


# ──────────────────────────── Fixtures ────────────────────────────────────


def _make_langfuse_client(
    traces_data: list | None = None, detail_observations: list | None = None
) -> MagicMock:
    """Create a mock Langfuse client with configurable trace list/get."""
    mock = MagicMock()
    mock.auth_check.return_value = True

    if traces_data is None:
        traces_data = []

    mock.api.trace.list.return_value = SimpleNamespace(
        data=traces_data,
        meta=SimpleNamespace(total_pages=1, page=1),
    )

    if detail_observations is not None:
        mock.api.trace.get.return_value = SimpleNamespace(
            observations=detail_observations
        )
    else:
        mock.api.trace.get.return_value = SimpleNamespace(observations=[])

    return mock


def _make_trace(
    trace_id: str = "trace-1",
    session_id: str = "user1~1",
    user_id: str = "user1",
    query: str = "test query",
    latency: float = 2.0,
    timestamp: datetime | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=trace_id,
        session_id=session_id,
        user_id=user_id,
        metadata={"query": query},
        tags=["agent"],
        latency=latency,
        timestamp=timestamp or datetime.now(timezone.utc),
    )


def _make_observation(
    obs_id: str = "obs-1",
    name: str = "tool_call",
    level: str = "ERROR",
    obs_type: str = "SPAN",
    latency: float | None = None,
    status_message: str | None = "Something failed",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=obs_id,
        name=name,
        level=level,
        type=obs_type,
        latency=latency,
        status_message=status_message,
        input="input data",
        output="output data",
    )


def _make_supabase_mock() -> MagicMock:
    """Create a mock Supabase sync client."""
    return MagicMock()


# ──────────────────────────── Langfuse tests ──────────────────────────────


class TestFetchErrorTraces:
    def test_filters_by_date(self):
        """Verify from_timestamp is passed to trace.list()."""
        since = datetime(2026, 3, 24, tzinfo=timezone.utc)
        mock_lf = _make_langfuse_client()

        fetch_error_traces(mock_lf, since)

        mock_lf.api.trace.list.assert_called_once_with(
            limit=50, tags=["agent"], from_timestamp=since
        )

    def test_extracts_errors(self):
        """Traces with ERROR observations are included in output."""
        trace = _make_trace(latency=1.0)  # low latency, but has errors
        error_obs = _make_observation(level="ERROR", status_message="Crash")
        mock_lf = _make_langfuse_client(
            traces_data=[trace], detail_observations=[error_obs]
        )

        results = fetch_error_traces(
            mock_lf, datetime.now(timezone.utc) - timedelta(hours=1)
        )

        assert len(results) == 1
        assert results[0]["trace_id"] == "trace-1"
        assert len(results[0]["errors"]) == 1
        assert results[0]["errors"][0]["level"] == "ERROR"

    def test_includes_slow_traces(self):
        """Traces with latency > 15s are included even without errors."""
        trace = _make_trace(latency=20.0)
        mock_lf = _make_langfuse_client(traces_data=[trace])

        results = fetch_error_traces(
            mock_lf, datetime.now(timezone.utc) - timedelta(hours=1)
        )

        assert len(results) == 1
        assert results[0]["latency_s"] == 20.0

    def test_excludes_healthy_traces(self):
        """Traces with no errors and low latency are excluded."""
        trace = _make_trace(latency=2.0)  # healthy
        mock_lf = _make_langfuse_client(traces_data=[trace])

        results = fetch_error_traces(
            mock_lf, datetime.now(timezone.utc) - timedelta(hours=1)
        )

        assert len(results) == 0

    def test_passes_user_id_filter(self):
        """user_id kwarg is forwarded to trace.list()."""
        mock_lf = _make_langfuse_client()

        fetch_error_traces(mock_lf, datetime.now(timezone.utc), user_id="uid-42")

        call_kwargs = mock_lf.api.trace.list.call_args.kwargs
        assert call_kwargs["user_id"] == "uid-42"


class TestFetchTraceBySession:
    def test_filters_by_session_id(self):
        """Verify session_id is passed to trace.list()."""
        mock_lf = _make_langfuse_client()

        fetch_trace_by_session(mock_lf, "user1~3")

        mock_lf.api.trace.list.assert_called_once_with(session_id="user1~3", limit=10)

    def test_returns_trace_details(self):
        """Returns full trace details for session."""
        trace = _make_trace(session_id="user1~3")
        mock_lf = _make_langfuse_client(traces_data=[trace])

        results = fetch_trace_by_session(mock_lf, "user1~3")

        assert len(results) == 1
        assert results[0]["session_id"] == "user1~3"
        assert results[0]["query"] == "test query"


# ──────────────────────────── Supabase tests ──────────────────────────────


class TestFetchConversationContext:
    def test_returns_conversation_with_messages(self):
        """Fetches conversation + last 10 messages."""
        mock_sb = _make_supabase_mock()

        # conversations query chain
        conv_chain = MagicMock()
        conv_chain.execute.return_value = MagicMock(
            data=[
                {
                    "session_id": "u1~1",
                    "user_id": "u1",
                    "title": "Mon plan repas",
                    "created_at": "2026-03-24T10:00:00Z",
                    "last_message_at": "2026-03-24T14:00:00Z",
                }
            ]
        )

        # messages query chain
        msg_chain = MagicMock()
        msg_chain.execute.return_value = MagicMock(
            data=[
                {
                    "message": {"type": "ai", "content": "Salut!"},
                    "created_at": "2026-03-24T10:01:00Z",
                },
                {
                    "message": {"type": "human", "content": "Bonjour"},
                    "created_at": "2026-03-24T10:00:00Z",
                },
            ]
        )

        # Route .table() calls to appropriate chains
        def table_router(name):
            mock_table = MagicMock()
            if name == "conversations":
                mock_table.select.return_value.eq.return_value = conv_chain
            elif name == "messages":
                mock_table.select.return_value.eq.return_value.order.return_value.limit.return_value = msg_chain
            return mock_table

        mock_sb.table.side_effect = table_router

        result = fetch_conversation_context(mock_sb, "u1~1")

        assert result is not None
        assert result["session_id"] == "u1~1"
        assert len(result["messages"]) == 2
        assert result["messages"][0]["type"] == "human"

    def test_returns_none_for_missing_session(self):
        """Returns None when conversation not found."""
        mock_sb = _make_supabase_mock()
        conv_chain = MagicMock()
        conv_chain.execute.return_value = MagicMock(data=[])

        mock_table = MagicMock()
        mock_table.select.return_value.eq.return_value = conv_chain
        mock_sb.table.return_value = mock_table

        result = fetch_conversation_context(mock_sb, "nonexistent~1")

        assert result is None


class TestFetchRecentConversations:
    def test_filters_by_time(self):
        """Fetches conversations with last_message_at >= since."""
        mock_sb = _make_supabase_mock()

        # conversations chain
        conv_chain = MagicMock()
        conv_chain.execute.return_value = MagicMock(
            data=[
                {
                    "session_id": "u1~1",
                    "user_id": "u1",
                    "title": "Test",
                    "created_at": "2026-03-24T10:00:00Z",
                    "last_message_at": "2026-03-24T14:00:00Z",
                }
            ]
        )

        # messages chains (last msg + count)
        last_msg_chain = MagicMock()
        last_msg_chain.execute.return_value = MagicMock(
            data=[{"message": {"type": "ai", "content": "Done"}}]
        )

        count_chain = MagicMock()
        count_chain.execute.return_value = MagicMock(data=[], count=5)

        call_count = [0]

        def table_router(name):
            mock_table = MagicMock()
            if name == "conversations":
                mock_table.select.return_value.gte.return_value.order.return_value.limit.return_value = conv_chain
            elif name == "messages":
                call_count[0] += 1
                if call_count[0] % 2 == 1:
                    # First messages call: last message
                    mock_table.select.return_value.eq.return_value.order.return_value.limit.return_value = last_msg_chain
                else:
                    # Second messages call: count
                    mock_table.select.return_value.eq.return_value = count_chain
            return mock_table

        mock_sb.table.side_effect = table_router

        since = datetime(2026, 3, 24, tzinfo=timezone.utc)
        results = fetch_recent_conversations(mock_sb, since)

        assert len(results) == 1
        assert results[0]["session_id"] == "u1~1"
        assert results[0]["last_message_type"] == "ai"


# ──────────────────────────── Report tests ────────────────────────────────


class TestBuildReport:
    def test_structure_with_both_sources(self):
        """Report includes both data sources when provided."""
        langfuse_data = [{"trace_id": "t1", "errors": []}]
        supabase_data = {"conversations": [{"session_id": "u1~1"}]}

        report = build_report(langfuse_data, supabase_data)

        assert "generated_at" in report
        assert report["data_sources"] == ["langfuse", "supabase"]
        assert report["langfuse"]["traces_scanned"] == 1
        assert len(report["supabase"]["conversations"]) == 1

    def test_langfuse_only(self):
        """Report works with only Langfuse data."""
        report = build_report([{"trace_id": "t1"}], None)

        assert report["data_sources"] == ["langfuse"]
        assert report["langfuse"] is not None
        assert report["supabase"] is None

    def test_supabase_only(self):
        """Report works with only Supabase data."""
        report = build_report(None, {"conversations": []})

        assert report["data_sources"] == ["supabase"]
        assert report["langfuse"] is None
        assert report["supabase"] is not None

    def test_empty_report(self):
        """No data = valid empty report, not crash."""
        report = build_report(None, None)

        assert report["data_sources"] == []
        assert report["langfuse"] is None
        assert report["supabase"] is None
        assert "generated_at" in report


# ──────────────────────────── Edge case tests ─────────────────────────────


class TestGracefulFailures:
    def test_graceful_langfuse_failure(self):
        """_get_langfuse_client returns None on import failure."""
        with patch.dict(sys.modules, {"langfuse": None}):
            from scripts.investigate_bugs import _get_langfuse_client

            result = _get_langfuse_client()
            assert result is None

    def test_main_no_flags(self, capsys):
        """Running main() with no flags outputs valid empty JSON report."""
        from scripts.investigate_bugs import main

        with patch("sys.argv", ["investigate_bugs.py", "--format", "json"]):
            main()

        output = capsys.readouterr().out
        report = json.loads(output)
        assert report["data_sources"] == []
        assert report["langfuse"] is None
        assert report["supabase"] is None


class TestHelpers:
    def test_truncate_short(self):
        assert _truncate("hello", 10) == "hello"

    def test_truncate_long(self):
        result = _truncate("a" * 300, 200)
        assert len(result) == 203  # 200 + "..."
        assert result.endswith("...")

    def test_truncate_none(self):
        assert _truncate(None) is None

    def test_extract_errors_filters_levels(self):
        """Only ERROR and WARNING observations are extracted."""
        obs = [
            _make_observation(obs_id="1", level="ERROR"),
            _make_observation(obs_id="2", level="DEFAULT"),
            _make_observation(obs_id="3", level="WARNING"),
        ]

        errors = _extract_observation_errors(obs)

        assert len(errors) == 2
        assert errors[0]["level"] == "ERROR"
        assert errors[1]["level"] == "WARNING"
