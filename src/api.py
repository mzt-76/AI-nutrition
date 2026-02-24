"""FastAPI backend for AI Nutrition Assistant.

Streaming agent endpoint with NDJSON responses, conversation management,
and rate limiting. Auth is NOT implemented yet — user_id comes from request body.

Usage:
    uvicorn src.api:app --port 8001 --reload
    python -m src api
"""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pathlib import Path
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.messages import PartDeltaEvent, PartStartEvent, TextPartDelta

from src.agent import agent, create_agent_deps, get_model
from src.clients import get_memory_client, get_supabase_client
from src.db_utils import (
    check_rate_limit,
    convert_history_to_pydantic_format,
    create_conversation,
    fetch_conversation_history,
    generate_conversation_title,
    generate_session_id,
    store_message,
    store_request,
    update_conversation_title,
)

# Load environment variables
project_root = Path(__file__).resolve().parent.parent
load_dotenv(project_root / ".env", override=True)

logger = logging.getLogger(__name__)

# Global clients initialized in lifespan
supabase: Any = None
title_agent: Any = None
mem0_client: Any = None


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    """Initialize and clean up global clients."""
    global supabase, title_agent, mem0_client

    supabase = get_supabase_client()

    # Title agent uses MEM0_LLM_CHOICE (cheap/fast model for 4-6 word titles).
    # We go through get_model() so it picks up LLM_API_KEY and LLM_BASE_URL.
    original_choice = os.getenv("LLM_CHOICE")
    os.environ["LLM_CHOICE"] = os.getenv("MEM0_LLM_CHOICE", "gpt-4o-mini")
    title_agent = Agent(model=get_model())
    if original_choice:
        os.environ["LLM_CHOICE"] = original_choice
    else:
        del os.environ["LLM_CHOICE"]

    try:
        mem0_client = get_memory_client()
        logger.info("mem0 client initialized")
    except Exception as e:
        logger.warning(f"mem0 not available: {e}")
        mem0_client = None

    logger.info("API startup complete")
    yield
    logger.info("API shutdown")


