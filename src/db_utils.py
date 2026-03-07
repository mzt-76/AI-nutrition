"""Database utility functions for the Agent API.

Conversation/message management, rate limiting, and session ID generation.
Adapted from course db_utils.py with project conventions:
- logging instead of print()
- No HTTPException (API layer handles errors)
- result.output not result.data (pydantic-ai 1.39.0)
"""

import logging
import random
import string
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter
from supabase import Client

logger = logging.getLogger(__name__)


async def fetch_conversation_history(
    supabase: Client, session_id: str, limit: int = 10
) -> list[dict[str, Any]]:
    """Fetch the most recent conversation history for a session.

    Args:
        supabase: Supabase client
        session_id: Session ID to fetch history for
        limit: Maximum number of messages to return

    Returns:
        List of message dicts in chronological order

    Raises:
        Exception: On database errors (caller handles)
    """
    response = (
        supabase.table("messages")
        .select("*")
        .eq("session_id", session_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    # Reverse to get chronological order
    messages: list[dict[str, Any]] = response.data[::-1]
    return messages


async def create_conversation(
    supabase: Client, user_id: str, session_id: str
) -> dict[str, Any]:
    """Create a new conversation record in the database.

    Args:
        supabase: Supabase client
        user_id: The user ID
        session_id: The session ID

    Returns:
        The created conversation record

    Raises:
        ValueError: If creation fails
    """
    response = (
        supabase.table("conversations")
        .insert({"user_id": user_id, "session_id": session_id})
        .execute()
    )

    if response.data and len(response.data) > 0:
        return response.data[0]
    raise ValueError("Failed to create conversation record")


async def update_conversation_title(
    supabase: Client, session_id: str, title: str
) -> dict[str, Any]:
    """Update the title of a conversation.

    Args:
        supabase: Supabase client
        session_id: The conversation session ID
        title: The new title

    Returns:
        The updated conversation record

    Raises:
        ValueError: If update fails
    """
    response = (
        supabase.table("conversations")
        .update({"title": title})
        .eq("session_id", session_id)
        .execute()
    )

    if response.data and len(response.data) > 0:
        return response.data[0]
    raise ValueError("Failed to update conversation title")


def generate_session_id(user_id: str) -> str:
    """Generate a unique session ID for a new conversation.

    Format: {user_id}~{random_10_chars}

    Args:
        user_id: The user ID

    Returns:
        Generated session ID
    """
    random_str = "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(10)
    )
    return f"{user_id}~{random_str}"


async def generate_conversation_title(title_agent: Agent, query: str) -> str:
    """Generate a title for a conversation based on the first user message.

    Args:
        title_agent: Pydantic AI agent for title generation
        query: The first user message

    Returns:
        Generated title string (4-6 words)
    """
    try:
        prompt = (
            "D'après le message utilisateur ci-dessous, génère un titre de conversation "
            f"de 4 à 6 mots en français.\n\n{query}"
        )
        result = await title_agent.run(prompt)
        title: str = result.output.strip()
        return title
    except Exception as e:
        logger.error(f"Error generating conversation title: {e}")
        return "Nouvelle conversation"


async def store_message(
    supabase: Client,
    session_id: str,
    message_type: str,
    content: str,
    message_data: bytes | None = None,
    data: dict[str, Any] | None = None,
    files: list[dict[str, str]] | None = None,
    ui_components: list[dict[str, Any]] | None = None,
) -> None:
    """Store a message in the Supabase messages table.

    Args:
        supabase: Supabase client
        session_id: The session ID for the conversation
        message_type: Type of message ('human' or 'ai')
        content: The message content
        message_data: Optional binary data (Pydantic AI message JSON)
        data: Optional additional data for the message
        files: Optional list of file attachments
        ui_components: Optional list of UI component dicts for generative UI
    """
    message_obj: dict[str, Any] = {"type": message_type, "content": content}
    if data:
        message_obj["data"] = data
    if files:
        message_obj["files"] = files
    if ui_components:
        message_obj["ui_components"] = ui_components

    insert_data: dict[str, Any] = {"session_id": session_id, "message": message_obj}
    if message_data:
        insert_data["message_data"] = message_data.decode("utf-8")

    supabase.table("messages").insert(insert_data).execute()


def convert_history_to_pydantic_format(
    conversation_history: list[dict[str, Any]],
) -> list[ModelMessage]:
    """Convert Supabase conversation history to Pydantic AI format.

    Only uses messages with message_data field (contains serialized ModelMessages).

    Args:
        conversation_history: List of message dicts from database

    Returns:
        List of ModelMessage objects for agent message_history
    """
    messages: list[ModelMessage] = []

    for msg in conversation_history:
        if msg.get("message_data"):
            try:
                messages.extend(
                    ModelMessagesTypeAdapter.validate_json(msg["message_data"])
                )
            except Exception as e:
                logger.warning(f"Error parsing message_data: {e}")
                continue

    return messages


async def check_rate_limit(
    supabase: Client,
    user_id: str,
    per_minute: int = 10,
    per_day: int = 100,
) -> tuple[bool, str | None]:
    """Check per-minute and daily rate limits.

    Args:
        supabase: Supabase client
        user_id: User ID to check
        per_minute: Maximum requests allowed per minute
        per_day: Maximum requests allowed per day

    Returns:
        Tuple of (allowed, error_message). If allowed, error_message is None.
    """
    try:
        now = datetime.now(timezone.utc)
        one_minute_ago = (now - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # Per-minute check
        minute_resp = (
            supabase.table("requests")
            .select("*", count="exact")
            .eq("user_id", user_id)
            .gte("timestamp", one_minute_ago)
            .execute()
        )
        minute_count: int = minute_resp.count if minute_resp.count is not None else 0
        if minute_count >= per_minute:
            return (
                False,
                "Doucement ! Veuillez patienter quelques secondes avant de renvoyer un message. 🕐",
            )

        # Daily check
        day_resp = (
            supabase.table("requests")
            .select("*", count="exact")
            .eq("user_id", user_id)
            .gte("timestamp", start_of_day)
            .execute()
        )
        day_count: int = day_resp.count if day_resp.count is not None else 0
        if day_count >= per_day:
            return (
                False,
                "Vous avez atteint votre limite de messages pour aujourd'hui. Revenez demain pour continuer ! 🌅",
            )

        return True, None
    except Exception as e:
        logger.error(f"Error checking rate limit: {e}")
        return True, None


async def store_request(
    supabase: Client, request_id: str, user_id: str, query: str
) -> None:
    """Store a request in the requests table for rate limiting.

    Args:
        supabase: Supabase client
        request_id: Unique request ID
        user_id: User ID
        query: User's query
    """
    try:
        supabase.table("requests").insert(
            {
                "id": request_id,
                "user_id": user_id,
                "user_query": query,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()
    except Exception as e:
        logger.error(f"Error storing request: {e}")
