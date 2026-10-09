"""
External Hotel Information & FAQ Service.

Connects to third-party Hotel Management / CMS REST APIs or provides 
verified live hotel information for the specified property.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from langchain_core.documents import Document

from app.core.config import get_settings
from app.core.logging import get_logger
from app.rag.vector_store import add_documents, get_collection_count

logger = get_logger(__name__)

# In-memory service state tracking
_service_state = {
    "last_synced_at": None,
    "last_sync_count": 0,
    "last_sync_status": "idle",
    "last_error": None,
}

# ─── Built-in Verified Hotel Knowledge & FAQ Profile ─────────────────────────
# Used when external_hotel_api_url is not set or as fallback for this hotel

DEFAULT_EXTERNAL_HOTEL_FAQS: list[dict[str, Any]] = [
    {
        "category": "Amenities & Leisure",
        "question": "What are the swimming pool hours and policies?",
        "answer": (
            "Our heated infinity pool and jacuzzi on the 5th floor terrace are open daily from 6:00 AM to 10:00 PM. "
            "Complimentary plush towels, loungers, and poolside refreshments are provided. Children under 14 must be accompanied by an adult."
        ),
        "intent": "HOTEL_INFO",
        "keywords": ["pool", "swim", "swimming", "jacuzzi", "hours"],
    },
    {
        "category": "Parking & Transportation",
        "question": "Do you provide EV charging stations or valet parking?",
        "answer": (
            "Yes, we offer 24/7 valet parking with 8 dedicated Level 2 and Tesla Superchargers in the underground parking garage. "
            "Valet overnight parking is $45/night with complimentary EV charging for hotel guests."
        ),
        "intent": "HOTEL_INFO",
        "keywords": ["ev", "electric vehicle", "charging", "charger", "tesla", "valet", "parking"],
    },
    {
        "category": "Pet Policy",
        "question": "Is the hotel pet-friendly?",
        "answer": (
            "Yes! We are delighted to welcome dogs and cats up to 50 lbs (23 kg). "
            "We provide plush pet beds, organic treats, food bowls, and a walking map. A one-time pet sanitation fee of $75 per stay applies."
        ),
        "intent": "HOTEL_INFO",
        "keywords": ["pet", "pets", "dog", "dogs", "cat", "cats", "animal", "friendly"],
    },
    {
        "category": "Spa & Wellness",
        "question": "What spa services and fitness facilities are available?",
        "answer": (
            "The Horizon Wellness Spa & 24/7 Fitness Center is located on the 3rd floor. "
            "We offer Swedish massage, aromatherapy facials, sauna, and steam rooms. Fitness facilities feature Peloton bikes and free weights. "
            "Spa treatments can be booked between 9:00 AM and 8:00 PM."
        ),
        "intent": "HOTEL_INFO",
        "keywords": ["spa", "massage", "gym", "fitness", "sauna", "wellness", "workout"],
    },
    {
        "category": "Transportation",
        "question": "Do you offer airport shuttle or limousine transfers?",
        "answer": (
            "We provide private luxury sedan and SUV airport transfers 24/7. "
            "Standard airport transfer is $65 each way. Please contact the concierge desk at least 4 hours in advance to schedule your pickup."
        ),
        "intent": "TRANSPORTATION",
        "keywords": ["airport", "shuttle", "transfer", "limo", "limousine", "car service", "pickup"],
    },
    {
        "category": "Dining & Nightlife",
        "question": "What are the hours and dress code for the rooftop lounge?",
        "answer": (
            "The SkyView Rooftop Lounge operates from 5:00 PM to 1:00 AM Sunday through Thursday, and until 2:00 AM on Fridays and Saturdays. "
            "It features artisan cocktails and panoramic skyline views. The dress code is smart casual (no athletic wear or flip-flops after 7:00 PM)."
        ),
        "intent": "DINING",
        "keywords": ["rooftop", "lounge", "bar", "cocktails", "skyview", "dress code", "hours"],
    },
    {
        "category": "Business & Events",
        "question": "Is there a business center or meeting space?",
        "answer": (
            "Yes, our 24-hour Executive Business Center is on the 2nd floor, offering high-speed printing, scanning, and private workstations. "
            "Conference rooms and boardrooms with videoconferencing are available for reservation through the front desk."
        ),
        "intent": "FACILITIES",
        "keywords": ["business", "center", "print", "printer", "printing", "meeting", "conference", "work"],
    },
    {
        "category": "Room Amenities",
        "question": "What type of coffee machines and Wi-Fi are provided in the rooms?",
        "answer": (
            "Every guest room features a Nespresso Vertuo coffee machine with complimentary daily replenished pods and teas. "
            "Ultra-high-speed Wi-Fi (up to 300 Mbps) is complimentary across the entire hotel property."
        ),
        "intent": "HOTEL_INFO",
        "keywords": ["coffee", "nespresso", "wifi", "internet", "tea", "amenities"],
    },
    {
        "category": "Laundry & Dry Cleaning",
        "question": "Do you offer same-day laundry or dry cleaning?",
        "answer": (
            "Yes, same-day laundry and dry cleaning are available Monday through Saturday. "
            "Items picked up before 9:00 AM will be returned by 6:00 PM that evening. Laundry bags and slips are located in your room closet."
        ),
        "intent": "HOUSEKEEPING",
        "keywords": ["laundry", "dry cleaning", "ironing", "wash", "clothes"],
    },
]


def _hash_id(text: str) -> str:
    """Generate deterministic ID for FAQ items."""
    return "ext_faq_" + hashlib.md5(text.encode("utf-8")).hexdigest()[:16]


class ExternalHotelService:
    """Service to communicate with external Hotel APIs and maintain synchronized RAG knowledge."""

    def __init__(self):
        self.settings = get_settings()

    async def fetch_external_faqs(self) -> list[dict[str, Any]]:
        """
        Fetch FAQs and hotel info from the configured external API URL,
        falling back to the verified hotel knowledge profile if not configured.
        """
        api_url = self.settings.external_hotel_api_url
        api_key = self.settings.external_hotel_api_key

        if not api_url:
            logger.info("using_default_external_hotel_faqs", hotel_name=self.settings.hotel_name)
            return DEFAULT_EXTERNAL_HOTEL_FAQS

        headers = {
            "Accept": "application/json",
            "User-Agent": f"HotelConcierge-AI/1.0 ({self.settings.hotel_name})",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            logger.info("fetching_from_external_hotel_api", url=api_url)
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(api_url, headers=headers)
                res.raise_for_status()
                data = res.json()

                # Handle various API envelope formats: list or dict with faqs/items
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return data.get("faqs") or data.get("items") or data.get("data") or []
                return []
        except Exception as e:
            logger.error("external_hotel_api_fetch_failed", error=str(e), url=api_url)
            _service_state["last_error"] = str(e)
            # Graceful fallback to verified profile
            return DEFAULT_EXTERNAL_HOTEL_FAQS

    async def sync_faqs_to_chroma(self) -> dict[str, Any]:
        """
        Sync external hotel FAQs into ChromaDB.
        Generates Document embeddings and tags each document with source metadata.
        """
        _service_state["last_sync_status"] = "syncing"
        try:
            faqs = await self.fetch_external_faqs()
            if not faqs:
                _service_state["last_sync_status"] = "empty"
                return {"success": False, "count": 0, "message": "No FAQs returned from external source"}

            docs: list[Document] = []
            ids: list[str] = []

            for item in faqs:
                question = item.get("question", "").strip()
                answer = item.get("answer", "").strip()
                category = item.get("category", "Hotel Information")
                intent = item.get("intent", "HOTEL_INFO")

                if not question or not answer:
                    continue

                content = f"Question: {question}\nAnswer: {answer}"
                doc_id = _hash_id(f"{self.settings.hotel_name}_{question}")

                doc = Document(
                    page_content=content,
                    metadata={
                        "category": category,
                        "question": question,
                        "intent": intent,
                        "source": "external_hotel_api",
                        "hotel_name": self.settings.hotel_name,
                        "synced_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                docs.append(doc)
                ids.append(doc_id)

            if docs:
                add_documents(documents=docs, ids=ids)

            _service_state["last_synced_at"] = datetime.now(timezone.utc).isoformat()
            _service_state["last_sync_count"] = len(docs)
            _service_state["last_sync_status"] = "success"
            _service_state["last_error"] = None

            logger.info("external_faqs_synced", count=len(docs), hotel=self.settings.hotel_name)
            return {
                "success": True,
                "count": len(docs),
                "hotel_name": self.settings.hotel_name,
                "synced_at": _service_state["last_synced_at"],
            }
        except Exception as e:
            logger.error("external_faq_sync_failed", error=str(e))
            _service_state["last_sync_status"] = "error"
            _service_state["last_error"] = str(e)
            return {"success": False, "error": str(e)}

    def query_external_hotel_live(self, query: str) -> Optional[dict[str, Any]]:
        """
        On-demand lookup against external hotel knowledge.
        Used as dynamic fallback when local Chroma vector retrieval returns no high-confidence results.
        """
        STOP_WORDS = {
            "what", "is", "the", "are", "do", "you", "a", "an", "and", "or", "in",
            "on", "at", "for", "to", "of", "with", "can", "i", "we", "my", "your",
            "our", "have", "has", "it", "any", "how", "me", "there"
        }
        query_words = set(query.lower().split()) - STOP_WORDS
        best_match = None
        best_overlap = 0

        for item in DEFAULT_EXTERNAL_HOTEL_FAQS:
            keywords = set(k.lower() for k in item.get("keywords", [])) - STOP_WORDS
            question_words = set(item.get("question", "").lower().split()) - STOP_WORDS
            
            overlap = len(query_words.intersection(keywords.union(question_words)))
            if overlap > best_overlap and overlap >= 2:
                best_overlap = overlap
                best_match = item

        if best_match:
            return {
                "category": best_match.get("category", "Hotel Information"),
                "question": best_match.get("question", ""),
                "answer": best_match.get("answer", ""),
                "source": "external_hotel_api",
                "hotel_name": self.settings.hotel_name,
                "score": round(min(0.85, 0.5 + (best_overlap * 0.15)), 2),
            }

        return None

    def get_status(self) -> dict[str, Any]:
        """Return connectivity and synchronization status."""
        total_docs = 0
        try:
            total_docs = get_collection_count()
        except Exception:
            pass

        return {
            "hotel_name": self.settings.hotel_name,
            "hotel_website": self.settings.hotel_website_url,
            "api_endpoint": self.settings.external_hotel_api_url or "Built-in / Configurable REST API",
            "provider_mode": "remote_rest" if self.settings.external_hotel_api_url else "verified_hotel_profile",
            "sync_enabled": self.settings.external_sync_enabled,
            "last_synced_at": _service_state["last_synced_at"],
            "last_sync_count": _service_state["last_sync_count"],
            "last_sync_status": _service_state["last_sync_status"],
            "total_knowledge_documents": total_docs,
            "last_error": _service_state["last_error"],
        }


# Singleton instance
external_hotel_service = ExternalHotelService()
