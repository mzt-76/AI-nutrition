"""
Client initialization for AI Nutrition Assistant.

This module creates and configures clients for:
- LLM (OpenAI API)
- Embeddings (OpenAI)
- Database (Supabase)
- Memory (mem0)
- HTTP (httpx for web search)
- Anthropic (Claude Sonnet 4.5 for skill-level LLM calls)
"""

from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from supabase import create_client, Client
from supabase._async.client import AsyncClient as SupabaseAsyncClient
from httpx import AsyncClient
from mem0 import AsyncMemory, Memory
from pathlib import Path
from dotenv import load_dotenv
import os

# Shared prompt for mem0 fact extraction — used by both sync and async clients.
CUSTOM_FACT_PROMPT = """You are a Personal Information Organizer for a nutrition coaching app.
Your job is to extract ONLY long-term personal facts from the conversation.

STORE these (personal preferences that persist across sessions):
- Food preferences: likes, dislikes, allergies, dietary restrictions
- Cooking habits: batch cooking preference, prep time, kitchen equipment
- Daily routine: wake time, work schedule, meal times, gym schedule
- Body/health: conditions, injuries, supplements
- Lifestyle: cuisine preferences, budget, family size

NEVER STORE these (session-specific, transient, or already in the user profile):
- Commands or requests: "créer un plan", "go", "lance", "calcule mes besoins"
- Plan parameters: "3 jours", "7 jours", "1 semaine", number of days/meals requested
- Biometrics already in profile: age, weight, height, gender, activity level, goals
- Greetings, confirmations, or generic statements
- Calculated values: BMR, TDEE, calorie targets, macro targets

Return a JSON object with key "facts" containing a list of SHORT PLAIN STRINGS.
Each fact must be a simple sentence string, NOT a dict/object.

Example output: {"facts": ["allergique aux arachides", "fait du sport le mardi et jeudi"]}
If nothing qualifies, return {"facts": []}.
"""
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
project_root = Path(__file__).resolve().parent.parent
dotenv_path = project_root / ".env"
load_dotenv(dotenv_path, override=True)


def get_openai_client() -> AsyncOpenAI:
    """
    Create and return an async OpenAI client for general use (chat, vision, etc.).

    Returns:
        AsyncOpenAI: Configured OpenAI client

    Raises:
        ValueError: If LLM_API_KEY is not set
    """
    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")

    if not api_key:
        raise ValueError("LLM_API_KEY not found in environment variables")

    logger.info(f"Initializing OpenAI client with base_url: {base_url}")

    return AsyncOpenAI(api_key=api_key, base_url=base_url)


def get_embedding_client() -> AsyncOpenAI:
    """
    Create and return an async OpenAI client for embeddings.

    Returns:
        AsyncOpenAI: Configured embedding client

    Raises:
        ValueError: If EMBEDDING_API_KEY is not set
    """
    api_key = os.getenv("EMBEDDING_API_KEY")
    base_url = os.getenv("EMBEDDING_BASE_URL", "https://api.openai.com/v1")

    if not api_key:
        raise ValueError("EMBEDDING_API_KEY not found in environment variables")

    logger.info(f"Initializing embedding client with base_url: {base_url}")

    return AsyncOpenAI(api_key=api_key, base_url=base_url)


def get_supabase_client() -> Client:
    """
    Create and return a Supabase client.

    Returns:
        Client: Configured Supabase client

    Raises:
        ValueError: If SUPABASE_URL or SUPABASE_SERVICE_KEY not set
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")

    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")

    logger.info(f"Initializing Supabase client for: {url}")

    return create_client(url, key)


def get_async_supabase_client() -> SupabaseAsyncClient:
    """Create and return an async Supabase client (sync construction).

    AsyncClient.__init__ is synchronous — only .execute() is async.
    This allows _get_shared_clients() to remain sync while providing
    a client whose queries can be properly awaited.
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    logger.info(f"Initializing async Supabase client for: {url}")
    return SupabaseAsyncClient(url, key)


def get_http_client() -> AsyncClient:
    """
    Create and return an async HTTP client for web searches.

    Returns:
        AsyncClient: Configured HTTP client with timeout
    """
    logger.info("Initializing HTTP client for web searches")

    return AsyncClient(timeout=30.0)


def _build_mem0_config() -> dict:
    """Build shared mem0 config dict and set required env vars."""
    llm_api_key = os.getenv("LLM_API_KEY")
    llm_model = os.getenv("MEM0_LLM_CHOICE", "gpt-4o-mini")
    embedding_model = os.getenv("EMBEDDING_MODEL_CHOICE", "text-embedding-3-small")
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError("DATABASE_URL required for mem0")

    if llm_api_key:
        os.environ["OPENAI_API_KEY"] = llm_api_key

    return {
        "llm": {
            "provider": "openai",
            "config": {
                "model": llm_model,
                "temperature": 0.2,
                "max_tokens": 2000,
            },
        },
        "embedder": {
            "provider": "openai",
            "config": {"model": embedding_model, "embedding_dims": 1536},
        },
        "vector_store": {
            "provider": "supabase",
            "config": {
                "connection_string": database_url,
                "collection_name": "mem0_memories",
                "embedding_model_dims": 1536,
            },
        },
        "custom_fact_extraction_prompt": CUSTOM_FACT_PROMPT,
    }


def get_memory_client() -> Memory:
    """
    Create and return a mem0 Memory client for long-term memory.

    Returns:
        Memory: Configured mem0 client

    Raises:
        ValueError: If required environment variables not set
    """
    logger.info("Initializing mem0 Memory client")
    return Memory.from_config(_build_mem0_config())


async def get_async_memory_client() -> AsyncMemory:
    """Create and return an async mem0 AsyncMemory client for the API.

    Uses the same config as get_memory_client() but returns an AsyncMemory
    instance that supports native await instead of requiring asyncio.to_thread().

    Returns:
        AsyncMemory: Configured async mem0 client
    """
    logger.info("Initializing async mem0 AsyncMemory client")
    return await AsyncMemory.from_config(_build_mem0_config())


def get_anthropic_client() -> AsyncAnthropic | None:
    """Create Anthropic client for skill-level LLM calls (Claude Sonnet 4.5).

    Used by meal-planning skill scripts for custom recipe generation and DB seeding.
    The Pydantic AI agent itself remains on its configured model (OpenAI).

    Returns:
        AsyncAnthropic: Configured Anthropic async client, or None if key not set
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        logger.warning(
            "ANTHROPIC_API_KEY not set — Anthropic client unavailable (LLM recipe fallback disabled)"
        )
        return None

    logger.info("Initializing Anthropic client for skill-level LLM calls")

    return AsyncAnthropic(api_key=api_key)


def get_brave_api_key() -> str | None:
    """
    Get Brave Search API key from environment.

    Returns:
        str | None: API key if set, None otherwise
    """
    key = os.getenv("BRAVE_API_KEY")
    if key:
        logger.info("Brave API key found")
    else:
        logger.warning("Brave API key not found - web search may not work")
    return key


def get_searxng_base_url() -> str | None:
    """
    Get SearXNG base URL from environment (alternative to Brave).

    Returns:
        str | None: Base URL if set, None otherwise
    """
    url = os.getenv("SEARXNG_BASE_URL")
    if url:
        logger.info(f"SearXNG base URL: {url}")
    return url
