"""
Test suite for Hotel AI Concierge.

Covers: RAG pipeline, intent classification, hotel tools, and API endpoints.
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

# ─── Test Intent Classification ───────────────────────────────────────────────

class TestIntentClassification:
    """Test the intent classifier."""

    def setup_method(self):
        from app.agents.intent import classify_intent, Intent
        self.classify = classify_intent
        self.Intent = Intent

    def test_housekeeping_intent(self):
        result = self.classify("Can you send two towels to my room?", use_llm=False)
        assert result.intent == self.Intent.HOUSEKEEPING
        assert result.confidence >= 0.8

    def test_maintenance_intent(self):
        result = self.classify("My AC is not working", use_llm=False)
        assert result.intent == self.Intent.MAINTENANCE
        assert result.confidence >= 0.8

    def test_check_in_intent(self):
        result = self.classify("What time is check-in?", use_llm=False)
        assert result.intent == self.Intent.CHECK_IN_CHECKOUT

    def test_dining_intent(self):
        result = self.classify("What time does the restaurant open?", use_llm=False)
        assert result.intent == self.Intent.DINING

    def test_human_escalation_intent(self):
        result = self.classify("I want to speak to the front desk", use_llm=False)
        assert result.intent == self.Intent.HUMAN_ESCALATION

    def test_emergency_intent(self):
        result = self.classify("There is a fire in my room", use_llm=False)
        assert result.intent == self.Intent.EMERGENCY
        assert result.confidence == 1.0

    def test_complaint_intent(self):
        result = self.classify("I am very dissatisfied with my experience", use_llm=False)
        assert result.intent == self.Intent.COMPLAINT

    def test_transportation_intent(self):
        result = self.classify("Can you arrange airport transfer?", use_llm=False)
        assert result.intent == self.Intent.TRANSPORTATION

    def test_unknown_falls_to_general(self):
        result = self.classify("xyzzy pqrs nonsense 12345", use_llm=False)
        assert result.intent in [self.Intent.GENERAL, self.Intent.HOTEL_INFO]


# ─── Test Hotel Tools ─────────────────────────────────────────────────────────

class TestHotelTools:
    """Test mock hotel service tools."""

    def setup_method(self):
        import app.tools.hotel_tools as tools
        self.tools = tools

    def test_housekeeping_request_creates_with_id(self):
        result = self.tools.create_housekeeping_request(
            room_number="405",
            description="Two extra towels please",
            items=["towel"],
            quantity=2,
        )
        assert result["success"] is True
        assert result["request_id"].startswith("HK")
        assert "405" in result["message"]
        assert "HK" in result["message"]

    def test_maintenance_request_creates_ticket(self):
        result = self.tools.create_maintenance_request(
            room_number="305",
            issue_type="Air Conditioning",
            description="AC not cooling",
        )
        assert result["success"] is True
        assert result["ticket_id"].startswith("MT")
        assert "305" in result["message"]

    def test_maintenance_urgent_escalation(self):
        result = self.tools.create_maintenance_request(
            room_number="201",
            issue_type="flood",
            description="Water flooding from bathroom",
        )
        assert result["details"]["priority"] == "URGENT"

    def test_complaint_creation(self):
        result = self.tools.create_complaint(
            description="Staff was extremely rude",
            room_number="101",
        )
        assert result["success"] is True
        assert result["complaint_id"].startswith("CP")

    def test_escalation_to_front_desk(self):
        result = self.tools.escalate_to_front_desk(
            reason="Guest requests human assistance",
            room_number="405",
        )
        assert result["success"] is True
        assert result["escalation_id"].startswith("ES")

    def test_get_reservation_by_room(self):
        result = self.tools.get_guest_reservation(room_number="405")
        assert result["success"] is True
        assert result["reservation"]["room_number"] == "405"

    def test_get_reservation_not_found(self):
        result = self.tools.get_guest_reservation(room_number="999")
        assert result["success"] is False

    def test_room_availability_check(self):
        result = self.tools.check_room_availability(room_type="Standard")
        assert result["success"] is True
        assert "available_rooms" in result

    def test_request_luggage_storage(self):
        result = self.tools.request_luggage_storage(room_number="405", bags=2)
        assert result["success"] is True
        assert "LG" in result["request_id"]

    def test_transport_request(self):
        result = self.tools.request_transport(
            destination="Airport",
            pickup_time="10:00 AM",
            passengers=2,
        )
        assert result["success"] is True
        assert "TR" in result["booking_id"]

    def test_update_request_status(self):
        # Create a request first
        create_result = self.tools.create_housekeeping_request(
            room_number="101",
            description="Towels",
        )
        req_id = create_result["request_id"]

        # Update status
        update_result = self.tools.update_request_status(req_id, "COMPLETED")
        assert update_result["success"] is True
        assert update_result["status"] == "COMPLETED"

    def test_update_nonexistent_request(self):
        result = self.tools.update_request_status("FAKE999", "COMPLETED")
        assert result["success"] is False


# ─── Test Session Service ─────────────────────────────────────────────────────

class TestSessionService:
    """Test guest session context management."""

    def setup_method(self):
        from app.services.session_service import (
            get_context, update_context, extract_and_update_context, clear_context
        )
        self.get_context = get_context
        self.update_context = update_context
        self.extract_and_update = extract_and_update_context
        self.clear_context = clear_context

    def test_empty_context_for_new_session(self):
        context = self.get_context("new-test-session-1234")
        assert context == {}

    def test_update_and_retrieve_context(self):
        self.update_context("sess-001", {"room_number": "405", "guest_name": "John"})
        ctx = self.get_context("sess-001")
        assert ctx["room_number"] == "405"
        assert ctx["guest_name"] == "John"

    def test_extract_room_from_message(self):
        ctx = self.extract_and_update("sess-002", "My room is 405")
        assert ctx.get("room_number") == "405"

    def test_extract_room_various_formats(self):
        ctx = self.extract_and_update("sess-003", "I'm in room 202")
        assert ctx.get("room_number") == "202"

    def test_context_persists_across_messages(self):
        self.extract_and_update("sess-004", "I'm in room 305")
        ctx = self.extract_and_update("sess-004", "Please send towels")
        assert ctx.get("room_number") == "305"

    def test_clear_context(self):
        self.update_context("sess-005", {"room_number": "101"})
        self.clear_context("sess-005")
        ctx = self.get_context("sess-005")
        assert ctx == {}


# ─── Test RAG Pipeline (unit) ─────────────────────────────────────────────────

class TestRAGPipeline:
    """Test RAG pipeline with mocked vector store."""

    def test_empty_knowledge_base_returns_fallback(self):
        """When no documents are indexed, RAG should return a graceful fallback."""
        from app.rag.pipeline import run_rag_pipeline

        with patch("app.rag.pipeline.get_collection_count", return_value=0):
            result = run_rag_pipeline("What time is check-in?")
            assert result.fallback is True
            assert len(result.sources) == 0

    def test_rag_builds_context_from_retrieved_docs(self):
        from app.rag.pipeline import _build_context
        from langchain_core.documents import Document

        docs = [
            (Document(
                page_content="Check-in is at 3 PM",
                metadata={"category": "Check-In", "question": "What time is check-in?"}
            ), 0.9),
        ]
        context = _build_context(docs)
        assert "Check-in is at 3 PM" in context
        assert "Check-In" in context

    def test_rag_extracts_sources(self):
        from app.rag.pipeline import _extract_sources
        from langchain_core.documents import Document

        docs = [
            (Document(
                page_content="Breakfast is at 7 AM",
                metadata={"category": "Dining", "question": "Breakfast time?", "source": "hotel_faq", "intent": "DINING"}
            ), 0.85),
        ]
        sources = _extract_sources(docs)
        assert len(sources) == 1
        assert sources[0].category == "Dining"
        assert sources[0].score == 0.85


# ─── Test LangGraph Graph ─────────────────────────────────────────────────────

class TestLangGraph:
    """Test LangGraph routing logic."""

    def test_route_housekeeping(self):
        from app.agents.graph import route_by_intent
        from app.agents.intent import Intent

        state = {"intent": Intent.HOUSEKEEPING, "user_message": "towels"}
        assert route_by_intent(state) == "housekeeping"

    def test_route_maintenance(self):
        from app.agents.graph import route_by_intent
        from app.agents.intent import Intent

        state = {"intent": Intent.MAINTENANCE, "user_message": "ac broken"}
        assert route_by_intent(state) == "maintenance"

    def test_route_emergency(self):
        from app.agents.graph import route_by_intent
        from app.agents.intent import Intent

        state = {"intent": Intent.EMERGENCY, "user_message": "fire"}
        assert route_by_intent(state) == "emergency"

    def test_route_escalation(self):
        from app.agents.graph import route_by_intent
        from app.agents.intent import Intent

        state = {"intent": Intent.HUMAN_ESCALATION, "user_message": "front desk"}
        assert route_by_intent(state) == "escalation"

    def test_route_hotel_info_to_rag(self):
        from app.agents.graph import route_by_intent
        from app.agents.intent import Intent

        state = {"intent": Intent.HOTEL_INFO, "user_message": "check-in time"}
        assert route_by_intent(state) == "rag"

    def test_extract_room_number(self):
        from app.agents.graph import _extract_room_number

        assert _extract_room_number("Send towels to room 405", {}) == "405"
        assert _extract_room_number("two towels please", {"room_number": "302"}) == "302"
        assert _extract_room_number("towels please", {}) is None

    def test_extract_quantity(self):
        from app.agents.graph import _extract_quantity

        assert _extract_quantity("two towels") == 2
        assert _extract_quantity("send 3 pillows") == 3
        assert _extract_quantity("some towels") == 1

    def test_extract_items(self):
        from app.agents.graph import _extract_items

        items = _extract_items("I need extra towels and pillows")
        assert "towel" in items
        assert "pillow" in items

    def test_extract_issue_type(self):
        from app.agents.graph import _extract_issue_type

        assert _extract_issue_type("AC not working") == "Air Conditioning"
        assert _extract_issue_type("shower is broken") == "Plumbing/Shower"
        assert _extract_issue_type("TV does not work") == "Television"


# ─── Sample Conversation Tests ────────────────────────────────────────────────

class TestSampleConversations:
    """Test key conversation flows end-to-end (mocked LLM/DB)."""

    def test_towels_request_flow(self):
        """
        Guest: 'Send two towels to room 405'
        Expected: HOUSEKEEPING intent → request created → HK ID returned
        """
        from app.agents.graph import node_housekeeping

        state = {
            "session_id": "test-session",
            "conversation_id": "test-conv",
            "user_message": "Send two towels to room 405",
            "guest_context": {},
            "intent": "HOUSEKEEPING",
            "sub_intent": "",
            "confidence": 0.9,
            "retrieved_docs": [],
            "rag_sources": [],
            "action_taken": "",
            "action_result": {},
            "response": "",
            "error": None,
            "history": [],
        }

        result = node_housekeeping(state)
        assert result["action_taken"] == "CREATE_HOUSEKEEPING_REQUEST"
        assert result["action_result"]["success"] is True
        assert "405" in result["response"]
        assert "HK" in result["action_result"]["request_id"]

    def test_maintenance_request_flow(self):
        """
        Guest: 'The AC in my room 305 isn't working'
        Expected: MAINTENANCE → ticket created → MT ID returned
        """
        from app.agents.graph import node_maintenance

        state = {
            "session_id": "test-session-2",
            "conversation_id": "test-conv-2",
            "user_message": "The AC in room 305 isn't working",
            "guest_context": {},
            "intent": "MAINTENANCE",
            "sub_intent": "",
            "confidence": 0.9,
            "retrieved_docs": [],
            "rag_sources": [],
            "action_taken": "",
            "action_result": {},
            "response": "",
            "error": None,
            "history": [],
        }

        result = node_maintenance(state)
        assert result["action_taken"] == "CREATE_MAINTENANCE_REQUEST"
        assert result["action_result"]["success"] is True
        assert "MT" in result["action_result"]["ticket_id"]

    def test_emergency_response(self):
        """Emergency should always return alert message."""
        from app.agents.graph import node_emergency

        state = {
            "session_id": "emergency-session",
            "conversation_id": "emergency-conv",
            "user_message": "There is a fire in room 205",
            "guest_context": {},
            "intent": "EMERGENCY",
            "sub_intent": "fire",
            "confidence": 1.0,
            "retrieved_docs": [],
            "rag_sources": [],
            "action_taken": "",
            "action_result": {},
            "response": "",
            "error": None,
            "history": [],
        }

        result = node_emergency(state)
        assert result["action_taken"] == "EMERGENCY_ALERT"
        assert "EMERGENCY" in result["response"] or "emergency" in result["response"].lower()
        assert "0" in result["response"]  # Front desk dial 0

    def test_escalation_flow(self):
        """Guest requesting front desk should create escalation."""
        from app.agents.graph import node_escalation

        state = {
            "session_id": "escl-session",
            "conversation_id": "escl-conv",
            "user_message": "I need to speak to the front desk immediately",
            "guest_context": {"room_number": "405"},
            "intent": "HUMAN_ESCALATION",
            "sub_intent": "",
            "confidence": 0.95,
            "retrieved_docs": [],
            "rag_sources": [],
            "action_taken": "",
            "action_result": {},
            "response": "",
            "error": None,
            "history": [],
        }

        result = node_escalation(state)
        assert result["action_taken"] == "ESCALATE_TO_FRONT_DESK"
        assert result["action_result"]["success"] is True
        assert "ES" in result["action_result"]["escalation_id"]

    def test_complaint_flow(self):
        """Complaint should be logged and escalation offered."""
        from app.agents.graph import node_complaint

        state = {
            "session_id": "complaint-session",
            "conversation_id": "complaint-conv",
            "user_message": "I am very disappointed with the service today",
            "guest_context": {"room_number": "202"},
            "intent": "COMPLAINT",
            "sub_intent": "",
            "confidence": 0.9,
            "retrieved_docs": [],
            "rag_sources": [],
            "action_taken": "",
            "action_result": {},
            "response": "",
            "error": None,
            "history": [],
        }

        result = node_complaint(state)
        assert result["action_taken"] == "CREATE_COMPLAINT"
        assert result["action_result"]["success"] is True
        assert "CP" in result["action_result"]["complaint_id"]

    def test_no_room_number_asks_for_it(self):
        """If room number unknown, system should ask for it."""
        from app.agents.graph import node_housekeeping

        state = {
            "session_id": "no-room-session",
            "conversation_id": "no-room-conv",
            "user_message": "Please send some towels",
            "guest_context": {},  # No room context
            "intent": "HOUSEKEEPING",
            "sub_intent": "",
            "confidence": 0.9,
            "retrieved_docs": [],
            "rag_sources": [],
            "action_taken": "",
            "action_result": {},
            "response": "",
            "error": None,
            "history": [],
        }

        result = node_housekeeping(state)
        assert result["action_taken"] == "AWAITING_ROOM_NUMBER"
        assert "room number" in result["response"].lower()
