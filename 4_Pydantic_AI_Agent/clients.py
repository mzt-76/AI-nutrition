"""
Client initialization for AI Nutrition Assistant.

This module creates and configures clients for:
- LLM (OpenAI API)
- Embeddings (OpenAI)
- Database (Supabase)
- Memory (mem0)
- HTTP (httpx for web search)
"""

from openai import AsyncOpenAI
from supabase import create_client, Client
from httpx import AsyncClient
from mem0 import Memory
from pathlib import Path
from dotenv import load_dotenv
import os
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
project_root = Path(__file__).resolve().parent
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


def get_http_client() -> AsyncClient:
    """
    Create and return an async HTTP client for web searches.

    Returns:
        AsyncClient: Configured HTTP client with timeout
    """
    logger.info("Initializing HTTP client for web searches")

    return AsyncClient(timeout=30.0)


def get_memory_client() -> Memory:
    """
    Create and return a mem0 Memory client for long-term memory.

    Returns:
        Memory: Configured mem0 client

    Raises:
        ValueError: If required environment variables not set
    """
    # Get configuration
    llm_provider = os.getenv("LLM_PROVIDER", "openai")
    llm_api_key = os.getenv("LLM_API_KEY")
    llm_model = os.getenv("LLM_CHOICE", "gpt-4o-mini")

    embedding_provider = os.getenv("EMBEDDING_PROVIDER", "openai")
    embedding_api_key = os.getenv("EMBEDDING_API_KEY")
    embedding_model = os.getenv("EMBEDDING_MODEL_CHOICE", "text-embedding-3-small")

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError("DATABASE_URL required for mem0")

    # Build config
    config = {
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
    }

    # Set API keys in environment for mem0
    if llm_api_key:
        os.environ["OPENAI_API_KEY"] = llm_api_key
    if embedding_api_key and embedding_api_key != llm_api_key:
        # If they're different, prioritize LLM key for mem0
        pass

    logger.info("Initializing mem0 Memory client")

    return Memory.from_config(config)


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
