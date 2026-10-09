"""
Chat API — main endpoint for the hotel concierge chatbot.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import process_message
from app.database.session import get_db
from app.services import conversation_service, session_service
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = None
    conversation_id: str | None = None
    guest_context: dict | None = None  # {room_number, guest_id, reservation_id}


class ChatResponse(BaseModel):
    conversation_id: str
    message: str
    intent: str
    sub_intent: str = ""
    action: str = ""
    request_id: str | None = None
    sources: list[dict] = []
    error: str | None = None
    guest_context: dict = {}


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Main chat endpoint — processes guest messages through the LangGraph pipeline.

    Handles intent classification, RAG retrieval, and tool execution.
    Returns a structured response with the AI reply, intent, and any action taken.
    """
    # Sanitize input
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Message cannot be empty.")

    # Session management
    session_id = request.session_id or str(uuid.uuid4())

    # Merge any explicitly provided guest context with stored session context
    stored_context = session_service.get_context(session_id)
    if request.guest_context:
        stored_context = session_service.update_context(session_id, request.guest_context)

    # Extract context clues from the message itself (room number, name, etc.)
    guest_context = session_service.extract_and_update_context(session_id, message)

    # Get or create conversation in DB
    conv = await conversation_service.get_or_create_conversation(
        db=db,
        session_id=session_id,
        conversation_id=request.conversation_id,
        guest_context=guest_context,
    )

    # Load conversation history for multi-turn context
    history = await conversation_service.get_conversation_history(
        db=db,
        conversation_id=conv.id,
        limit=10,
    )

    # Save user message
    await conversation_service.save_message(
        db=db,
        conversation_id=conv.id,
        role="user",
        content=message,
    )

    # Process through LangGraph
    result = await process_message(
        session_id=session_id,
        message=message,
        conversation_id=conv.id,
        guest_context=guest_context,
        history=history,
    )

    # If escalation occurred, mark conversation
    if result.get("action") == "ESCALATE_TO_FRONT_DESK":
        await conversation_service.mark_conversation_escalated(db, conv.id)

    # Persist assistant response
    await conversation_service.save_message(
        db=db,
        conversation_id=conv.id,
        role="assistant",
        content=result["message"],
        intent=result.get("intent"),
        action=result.get("action"),
        sources=result.get("sources", []),
        metadata={"action_result": result.get("action_result", {})},
    )

    # Extract request ID from action result if present
    action_result = result.get("action_result", {})
    request_id = (
        action_result.get("request_id")
        or action_result.get("ticket_id")
        or action_result.get("complaint_id")
        or action_result.get("escalation_id")
        or action_result.get("booking_id")
    )

    logger.info(
        "chat_response",
        session=session_id[:12],
        conversation=conv.id[:12],
        intent=result.get("intent"),
        action=result.get("action"),
        request_id=request_id,
    )

    return ChatResponse(
        conversation_id=conv.id,
        message=result["message"],
        intent=result.get("intent", "GENERAL"),
        sub_intent=result.get("sub_intent", ""),
        action=result.get("action", ""),
        request_id=request_id,
        sources=result.get("sources", []),
        error=result.get("error"),
        guest_context=guest_context,
    )


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve full conversation history."""
    from sqlalchemy import select
    from app.database.models import Conversation

    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    history = await conversation_service.get_conversation_history(
        db=db,
        conversation_id=conversation_id,
    )

    return {
        "conversation_id": conv.id,
        "session_id": conv.session_id,
        "status": conv.status.value,
        "guest_context": conv.guest_context,
        "room_number": conv.room_number,
        "messages": history,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
    }
