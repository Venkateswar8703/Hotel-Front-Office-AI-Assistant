"""
Maintenance tickets API.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.tools.hotel_tools import (
    get_all_maintenance_tickets,
    create_maintenance_request,
    update_request_status,
)

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])


class MaintenanceCreate(BaseModel):
    room_number: str
    issue_type: str
    description: str
    priority: str = "MEDIUM"


class StatusUpdate(BaseModel):
    status: str


@router.get("")
async def list_maintenance():
    return {"tickets": get_all_maintenance_tickets()}


@router.post("")
async def create_maintenance(payload: MaintenanceCreate):
    result = create_maintenance_request(
        room_number=payload.room_number,
        issue_type=payload.issue_type,
        description=payload.description,
        priority=payload.priority,
    )
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result


@router.patch("/{ticket_id}")
async def update_maintenance_status(ticket_id: str, payload: StatusUpdate):
    result = update_request_status(ticket_id, payload.status)
    if not result["success"]:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return result
