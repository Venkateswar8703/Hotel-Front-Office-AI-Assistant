"""
Service requests API — housekeeping, room service, etc.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.tools.hotel_tools import (
    get_all_service_requests,
    create_housekeeping_request,
    update_request_status,
)

router = APIRouter(prefix="/api/service-requests", tags=["service-requests"])


class ServiceRequestCreate(BaseModel):
    category: str = Field(..., description="HOUSEKEEPING | ROOM_SERVICE | etc.")
    room_number: str
    description: str
    items: list[str] = []
    quantity: int = 1
    priority: str = "MEDIUM"


class StatusUpdate(BaseModel):
    status: str = Field(..., description="PENDING|ASSIGNED|IN_PROGRESS|COMPLETED|CANCELLED")


@router.get("")
async def list_service_requests():
    """Get all service requests (for staff dashboard)."""
    return {"requests": get_all_service_requests()}


@router.post("")
async def create_service_request(payload: ServiceRequestCreate):
    """Create a service request directly (bypasses chat)."""
    result = create_housekeeping_request(
        room_number=payload.room_number,
        description=payload.description,
        items=payload.items,
        quantity=payload.quantity,
        priority=payload.priority,
    )
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error", "Failed"))
    return result


@router.patch("/{request_id}")
async def update_service_request_status(request_id: str, payload: StatusUpdate):
    """Update status of a service request (staff action)."""
    result = update_request_status(request_id, payload.status)
    if not result["success"]:
        raise HTTPException(status_code=404, detail="Request not found")
    return result
