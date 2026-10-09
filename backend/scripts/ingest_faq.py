#!/usr/bin/env python3
"""
FAQ Ingestion Script — loads hotel FAQs into Chroma vector store.

Usage:
    python scripts/ingest_faq.py                    # Ingest default sample_faqs.json
    python scripts/ingest_faq.py --file /path/to/faqs.json
    python scripts/ingest_faq.py --reset             # Clear existing data and re-index
    python scripts/ingest_faq.py --file data/custom_faqs.json --reset

FAQ JSON format (per item):
{
    "category": "Housekeeping",
    "question": "Can I request extra towels?",
    "answer": "Yes, you can request additional towels...",
    "intent": "HOUSEKEEPING",
    "entities": ["room_number", "quantity"],
    "source": "hotel_faq"
}
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

# Ensure the backend app is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env before imports that use settings
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")

from langchain_core.documents import Document

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.rag.embeddings import get_embeddings
from app.rag.vector_store import add_documents, get_vector_store

configure_logging("INFO")
logger = get_logger("ingest")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _stable_id(item: dict[str, Any]) -> str:
    """Generate a stable, deterministic ID from question text."""
    text = item.get("question", "") + item.get("category", "")
    return "faq_" + hashlib.md5(text.encode()).hexdigest()[:16]


def _clean_text(text: str) -> str:
    """Basic text cleaning."""
    return " ".join(text.split()).strip()


def _build_document(item: dict[str, Any]) -> Document:
    """Build a LangChain Document from an FAQ item."""
    question = _clean_text(item.get("question", ""))
    answer = _clean_text(item.get("answer", ""))

    # page_content is what gets embedded — combine Q+A for richer retrieval
    page_content = f"Question: {question}\nAnswer: {answer}"

    metadata = {
        "category": item.get("category", "General"),
        "question": question,
        "intent": item.get("intent", "GENERAL"),
        "source": item.get("source", "hotel_faq"),
        "entities": json.dumps(item.get("entities", [])),
    }

    return Document(page_content=page_content, metadata=metadata)


def load_faqs(file_path: Path) -> list[dict[str, Any]]:
    """Load and validate FAQ JSON file."""
    if not file_path.exists():
        logger.error("faq_file_not_found", path=str(file_path))
        sys.exit(1)

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        logger.error("invalid_faq_format", message="Expected a JSON array")
        sys.exit(1)

    valid = []
    for i, item in enumerate(data):
        if not item.get("question") or not item.get("answer"):
            logger.warning("skipping_invalid_item", index=i, item=str(item)[:60])
            continue
        valid.append(item)

    logger.info("faqs_loaded", total=len(data), valid=len(valid))
    return valid


def ingest(file_path: Path, reset: bool = False) -> None:
    """Main ingestion function."""
    settings = get_settings()

    logger.info(
        "ingestion_starting",
        file=str(file_path),
        chroma_dir=settings.chroma_persist_directory,
        collection=settings.chroma_collection_name,
        reset=reset,
    )

    # Load FAQ data
    faqs = load_faqs(file_path)

    # Reset collection if requested
    if reset:
        import chromadb
        client = chromadb.PersistentClient(path=settings.chroma_persist_directory)
        try:
            client.delete_collection(settings.chroma_collection_name)
            logger.info("collection_reset", collection=settings.chroma_collection_name)
        except Exception:
            pass  # Collection may not exist yet

    # Warm up embedding model
    logger.info("loading_embedding_model", model=settings.embedding_model)
    get_embeddings()

    # Build documents
    documents = []
    ids = []
    for item in faqs:
        doc = _build_document(item)
        doc_id = _stable_id(item)
        documents.append(doc)
        ids.append(doc_id)

    logger.info("documents_prepared", count=len(documents))

    # Ingest in batches
    BATCH_SIZE = 50
    total_added = 0
    for i in range(0, len(documents), BATCH_SIZE):
        batch_docs = documents[i : i + BATCH_SIZE]
        batch_ids = ids[i : i + BATCH_SIZE]

        try:
            add_documents(batch_docs, ids=batch_ids)
            total_added += len(batch_docs)
            logger.info(
                "batch_ingested",
                batch=i // BATCH_SIZE + 1,
                count=len(batch_docs),
                total_so_far=total_added,
            )
        except Exception as e:
            logger.error("batch_failed", batch=i // BATCH_SIZE + 1, error=str(e))

    # Verify
    store = get_vector_store()
    final_count = store._collection.count()
    logger.info(
        "ingestion_complete",
        ingested=total_added,
        total_in_store=final_count,
        collection=settings.chroma_collection_name,
    )

    print(f"\n✅ Ingestion complete!")
    print(f"   Processed: {total_added} FAQ documents")
    print(f"   Total in knowledge base: {final_count} documents")
    print(f"   Collection: {settings.chroma_collection_name}")
    print(f"   Chroma path: {settings.chroma_persist_directory}")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Ingest hotel FAQ data into Chroma vector store"
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=Path(__file__).parent.parent / "data" / "sample_faqs.json",
        help="Path to FAQ JSON file (default: data/sample_faqs.json)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing collection before ingestion (full re-index)",
    )

    args = parser.parse_args()
    ingest(args.file, reset=args.reset)


if __name__ == "__main__":
    main()
