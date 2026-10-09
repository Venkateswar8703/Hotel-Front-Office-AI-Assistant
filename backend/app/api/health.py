"""
Health check and dashboard stats API.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.rag.vector_store import get_collection_count
from app.tools.hotel_tools import (
    get_all_complaints,
    get_all_escalations,
    get_all_maintenance_tickets,
    get_all_service_requests,
)
from app.services.session_service import get_active_session_count

from app.core.langsmith import get_langsmith_status

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health():
    """Health check endpoint."""
    try:
        doc_count = get_collection_count()
        kb_status = "ready" if doc_count > 0 else "empty"
    except Exception:
        doc_count = 0
        kb_status = "unavailable"

    return {
        "status": "healthy",
        "knowledge_base": kb_status,
        "document_count": doc_count,
        "active_sessions": get_active_session_count(),
        "langsmith": get_langsmith_status(),
    }


@router.get("/dashboard/stats")
async def dashboard_stats():
    """Aggregate stats for the staff dashboard."""
    service_requests = get_all_service_requests()
    maintenance = get_all_maintenance_tickets()
    complaints = get_all_complaints()
    escalations = get_all_escalations()

    def _count_by_status(items: list[dict]) -> dict:
        counts: dict = {}
        for item in items:
            s = item.get("status", "PENDING")
            counts[s] = counts.get(s, 0) + 1
        return counts

    return {
        "service_requests": {
            "total": len(service_requests),
            "by_status": _count_by_status(service_requests),
            "items": service_requests,
        },
        "maintenance": {
            "total": len(maintenance),
            "by_status": _count_by_status(maintenance),
            "items": maintenance,
        },
        "complaints": {
            "total": len(complaints),
            "by_status": _count_by_status(complaints),
            "items": complaints,
        },
        "escalations": {
            "total": len(escalations),
            "by_status": _count_by_status(escalations),
            "items": escalations,
        },
    }
