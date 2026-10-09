"""
In-memory guest/session context store.

Holds temporary session data (room number, guest name, preferences)
so guests don't have to repeat themselves in a conversation.

Design: Can be replaced with Redis when REDIS_URL is configured.
"""
from __future__ import annotations

import time
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# In-memory session store: session_id → {context dict, last_access}
_sessions: dict[str, dict[str, Any]] = {}

# Session TTL in seconds (30 minutes)
SESSION_TTL = 1800


def get_context(session_id: str) -> dict[str, Any]:
    """Retrieve guest context for a session."""
    entry = _sessions.get(session_id)
    if not entry:
        return {}

    # Check TTL
    if time.time() - entry["last_access"] > SESSION_TTL:
        del _sessions[session_id]
        logger.info("session_expired", session=session_id[:12])
        return {}

    entry["last_access"] = time.time()
    return entry.get("context", {})


def update_context(session_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    """
    Update guest context — merges updates into existing context.
    Automatically extracts room numbers and guest info from message patterns.
    """
    if session_id not in _sessions:
        _sessions[session_id] = {"context": {}, "last_access": time.time()}

    _sessions[session_id]["context"].update(updates)
    _sessions[session_id]["last_access"] = time.time()

    logger.debug("session_updated", session=session_id[:12], keys=list(updates.keys()))
    return _sessions[session_id]["context"]


def extract_and_update_context(session_id: str, message: str) -> dict[str, Any]:
    """
    Parse a guest message for context clues (room number, name, etc.)
    and persist them to the session.
    """
    import re
    updates = {}

    # Room number patterns: "room 405", "I'm in 405", "my room is 405"
    room_match = re.search(
        r'(?:room|rm\.?|in)\s*(?:is\s*)?[#]?(\d{3,4})\b',
        message,
        re.IGNORECASE,
    )
    if room_match:
        updates["room_number"] = room_match.group(1)

    # Name patterns: "My name is John", "I'm John Smith"
    name_match = re.search(
        r"(?:my name is|i'm|i am)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        message,
        re.IGNORECASE,
    )
    if name_match:
        updates["guest_name"] = name_match.group(1).title()

    if updates:
        update_context(session_id, updates)

    return get_context(session_id)


def clear_context(session_id: str) -> None:
    """Clear all session context for a session."""
    _sessions.pop(session_id, None)
    logger.info("session_cleared", session=session_id[:12])


def get_active_session_count() -> int:
    return len(_sessions)
