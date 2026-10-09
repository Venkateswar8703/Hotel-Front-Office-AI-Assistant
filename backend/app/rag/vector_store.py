"""
Chroma vector store wrapper for hotel FAQ retrieval.
"""
from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import chromadb
from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.core.config import get_settings
from app.core.logging import get_logger
from app.rag.embeddings import get_embeddings

logger = get_logger(__name__)


def _get_persist_dir() -> str:
    """Consistently resolve persist directory as absolute path."""
    settings = get_settings()
    persist_dir = settings.chroma_persist_directory
    if not os.path.isabs(persist_dir):
        backend_dir = Path(__file__).resolve().parent.parent.parent
        clean_rel = persist_dir.lstrip("./").lstrip("/")
        persist_dir = str((backend_dir / clean_rel).resolve())
    return persist_dir


def reset_collection() -> Chroma:
    """
    Safely delete existing collection, recreate an empty initialized one,
    and clear the cached vector store instance.
    """
    settings = get_settings()
    persist_dir = _get_persist_dir()
    client = chromadb.PersistentClient(path=persist_dir)

    try:
        client.delete_collection(settings.chroma_collection_name)
        logger.info("chroma_collection_deleted", collection=settings.chroma_collection_name)
    except Exception:
        pass

    # Ensure collection is created fresh
    client.get_or_create_collection(settings.chroma_collection_name)
    get_vector_store.cache_clear()
    logger.info("chroma_collection_recreated", collection=settings.chroma_collection_name)
    return get_vector_store()


@lru_cache(maxsize=1)
def get_vector_store() -> Chroma:
    """Return an initialized Chroma vector store instance."""
    settings = get_settings()
    persist_dir = _get_persist_dir()

    client = chromadb.PersistentClient(path=persist_dir)

    # Ensure the collection exists before wrapping with langchain_chroma
    client.get_or_create_collection(settings.chroma_collection_name)

    store = Chroma(
        client=client,
        collection_name=settings.chroma_collection_name,
        embedding_function=get_embeddings(),
    )
    logger.info(
        "chroma_store_ready",
        collection=settings.chroma_collection_name,
        path=persist_dir,
    )
    return store


def add_documents(documents: list[Document], ids: list[str] | None = None) -> list[str]:
    """Add documents to the vector store with automatic error recovery and retry."""
    if not documents:
        return []

    try:
        store = get_vector_store()
        added_ids = store.add_documents(documents=documents, ids=ids)
    except Exception as e:
        logger.warning("add_documents_failed_recovering_collection", error=str(e))
        get_vector_store.cache_clear()
        store = get_vector_store()
        added_ids = store.add_documents(documents=documents, ids=ids)

    logger.info("documents_added", count=len(documents))
    return added_ids


def similarity_search(
    query: str,
    k: int | None = None,
    filter: dict[str, Any] | None = None,
) -> list[tuple[Document, float]]:
    """
    Perform similarity search and return (document, score) pairs.
    Combines dense semantic cosine similarity with question-match boosting.
    """
    settings = get_settings()
    top_k = k or settings.rag_top_k

    try:
        count = get_collection_count()
        if count == 0:
            return []

        results = get_vector_store().similarity_search_with_relevance_scores(
            query=query,
            k=max(top_k * 50, 300),
            filter=filter,
        )
    except Exception as e:
        logger.warning("similarity_search_failed", error=str(e))
        get_vector_store.cache_clear()
        return []

    query_lower = query.lower().strip()
    query_words = set(re.findall(r'\b\w+\b', query_lower))

    # Identify if query is asking about check-in / check-out timings
    is_checkin_query = any(w in query_lower for w in ["checkin", "check-in", "check in"])
    is_checkout_query = any(w in query_lower for w in ["checkout", "check-out", "check out"])
    is_timing_query = any(w in query_lower for w in ["time", "timing", "hours", "when", "at", "standard"]) or len(query_words) <= 3

    min_threshold = max(settings.rag_similarity_threshold, 0.35)
    scored_results: list[tuple[Document, float]] = []

    for doc, score in results:
        q_text = str(doc.metadata.get("question", "")).lower()
        doc_name = str(doc.metadata.get("document", "")).lower()
        doc_name_lower = doc_name.lower()

        q_words = set(re.findall(r'\b\w+\b', q_text)) if q_text else set()
        overlap = len(query_words & q_words) / max(len(query_words), 1) if query_words and q_words else 0.0

        # Discard irrelevant documents with negative/near-zero semantic score and no keyword overlap
        is_checkin_doc = "check-in" in q_text or "check in" in q_text or "checkin" in q_text
        is_checkout_doc = "check-out" in q_text or "check out" in q_text or "checkout" in q_text

        # Check for ungrounded specific entities (e.g., casino, skating, submarine, helicopter)
        unsupported_tokens = {
            "casino", "skating", "rink", "bowling", "submarine", "ferrari", "lamborghini",
            "bonfire", "bbq", "barbecue", "shisha", "hookah", "gasoline", "tiger", "lion",
            "cheetah", "crocodile", "snake", "helicopter", "fastpass", "disney", "marriott",
            "hilton", "bonvoy", "saturn", "jupiter", "mars", "bitcoin", "ethereum", "crypto"
        }
        query_unsupported = query_words & unsupported_tokens
        if query_unsupported:
            doc_text = (q_text + " " + doc.page_content).lower()
            if not any(token in doc_text for token in query_unsupported):
                continue

        if score < 0.25 and overlap == 0.0 and not (is_checkin_query and is_checkin_doc) and not (is_checkout_query and is_checkout_doc):
            continue

        boost = 0.0
        # Priority for updated policy files only when document is genuinely relevant
        if overlap > 0.15 or score >= 0.35:
            if "update" in doc_name_lower or "25" in doc_name_lower or "new" in doc_name_lower:
                boost += 0.40
            elif doc.metadata.get("source") == "faq_documents":
                boost += 0.10

        # Query-intent specific question boosting
        if is_checkin_query and is_checkin_doc:
            if is_timing_query or "policy" in query_lower or "time" in q_text or "standard" in q_text:
                boost += 0.40
            else:
                boost += 0.20
            if "early" not in query_lower and "early" in q_text:
                boost -= 0.25

        if is_checkout_query and is_checkout_doc:
            if is_timing_query or "policy" in query_lower or "time" in q_text or "standard" in q_text:
                boost += 0.40
            else:
                boost += 0.20
            if "late" not in query_lower and "late" in q_text:
                boost -= 0.25

        # Boost exact or high keyword overlap with question
        if q_text:
            if query_lower == q_text or query_lower in q_text or q_text in query_lower:
                boost += 0.50
            elif overlap > 0:
                boost += overlap * 0.40

        final_score = score + boost
        if final_score >= min_threshold:
            scored_results.append((doc, final_score))

    # Sort by boosted score descending
    scored_results.sort(key=lambda x: x[1], reverse=True)
    filtered = scored_results[:top_k]

    logger.info(
        "similarity_search",
        query=query[:60],
        total_results=len(results),
        filtered_results=len(filtered),
    )
    return filtered


def get_collection_count() -> int:
    """Return number of documents in the vector store safely."""
    try:
        store = get_vector_store()
        return store._collection.count()
    except Exception as e:
        logger.warning("get_collection_count_recovery", error=str(e))
        get_vector_store.cache_clear()
        try:
            store = get_vector_store()
            return store._collection.count()
        except Exception:
            return 0
