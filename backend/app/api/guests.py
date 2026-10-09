"""
Guest API — retrieve and seed guest records.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Guest
from app.database.session import get_db
from app.tools.hotel_tools import get_guest_reservation

router = APIRouter(prefix="/api/guest", tags=["guest"])


@router.get("/{guest_id}")
async def get_guest(guest_id: str, db: AsyncSession = Depends(get_db)):
    """Get guest details and reservation."""
    result = await db.execute(select(Guest).where(Guest.id == guest_id))
    guest = result.scalar_one_or_none()
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")

    reservation = get_guest_reservation(guest_id=guest_id)

    return {
        "guest_id": guest.id,
        "name": guest.full_name,
        "email": guest.email,
        "phone": guest.phone,
        "loyalty_number": guest.loyalty_number,
        "preferences": guest.preferences,
        "reservation": reservation.get("reservation"),
    }
