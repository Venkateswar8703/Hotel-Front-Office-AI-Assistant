"""
Escalations API.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.tools.hotel_tools import get_all_escalations, escalate_to_front_desk, update_request_status

router = APIRouter(prefix="/api/escalations", tags=["escalations"])


class EscalationCreate(BaseModel):
    reason: str
    room_number: str | None = None
    conversation_id: str | None = None
    conversation_summary: str | None = None


class StatusUpdate(BaseModel):
    status: str


@router.get("")
async def list_escalations():
    return {"escalations": get_all_escalations()}


@router.post("")
async def create_escalation(payload: EscalationCreate):
    result = escalate_to_front_desk(
        reason=payload.reason,
        room_number=payload.room_number,
        conversation_id=payload.conversation_id,
        conversation_summary=payload.conversation_summary,
    )
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result


@router.patch("/{escalation_id}")
async def update_escalation_status(escalation_id: str, payload: StatusUpdate):
    result = update_request_status(escalation_id, payload.status)
    if not result["success"]:
        raise HTTPException(status_code=404, detail="Escalation not found")
    return result
