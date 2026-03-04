"""FastAPI backend for AI Nutrition Assistant.

Streaming agent endpoint with NDJSON responses, conversation management,
rate limiting, and JWT authentication via Supabase Auth.

Usage:
    uvicorn src.api:app --port 8001 --reload
    python -m src api
"""

import asyncio
import json
import logging
import os
import re
from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv
import httpx
from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pathlib import Path
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.messages import PartDeltaEvent, PartStartEvent, TextPartDelta

from src.agent import agent, create_agent_deps, get_model
from src.clients import get_memory_client, get_supabase_client
from src.ui_components import extract_ui_components
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


security = HTTPBearer(auto_error=False)


async def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
) -> dict[str, Any] | None:
    """Verify Supabase JWT by calling the Auth API.

    Returns the user dict (with 'id' field) or None if no token provided.
    Raises HTTPException 401 if token is invalid or expired.
    """
    if not credentials:
        return None

    token = credentials.credentials
    supabase_url = os.getenv("SUPABASE_URL", "")
    service_key = os.getenv("SUPABASE_SERVICE_KEY", "")

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{supabase_url}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": service_key,
            },
        )

    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Token invalide ou expiré")

    return response.json()


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


class DailyLogCreate(BaseModel):
    user_id: str
    log_date: str | None = None
    meal_type: str
    food_name: str
    quantity: float = 1
    unit: str = "portion"
    calories: float = 0
    protein_g: float = 0
    carbs_g: float = 0
    fat_g: float = 0
    source: str = "openfoodfacts"
    meal_plan_id: str | None = None


class DailyLogUpdate(BaseModel):
    meal_type: str | None = None
    food_name: str | None = None
    quantity: float | None = None
    unit: str | None = None
    calories: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    source: str | None = None
    meal_plan_id: str | None = None


class FavoriteCreate(BaseModel):
    user_id: str
    recipe_id: str
    notes: str | None = None


class ShoppingListUpdate(BaseModel):
    title: str | None = None
    items: list[dict[str, Any]] | None = None


