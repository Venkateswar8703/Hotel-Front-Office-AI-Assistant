"""
LangGraph orchestration graph for the Hotel AI Concierge.

One StateGraph with specialized nodes:
  classify_intent → route → [rag | housekeeping | maintenance | complaint | escalation | general]
"""
from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END

from app.agents.intent import Intent, classify_intent
from app.agents.state import ConversationState
from app.core.llm import get_llm
from app.core.logging import get_logger
from app.rag.pipeline import run_rag_pipeline
from app.tools import hotel_tools as tools

logger = get_logger(__name__)


# ─── Helper: Extract Room Number ──────────────────────────────────────────────

def _extract_room_number(text: str, context: dict) -> str | None:
    """Extract room number from message or guest context."""
    # From message
    match = re.search(r'\broom\s*(\d{3,4})\b', text, re.IGNORECASE)
    if match:
        return match.group(1)
    # From context
    return context.get("room_number")


def _extract_quantity(text: str, default: int = 1) -> int:
    """Extract quantity from text like 'two towels', '3 pillows'."""
    word_map = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    }
    # Number words
    for word, num in word_map.items():
        if word in text.lower():
            return num
    # Digits
    match = re.search(r'\b(\d+)\b', text)
    if match:
        return int(match.group(1))
    return default


def _extract_items(text: str) -> list[str]:
    """Extract requested items from text."""
    item_keywords = [
        "towel", "pillow", "blanket", "shampoo", "conditioner", "soap",
        "toiletries", "toilet paper", "toothbrush", "toothpaste", "razor",
        "robe", "slipper", "iron", "ironing board", "hair dryer", "coffee",
        "tea", "water", "amenities", "dental kit", "dental", "bed sheet", "sheet",
    ]
    found = []
    text_lower = text.lower()
    for item in item_keywords:
        if item in text_lower:
            found.append(item)
    return found if found else ["requested items"]


def _extract_issue_type(text: str) -> str:
    """Extract maintenance issue type from text."""
    issue_map = {
        "ac": "Air Conditioning",
        "air condition": "Air Conditioning",
        "heating": "Heating",
        "plumbing": "Plumbing",
        "leak": "Plumbing/Leak",
        "toilet": "Plumbing/Toilet",
        "flush": "Plumbing/Toilet",
        "shower": "Plumbing/Shower",
        "hot water": "Plumbing/Hot Water",
        "tv": "Television",
        "television": "Television",
        "internet": "Internet/WiFi",
        "wifi": "Internet/WiFi",
        "light": "Electrical/Lighting",
        "electricity": "Electrical",
        "keycard": "Door/Keycard",
        "key card": "Door/Keycard",
        "door": "Door/Lock",
        "lock": "Door/Lock",
        "window": "Window",
        "safe": "Room Safe",
        "minibar": "Minibar",
        "noise": "Noise Issue",
    }
    text_lower = text.lower()
    for keyword, issue in issue_map.items():
        if keyword in text_lower:
            return issue
    return "General Maintenance"


# ─── Graph Nodes ──────────────────────────────────────────────────────────────

def node_classify_intent(state: ConversationState) -> ConversationState:
    """Classify the guest's intent."""
    message = state["user_message"]
    result = classify_intent(message, use_llm=True)

    logger.info(
        "intent_classified",
        session=state["session_id"][:12],
        intent=result.intent,
        confidence=result.confidence,
        message=message[:50],
    )

    return {
        **state,
        "intent": result.intent,
        "sub_intent": result.sub_intent,
        "confidence": result.confidence,
    }


def node_rag_retrieval(state: ConversationState) -> ConversationState:
    """Answer hotel information questions using RAG."""
    message = state["user_message"]
    history = state.get("history", [])

    result = run_rag_pipeline(
        query=message,
        conversation_history=history,
    )

    logger.info(
        "rag_node_complete",
        session=state["session_id"][:12],
        docs=result.retrieved_docs,
        fallback=result.fallback,
        latency_ms=result.latency_ms,
    )

    return {
        **state,
        "response": result.answer,
        "rag_sources": [s.to_dict() for s in result.sources],
        "retrieved_docs": [s.to_dict() for s in result.sources],
        "action_taken": "RAG_RETRIEVAL",
        "action_result": {"retrieved": result.retrieved_docs, "fallback": result.fallback},
        "error": None,
    }


