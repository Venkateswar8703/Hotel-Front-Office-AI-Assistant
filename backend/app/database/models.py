"""
SQLAlchemy ORM models for the Hotel AI Concierge system.

Tables: guests, reservations, rooms, conversations, messages,
        service_requests, maintenance_tickets, complaints, staff, notifications
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# ─── Enums ────────────────────────────────────────────────────────────────────

class RequestStatus(str, PyEnum):
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class RequestPriority(str, PyEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class RoomType(str, PyEnum):
    STANDARD = "STANDARD"
    DELUXE = "DELUXE"
    SUITE = "SUITE"
    PRESIDENTIAL = "PRESIDENTIAL"


class RoomStatus(str, PyEnum):
    AVAILABLE = "AVAILABLE"
    OCCUPIED = "OCCUPIED"
    MAINTENANCE = "MAINTENANCE"
    CLEANING = "CLEANING"


class ReservationStatus(str, PyEnum):
    CONFIRMED = "CONFIRMED"
    CHECKED_IN = "CHECKED_IN"
    CHECKED_OUT = "CHECKED_OUT"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"


class MessageRole(str, PyEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ConversationStatus(str, PyEnum):
    ACTIVE = "ACTIVE"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"
    CLOSED = "CLOSED"


class ComplaintSeverity(str, PyEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# ─── Models ───────────────────────────────────────────────────────────────────

class Guest(Base):
    __tablename__ = "guests"

    id = Column(String, primary_key=True, default=_uuid)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    phone = Column(String(50))
    nationality = Column(String(100))
    id_document = Column(String(100))
    loyalty_number = Column(String(100))
    preferences = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    reservations = relationship("Reservation", back_populates="guest")
    conversations = relationship("Conversation", back_populates="guest")
    service_requests = relationship("ServiceRequest", back_populates="guest")
    complaints = relationship("Complaint", back_populates="guest")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class Room(Base):
    __tablename__ = "rooms"

    id = Column(String, primary_key=True, default=_uuid)
    room_number = Column(String(20), unique=True, nullable=False)
    floor = Column(Integer)
    room_type = Column(Enum(RoomType), default=RoomType.STANDARD)
    status = Column(Enum(RoomStatus), default=RoomStatus.AVAILABLE)
    max_occupancy = Column(Integer, default=2)
    base_rate = Column(Integer, default=0)  # cents
    amenities = Column(JSON, default=list)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    reservations = relationship("Reservation", back_populates="room")
    service_requests = relationship("ServiceRequest", back_populates="room")
    maintenance_tickets = relationship("MaintenanceTicket", back_populates="room")


class Reservation(Base):
    __tablename__ = "reservations"

    id = Column(String, primary_key=True, default=_uuid)
    guest_id = Column(String, ForeignKey("guests.id"), nullable=False)
    room_id = Column(String, ForeignKey("rooms.id"))
    status = Column(Enum(ReservationStatus), default=ReservationStatus.CONFIRMED)
    check_in_date = Column(DateTime(timezone=True))
    check_out_date = Column(DateTime(timezone=True))
    actual_check_in = Column(DateTime(timezone=True))
    actual_check_out = Column(DateTime(timezone=True))
    adults = Column(Integer, default=1)
    children = Column(Integer, default=0)
    special_requests = Column(Text)
    total_amount = Column(Integer, default=0)  # cents
    external_pms_id = Column(String(100))  # for future PMS integration
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    guest = relationship("Guest", back_populates="reservations")
    room = relationship("Room", back_populates="reservations")


class Staff(Base):
    __tablename__ = "staff"

    id = Column(String, primary_key=True, default=_uuid)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    department = Column(String(100))
    role = Column(String(100))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_now)

    assigned_requests = relationship("ServiceRequest", back_populates="assigned_staff")
    assigned_maintenance = relationship("MaintenanceTicket", back_populates="assigned_staff")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=_uuid)
    guest_id = Column(String, ForeignKey("guests.id"), nullable=True)
    session_id = Column(String(255), nullable=False, index=True)
    status = Column(Enum(ConversationStatus), default=ConversationStatus.ACTIVE)
    room_number = Column(String(20))  # denormalized for quick access
    guest_context = Column(JSON, default=dict)  # session-level context
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    guest = relationship("Guest", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    role = Column(Enum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)
    intent = Column(String(100))
    action = Column(String(100))
    sources = Column(JSON, default=list)  # RAG sources
    extra_metadata = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=_now)

    conversation = relationship("Conversation", back_populates="messages")


class ServiceRequest(Base):
    __tablename__ = "service_requests"

    id = Column(String, primary_key=True, default=_uuid)
    request_number = Column(String(20), unique=True, nullable=False)  # e.g. HK1024
    guest_id = Column(String, ForeignKey("guests.id"), nullable=True)
    room_id = Column(String, ForeignKey("rooms.id"), nullable=True)
    room_number = Column(String(20))  # denormalized
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=True)
    assigned_staff_id = Column(String, ForeignKey("staff.id"), nullable=True)
    category = Column(String(100), nullable=False)  # HOUSEKEEPING, ROOM_SERVICE, etc.
    description = Column(Text, nullable=False)
    status = Column(Enum(RequestStatus), default=RequestStatus.PENDING)
    priority = Column(Enum(RequestPriority), default=RequestPriority.MEDIUM)
    details = Column(JSON, default=dict)  # items, quantity, notes
    notes = Column(Text)
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    guest = relationship("Guest", back_populates="service_requests")
    room = relationship("Room", back_populates="service_requests")
    assigned_staff = relationship("Staff", back_populates="assigned_requests")
    conversation = relationship("Conversation")


class MaintenanceTicket(Base):
    __tablename__ = "maintenance_tickets"

    id = Column(String, primary_key=True, default=_uuid)
    ticket_number = Column(String(20), unique=True, nullable=False)  # e.g. MT1024
    guest_id = Column(String, ForeignKey("guests.id"), nullable=True)
    room_id = Column(String, ForeignKey("rooms.id"), nullable=True)
    room_number = Column(String(20))  # denormalized
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=True)
    assigned_staff_id = Column(String, ForeignKey("staff.id"), nullable=True)
    issue_type = Column(String(100), nullable=False)  # AC, plumbing, electrical, etc.
    description = Column(Text, nullable=False)
    status = Column(Enum(RequestStatus), default=RequestStatus.PENDING)
    priority = Column(Enum(RequestPriority), default=RequestPriority.MEDIUM)
    resolved_at = Column(DateTime(timezone=True))
    resolution_notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    room = relationship("Room", back_populates="maintenance_tickets")
    assigned_staff = relationship("Staff", back_populates="assigned_maintenance")


class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(String, primary_key=True, default=_uuid)
    complaint_number = Column(String(20), unique=True, nullable=False)  # e.g. CP1024
    guest_id = Column(String, ForeignKey("guests.id"), nullable=True)
    room_number = Column(String(20))
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=True)
    category = Column(String(100))
    description = Column(Text, nullable=False)
    severity = Column(Enum(ComplaintSeverity), default=ComplaintSeverity.MEDIUM)
    status = Column(Enum(RequestStatus), default=RequestStatus.PENDING)
    resolution = Column(Text)
    resolved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    guest = relationship("Guest", back_populates="complaints")


class Escalation(Base):
    __tablename__ = "escalations"

    id = Column(String, primary_key=True, default=_uuid)
    escalation_number = Column(String(20), unique=True, nullable=False)  # e.g. ES1024
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=True)
    guest_id = Column(String, ForeignKey("guests.id"), nullable=True)
    room_number = Column(String(20))
    reason = Column(Text, nullable=False)
    status = Column(Enum(RequestStatus), default=RequestStatus.PENDING)
    conversation_summary = Column(Text)
    resolved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String, primary_key=True, default=_uuid)
    target_type = Column(String(50))  # staff | guest
    target_id = Column(String)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    related_type = Column(String(50))  # service_request | maintenance | complaint
    related_id = Column(String)
    created_at = Column(DateTime(timezone=True), default=_now)
