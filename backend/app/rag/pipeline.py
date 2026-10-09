"""
RAG pipeline — retrieval-augmented generation for hotel FAQ answering.

Flow:
  query → embed → similarity search → context construction → LLM → grounded response
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.llm import get_llm
from app.core.logging import get_logger
from app.rag.vector_store import similarity_search, get_collection_count

logger = get_logger(__name__)

# ─── System Prompt ────────────────────────────────────────────────────────────

HOTEL_SYSTEM_PROMPT = """You are "Front Office AI Copilot", an operational assistant tailored specifically for Hotel Reception and Front Desk staff.

COMMUNICATION & OPERATIONAL GUIDELINES:
1. Target Audience: Hotel receptionists, front desk agents, concierges, and guest service staff (non-technical hospitality workers).
2. Professional Hospitality Tone: Provide concise, polite, actionable, and customer-ready information that a receptionist can immediately use when speaking to a guest or handling a front-desk task.
3. No Technical Jargon: Never mention internal systems, databases, vector stores, algorithms, embeddings, JSON, code, or technical architecture.
4. Strict Knowledge Grounding: ONLY answer using the verified facts provided in the CONTEXT below. Never assume, invent, or guess hotel policies, rates, fees, amenities, or hours.
5. Missing Information: If the CONTEXT does not contain the answer or is empty, respond simply and clearly:
   "I could not find verified hotel policy information on this in the knowledge base. Please check the property management system (PMS) or consult the Duty Manager."
6. Formatting: Present information clearly with bullet points and bold highlights for quick scanning during busy front desk shifts.

