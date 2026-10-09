"""
Mock hotel service tools.

Each tool returns a structured dict with request_id, status, and message.
All tools are designed for easy replacement with real PMS/CRM integrations.

Integration Points:
  - Oracle OPERA PMS: replace _mock_* functions with OPERA API calls
  - Salesforce CRM: replace with SF REST API calls  
  - Amadeus: replace booking tools with Amadeus API
"""
from __future__ import annotations

import random
import string
import time
from datetime import datetime, timezone
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


# ─── ID Generators ────────────────────────────────────────────────────────────

def _generate_id(prefix: str, length: int = 4) -> str:
    """Generate a human-readable request ID like HK1024."""
    num = random.randint(1000, 9999)
    return f"{prefix}{num}"


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Mock Data Stores (in-memory for MVP) ─────────────────────────────────────

_reservations_db: dict[str, dict] = {
    "RES001": {
        "id": "RES001",
        "guest_id": "G001",
        "guest_name": "John Smith",
        "room_number": "405",
        "room_type": "Deluxe",
        "check_in": "2026-09-22",
        "check_out": "2026-09-25",
        "adults": 2,
        "children": 0,
        "status": "CHECKED_IN",
    },
    "RES002": {
        "id": "RES002",
        "guest_id": "G002",
        "guest_name": "Priya Sharma",
        "room_number": "402",
        "room_type": "Deluxe",
        "check_in": "2026-09-23",
        "check_out": "2026-09-26",
        "adults": 1,
        "children": 0,
        "status": "CHECKED_IN",
    },
}

_rooms_db: dict[str, dict] = {
    "401": {"room_number": "401", "type": "Standard", "status": "AVAILABLE", "floor": 4},
    "402": {"room_number": "402", "type": "Deluxe", "status": "OCCUPIED", "floor": 4},
    "403": {"room_number": "403", "type": "Suite", "status": "AVAILABLE", "floor": 4},
    "405": {"room_number": "405", "type": "Deluxe", "status": "OCCUPIED", "floor": 4},
    "501": {"room_number": "501", "type": "Suite", "status": "AVAILABLE", "floor": 5},
}

# In-memory request log (populated at runtime)
_service_requests: dict[str, dict] = {}
_maintenance_tickets: dict[str, dict] = {}
_complaints: dict[str, dict] = {}
_escalations: dict[str, dict] = {}


# ─── Reservation Tools ────────────────────────────────────────────────────────

def get_guest_reservation(
    guest_id: str | None = None,
    room_number: str | None = None,
    reservation_id: str | None = None,
) -> dict[str, Any]:
    """
    Retrieve guest reservation details.
    Integration point: Oracle OPERA / Amadeus reservation lookup.
    """
    try:
        if reservation_id and reservation_id in _reservations_db:
            return {"success": True, "reservation": _reservations_db[reservation_id]}

        if room_number:
            for res in _reservations_db.values():
                if res["room_number"] == room_number and res["status"] == "CHECKED_IN":
                    return {"success": True, "reservation": res}

        if guest_id:
            for res in _reservations_db.values():
                if res["guest_id"] == guest_id:
                    return {"success": True, "reservation": res}

        return {"success": False, "error": "Reservation not found", "reservation": None}
    except Exception as e:
        logger.error("get_reservation_failed", error=str(e))
        return {"success": False, "error": str(e)}


def check_room_availability(
    room_type: str | None = None,
    check_in: str | None = None,
    check_out: str | None = None,
) -> dict[str, Any]:
    """
    Check room availability for given dates.
    Integration point: PMS availability API.
    """
    available = [
        r for r in _rooms_db.values()
        if r["status"] == "AVAILABLE"
        and (room_type is None or room_type.lower() in r["type"].lower())
    ]
    return {
        "success": True,
        "available_rooms": available,
        "count": len(available),
        "check_in": check_in,
        "check_out": check_out,
    }


def modify_reservation(
    reservation_id: str,
    changes: dict[str, Any],
) -> dict[str, Any]:
    """
    Modify an existing reservation.
    Integration point: PMS modification API.
    """
    if reservation_id not in _reservations_db:
        return {"success": False, "error": "Reservation not found"}

    _reservations_db[reservation_id].update(changes)
    return {
        "success": True,
        "reservation_id": reservation_id,
        "message": f"Reservation {reservation_id} updated successfully.",
        "updated_at": _timestamp(),
    }


