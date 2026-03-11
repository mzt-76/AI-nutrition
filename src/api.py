"""FastAPI backend for AI Nutrition Assistant.

Streaming agent endpoint with NDJSON responses, conversation management,
rate limiting, and JWT authentication via Supabase Auth.

Usage:
    uvicorn src.api:app --port 8001 --reload
    python -m src api
"""

import asyncio
import base64
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import UUID as _UUID
from typing import Any

from dotenv import load_dotenv
import httpx
from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pathlib import Path
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse
from pydantic_ai import Agent, BinaryContent

from src.api_models import (
    AgentRequest,
    DailyLogCreate,
    DailyLogUpdate,
    FavoriteCreate,
    FavoriteUpdate,
    RecalculateRequest,
    RecipeCreate,
    ShoppingListCreate,
    ShoppingListUpdate,
)

from src.nutrition.calculations import (
    ACTIVITY_MULTIPLIERS,
    calculate_macros,
    calculate_protein_target,
    calculate_tdee,
    infer_goals_from_context,
    mifflin_st_jeor_bmr,
)
from src.nutrition.constants import (
    GOAL_CALORIE_ADJUSTMENTS,
    MIN_CALORIES_MEN,
    MIN_CALORIES_WOMEN,
)
from src.nutrition.validators import sanitize_user_text
from src.nutrition.openfoodfacts_client import (
    match_ingredient,
    normalize_ingredient_name,
)
from pydantic_ai.messages import PartDeltaEvent, PartStartEvent, TextPartDelta

from src.agent import agent, create_agent_deps, get_model
from src.clients import get_async_memory_client, get_async_supabase_client
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

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _log_task_exception(task: asyncio.Task) -> None:  # type: ignore[type-arg]
    """Log exceptions from fire-and-forget background tasks."""
    if task.cancelled():
        return
    if exc := task.exception():
        logger.error("Background task failed: %s", exc, exc_info=exc)


# Global clients initialized in lifespan
supabase: Any = None
title_agent: Any = None
mem0_client: Any = None
_http_client: httpx.AsyncClient | None = None


def _require_supabase() -> Any:
    """Return supabase client, raising if not yet initialized."""
    if supabase is None:
        raise RuntimeError("Supabase client not initialized — server still starting")
    return supabase


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    """Initialize and clean up global clients."""
    global supabase, title_agent, mem0_client, _http_client

    missing = [
        v
        for v in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "LLM_API_KEY")
        if not os.getenv(v)
    ]
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")

    supabase = get_async_supabase_client()

    # Title agent uses MEM0_LLM_CHOICE (cheap/fast model for 4-6 word titles).
    # We pass model_name directly to avoid mutating os.environ (race condition).
    title_model_name = os.getenv("MEM0_LLM_CHOICE", "gpt-4o-mini")
    title_agent = Agent(model=get_model(model_name=title_model_name))

    try:
        mem0_client = await get_async_memory_client()
        logger.info("mem0 async client initialized")
    except Exception as e:
        logger.warning(f"mem0 not available: {e}")
        mem0_client = None

    if not os.getenv("ANTHROPIC_API_KEY"):
        logger.warning(
            "ANTHROPIC_API_KEY not set — agent will use LLM_API_KEY fallback"
        )

    # Validate main agent model at startup
    try:
        get_model()
        logger.info("Agent model validated")
    except Exception as e:
        logger.error(f"Agent model configuration error: {e}", exc_info=True)

    _http_client = httpx.AsyncClient(
        timeout=30.0,
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    )

    logger.info("API startup complete")
    yield
    await _http_client.aclose()
    logger.info("API shutdown")


