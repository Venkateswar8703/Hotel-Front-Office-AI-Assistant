"""
LangGraph conversation state definition.
"""
from __future__ import annotations

from typing import Any, TypedDict


class ConversationState(TypedDict):
    """State carried through the LangGraph orchestration graph."""

    # Input
    session_id: str
    user_message: str
    conversation_id: str

    # Guest context (from session store or DB)
    guest_context: dict[str, Any]  # {guest_id, room_number, reservation_id, name, ...}

    # Classification
    intent: str          # e.g. HOUSEKEEPING, MAINTENANCE, HOTEL_INFO
    sub_intent: str      # e.g. EXTRA_TOWELS within HOUSEKEEPING
    confidence: float    # 0.0 – 1.0

    # RAG
    retrieved_docs: list[dict]
    rag_sources: list[dict]

    # Action result
    action_taken: str    # e.g. CREATE_HOUSEKEEPING_REQUEST
    action_result: dict  # Tool call result with IDs, status

    # Final output
    response: str
    error: str | None

    # Conversation history (last N messages for context)
    history: list[dict[str, str]]  # [{role, content}, ...]
