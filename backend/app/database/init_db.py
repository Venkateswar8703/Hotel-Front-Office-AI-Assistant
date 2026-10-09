"""
Database initialization — creates all tables and seeds demo data.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta

from app.database.models import (
    Base, Guest, Room, Reservation, Staff,
    RoomType, RoomStatus, ReservationStatus,
)
from app.database.session import engine, AsyncSessionLocal
from app.core.logging import get_logger

logger = get_logger(__name__)


async def create_tables() -> None:
    """Create all tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("database_tables_created")


async def seed_demo_data() -> None:
    """Seed minimal demo data for local development."""
    async with AsyncSessionLocal() as session:
        # Check if already seeded
        from sqlalchemy import select
        result = await session.execute(select(Guest).limit(1))
        if result.scalar_one_or_none():
            logger.info("demo_data_already_seeded")
            return

        # Demo guests
        guests = [
            Guest(
                id="G001",
                first_name="John",
                last_name="Smith",
                email="john.smith@example.com",
                phone="+1-555-0100",
                nationality="American",
                loyalty_number="LYL001",
                preferences={"pillow": "firm", "floor": "high"},
            ),
            Guest(
                id="G002",
                first_name="Priya",
                last_name="Sharma",
                email="priya.sharma@example.com",
                phone="+91-98765-43210",
                nationality="Indian",
                preferences={"vegetarian": True},
            ),
        ]

        # Demo rooms
        rooms = [
            Room(id="R401", room_number="401", floor=4, room_type=RoomType.STANDARD, status=RoomStatus.AVAILABLE),
            Room(id="R402", room_number="402", floor=4, room_type=RoomType.DELUXE, status=RoomStatus.OCCUPIED),
            Room(id="R403", room_number="403", floor=4, room_type=RoomType.SUITE, status=RoomStatus.AVAILABLE),
            Room(id="R404", room_number="404", floor=4, room_type=RoomType.STANDARD, status=RoomStatus.CLEANING),
            Room(id="R405", room_number="405", floor=4, room_type=RoomType.DELUXE, status=RoomStatus.OCCUPIED),
            Room(id="R501", room_number="501", floor=5, room_type=RoomType.SUITE, status=RoomStatus.AVAILABLE),
            Room(id="R502", room_number="502", floor=5, room_type=RoomType.PRESIDENTIAL, status=RoomStatus.OCCUPIED),
        ]

        # Demo reservations
        now = datetime.now(timezone.utc)
        reservations = [
            Reservation(
                id="RES001",
                guest_id="G001",
                room_id="R405",
                status=ReservationStatus.CHECKED_IN,
                check_in_date=now - timedelta(days=1),
                check_out_date=now + timedelta(days=2),
                adults=2,
                children=0,
                special_requests="High floor preferred",
            ),
            Reservation(
                id="RES002",
                guest_id="G002",
                room_id="R402",
                status=ReservationStatus.CHECKED_IN,
                check_in_date=now,
                check_out_date=now + timedelta(days=3),
                adults=1,
                children=0,
            ),
        ]

        # Demo staff
        staff_members = [
            Staff(
                id="S001",
                first_name="Maria",
                last_name="Garcia",
                email="maria.garcia@hotel.com",
                department="Housekeeping",
                role="Housekeeping Supervisor",
            ),
            Staff(
                id="S002",
                first_name="David",
                last_name="Chen",
                email="david.chen@hotel.com",
                department="Maintenance",
                role="Maintenance Engineer",
            ),
            Staff(
                id="S003",
                first_name="Sarah",
                last_name="Johnson",
                email="sarah.johnson@hotel.com",
                department="Front Desk",
                role="Guest Relations Manager",
            ),
        ]

        session.add_all(guests + rooms + reservations + staff_members)
        await session.commit()
        logger.info("demo_data_seeded", guests=len(guests), rooms=len(rooms))


async def init_db() -> None:
    await create_tables()
    await seed_demo_data()


if __name__ == "__main__":
    asyncio.run(init_db())