def cancel_reservation(reservation_id: str, reason: str = "") -> dict[str, Any]:
    """
    Cancel a reservation.
    Integration point: PMS cancellation API.
    """
    if reservation_id not in _reservations_db:
        return {"success": False, "error": "Reservation not found"}

    _reservations_db[reservation_id]["status"] = "CANCELLED"
    return {
        "success": True,
        "reservation_id": reservation_id,
        "message": f"Reservation {reservation_id} has been cancelled.",
        "cancelled_at": _timestamp(),
    }


# ─── Housekeeping Tools ───────────────────────────────────────────────────────

def create_housekeeping_request(
    room_number: str,
    description: str,
    items: list[str] | None = None,
    quantity: int = 1,
    priority: str = "MEDIUM",
    conversation_id: str | None = None,
) -> dict[str, Any]:
    """
    Create a housekeeping service request.
    Integration point: Hotel operations system (HotSOS, Quore, etc.)
    """
    request_id = _generate_id("HK")
    request = {
        "request_id": request_id,
        "type": "HOUSEKEEPING",
        "room_number": room_number,
        "description": description,
        "items": items or [],
        "quantity": quantity,
        "priority": priority,
        "status": "PENDING",
        "conversation_id": conversation_id,
        "created_at": _timestamp(),
        "estimated_minutes": 15,
    }
    _service_requests[request_id] = request

    logger.info(
        "housekeeping_request_created",
        request_id=request_id,
        room=room_number,
        description=description[:50],
    )

    return {
        "success": True,
        "request_id": request_id,
        "message": (
            f"Housekeeping dispatch logged (Request ID: {request_id}) for Room {room_number}. "
            f"Attending team notified (ETA: ~15 mins)."
        ),
        "details": request,
    }


# ─── Maintenance Tools ────────────────────────────────────────────────────────

def create_maintenance_request(
    room_number: str,
    issue_type: str,
    description: str,
    priority: str = "MEDIUM",
    conversation_id: str | None = None,
) -> dict[str, Any]:
    """
    Create a maintenance ticket.
    Integration point: CMMS (Computerized Maintenance Management System).
    """
    ticket_id = _generate_id("MT")

    # Auto-escalate certain issues
    if any(w in issue_type.lower() for w in ["flood", "fire", "gas", "electric"]):
        priority = "URGENT"

    ticket = {
        "ticket_id": ticket_id,
        "type": "MAINTENANCE",
        "room_number": room_number,
        "issue_type": issue_type,
        "description": description,
        "priority": priority,
        "status": "PENDING",
        "conversation_id": conversation_id,
        "created_at": _timestamp(),
        "estimated_response_minutes": 30 if priority != "URGENT" else 10,
    }
    _maintenance_tickets[ticket_id] = ticket

    logger.info(
        "maintenance_ticket_created",
        ticket_id=ticket_id,
        room=room_number,
        issue=issue_type,
        priority=priority,
    )

    eta = "10 minutes" if priority == "URGENT" else "30 minutes"
    return {
        "success": True,
        "ticket_id": ticket_id,
        "priority": priority,
        "message": (
            f"Maintenance work order {ticket_id} created for {issue_type} "
            f"in Room {room_number} (Priority: {priority}). Engineering ETA: {eta}."
        ),
        "details": ticket,
    }


# ─── Room Service Tools ───────────────────────────────────────────────────────

def create_room_service_request(
    room_number: str,
    items: list[dict[str, Any]],
    special_instructions: str = "",
    conversation_id: str | None = None,
) -> dict[str, Any]:
    """
    Create a food/beverage room service order.
    Integration point: F&B POS system.
    """
    request_id = _generate_id("RS")
    request = {
        "request_id": request_id,
        "type": "ROOM_SERVICE",
        "room_number": room_number,
        "items": items,
        "special_instructions": special_instructions,
        "status": "PENDING",
        "conversation_id": conversation_id,
        "created_at": _timestamp(),
        "estimated_delivery_minutes": 30,
    }
    _service_requests[request_id] = request

    item_summary = ", ".join(
        [f"{i.get('quantity', 1)}x {i.get('name', 'item')}" for i in items]
    )
    return {
        "success": True,
        "request_id": request_id,
        "message": (
            f"Room service order {request_id} placed for Room {room_number}. "
            f"Order: {item_summary}. Kitchen ETA: 30 minutes."
        ),
        "details": request,
    }


# ─── Complaint Tools ──────────────────────────────────────────────────────────