app = FastAPI(
    title="AI Nutrition Assistant API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — configurable via environment
cors_origins = os.getenv("CORS_ORIGINS", "")
_environment = os.getenv("ENVIRONMENT", "development")
if not cors_origins:
    if _environment == "production":
        raise RuntimeError(
            "CORS_ORIGINS must be set in production. "
            "Example: CORS_ORIGINS=https://myapp.example.com"
        )
    logger.warning(
        "CORS_ORIGINS not set — using localhost defaults. Set explicitly in production!"
    )
    cors_origins = "http://localhost:5173,http://localhost:3000,http://localhost:8080"
_parsed_origins = [o.strip() for o in cors_origins.split(",")]
if "*" in _parsed_origins:
    raise RuntimeError(
        "CORS_ORIGINS='*' is incompatible with allow_credentials=True. "
        "Set explicit origins (e.g. CORS_ORIGINS=https://myapp.example.com)."
    )
app.add_middleware(
    CORSMiddleware,
    allow_origins=_parsed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):  # type: ignore[override]
        response: StarletteResponse = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'none'"
        response.headers[
            "Strict-Transport-Security"
        ] = "max-age=31536000; includeSubDomains"
        return response


app.add_middleware(SecurityHeadersMiddleware)


@app.middleware("http")
async def check_supabase_initialized(request_obj, call_next):
    """Reject requests if Supabase client is not yet initialized."""
    if supabase is None and request_obj.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=503,
            content={"detail": "Service en cours de démarrage, veuillez réessayer."},
        )
    return await call_next(request_obj)


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

    if _http_client is None:
        raise RuntimeError("HTTP client not initialized")
    response = await _http_client.get(
        f"{supabase_url}/auth/v1/user",
        headers={
            "Authorization": f"Bearer {token}",
            "apikey": service_key,
        },
    )

    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Token invalide ou expiré")

    data = response.json()
    if "id" not in data:
        raise HTTPException(status_code=401, detail="Token invalide")
    return data


async def require_auth(
    auth_user: dict[str, Any] | None = Depends(verify_token),
) -> dict[str, Any]:
    """Dependency that always requires authentication. Use on all data endpoints."""
    if not auth_user:
        raise HTTPException(status_code=401, detail="Authentification requise")
    return auth_user


def _validate_uuid(value: str) -> None:
    """Raise 400 if value is not a valid UUID."""
    try:
        _UUID(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="Format d'identifiant invalide")


