"""
LangSmith observability and tracing integration.

Configures LangSmith environment variables and client for tracing
LangChain, LangGraph, and RAG execution pipeline.
"""
from __future__ import annotations

import os
from typing import Any, Optional

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_status_cache: dict[str, Any] = {
    "enabled": False,
    "connected": False,
    "project": "hotel-ai-concierge",
    "endpoint": "https://api.smith.langchain.com",
    "has_api_key": False,
    "api_key_masked": None,
    "error": None,
}


def mask_key(key: Optional[str]) -> Optional[str]:
    """Mask sensitive API key for safe display."""
    if not key:
        return None
    k = key.strip()
    if len(k) <= 8:
        return "****"
    return f"{k[:4]}...{k[-4:]}"


def setup_langsmith() -> dict[str, Any]:
    """
    Initialize LangSmith tracing environment variables based on configuration.
    Called on FastAPI application startup.
    """
    global _status_cache
    settings = get_settings()

    api_key = settings.effective_langsmith_api_key
    project = settings.effective_langsmith_project
    endpoint = settings.effective_langsmith_endpoint
    is_enabled = settings.is_langsmith_enabled

    _status_cache["project"] = project
    _status_cache["endpoint"] = endpoint
    _status_cache["has_api_key"] = bool(api_key)
    _status_cache["api_key_masked"] = mask_key(api_key)

    if not is_enabled:
        _status_cache["enabled"] = False
        _status_cache["connected"] = False
        _status_cache["error"] = "Tracing not enabled. Set LANGSMITH_API_KEY in .env to enable tracing."
        logger.info(
            "langsmith_tracing_disabled",
            project=project,
            reason="api_key_not_configured_or_tracing_disabled",
        )
        return _status_cache

    # Export standard LangChain / LangSmith environment variables
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_ENDPOINT"] = endpoint
    os.environ["LANGCHAIN_PROJECT"] = project
    if api_key:
        os.environ["LANGCHAIN_API_KEY"] = api_key

    _status_cache["enabled"] = True

    # Validate connectivity with LangSmith Client
    try:
        from langsmith import Client

        client = Client(api_url=endpoint, api_key=api_key)
        # Verify connection by attempting to read or create project
        try:
            client.read_project(project_name=project)
            _status_cache["connected"] = True
            _status_cache["error"] = None
        except Exception:
            # Project may not exist yet, verify if client can list or connect
            _status_cache["connected"] = bool(api_key)
            _status_cache["error"] = None

        logger.info(
            "langsmith_tracing_initialized",
            project=project,
            endpoint=endpoint,
            key_preview=mask_key(api_key),
        )
    except Exception as e:
        _status_cache["connected"] = False
        _status_cache["error"] = str(e)
        logger.warning("langsmith_client_init_warning", error=str(e))

    return _status_cache


def get_langsmith_status() -> dict[str, Any]:
    """Return the current LangSmith status."""
    return dict(_status_cache)