CONTEXT PROVIDED:
{context}
"""

# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class RAGSource:
    """Metadata about a retrieved knowledge base document."""
    category: str
    question: str
    score: float
    source: str = "hotel_faq"
    intent: str = ""
    document: str = ""

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "question": self.question,
            "score": round(self.score, 3),
            "source": self.source,
            "intent": self.intent,
            "document": self.document,
        }


@dataclass
class RAGResult:
    """Result from the RAG pipeline."""
    answer: str
    sources: list[RAGSource] = field(default_factory=list)
    retrieved_docs: int = 0
    latency_ms: float = 0.0
    used_rag: bool = True
    fallback: bool = False

    def to_dict(self) -> dict:
        return {
            "answer": self.answer,
            "sources": [s.to_dict() for s in self.sources],
            "retrieved_docs": self.retrieved_docs,
            "latency_ms": round(self.latency_ms, 1),
            "used_rag": self.used_rag,
            "fallback": self.fallback,
        }


# ─── Pipeline ─────────────────────────────────────────────────────────────────

def _build_context(retrieved: list[tuple[Document, float]]) -> str:
    """Build a formatted context string from retrieved documents."""
    if not retrieved:
        return ""

    def _doc_sort_key(item: tuple[Document, float]):
        doc, score = item
        doc_name = str(doc.metadata.get("document", "")).lower()
        source = str(doc.metadata.get("source", "")).lower()
        is_updated = 1 if ("update" in doc_name or "25" in doc_name or "new" in doc_name) else 0
        is_pdf_doc = 1 if (source == "faq_documents" or doc_name.endswith(".pdf")) else 0
        return (is_updated, is_pdf_doc, score)

    sorted_retrieved = sorted(retrieved, key=_doc_sort_key, reverse=True)

    parts = []
    for i, (doc, score) in enumerate(sorted_retrieved, 1):
        meta = doc.metadata
        category = meta.get("category", "General")
        question = meta.get("question", "")
        raw_content = doc.page_content
        if "\nAnswer:" in raw_content:
            answer = raw_content.split("\nAnswer:", 1)[1].strip()
        elif "Answer:" in raw_content:
            answer = raw_content.split("Answer:", 1)[1].strip()
        elif "\nA: " in raw_content:
            answer = raw_content.split("\nA: ", 1)[1].strip()
        else:
            answer = raw_content.strip()

        parts.append(
            f"[{i}] Category: {category}\n"
            f"    Q: {question}\n"
            f"    A: {answer}\n"
            f"    (Relevance: {score:.2f})"
        )
    return "\n\n".join(parts)


def _extract_sources(retrieved: list[tuple[Document, float]]) -> list[RAGSource]:
    """Extract source metadata from retrieved documents."""
    sources = []
    for doc, score in retrieved:
        meta = doc.metadata
        sources.append(RAGSource(
            category=meta.get("category", "General"),
            question=meta.get("question", ""),
            score=score,
            source=meta.get("source", "hotel_faq"),
            intent=meta.get("intent", ""),
            document=meta.get("document", ""),
        ))
    return sources


def run_rag_pipeline(
    query: str,
    conversation_history: list[dict] | None = None,
    filter_category: str | None = None,
) -> RAGResult:
    """
    Execute the full RAG pipeline for a guest query.

    Args:
        query: The guest's question/request.
        conversation_history: Previous messages for multi-turn context.
        filter_category: Optional Chroma metadata filter by category.

    Returns:
        RAGResult with answer, sources, and metadata.
    """
    start_time = time.monotonic()

    # Step 1: Check if FAQ store has documents
    try:
        doc_count = get_collection_count()
    except Exception:
        doc_count = 0

    if doc_count == 0:
        logger.warning("rag_empty_knowledge_base", query=query[:60])
        return RAGResult(
            answer=(
                "No hotel policy records are currently found in the system. "
                "Please check the property management system (PMS) or consult the Front Office Manager."
            ),
            fallback=True,
            used_rag=False,
        )

    # Step 2: Similarity search
    chroma_filter = {"category": filter_category} if filter_category else None
    try:
        retrieved = similarity_search(query, filter=chroma_filter)
    except Exception as e:
        logger.error("rag_retrieval_failed", error=str(e), query=query[:60])
        retrieved = []

    def _doc_sort_key(item: tuple[Document, float]):
        doc, score = item
        doc_name = str(doc.metadata.get("document", "")).lower()
        source = str(doc.metadata.get("source", "")).lower()
        is_updated = 1 if ("update" in doc_name or "25" in doc_name or "new" in doc_name) else 0
        is_pdf_doc = 1 if (source == "faq_documents" or doc_name.endswith(".pdf")) else 0
        return (is_updated, is_pdf_doc, score)

    retrieved = sorted(retrieved, key=_doc_sort_key, reverse=True)

    # If local vector search returned no results or weak matches, consult external hotel knowledge
    external_match = None
    if not retrieved or (retrieved and retrieved[0][1] < 0.45):
        from app.services.external_hotel_service import external_hotel_service
        try:
            external_match = external_hotel_service.query_external_hotel_live(query)
        except Exception as e:
            logger.warning("external_hotel_query_failed", error=str(e))

    if not retrieved and not external_match:
        logger.info("rag_no_relevant_context", query=query[:60])
        return RAGResult(
            answer="I could not find verified hotel policy information on this in the knowledge base. Please check the property management system (PMS) or consult the Duty Manager.",
            sources=[],
            retrieved_docs=0,
            latency_ms=(time.monotonic() - start_time) * 1000,
            used_rag=True,
            fallback=True,
        )

    context = _build_context(retrieved)
    sources = _extract_sources(retrieved)

    if external_match:
        ext_snippet = (
            f"[External Hotel API] Category: {external_match['category']}\n"
            f"    Q: {external_match['question']}\n"
            f"    A: {external_match['answer']}\n"
            f"    (Source: {external_match.get('hotel_name', 'External Hotel API')})"
        )
        context = f"{context}\n\n{ext_snippet}" if context else ext_snippet
        sources.append(RAGSource(
            category=external_match.get("category", "Hotel Info"),
            question=external_match.get("question", ""),
            score=external_match.get("score", 0.8),
            source="external_hotel_api",
            intent="HOTEL_INFO",
        ))

    # Step 3: Build prompt
    system_content = HOTEL_SYSTEM_PROMPT.format(context=context or "No relevant context found.")

    messages = [SystemMessage(content=system_content)]

    # Include recent conversation history (last 4 turns)
    if conversation_history:
        for turn in conversation_history[-8:]:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            # Skip assistant messages in history to keep prompt tight
    messages.append(HumanMessage(content=query))

    # Step 4: LLM inference
    try:
        llm = get_llm()
        llm_config = {
            "run_name": "hotel_rag_llm",
            "metadata": {
                "retrieved_docs_count": len(retrieved),
                "has_external_match": bool(external_match),
            },
            "tags": ["rag-pipeline", "concierge-llm"],
        }
        response = llm.invoke(messages, config=llm_config)
        answer = response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        logger.error("rag_llm_failed", error=str(e))
        answer = (
            "Unable to process query at this time. "
            "Please check the property management system (PMS) or consult the Duty Manager."
        )
        return RAGResult(
            answer=answer,
            fallback=True,
            used_rag=False,
            latency_ms=(time.monotonic() - start_time) * 1000,
        )

    latency_ms = (time.monotonic() - start_time) * 1000

    logger.info(
        "rag_pipeline_complete",
        query=query[:60],
        retrieved_docs=len(retrieved),
        sources=len(sources),
        latency_ms=round(latency_ms, 1),
    )

    return RAGResult(
        answer=answer,
        sources=sources,
        retrieved_docs=len(retrieved),
        latency_ms=latency_ms,
        used_rag=True,
        fallback=len(retrieved) == 0,
    )
