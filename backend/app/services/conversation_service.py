"""
Conversation persistence service — saves conversations and messages to DB.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    Conversation, Message, MessageRole, ConversationStatus
)
from app.core.logging import get_logger

logger = get_logger(__name__)


async def get_or_create_conversation(
    db: AsyncSession,
    session_id: str,
    conversation_id: str | None = None,
    guest_context: dict | None = None,
) -> Conversation:
    """Get existing conversation or create a new one."""
    if conversation_id:
        result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conv = result.scalar_one_or_none()
        if conv:
            # Update context
            if guest_context:
                conv.guest_context = {**(conv.guest_context or {}), **guest_context}
            return conv

    # Create new conversation
    conv_id = conversation_id or str(uuid.uuid4())
    conv = Conversation(
        id=conv_id,
        session_id=session_id,
        status=ConversationStatus.ACTIVE,
        guest_context=guest_context or {},
        room_number=guest_context.get("room_number") if guest_context else None,
    )
    db.add(conv)
    await db.flush()
    logger.info("conversation_created", conversation_id=conv_id, session=session_id[:12])
    return conv


async def save_message(
    db: AsyncSession,
    conversation_id: str,
    role: str,
    content: str,
    intent: str | None = None,
    action: str | None = None,
    sources: list | None = None,
    metadata: dict | None = None,
) -> Message:
    """Persist a chat message to the database."""
    msg = Message(
        conversation_id=conversation_id,
        role=MessageRole(role),
        content=content,
        intent=intent,
        action=action,
        sources=sources or [],
        extra_metadata=metadata or {},
    )
    db.add(msg)
    await db.flush()
    return msg


async def get_conversation_history(
    db: AsyncSession,
    conversation_id: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Retrieve conversation message history."""
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
        .limit(limit)
    )
    messages = result.scalars().all()
    return [
        {
            "id": m.id,
            "role": m.role.value,
            "content": m.content,
            "intent": m.intent,
            "action": m.action,
            "sources": m.sources,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]


async def mark_conversation_escalated(
    db: AsyncSession,
    conversation_id: str,
) -> None:
    """Mark a conversation as escalated to human staff."""
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if conv:
        conv.status = ConversationStatus.ESCALATED