def create_complaint(
    description: str,
    room_number: str | None = None,
    category: str = "General",
    severity: str = "MEDIUM",
    conversation_id: str | None = None,
) -> dict[str, Any]:
    """
    Create a guest complaint record.
    Integration point: CRM / Guest experience platform.
    """
    complaint_id = _generate_id("CP")
    complaint = {
        "complaint_id": complaint_id,
        "type": "COMPLAINT",
        "room_number": room_number,
        "category": category,
        "description": description,
        "severity": severity,
        "status": "PENDING",
        "conversation_id": conversation_id,
        "created_at": _timestamp(),
    }
    _complaints[complaint_id] = complaint

    logger.info(
        "complaint_created",
        complaint_id=complaint_id,
        severity=severity,
        category=category,
    )

    return {
        "success": True,
        "complaint_id": complaint_id,
        "message": (
            f"Guest complaint logged (Reference: {complaint_id}) for Room {room_number or 'General'}. "
            "Alert dispatched to Guest Relations & Duty Manager."
        ),
        "details": complaint,
    }


# ─── Guest Service Tools ──────────────────────────────────────────────────────

def request_late_checkout(
    room_number: str,
    requested_time: str,
    reservation_id: str | None = None,
) -> dict[str, Any]:
    """
    Request a late checkout. Subject to availability.
    Integration point: PMS late checkout module.
    """
    # Mock: 80% approval rate
    approved = random.random() > 0.2
    if approved:
        return {
            "success": True,
            "approved": True,
            "requested_time": requested_time,
            "message": (
                f"Late checkout until {requested_time} approved for Room {room_number}. "
                "PMS guest departure time updated (Complimentary)."
            ),
        }
    else:
        return {
            "success": True,
            "approved": False,
            "message": (
                f"Late checkout until {requested_time} unavailable due to high occupancy. "
                "Maximum complimentary checkout permitted today is 1:00 PM without manager override."
            ),
        }


def request_luggage_storage(
    room_number: str,
    bags: int = 1,
    until: str | None = None,
) -> dict[str, Any]:
    """Request luggage storage service."""
    request_id = _generate_id("LG")
    return {
        "success": True,
        "request_id": request_id,
        "message": (
            f"Luggage storage tag generated for {bags} bag(s) (Tag Reference: {request_id}) for Room {room_number}."
        ),
    }


def request_transport(
    destination: str,
    pickup_time: str,
    passengers: int = 1,
    transport_type: str = "taxi",
    room_number: str | None = None,
) -> dict[str, Any]:
    """
    Arrange transport for a guest.
    Integration point: Transport management system.
    """
    booking_id = _generate_id("TR")
    return {
        "success": True,
        "booking_id": booking_id,
        "message": (
            f"Transport booking {booking_id} created for {passengers} passenger(s) to {destination} at {pickup_time} "
            f"(Room: {room_number or 'N/A'}). Concierge dispatch notified."
        ),
    }


def escalate_to_front_desk(
    reason: str,
    room_number: str | None = None,
    conversation_id: str | None = None,
    conversation_summary: str | None = None,
) -> dict[str, Any]:
    """
    Escalate to Front Office Duty Manager.
    Integration point: Hotel staff communication platform (HotSOS, Whistle, etc.)
    """
    escalation_id = _generate_id("ES")
    escalation = {
        "escalation_id": escalation_id,
        "type": "ESCALATION",
        "room_number": room_number,
        "reason": reason,
        "conversation_id": conversation_id,
        "conversation_summary": conversation_summary,
        "status": "PENDING",
        "created_at": _timestamp(),
    }
    _escalations[escalation_id] = escalation

    logger.info(
        "escalation_created",
        escalation_id=escalation_id,
        reason=reason[:50],
        room=room_number,
    )

    return {
        "success": True,
        "escalation_id": escalation_id,
        "message": (
            f"Incident escalated to Front Office Duty Manager (Reference: {escalation_id}). "
            "High-priority notification posted to staff operations dashboard."
        ),
        "details": escalation,
    }


# ─── Read Access for Dashboard ────────────────────────────────────────────────

def get_all_service_requests() -> list[dict]:
    return list(_service_requests.values())


def get_all_maintenance_tickets() -> list[dict]:
    return list(_maintenance_tickets.values())


def get_all_complaints() -> list[dict]:
    return list(_complaints.values())


def get_all_escalations() -> list[dict]:
    return list(_escalations.values())


def update_request_status(request_id: str, status: str) -> dict[str, Any]:
    """Update status of any request type."""
    for store in [_service_requests, _maintenance_tickets, _complaints, _escalations]:
        if request_id in store:
            store[request_id]["status"] = status
            store[request_id]["updated_at"] = _timestamp()
            return {"success": True, "request_id": request_id, "status": status}
    return {"success": False, "error": "Request not found"}
