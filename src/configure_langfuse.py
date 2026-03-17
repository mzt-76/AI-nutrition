"""Langfuse observability configuration for Pydantic AI agents.

Uses the Langfuse SDK v3 direct integration (no OTEL/Logfire bridge needed).
Agent.instrument_all() auto-captures all Pydantic AI agent operations.

Gracefully degrades to no-op when credentials are missing or package not installed.
"""

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def configure_langfuse() -> Any:
    """Configure Langfuse for agent observability.

    Reads credentials from environment variables:
        LANGFUSE_PUBLIC_KEY: Langfuse public key
        LANGFUSE_SECRET_KEY: Langfuse secret key
        LANGFUSE_BASE_URL: Langfuse endpoint (defaults to https://cloud.langfuse.com)

    Returns:
        Langfuse client if configured, None otherwise.
    """
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")

    if not public_key or not secret_key:
        logger.info("Langfuse credentials not found. Tracing disabled.")
        return None

    # Ensure LANGFUSE_BASE_URL is set (SDK reads it automatically)
    if not os.getenv("LANGFUSE_BASE_URL"):
        os.environ["LANGFUSE_BASE_URL"] = "https://cloud.langfuse.com"

    try:
        from langfuse import get_client
        from pydantic_ai import Agent

        langfuse = get_client()

        # Instrument all Pydantic AI agents globally
        Agent.instrument_all()

        if langfuse.auth_check():
            logger.info(
                "Langfuse tracing enabled → %s",
                os.getenv("LANGFUSE_BASE_URL"),
            )
        else:
            logger.warning("Langfuse auth check failed — tracing may not work")

        return langfuse

    except ImportError as e:
        logger.error(
            "langfuse package not installed (%s). Add it to requirements-prod.txt!", e
        )
        return None
    except Exception as e:
        logger.warning("Langfuse initialization failed: %s", e)
        return None
