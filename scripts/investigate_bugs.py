"""Fetch diagnostic data from Langfuse and Supabase for bug investigation.

Queries Langfuse API for error traces, high-latency spans, and tool failures.
Queries Supabase conversations/messages for related chat context.
Both data sources are opt-in via CLI flags.
Outputs structured JSON to stdout for Claude Code trigger to analyze.

LLM-free (rule 10) — uses only langfuse SDK (query API), src.clients, stdlib.

Usage:
    PYTHONPATH=. python scripts/investigate_bugs.py --langfuse --hours 24
    PYTHONPATH=. python scripts/investigate_bugs.py --supabase --session-id "abc~1"
    PYTHONPATH=. python scripts/investigate_bugs.py --langfuse --supabase --hours 48
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Max traces to fetch full details for (avoid slowness)
MAX_DETAILED_TRACES = 10


# ──────────────────────────── Langfuse queries ────────────────────────────


def _get_langfuse_client():
    """Lazily import and create Langfuse client. Returns None if unavailable."""
    try:
        from langfuse import get_client

        client = get_client()
        if not client.auth_check():
            logger.warning("Langfuse auth check failed")
            return None
        return client
    except Exception as e:
        logger.warning("Langfuse unavailable: %s", e)
        return None


def _extract_observation_errors(observations: list) -> list[dict]:
    """Extract ERROR/WARNING observations from a trace's observation list."""
    errors = []
    for obs in observations:
        level = getattr(obs, "level", None) or "DEFAULT"
        if level in ("ERROR", "WARNING"):
            errors.append(
                {
                    "id": getattr(obs, "id", None),
                    "name": getattr(obs, "name", None),
                    "level": level,
                    "status_message": getattr(obs, "status_message", None),
                    "input": _truncate(getattr(obs, "input", None), 200),
                    "output": _truncate(getattr(obs, "output", None), 200),
                }
            )
    return errors


def _truncate(value, max_len: int = 200) -> str | None:
    """Truncate a value to max_len characters for readability."""
    if value is None:
        return None
    s = str(value)
    return s[:max_len] + "..." if len(s) > max_len else s


def fetch_error_traces(
    langfuse_client, since: datetime, user_id: str | None = None
) -> list[dict]:
    """Fetch traces with errors or high latency from Langfuse."""
    kwargs: dict = {
        "limit": 50,
        "tags": ["agent"],
        "from_timestamp": since,
    }
    if user_id:
        kwargs["user_id"] = user_id

    try:
        result = langfuse_client.api.trace.list(**kwargs)
    except Exception as e:
        logger.warning("Failed to list Langfuse traces: %s", e)
        return []

    traces_summary = []
    detailed_count = 0

    for trace in result.data:
        trace_id = getattr(trace, "id", None)
        latency = getattr(trace, "latency", None)
        metadata = getattr(trace, "metadata", None) or {}

        # Fetch full detail for up to MAX_DETAILED_TRACES
        errors = []
        tool_calls = []
        if detailed_count < MAX_DETAILED_TRACES and trace_id:
            try:
                detail = langfuse_client.api.trace.get(trace_id)
                observations = getattr(detail, "observations", []) or []
                errors = _extract_observation_errors(observations)
                tool_calls = [
                    {
                        "name": getattr(obs, "name", None),
                        "duration_ms": (
                            int(getattr(obs, "latency", 0) * 1000)
                            if getattr(obs, "latency", None)
                            else None
                        ),
                        "level": getattr(obs, "level", "DEFAULT"),
                    }
                    for obs in observations
                    if getattr(obs, "type", None) == "GENERATION"
                    or getattr(obs, "name", "").startswith("tool_")
                ]
                detailed_count += 1
            except Exception as e:
                logger.warning("Failed to get trace detail %s: %s", trace_id, e)

        # Include trace if it has errors OR high latency (>15s)
        has_errors = len(errors) > 0
        is_slow = latency is not None and latency > 15.0
        if has_errors or is_slow:
            traces_summary.append(
                {
                    "trace_id": trace_id,
                    "session_id": getattr(trace, "session_id", None),
                    "user_id": getattr(trace, "user_id", None),
                    "query": metadata.get("query"),
                    "timestamp": str(getattr(trace, "timestamp", None)),
                    "latency_s": latency,
                    "errors": errors,
                    "tool_calls": tool_calls,
                }
            )

    return traces_summary


def fetch_trace_by_session(langfuse_client, session_id: str) -> list[dict]:
    """Fetch trace details for a specific session_id."""
    try:
        result = langfuse_client.api.trace.list(session_id=session_id, limit=10)
    except Exception as e:
        logger.warning("Failed to list traces for session %s: %s", session_id, e)
        return []

    traces = []
    for trace in result.data:
        trace_id = getattr(trace, "id", None)
        metadata = getattr(trace, "metadata", None) or {}
        errors = []
        tool_calls = []

        if trace_id:
            try:
                detail = langfuse_client.api.trace.get(trace_id)
                observations = getattr(detail, "observations", []) or []
                errors = _extract_observation_errors(observations)
                tool_calls = [
                    {
                        "name": getattr(obs, "name", None),
                        "duration_ms": (
                            int(getattr(obs, "latency", 0) * 1000)
                            if getattr(obs, "latency", None)
                            else None
                        ),
                        "level": getattr(obs, "level", "DEFAULT"),
                    }
                    for obs in observations
                ]
            except Exception as e:
                logger.warning("Failed to get trace detail %s: %s", trace_id, e)

        traces.append(
            {
                "trace_id": trace_id,
                "session_id": getattr(trace, "session_id", None),
                "user_id": getattr(trace, "user_id", None),
                "query": metadata.get("query"),
                "timestamp": str(getattr(trace, "timestamp", None)),
                "latency_s": getattr(trace, "latency", None),
                "errors": errors,
                "tool_calls": tool_calls,
            }
        )

    return traces


