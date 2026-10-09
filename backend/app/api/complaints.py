"""
Complaints API.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.tools.hotel_tools import get_all_complaints, create_complaint, update_request_status

router = APIRouter(prefix="/api/complaints", tags=["complaints"])


class ComplaintCreate(BaseModel):
    description: str
    room_number: str | None = None
    category: str = "General"
    severity: str = "MEDIUM"


class StatusUpdate(BaseModel):
    status: str


@router.get("")
async def list_complaints():
    return {"complaints": get_all_complaints()}


@router.post("")
async def create_complaint_endpoint(payload: ComplaintCreate):
    result = create_complaint(
        description=payload.description,
        room_number=payload.room_number,
        category=payload.category,
        severity=payload.severity,
    )
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result


@router.patch("/{complaint_id}")
async def update_complaint_status(complaint_id: str, payload: StatusUpdate):
    result = update_request_status(complaint_id, payload.status)
    if not result["success"]:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return result