def _validate_session_id(value: str) -> None:
    """Raise 400 if session_id is empty or suspiciously long."""
    if not value or len(value) > 60:
        raise HTTPException(status_code=400, detail="Format de session_id invalide")


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
    auth_user: dict[str, Any] = Depends(require_auth),
) -> list[dict[str, Any]]:
    """List conversations for a user."""
    if auth_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Accès non autorisé")
    response = await (
        supabase.table("conversations")
        .select("id, session_id, title, created_at, updated_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )
    return response.data or []


@app.post("/api/agent")
async def agent_endpoint(
    request: AgentRequest,
    auth_user: dict[str, Any] = Depends(require_auth),
):
    """Main streaming agent endpoint.

    Accepts a user query, runs the agent, and streams NDJSON chunks.
    Each chunk: {"text": "accumulated_response"}
    Final chunk adds: {"session_id": "...", "conversation_title": "...", "complete": true}
    """
    try:
        if auth_user["id"] != request.user_id:
            raise HTTPException(
                status_code=403,
                detail="user_id does not match authenticated user",
            )

        # Validate file attachments (defense in depth)
        _ALLOWED_MIME_TYPES = {
            "image/jpeg",
            "image/png",
            "image/gif",
            "image/webp",
            "text/plain",
            "application/pdf",
        }
        if request.files:
            if len(request.files) > 5:
                return StreamingResponse(
                    _stream_error("Maximum 5 fichiers autorisés.", request.session_id),
                    media_type="text/plain",
                    status_code=400,
                )
            for f in request.files:
                # Pre-check: reject obviously oversized payloads before allocating memory
                # base64 expands ~4/3, so 1MB decoded ≈ 1.33MB encoded
                if len(f.content) > 1_400_000:
                    return StreamingResponse(
                        _stream_error(
                            f"Le fichier {f.file_name} dépasse 1 Mo.",
                            request.session_id,
                        ),
                        media_type="text/plain",
                        status_code=400,
                    )
                # Validate base64 is well-formed BEFORE checking size
                # (malformed base64 could bypass the size check)
                try:
                    decoded = base64.b64decode(f.content, validate=True)
                except Exception:
                    return StreamingResponse(
                        _stream_error(
                            f"Le fichier {f.file_name} est mal encodé.",
                            request.session_id,
                        ),
                        media_type="text/plain",
                        status_code=400,
                    )
                if len(decoded) > 1_000_000:  # 1MB decoded size
                    return StreamingResponse(
                        _stream_error(
                            f"Le fichier {f.file_name} dépasse 1 Mo.",
                            request.session_id,
                        ),
                        media_type="text/plain",
                        status_code=400,
                    )
                if f.mime_type not in _ALLOWED_MIME_TYPES:
                    return StreamingResponse(
                        _stream_error(
                            f"Type de fichier non supporté : {f.mime_type}",
                            request.session_id,
                        ),
                        media_type="text/plain",
                        status_code=400,
                    )

        # Sanitize user input early — before any DB write or LLM call
        try:
            sanitized_query = sanitize_user_text(request.query, 5000, "agent_query")
        except ValueError:
            return StreamingResponse(
                _stream_error("Requête invalide.", request.session_id),
                media_type="text/plain",
                status_code=400,
            )

        # Rate limit check (per-minute + daily)
        rate_limit_ok, rate_limit_msg = await check_rate_limit(
            supabase, request.user_id
        )
        if not rate_limit_ok:
            return StreamingResponse(
                _stream_error(rate_limit_msg or "Limite atteinte.", request.session_id),
                media_type="text/plain",
                status_code=429,
                headers={"Retry-After": "60"},
            )

        # Fire-and-forget request tracking (use sanitized query)
        task = asyncio.create_task(
            store_request(
                supabase, request.request_id, request.user_id, sanitized_query
            )
        )
        task.add_done_callback(_log_task_exception)

        # Session management
        session_id = request.session_id
        conversation_record = None

        if request.ephemeral:
            # Ephemeral requests get a throwaway session_id; no DB records
            session_id = session_id or generate_session_id(request.user_id)
        else:
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
                    content=sanitized_query,
                    files=file_attachments,
                )
            except Exception as e:
                logger.error(f"Failed to store user message: {e}")

        # Load conversation history + mem0 memories in parallel
        # Ephemeral requests skip history (no prior messages) and mem0
        pydantic_messages: list = []  # type: ignore[type-arg]
        memories_str = ""

        if not request.ephemeral:
            history_task = asyncio.create_task(
                fetch_conversation_history(supabase, session_id)
            )
            memory_search_task = (
                asyncio.create_task(
                    mem0_client.search(
                        query=sanitized_query,
                        user_id=request.user_id,
                        limit=3,
                    )
                )
                if mem0_client
                else None
            )

            try:
                conversation_history = await history_task
                pydantic_messages = convert_history_to_pydantic_format(
                    conversation_history
                )
            except Exception as e:
                logger.error(f"Failed to load conversation history: {e}")

            if memory_search_task:
                try:
                    relevant = await memory_search_task
                    if relevant and relevant.get("results"):
                        memories_str = "\n".join(
                            f"- {entry['memory']}" for entry in relevant["results"]
                        )
                        logger.debug(
                            "mem0 memories injected (%d entries)",
                            len(relevant["results"]),
                        )
                except Exception as e:
                    logger.warning(f"Could not load memories: {e}")

            if mem0_client:

                async def _save_memory() -> None:
                    try:
                        await mem0_client.add(
                            [{"role": "user", "content": sanitized_query}],
                            user_id=request.user_id,
                        )
                    except Exception as e:
                        logger.warning(f"Could not save memory: {e}")

                task = asyncio.create_task(_save_memory())
                task.add_done_callback(_log_task_exception)

        title_task = None
        if conversation_record and title_agent:
            title_task = asyncio.create_task(
                generate_conversation_title(title_agent, sanitized_query)
            )

        # Stream response
        return StreamingResponse(
            _stream_agent_response(
                request=request,
                session_id=session_id,
                pydantic_messages=pydantic_messages,
                memories_str=memories_str,
                title_task=title_task,
                ephemeral=request.ephemeral,
                sanitized_query=sanitized_query,
            ),
            media_type="text/plain",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing request: {e}", exc_info=True)
        return StreamingResponse(
            _stream_error(
                "Une erreur interne est survenue. Veuillez réessayer.",
                request.session_id,
            ),
            media_type="text/plain",
        )


@app.get("/api/meal-plans/{plan_id}")
async def get_meal_plan(
    plan_id: str,
    auth_user: dict[str, Any] = Depends(require_auth),
) -> dict[str, Any]:
    """Fetch a stored meal plan by ID for visual rendering."""
    _validate_uuid(plan_id)

    user_id = auth_user["id"]
    result = await (
        supabase.table("meal_plans").select("*").eq("id", plan_id).limit(1).execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Plan repas introuvable")

    if result.data[0].get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Accès non autorisé")

    return result.data[0]


@app.get("/api/meal-plans")
async def list_meal_plans(
    user_id: str,
    auth_user: dict[str, Any] = Depends(require_auth),
) -> list[dict[str, Any]]:
    """List meal plans for a user (metadata only, no plan_data blob)."""
    if auth_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Accès non autorisé")

    result = await (
        supabase.table("meal_plans")
        .select(
            "id, user_id, week_start, target_calories_daily, target_protein_g, target_carbs_g, target_fat_g, notes, created_at"
        )
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )
    return result.data or []


@app.delete("/api/meal-plans/{plan_id}")
async def delete_meal_plan(
    plan_id: str,
    auth_user: dict[str, Any] = Depends(require_auth),
) -> dict[str, str]:
    """Delete a meal plan by ID (owner only)."""
    _validate_uuid(plan_id)

    user_id = auth_user["id"]
    result = await (
        supabase.table("meal_plans")
        .select("id, user_id")
        .eq("id", plan_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Plan repas introuvable")
    if result.data[0].get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Accès non autorisé")

    try:
        await supabase.table("meal_plans").delete().eq("id", plan_id).execute()
    except Exception as e:
        logger.error(f"Erreur suppression plan repas {plan_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Erreur lors de la suppression du plan repas"
        )
    return {"status": "deleted"}


@app.delete("/api/conversations/{session_id}")
async def delete_conversation(
    session_id: str,
    auth_user: dict[str, Any] = Depends(require_auth),
) -> dict[str, str]:
    """Delete a conversation and its messages (owner only)."""
    _validate_session_id(session_id)
    user_id = auth_user["id"]
    result = await (
        supabase.table("conversations")
        .select("session_id, user_id")
        .eq("session_id", session_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Conversation introuvable")
    if result.data[0].get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Accès non autorisé")

    try:
        await supabase.table("messages").delete().eq("session_id", session_id).execute()
        await (
            supabase.table("conversations")
            .delete()
            .eq("session_id", session_id)
            .execute()
        )
    except Exception as e:
        logger.error(
            f"Erreur suppression conversation {session_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500, detail="Erreur lors de la suppression de la conversation"
        )
    return {"status": "deleted"}


# =============================================================================
# Daily Food Log
# =============================================================================


@app.get("/api/food-search")
async def food_search(
    q: str,
    quantity: float = 100,
    unit: str = "g",
    auth_user: dict[str, Any] = Depends(require_auth),
) -> dict[str, Any]:
    """Search for a food item and return its macros."""
    try:
        q = sanitize_user_text(q.strip(), 200, "food_search")
    except ValueError:
        raise HTTPException(status_code=400, detail="Requête invalide")
    if not q:
        raise HTTPException(status_code=400, detail="Le paramètre 'q' est requis")

    result = await match_ingredient(q, quantity, unit, supabase)
    if result.get("confidence", 0) == 0:
        raise HTTPException(status_code=404, detail="Aliment non trouvé")

    return result


@app.get("/api/daily-log")
async def get_daily_log(
    user_id: str,
    date: str,
    auth_user: dict[str, Any] = Depends(require_auth),
) -> list[dict[str, Any]]:
    """Get food log entries for a user on a specific date."""
    if auth_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Accès non autorisé")

    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Format de date invalide (AAAA-MM-JJ attendu)"
        )

    result = await (
        supabase.table("daily_food_log")
        .select("*")
        .eq("user_id", user_id)
        .eq("log_date", date)
        .order("created_at", desc=False)
        .limit(200)
        .execute()
    )
    return result.data or []


@app.post("/api/daily-log")
async def create_daily_log(
    body: DailyLogCreate,
    auth_user: dict[str, Any] = Depends(require_auth),
) -> dict[str, Any]:
    """Create a new food log entry."""
    if auth_user["id"] != body.user_id:
        raise HTTPException(status_code=403, detail="Accès non autorisé")

    row = body.model_dump(exclude_none=True)
    result = await supabase.table("daily_food_log").insert(row).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Impossible de créer l'entrée")
    return result.data[0]


@app.put("/api/daily-log/{entry_id}")
async def update_daily_log(
    entry_id: str,
    body: DailyLogUpdate,
    auth_user: dict[str, Any] = Depends(require_auth),
) -> dict[str, Any]:
    """Update a food log entry (partial update)."""
    _validate_uuid(entry_id)

    # Verify ownership (fetch quantity/unit too for potential macro recalc)
    existing = await (
        supabase.table("daily_food_log")
        .select("user_id, quantity, unit")
        .eq("id", entry_id)
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Entrée introuvable")
    if existing.data[0].get("user_id") != auth_user["id"]:
        raise HTTPException(status_code=403, detail="Accès non autorisé")

    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="Aucun champ à mettre à jour")

    # If food_name changed, recalculate macros via OpenFoodFacts
    if "food_name" in updates:
        qty = existing.data[0].get("quantity") or 100
        unit = existing.data[0].get("unit") or "g"
        macros = await match_ingredient(updates["food_name"], qty, unit, supabase)
        if macros.get("confidence", 0) == 0:
            raise HTTPException(
                status_code=422,
                detail="Aliment non trouvé dans la base",
            )
        updates["calories"] = round(macros["calories"], 1)
        updates["protein_g"] = round(macros["protein_g"], 1)
        updates["carbs_g"] = round(macros["carbs_g"], 1)
        updates["fat_g"] = round(macros["fat_g"], 1)

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = await (
        supabase.table("daily_food_log").update(updates).eq("id", entry_id).execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=500, detail="Impossible de mettre à jour l'entrée"
        )
    return result.data[0]


@app.delete("/api/daily-log/{entry_id}")
async def delete_daily_log(
    entry_id: str,
    auth_user: dict[str, Any] = Depends(require_auth),
) -> dict[str, str]:
    """Delete a food log entry."""
    _validate_uuid(entry_id)

    # Verify ownership
    existing = await (
        supabase.table("daily_food_log")
        .select("user_id")
        .eq("id", entry_id)
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Entrée introuvable")
    if existing.data[0].get("user_id") != auth_user["id"]:
        raise HTTPException(status_code=403, detail="Accès non autorisé")

    try:
        await supabase.table("daily_food_log").delete().eq("id", entry_id).execute()
    except Exception as e:
        logger.error(
            f"Erreur suppression entrée journal {entry_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500, detail="Erreur lors de la suppression de l'entrée"
        )
    return {"status": "deleted"}


# =============================================================================
# Favorite Recipes
# =============================================================================


@app.get("/api/favorites")
async def list_favorites(
    user_id: str,
    auth_user: dict[str, Any] = Depends(require_auth),
) -> list[dict[str, Any]]:
    """List favorite recipes for a user, with joined recipe data."""
    if auth_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Accès non autorisé")

    result = await (
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
    auth_user: dict[str, Any] = Depends(require_auth),
) -> dict[str, Any]:
    """Add a recipe to favorites."""
    if auth_user["id"] != body.user_id:
        raise HTTPException(status_code=403, detail="Accès non autorisé")

    # Return existing if already favorited (unique constraint on user_id + recipe_id)
    existing = await (
        supabase.table("favorite_recipes")
        .select("*")
        .eq("user_id", body.user_id)
        .eq("recipe_id", body.recipe_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        return existing.data[0]

    row = body.model_dump(exclude_none=True)
    result = await supabase.table("favorite_recipes").insert(row).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Impossible d'ajouter le favori")
    return result.data[0]


@app.delete("/api/favorites/{favorite_id}")
async def remove_favorite(
    favorite_id: str,
    auth_user: dict[str, Any] = Depends(require_auth),
) -> dict[str, str]:
    """Remove a recipe from favorites."""
    _validate_uuid(favorite_id)

    existing = await (
        supabase.table("favorite_recipes")
        .select("user_id")
        .eq("id", favorite_id)
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Favori introuvable")
    if existing.data[0].get("user_id") != auth_user["id"]:
        raise HTTPException(status_code=403, detail="Accès non autorisé")

    try:
        await (
            supabase.table("favorite_recipes").delete().eq("id", favorite_id).execute()
        )
    except Exception as e:
        logger.error(f"Erreur suppression favori {favorite_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Erreur lors de la suppression du favori"
        )
    return {"status": "deleted"}


@app.patch("/api/favorites/{favorite_id}")
async def update_favorite(
    favorite_id: str,
    body: FavoriteUpdate,
    auth_user: dict[str, Any] = Depends(require_auth),
) -> dict[str, Any]:
    """Update a favorite's notes."""
    _validate_uuid(favorite_id)

    existing = await (
        supabase.table("favorite_recipes")
        .select("user_id")
        .eq("id", favorite_id)
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Favori introuvable")
    if existing.data[0].get("user_id") != auth_user["id"]:
        raise HTTPException(status_code=403, detail="Accès non autorisé")

    result = await (
        supabase.table("favorite_recipes")
        .update({"notes": body.notes})
        .eq("id", favorite_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=500, detail="Erreur lors de la mise à jour du favori"
        )
    return result.data[0]


@app.get("/api/favorites/check")
async def check_favorite(
    user_id: str,
    recipe_id: str,
    auth_user: dict[str, Any] = Depends(require_auth),
) -> dict[str, Any]:
    """Check if a recipe is already favorited by a user."""
    _validate_uuid(recipe_id)
    if auth_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Accès non autorisé")

    result = await (
        supabase.table("favorite_recipes")
        .select("id, notes")
        .eq("user_id", user_id)
        .eq("recipe_id", recipe_id)
        .limit(1)
        .execute()
    )
    if result.data:
        return {
            "is_favorite": True,
            "favorite_id": result.data[0]["id"],
            "notes": result.data[0].get("notes"),
        }
    return {"is_favorite": False, "favorite_id": None, "notes": None}


# =============================================================================
# Recipes
# =============================================================================


@app.post("/api/recipes")
async def upsert_recipe(
    body: RecipeCreate,
    auth_user: dict[str, Any] = Depends(require_auth),
) -> dict[str, Any]:
    """Upsert a recipe by normalized name. Returns existing if found."""

    # Atwater macro validation — reject recipes with incoherent macros
    cal = body.calories_per_serving
    atwater = body.protein_g_per_serving * 4 + body.carbs_g_per_serving * 4 + body.fat_g_per_serving * 9
    if cal > 5 and atwater > 0:
        discrepancy = abs(cal - atwater) / max(cal, atwater)
        if discrepancy > 0.30:
            raise HTTPException(
                status_code=422,
                detail="Données nutritionnelles incohérentes",
            )

    name_norm = normalize_ingredient_name(body.name)
    meal_type_norm = body.meal_type.lower().replace("é", "e").replace("î", "i")

    # Check for existing recipe with same normalized name and meal_type
    existing = await (
        supabase.table("recipes")
        .select("*")
        .eq("name_normalized", name_norm)
        .eq("meal_type", meal_type_norm)
        .limit(1)
        .execute()
    )
    if existing.data:
        return existing.data[0]

    row = {
        "name": body.name,
        "name_normalized": name_norm,
        "meal_type": meal_type_norm,
        "ingredients": body.ingredients,
        "instructions": body.instructions,
        "prep_time_minutes": body.prep_time_minutes,
        "calories_per_serving": body.calories_per_serving,
        "protein_g_per_serving": body.protein_g_per_serving,
        "carbs_g_per_serving": body.carbs_g_per_serving,
        "fat_g_per_serving": body.fat_g_per_serving,
        "source": "user_saved",
    }

    result = await supabase.table("recipes").insert(row).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Impossible de créer la recette")
    return result.data[0]


@app.get("/api/recipes/{recipe_id}")
async def get_recipe(
    recipe_id: str,
    auth_user: dict[str, Any] = Depends(require_auth),
) -> dict[str, Any]:
    """Fetch a single recipe by ID."""
    _validate_uuid(recipe_id)

    result = await (
        supabase.table("recipes").select("*").eq("id", recipe_id).limit(1).execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Recette introuvable")
    return result.data[0]


# =============================================================================
# Shopping Lists
# =============================================================================


@app.get("/api/shopping-lists")
async def list_shopping_lists(
    user_id: str,
    auth_user: dict[str, Any] = Depends(require_auth),
) -> list[dict[str, Any]]:
    """List all shopping lists for a user."""
    if auth_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Accès non autorisé")

    result = await (
        supabase.table("shopping_lists")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


@app.post("/api/shopping-lists")
async def create_shopping_list(
    body: ShoppingListCreate,
    auth_user: dict[str, Any] = Depends(require_auth),
) -> dict[str, Any]:
    """Create a new shopping list."""
    if auth_user["id"] != body.user_id:
        raise HTTPException(status_code=403, detail="Accès non autorisé")

    if not body.items:
        raise HTTPException(
            status_code=422,
            detail="La liste de courses ne peut pas être vide.",
        )

    row: dict[str, Any] = {
        "user_id": body.user_id,
        "title": body.title,
        "items": [item.model_dump() for item in body.items],
    }
    if body.meal_plan_id:
        _validate_uuid(body.meal_plan_id)
        plan = await (
            supabase.table("meal_plans")
            .select("user_id")
            .eq("id", body.meal_plan_id)
            .limit(1)
            .execute()
        )
        if not plan.data or plan.data[0].get("user_id") != auth_user["id"]:
            raise HTTPException(
                status_code=403, detail="Accès non autorisé au plan repas"
            )
        row["meal_plan_id"] = body.meal_plan_id

    result = await supabase.table("shopping_lists").insert(row).execute()
    if not result.data:
        raise HTTPException(
            status_code=500,
            detail="Impossible de créer la liste de courses",
        )
    return result.data[0]


@app.get("/api/shopping-lists/{list_id}")
async def get_shopping_list(
    list_id: str,
    auth_user: dict[str, Any] = Depends(require_auth),
) -> dict[str, Any]:
    """Get a single shopping list with items."""
    _validate_uuid(list_id)

    result = await (
        supabase.table("shopping_lists")
        .select("*")
        .eq("id", list_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Liste de courses introuvable")
    if result.data[0].get("user_id") != auth_user["id"]:
        raise HTTPException(status_code=403, detail="Accès non autorisé")

    return result.data[0]


@app.put("/api/shopping-lists/{list_id}")
async def update_shopping_list(
    list_id: str,
    body: ShoppingListUpdate,
    auth_user: dict[str, Any] = Depends(require_auth),
) -> dict[str, Any]:
    """Update a shopping list (e.g., check off items, rename)."""
    _validate_uuid(list_id)

    existing = await (
        supabase.table("shopping_lists")
        .select("user_id")
        .eq("id", list_id)
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Liste de courses introuvable")
    if existing.data[0].get("user_id") != auth_user["id"]:
        raise HTTPException(status_code=403, detail="Accès non autorisé")

    updates: dict[str, Any] = {}
    if body.title is not None:
        updates["title"] = body.title
    if body.items is not None:
        updates["items"] = [item.model_dump() for item in body.items]
    if not updates:
        raise HTTPException(status_code=400, detail="Aucun champ à mettre à jour")

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = await (
        supabase.table("shopping_lists").update(updates).eq("id", list_id).execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=500, detail="Impossible de mettre à jour la liste de courses"
        )
    return result.data[0]


@app.delete("/api/shopping-lists/{list_id}")
async def delete_shopping_list(
    list_id: str,
    auth_user: dict[str, Any] = Depends(require_auth),
) -> dict[str, str]:
    """Delete a shopping list."""
    _validate_uuid(list_id)

    existing = await (
        supabase.table("shopping_lists")
        .select("user_id")
        .eq("id", list_id)
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Liste de courses introuvable")
    if existing.data[0].get("user_id") != auth_user["id"]:
        raise HTTPException(status_code=403, detail="Accès non autorisé")

    try:
        await supabase.table("shopping_lists").delete().eq("id", list_id).execute()
    except Exception as e:
        logger.error(f"Erreur suppression liste courses {list_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Erreur lors de la suppression de la liste"
        )
    return {"status": "deleted"}


# =============================================================================
# Profile Recalculate
# =============================================================================


@app.post("/api/profile/recalculate")
async def recalculate_profile(
    body: RecalculateRequest,
    auth_user: dict[str, Any] = Depends(require_auth),
) -> dict[str, Any]:
    """Recalculate BMR/TDEE/macros from biometric data and persist to user_profiles."""
    user_id = auth_user["id"]

    # Validate activity level
    if body.activity_level not in ACTIVITY_MULTIPLIERS:
        valid = ", ".join(ACTIVITY_MULTIPLIERS.keys())
        raise HTTPException(
            status_code=422,
            detail=f"activity_level doit être l'un de : {valid}",
        )

    # Calculate
    bmr = mifflin_st_jeor_bmr(body.age, body.gender, body.weight_kg, body.height_cm)
    tdee = calculate_tdee(bmr, body.activity_level)

    goals = infer_goals_from_context(None, None, body.goals)
    primary_goal = max(goals, key=lambda k: goals[k]) if goals else "muscle_gain"

    # Target calories based on goal
    target_calories = tdee + GOAL_CALORIE_ADJUSTMENTS.get(primary_goal, 0)

    # Safety: enforce minimum calorie thresholds
    min_calories = MIN_CALORIES_WOMEN if body.gender == "female" else MIN_CALORIES_MEN
    target_calories = max(target_calories, min_calories)

    protein_g, _, _ = calculate_protein_target(body.weight_kg, primary_goal)
    macros = calculate_macros(
        target_calories, protein_g, primary_goal, weight_kg=body.weight_kg
    )

    result = {
        "bmr": bmr,
        "tdee": tdee,
        "target_calories": target_calories,
        "target_protein_g": protein_g,
        "target_carbs_g": macros["carbs_g"],
        "target_fat_g": macros["fat_g"],
        "primary_goal": primary_goal,
    }

    # Persist to user_profiles
    try:
        db_result = await (
            supabase.table("user_profiles")
            .update(
                {
                    "bmr": bmr,
                    "tdee": tdee,
                    "target_calories": target_calories,
                    "target_protein_g": protein_g,
                    "target_carbs_g": macros["carbs_g"],
                    "target_fat_g": macros["fat_g"],
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            .eq("id", user_id)
            .execute()
        )
        if not db_result.data:
            logger.error(
                f"Profil non trouvé pour user_id={user_id} — aucun row mis à jour"
            )
            raise HTTPException(
                status_code=404, detail="Profil utilisateur introuvable"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur mise à jour profil {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Erreur lors de la mise à jour du profil"
        )

    return result


async def _stream_agent_response(
    request: AgentRequest,
    session_id: str,
    pydantic_messages: list,
    memories_str: str,
    title_task: asyncio.Task | None,
    ephemeral: bool = False,
    sanitized_query: str = "",
):
    """Stream agent response as NDJSON chunks."""
    agent_deps = create_agent_deps(memories=memories_str, user_id=request.user_id)
    full_response = ""
    ui_components: list[dict[str, Any]] = []

    # Process file attachments into BinaryContent for the agent
    binary_contents: list[BinaryContent] = []
    if request.files:
        for f in request.files:
            try:
                binary_data = base64.b64decode(f.content)
                media_type = f.mime_type
                binary_contents.append(
                    BinaryContent(data=binary_data, media_type=media_type)
                )
            except Exception as e:
                logger.warning(f"Error processing file {f.file_name}: {e}")

    # Query already sanitized at entry point (agent_endpoint)
    # Build agent input: query + any binary contents
    agent_input: str | list = sanitized_query or request.query
    if binary_contents:
        agent_input = [sanitized_query, *binary_contents]

    skills_used: list[str] = []
    try:
        async with agent.iter(
            agent_input,
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

        # Detect which skills were used (for frontend cache invalidation)
        try:
            for msg in run.result.all_messages():
                if hasattr(msg, "parts"):
                    for part in msg.parts:
                        if (
                            hasattr(part, "tool_name")
                            and part.tool_name == "run_skill_script"
                            and hasattr(part, "args")
                        ):
                            if isinstance(part.args, dict):
                                skill = part.args.get("skill_name", "")
                            else:
                                # args might be ArgsJson — try parsing
                                import re as _re

                                m = _re.search(
                                    r'"skill_name"\s*:\s*"([^"]+)"',
                                    str(part.args),
                                )
                                skill = m.group(1) if m else ""
                            if skill and skill not in skills_used:
                                skills_used.append(skill)
        except Exception:
            pass  # Non-critical — don't break streaming for this

        # Extract UI components from agent response
        cleaned_text, ui_components = extract_ui_components(full_response)
        if ui_components:
            full_response = cleaned_text
            for comp in ui_components:
                yield (
                    json.dumps({"type": "ui_component", **comp}).encode("utf-8") + b"\n"
                )

        # Store AI response (skip for ephemeral requests)
        if not ephemeral:
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
        error_text = (
            "Désolé, une erreur est survenue lors du traitement de votre demande."
        )
        yield json.dumps({"text": error_text}).encode("utf-8") + b"\n"
        full_response = error_text

    # Final chunk with metadata
    conversation_title = None
    if title_task:
        try:
            conversation_title = await title_task
            conversation_title = sanitize_user_text(
                conversation_title, 100, "conversation_title"
            )
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
    if skills_used:
        final_data["skills_used"] = skills_used

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