# ──────────────────────────── Supabase queries ────────────────────────────


def fetch_conversation_context(supabase, session_id: str) -> dict | None:
    """Fetch conversation + last 10 messages for a given session_id."""
    conv_result = (
        supabase.table("conversations")
        .select("session_id, user_id, title, created_at, last_message_at")
        .eq("session_id", session_id)
        .execute()
    )
    if not conv_result.data:
        logger.info("No conversation found for session_id=%s", session_id)
        return None

    conv = conv_result.data[0]

    msg_result = (
        supabase.table("messages")
        .select("message, created_at")
        .eq("session_id", session_id)
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    )

    messages = []
    for row in reversed(msg_result.data):
        msg = row.get("message", {})
        messages.append(
            {
                "type": msg.get("type"),
                "content": _truncate(msg.get("content"), 500),
                "created_at": row.get("created_at"),
            }
        )

    return {
        "session_id": conv["session_id"],
        "user_id": str(conv.get("user_id")),
        "title": conv.get("title"),
        "created_at": str(conv.get("created_at")),
        "last_message_at": str(conv.get("last_message_at")),
        "messages": messages,
    }


def fetch_recent_conversations(supabase, since: datetime) -> list[dict]:
    """Fetch conversations in time window with basic stats."""
    since_iso = since.isoformat()
    conv_result = (
        supabase.table("conversations")
        .select("session_id, user_id, title, created_at, last_message_at")
        .gte("last_message_at", since_iso)
        .order("last_message_at", desc=True)
        .limit(50)
        .execute()
    )

    conversations = []
    for conv in conv_result.data:
        sid = conv["session_id"]
        # Count messages and get last message type
        msg_result = (
            supabase.table("messages")
            .select("message")
            .eq("session_id", sid)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        count_result = (
            supabase.table("messages")
            .select("id", count="exact")
            .eq("session_id", sid)
            .execute()
        )

        last_msg_type = None
        if msg_result.data:
            last_msg = msg_result.data[0].get("message", {})
            last_msg_type = last_msg.get("type")

        conversations.append(
            {
                "session_id": sid,
                "user_id": str(conv.get("user_id")),
                "title": conv.get("title"),
                "message_count": count_result.count if count_result.count else 0,
                "last_message_type": last_msg_type,
                "created_at": str(conv.get("created_at")),
                "last_message_at": str(conv.get("last_message_at")),
            }
        )

    return conversations


# ──────────────────────────── Report building ─────────────────────────────


def build_report(
    langfuse_data: list[dict] | None,
    supabase_data: dict | None,
) -> dict:
    """Combine available data into a structured diagnostic report."""
    data_sources = []
    if langfuse_data is not None:
        data_sources.append("langfuse")
    if supabase_data is not None:
        data_sources.append("supabase")

    report: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_sources": data_sources,
    }

    if langfuse_data is not None:
        report["langfuse"] = {
            "traces_scanned": len(langfuse_data),
            "error_traces": langfuse_data,
        }
    else:
        report["langfuse"] = None

    if supabase_data is not None:
        report["supabase"] = supabase_data
    else:
        report["supabase"] = None

    return report


# ──────────────────────────── CLI ─────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch bug investigation data from Langfuse and/or Supabase"
    )
    parser.add_argument("--langfuse", action="store_true", help="Query Langfuse traces")
    parser.add_argument(
        "--supabase", action="store_true", help="Query Supabase conversations"
    )
    parser.add_argument(
        "--hours", type=int, default=24, help="Look back N hours (default: 24)"
    )
    parser.add_argument("--session-id", help="Investigate a specific session")
    parser.add_argument("--user-id", help="Filter by user_id")
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="Output format",
    )
    args = parser.parse_args()

    since = datetime.now(timezone.utc) - timedelta(hours=args.hours)
    langfuse_data = None
    supabase_data = None

    if args.langfuse:
        client = _get_langfuse_client()
        if client:
            if args.session_id:
                langfuse_data = fetch_trace_by_session(client, args.session_id)
            else:
                langfuse_data = fetch_error_traces(client, since, args.user_id)
        else:
            logger.warning("Langfuse requested but unavailable — skipping")

    if args.supabase:
        from src.clients import get_supabase_client

        sb = get_supabase_client()
        if args.session_id:
            conv = fetch_conversation_context(sb, args.session_id)
            supabase_data = {"conversations": [conv] if conv else []}
        else:
            convs = fetch_recent_conversations(sb, since)
            supabase_data = {"conversations": convs}

    report = build_report(langfuse_data, supabase_data)
    json.dump(report, sys.stdout, indent=2, default=str)


if __name__ == "__main__":
    main()