def node_housekeeping(state: ConversationState) -> ConversationState:
    """Handle housekeeping requests."""
    message = state["user_message"]
    context = state.get("guest_context", {})

    room_number = _extract_room_number(message, context)
    quantity = _extract_quantity(message)
    items = _extract_items(message)

    # If message is asking a policy question or mentions animals/unrelated items, route to RAG
    lower_msg = message.lower()
    has_dispatch_trigger = any(w in lower_msg for w in ["send", "bring", "deliver", "get extra", "need extra", "please deliver", "delivered"]) and room_number
    is_policy_q = (not has_dispatch_trigger) and any(w in lower_msg for w in ["can i", "can we", "is it allowed", "policy", "fee", "tiger", "pet", "animal", "crocodile", "snake", "helicopter"])
    if not has_dispatch_trigger and (is_policy_q or (items == ["requested items"] and not any(w in lower_msg for w in ["clean", "housekeeping", "towel", "pillow", "blanket", "soap"]))):
        return node_rag_retrieval(state)

    if not room_number:
        return {
            **state,
            "response": (
                "Please specify the room number to dispatch this housekeeping request."
            ),
            "action_taken": "AWAITING_ROOM_NUMBER",
            "action_result": {},
        }

    result = tools.create_housekeeping_request(
        room_number=room_number,
        description=f"Front Office request: {message}",
        items=items,
        quantity=quantity,
        conversation_id=state.get("conversation_id"),
    )

    return {
        **state,
        "response": result["message"],
        "action_taken": "CREATE_HOUSEKEEPING_REQUEST",
        "action_result": result,
        "error": None if result["success"] else result.get("error"),
    }


def node_maintenance(state: ConversationState) -> ConversationState:
    """Handle maintenance requests."""
    message = state["user_message"]
    context = state.get("guest_context", {})

    room_number = _extract_room_number(message, context)
    issue_type = _extract_issue_type(message)

    if not room_number:
        return {
            **state,
            "response": (
                "Please specify the room number to log this maintenance ticket."
            ),
            "action_taken": "AWAITING_ROOM_NUMBER",
            "action_result": {},
        }

    result = tools.create_maintenance_request(
        room_number=room_number,
        issue_type=issue_type,
        description=message,
        conversation_id=state.get("conversation_id"),
    )

    return {
        **state,
        "response": result["message"],
        "action_taken": "CREATE_MAINTENANCE_REQUEST",
        "action_result": result,
        "error": None if result["success"] else result.get("error"),
    }


def node_complaint(state: ConversationState) -> ConversationState:
    """Handle complaints — create record and alert Guest Relations."""
    message = state["user_message"]
    context = state.get("guest_context", {})
    room_number = _extract_room_number(message, context)

    result = tools.create_complaint(
        description=message,
        room_number=room_number,
        conversation_id=state.get("conversation_id"),
    )

    return {
        **state,
        "response": result["message"],
        "action_taken": "CREATE_COMPLAINT",
        "action_result": result,
        "error": None if result["success"] else result.get("error"),
    }


def node_escalation(state: ConversationState) -> ConversationState:
    """Handle duty manager escalation requests."""
    message = state["user_message"]
    context = state.get("guest_context", {})
    room_number = _extract_room_number(message, context)

    history = state.get("history", [])
    summary = " | ".join(
        [f"{h['role']}: {h['content'][:80]}" for h in history[-4:]]
    ) if history else "No prior context."

    result = tools.escalate_to_front_desk(
        reason=message,
        room_number=room_number,
        conversation_id=state.get("conversation_id"),
        conversation_summary=summary,
    )

    return {
        **state,
        "response": result["message"],
        "action_taken": "ESCALATE_TO_FRONT_DESK",
        "action_result": result,
        "error": None if result["success"] else result.get("error"),
    }


def node_emergency(state: ConversationState) -> ConversationState:
    """Handle emergencies — front desk protocol."""
    return {
        **state,
        "response": (
            "🚨 **FRONT DESK EMERGENCY RESPONSE PROTOCOL** 🚨\n\n"
            "1. **Life Safety / Medical / Fire**: Immediately contact emergency services (911 / local dispatch).\n"
            "2. **Security & Management**: Alert Chief of Security and Hotel Manager immediately (Front Desk Ext 0).\n"
            "3. **Guest Verification**: Check PMS guest profile and room occupancy status.\n"
            "4. **Incident Logging**: An emergency incident ticket has been flagged on the operations board."
        ),
        "action_taken": "EMERGENCY_ALERT",
        "action_result": {"alerted": True},
        "error": None,
    }


def node_general(state: ConversationState) -> ConversationState:
    """Handle general queries with LLM + context."""
    message = state["user_message"]
    context = state.get("guest_context", {})
    history = state.get("history", [])

    # Try RAG first for general queries
    result = run_rag_pipeline(query=message, conversation_history=history)

    if not result.fallback:
        return {
            **state,
            "response": result.answer,
            "rag_sources": [s.to_dict() for s in result.sources],
            "action_taken": "RAG_RETRIEVAL",
            "action_result": {},
            "error": None,
        }

    # Fallback to LLM general response
    try:
        llm = get_llm()
        context_str = ""
        if context.get("room_number"):
            context_str = f"Inquiring regarding room {context['room_number']}. "

        response = llm.invoke([
            SystemMessage(content=(
                "You are Front Office AI Copilot, a specialized operational assistant for hotel front desk and reception staff. "
                f"{context_str}"
                "Provide clear, professional, and actionable operational guidance for hotel receptionists. "
                "If information is not verified in hotel records, advise checking the PMS or consulting the Duty Manager."
            )),
            HumanMessage(content=message),
        ])
        answer = response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        logger.error("general_node_llm_failed", error=str(e))
        answer = (
            "Unable to process query. Please check the property management system (PMS) or consult the Duty Manager."
        )

    return {
        **state,
        "response": answer,
        "action_taken": "GENERAL_RESPONSE",
        "action_result": {},
        "error": None,
    }