app = FastAPI(
    title="AI Nutrition Assistant API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — configurable via environment
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# TODO: Wire verify_token() when auth module is implemented.
# For now, user_id is trusted from request body.
async def verify_token() -> dict[str, Any]:
    """Placeholder for JWT verification. Returns empty dict (no auth yet)."""
    return {}


# =============================================================================
# Request / Response models
# =============================================================================


class FileAttachment(BaseModel):
    file_name: str
    content: str  # Base64 encoded
    mime_type: str


class AgentRequest(BaseModel):
    query: str
    user_id: str
    request_id: str
    session_id: str = ""
    files: list[FileAttachment] | None = None


# =============================================================================
# Endpoints
# =============================================================================


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Service health check."""
    return {"status": "healthy", "service": "ai-nutrition-api"}


@app.get("/api/conversations")
async def list_conversations(user_id: str) -> list[dict[str, Any]]:
    """List conversations for a user.

    Args:
        user_id: User ID to list conversations for
    """
    response = (
        supabase.table("conversations")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )
    return response.data or []


@app.post("/api/agent")
async def agent_endpoint(request: AgentRequest):
    """Main streaming agent endpoint.

    Accepts a user query, runs the agent, and streams NDJSON chunks.
    Each chunk: {"text": "accumulated_response"}
    Final chunk adds: {"session_id": "...", "conversation_title": "...", "complete": true}
    """
    try:
        # Rate limit check
        rate_limit_ok = await check_rate_limit(supabase, request.user_id)
        if not rate_limit_ok:
            return StreamingResponse(
                _stream_error(
                    "Rate limit exceeded. Please try again later.", request.session_id
                ),
                media_type="text/plain",
                status_code=429,
            )

        # Session management
        session_id = request.session_id
        conversation_record = None

        if not session_id:
            session_id = generate_session_id(request.user_id)
            try:
                conversation_record = await create_conversation(
                    supabase, request.user_id, session_id
                )
            except Exception as e:
                logger.error(f"Failed to create conversation: {e}")

        # Store user message
        file_attachments = None
        if request.files:
            file_attachments = [
                {
                    "fileName": f.file_name,
                    "content": f.content,
                    "mimeType": f.mime_type,
                }
                for f in request.files
            ]

        try:
            await store_message(
                supabase=supabase,
                session_id=session_id,
                message_type="human",
                content=request.query,
                files=file_attachments,
            )
        except Exception as e:
            logger.error(f"Failed to store user message: {e}")

        # Load conversation history
        try:
            conversation_history = await fetch_conversation_history(
                supabase, session_id
            )
            pydantic_messages = convert_history_to_pydantic_format(
                conversation_history
            )
        except Exception as e:
            logger.error(f"Failed to load conversation history: {e}")
            pydantic_messages = []

        # Load mem0 memories
        memories_str = ""
        if mem0_client:
            try:
                relevant = mem0_client.search(
                    query=request.query, user_id=request.user_id, limit=3
                )
                if relevant and relevant.get("results"):
                    memories_str = "\n".join(
                        f"- {entry['memory']}" for entry in relevant["results"]
                    )
            except Exception as e:
                logger.warning(f"Could not load memories: {e}")

        # Fire-and-forget background tasks
        asyncio.create_task(
            store_request(
                supabase, request.request_id, request.user_id, request.query
            )
        )

        if mem0_client:
            try:
                memory_messages = [{"role": "user", "content": request.query}]
                mem0_client.add(memory_messages, user_id=request.user_id)
            except Exception as e:
                logger.warning(f"Could not save memory: {e}")

        title_task = None
        if conversation_record and title_agent:
            title_task = asyncio.create_task(
                generate_conversation_title(title_agent, request.query)
            )

        # Stream response
        return StreamingResponse(
            _stream_agent_response(
                request=request,
                session_id=session_id,
                pydantic_messages=pydantic_messages,
                memories_str=memories_str,
                title_task=title_task,
            ),
            media_type="text/plain",
        )

    except Exception as e:
        logger.error(f"Error processing request: {e}", exc_info=True)
        return StreamingResponse(
            _stream_error(f"Error: {e}", request.session_id),
            media_type="text/plain",
        )


async def _stream_agent_response(
    request: AgentRequest,
    session_id: str,
    pydantic_messages: list,
    memories_str: str,
    title_task: asyncio.Task | None,
):
    """Stream agent response as NDJSON chunks."""
    agent_deps = create_agent_deps(memories=memories_str, user_id=request.user_id)
    full_response = ""

    try:
        async with agent.iter(
            request.query,
            deps=agent_deps,
            message_history=pydantic_messages,
        ) as run:
            async for node in run:
                if Agent.is_model_request_node(node):
                    async with node.stream(run.ctx) as request_stream:
                        async for event in request_stream:
                            if (
                                isinstance(event, PartStartEvent)
                                and event.part.part_kind == "text"
                            ):
                                full_response += event.part.content
                                yield (
                                    json.dumps({"text": full_response}).encode("utf-8")
                                    + b"\n"
                                )
                            elif isinstance(event, PartDeltaEvent) and isinstance(
                                event.delta, TextPartDelta
                            ):
                                full_response += event.delta.content_delta
                                yield (
                                    json.dumps({"text": full_response}).encode("utf-8")
                                    + b"\n"
                                )

        # Store AI response
        try:
            message_data = run.result.new_messages_json()
            await store_message(
                supabase=supabase,
                session_id=session_id,
                message_type="ai",
                content=full_response,
                message_data=message_data,
                data={"request_id": request.request_id},
            )
        except Exception as e:
            logger.error(f"Failed to store AI response: {e}")

    except Exception as e:
        logger.error(f"Agent streaming error: {e}", exc_info=True)
        error_text = "I apologize, but I encountered an error processing your request."
        yield json.dumps({"text": error_text}).encode("utf-8") + b"\n"
        full_response = error_text

    # Final chunk with metadata
    conversation_title = None
    if title_task:
        try:
            conversation_title = await title_task
            await update_conversation_title(supabase, session_id, conversation_title)
        except Exception as e:
            logger.error(f"Error processing title: {e}")

    final_data: dict[str, Any] = {
        "text": full_response,
        "session_id": session_id,
        "complete": True,
    }
    if conversation_title:
        final_data["conversation_title"] = conversation_title

    yield json.dumps(final_data).encode("utf-8") + b"\n"


async def _stream_error(error_message: str, session_id: str):
    """Stream an error response as NDJSON."""
    yield json.dumps({"text": error_message}).encode("utf-8") + b"\n"
    yield (
        json.dumps(
            {
                "text": error_message,
                "session_id": session_id,
                "error": error_message,
                "complete": True,
            }
        ).encode("utf-8")
        + b"\n"
    )