# =============================================================================
# Endpoints
# =============================================================================


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Service health check."""
    return {"status": "healthy", "service": "ai-nutrition-api"}


@app.get("/api/conversations")
async def list_conversations(
    user_id: str,
    auth_user: dict[str, Any] | None = Depends(verify_token),
) -> list[dict[str, Any]]:
    """List conversations for a user.

    Args:
        user_id: User ID to list conversations for
        auth_user: Authenticated user from JWT (injected by Depends)
    """
    if auth_user and auth_user.get("id") != user_id:
        raise HTTPException(
            status_code=403, detail="user_id does not match authenticated user"
        )
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
async def agent_endpoint(
    request: AgentRequest,
    auth_user: dict[str, Any] | None = Depends(verify_token),
):
    """Main streaming agent endpoint.

    Accepts a user query, runs the agent, and streams NDJSON chunks.
    Each chunk: {"text": "accumulated_response"}
    Final chunk adds: {"session_id": "...", "conversation_title": "...", "complete": true}
    """
    try:
        # Verify user_id matches the authenticated user
        if auth_user and auth_user.get("id") != request.user_id:
            raise HTTPException(
                status_code=403,
                detail="user_id does not match authenticated user",
            )

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
            pydantic_messages = convert_history_to_pydantic_format(conversation_history)
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
                    logger.info(f"mem0 memories injected: {memories_str}")
            except Exception as e:
                logger.warning(f"Could not load memories: {e}")

        # Fire-and-forget background tasks
        asyncio.create_task(
            store_request(supabase, request.request_id, request.user_id, request.query)
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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing request: {e}", exc_info=True)
        return StreamingResponse(
            _stream_error(f"Error: {e}", request.session_id),
            media_type="text/plain",
        )


@app.get("/api/meal-plans/{plan_id}")
async def get_meal_plan(
    plan_id: str,
    auth_user: dict[str, Any] | None = Depends(verify_token),
) -> dict[str, Any]:
    """Fetch a stored meal plan by ID for visual rendering."""
    if not auth_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Validate UUID format to reject junk early
    if not re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        plan_id,
        re.IGNORECASE,
    ):
        raise HTTPException(status_code=400, detail="Invalid plan ID format")

    user_id = auth_user["id"]
    result = (
        supabase.table("meal_plans").select("*").eq("id", plan_id).single().execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Meal plan not found")

    if result.data.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    return result.data


@app.get("/api/meal-plans")
async def list_meal_plans(
    user_id: str,
    auth_user: dict[str, Any] | None = Depends(verify_token),
) -> list[dict[str, Any]]:
    """List meal plans for a user (metadata only, no plan_data blob)."""
    if not auth_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if auth_user.get("id") != user_id:
        raise HTTPException(status_code=403, detail="user_id does not match authenticated user")

    result = (
        supabase.table("meal_plans")
        .select("id, user_id, week_start, target_calories_daily, target_protein_g, target_carbs_g, target_fat_g, notes, created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )
    return result.data or []


# =============================================================================
# Daily Food Log
# =============================================================================


@app.get("/api/daily-log")
async def get_daily_log(
    user_id: str,
    date: str,
    auth_user: dict[str, Any] | None = Depends(verify_token),
) -> list[dict[str, Any]]:
    """Get food log entries for a user on a specific date."""
    if not auth_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if auth_user.get("id") != user_id:
        raise HTTPException(status_code=403, detail="user_id does not match authenticated user")

    result = (
        supabase.table("daily_food_log")
        .select("*")
        .eq("user_id", user_id)
        .eq("log_date", date)
        .order("created_at", desc=False)
        .execute()
    )
    return result.data or []


@app.post("/api/daily-log")
async def create_daily_log(
    body: DailyLogCreate,
    auth_user: dict[str, Any] | None = Depends(verify_token),
) -> dict[str, Any]:
    """Create a new food log entry."""
    if not auth_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if auth_user.get("id") != body.user_id:
        raise HTTPException(status_code=403, detail="user_id does not match authenticated user")

    row = body.model_dump(exclude_none=True)
    result = supabase.table("daily_food_log").insert(row).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create log entry")
    return result.data[0]


@app.put("/api/daily-log/{entry_id}")
async def update_daily_log(
    entry_id: str,
    body: DailyLogUpdate,
    auth_user: dict[str, Any] | None = Depends(verify_token),
) -> dict[str, Any]:
    """Update a food log entry (partial update)."""
    if not auth_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Verify ownership
    existing = supabase.table("daily_food_log").select("user_id").eq("id", entry_id).single().execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Log entry not found")
    if existing.data.get("user_id") != auth_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates["updated_at"] = "now()"
    result = supabase.table("daily_food_log").update(updates).eq("id", entry_id).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to update log entry")
    return result.data[0]


@app.delete("/api/daily-log/{entry_id}")
async def delete_daily_log(
    entry_id: str,
    auth_user: dict[str, Any] | None = Depends(verify_token),
) -> dict[str, str]:
    """Delete a food log entry."""
    if not auth_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Verify ownership
    existing = supabase.table("daily_food_log").select("user_id").eq("id", entry_id).single().execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Log entry not found")
    if existing.data.get("user_id") != auth_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    supabase.table("daily_food_log").delete().eq("id", entry_id).execute()
    return {"status": "deleted"}


# =============================================================================
# Favorite Recipes
# =============================================================================


@app.get("/api/favorites")
async def list_favorites(
    user_id: str,
    auth_user: dict[str, Any] | None = Depends(verify_token),
) -> list[dict[str, Any]]:
    """List favorite recipes for a user, with joined recipe data."""
    if not auth_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if auth_user.get("id") != user_id:
        raise HTTPException(status_code=403, detail="user_id does not match authenticated user")

    result = (
        supabase.table("favorite_recipes")
        .select("*, recipes(*)")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


@app.post("/api/favorites")
async def add_favorite(
    body: FavoriteCreate,
    auth_user: dict[str, Any] | None = Depends(verify_token),
) -> dict[str, Any]:
    """Add a recipe to favorites."""
    if not auth_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if auth_user.get("id") != body.user_id:
        raise HTTPException(status_code=403, detail="user_id does not match authenticated user")

    row = body.model_dump(exclude_none=True)
    result = supabase.table("favorite_recipes").insert(row).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to add favorite")
    return result.data[0]


@app.delete("/api/favorites/{favorite_id}")
async def remove_favorite(
    favorite_id: str,
    auth_user: dict[str, Any] | None = Depends(verify_token),
) -> dict[str, str]:
    """Remove a recipe from favorites."""
    if not auth_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    existing = supabase.table("favorite_recipes").select("user_id").eq("id", favorite_id).single().execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Favorite not found")
    if existing.data.get("user_id") != auth_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    supabase.table("favorite_recipes").delete().eq("id", favorite_id).execute()
    return {"status": "deleted"}


# =============================================================================
# Shopping Lists
# =============================================================================


@app.get("/api/shopping-lists")
async def list_shopping_lists(
    user_id: str,
    auth_user: dict[str, Any] | None = Depends(verify_token),
) -> list[dict[str, Any]]:
    """List all shopping lists for a user."""
    if not auth_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if auth_user.get("id") != user_id:
        raise HTTPException(status_code=403, detail="user_id does not match authenticated user")

    result = (
        supabase.table("shopping_lists")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


@app.get("/api/shopping-lists/{list_id}")
async def get_shopping_list(
    list_id: str,
    auth_user: dict[str, Any] | None = Depends(verify_token),
) -> dict[str, Any]:
    """Get a single shopping list with items."""
    if not auth_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    result = supabase.table("shopping_lists").select("*").eq("id", list_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Shopping list not found")
    if result.data.get("user_id") != auth_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    return result.data


@app.put("/api/shopping-lists/{list_id}")
async def update_shopping_list(
    list_id: str,
    body: ShoppingListUpdate,
    auth_user: dict[str, Any] | None = Depends(verify_token),
) -> dict[str, Any]:
    """Update a shopping list (e.g., check off items, rename)."""
    if not auth_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    existing = supabase.table("shopping_lists").select("user_id").eq("id", list_id).single().execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Shopping list not found")
    if existing.data.get("user_id") != auth_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates["updated_at"] = "now()"
    result = supabase.table("shopping_lists").update(updates).eq("id", list_id).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to update shopping list")
    return result.data[0]


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
    ui_components: list[dict[str, Any]] = []

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

        # Extract UI components from agent response
        cleaned_text, ui_components = extract_ui_components(full_response)
        if ui_components:
            full_response = cleaned_text
            for comp in ui_components:
                yield (
                    json.dumps({"type": "ui_component", **comp}).encode("utf-8") + b"\n"
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
                ui_components=ui_components if ui_components else None,
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
    if ui_components:
        final_data["ui_components"] = ui_components

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