# ─── Routing Logic ────────────────────────────────────────────────────────────

def route_by_intent(state: ConversationState) -> str:
    """Route to the appropriate handler node based on classified intent."""
    intent = state.get("intent", Intent.GENERAL)

    routing_map = {
        Intent.EMERGENCY: "emergency",
        Intent.HUMAN_ESCALATION: "escalation",
        Intent.HOUSEKEEPING: "housekeeping",
        Intent.MAINTENANCE: "maintenance",
        Intent.COMPLAINT: "complaint",
        Intent.HOTEL_INFO: "rag",
        Intent.CHECK_IN_CHECKOUT: "rag",
        Intent.DINING: "rag",
        Intent.FACILITIES: "rag",
        Intent.TRANSPORTATION: "rag",
        Intent.ROOM_INFORMATION: "rag",
        Intent.CONCIERGE: "rag",
        Intent.BOOKING: "rag",
        Intent.BILLING: "rag",
        Intent.LOST_FOUND: "rag",
        Intent.ACCESSIBILITY: "rag",
    }

    node = routing_map.get(intent, "general")
    logger.info("routing", intent=intent, node=node)
    return node


# ─── Build Graph ──────────────────────────────────────────────────────────────

def build_concierge_graph() -> Any:
    """Construct and compile the LangGraph StateGraph."""
    graph = StateGraph(ConversationState)

    # Add all nodes
    graph.add_node("classify_intent", node_classify_intent)
    graph.add_node("rag", node_rag_retrieval)
    graph.add_node("housekeeping", node_housekeeping)
    graph.add_node("maintenance", node_maintenance)
    graph.add_node("complaint", node_complaint)
    graph.add_node("escalation", node_escalation)
    graph.add_node("emergency", node_emergency)
    graph.add_node("general", node_general)

    # Entry point
    graph.set_entry_point("classify_intent")

    # Routing from classifier
    graph.add_conditional_edges(
        "classify_intent",
        route_by_intent,
        {
            "rag": "rag",
            "housekeeping": "housekeeping",
            "maintenance": "maintenance",
            "complaint": "complaint",
            "escalation": "escalation",
            "emergency": "emergency",
            "general": "general",
        },
    )

    # All action nodes end the graph
    for node in ["rag", "housekeeping", "maintenance", "complaint", "escalation", "emergency", "general"]:
        graph.add_edge(node, END)

    compiled = graph.compile()
    logger.info("langgraph_compiled", nodes=7)
    return compiled


# Singleton compiled graph
_graph = None


def get_graph() -> Any:
    global _graph
    if _graph is None:
        _graph = build_concierge_graph()
    return _graph


async def process_message(
    session_id: str,
    message: str,
    conversation_id: str,
    guest_context: dict | None = None,
    history: list[dict] | None = None,
) -> dict[str, Any]:
    """
    Process a guest message through the full LangGraph pipeline.

    Returns structured response dict for the API layer.
    """
    initial_state: ConversationState = {
        "session_id": session_id,
        "user_message": message,
        "conversation_id": conversation_id,
        "guest_context": guest_context or {},
        "intent": "",
        "sub_intent": "",
        "confidence": 0.0,
        "retrieved_docs": [],
        "rag_sources": [],
        "action_taken": "",
        "action_result": {},
        "response": "",
        "error": None,
        "history": history or [],
    }

    try:
        graph = get_graph()
        run_config = {
            "run_name": "hotel_concierge_graph",
            "metadata": {
                "session_id": session_id,
                "conversation_id": conversation_id,
                "room_number": (guest_context or {}).get("room_number", ""),
            },
            "tags": ["concierge-agent", "langgraph"],
        }
        final_state = await graph.ainvoke(initial_state, config=run_config)

        return {
            "conversation_id": conversation_id,
            "message": final_state.get("response", "I'm unable to process your request right now."),
            "intent": final_state.get("intent", "GENERAL"),
            "sub_intent": final_state.get("sub_intent", ""),
            "confidence": final_state.get("confidence", 0.0),
            "action": final_state.get("action_taken", ""),
            "action_result": final_state.get("action_result", {}),
            "sources": final_state.get("rag_sources", []),
            "error": final_state.get("error"),
        }
    except Exception as e:
        logger.error("graph_processing_failed", error=str(e), session=session_id[:12])
        return {
            "conversation_id": conversation_id,
            "message": (
                "I apologize, I'm experiencing a technical issue. "
                "Please contact the front desk by dialing '0'."
            ),
            "intent": "GENERAL",
            "action": "ERROR",
            "sources": [],
            "error": str(e),
        }
