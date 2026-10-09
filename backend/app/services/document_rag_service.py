"""
Document RAG Service — Ingests and manages hotel knowledge from FAQ PDF documents.

Parses PDF documents in the FAQ folder, extracting structured Q&A pairs
and indexing them into ChromaDB for high-accuracy semantic search.
Features high-speed incremental diff caching so subsequent re-indexes
take milliseconds instead of full multi-minute reprocessing.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pypdf
from langchain_core.documents import Document

from app.core.config import get_settings
from app.core.logging import get_logger
from app.rag.vector_store import add_documents, get_collection_count, get_vector_store, reset_collection

logger = get_logger(__name__)

# State tracking for document ingestion
_document_stats: dict[str, Any] = {
    "total_pdfs": 0,
    "total_qa_pairs": 0,
    "last_ingested_at": None,
    "status": "idle",
    "categories": [],
    "error": None,
}


import yaml

def _get_cache_path() -> Path:
    """Return path to the PDF ingest hash cache file."""
    base_path = Path(__file__).parent.parent.parent
    return base_path / "data" / ".pdf_ingest_cache.json"


def _get_yaml_knowledge_path() -> Path:
    """Return path to the human-readable YAML knowledge catalog."""
    base_path = Path(__file__).parent.parent.parent
    return base_path / "data" / "hotel_knowledge.yaml"


def export_knowledge_to_yaml(faq_dir: Optional[str] = None) -> Path:
    """Export all parsed FAQ policies into a clean, human-readable YAML file."""
    if faq_dir is None:
        base_path = Path(__file__).parent.parent.parent.parent
        faq_dir = str(base_path / "FAQ")

    pdf_files = sorted(glob.glob(os.path.join(faq_dir, "*.pdf")))
    data_by_category: dict[str, list[dict[str, str]]] = {}

    for pdf_path in pdf_files:
        doc_name = os.path.basename(pdf_path)
        items = parse_pdf_document(pdf_path)
        for item in items:
            cat = item.get("category", "General")
            if cat not in data_by_category:
                data_by_category[cat] = []
            data_by_category[cat].append({
                "question": item["question"],
                "answer": item["answer"],
                "document": doc_name,
            })

    export_path = _get_yaml_knowledge_path()
    export_path.parent.mkdir(parents=True, exist_ok=True)
    with open(export_path, "w", encoding="utf-8") as f:
        yaml.dump(
            {
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "total_documents": len(pdf_files),
                "knowledge_by_category": data_by_category,
            },
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )
    return export_path


def _load_cache() -> dict[str, Any]:
    """Load cached file hashes and metadata."""
    cache_path = _get_cache_path()
    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("failed_to_read_pdf_cache", error=str(e))
    return {}


def _save_cache(cache: dict[str, Any]) -> None:
    """Save updated file hashes and metadata to cache."""
    cache_path = _get_cache_path()
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        logger.warning("failed_to_save_pdf_cache", error=str(e))


def _get_file_hash(file_path: str) -> str:
    """Compute SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _clean(text: str) -> str:
    """Normalize whitespace in text."""
    return " ".join(text.split()).strip()


def _make_doc_id(doc_name: str, question: str) -> str:
    """Generate a deterministic ID for a Q&A pair."""
    raw = f"{doc_name}:{question}"
    return "pdf_faq_" + hashlib.md5(raw.encode("utf-8")).hexdigest()[:16]


def _extract_category_from_doc_name(doc_name: str) -> str:
    """Derive human-readable category name from document filename."""
    # E.g. "Doc_5_Food_Dining.pdf" -> "Food & Dining"
    clean_name = re.sub(r"^Doc_\d+_[-_]*", "", doc_name)
    clean_name = clean_name.replace(".pdf", "").replace("_", " ").strip()
    return clean_name.title() if clean_name else "General Hotel Information"


def parse_pdf_document(file_path: str) -> list[dict[str, Any]]:
    """
    Parse a single PDF file and extract all Q&A pairs / policy chunks with metadata.
    Handles multiple PDF layout formats:
      - 'Question: ... Answer: ...' or 'Q: ... A: ...'
      - '1. ... Answer: ...'
      - '1. Question? \n Answer text'
      - 'Question? \n Answer text'
      - Section headings / bulleted policies
      - Paragraph chunking fallback for general text documents
    """
    doc_name = os.path.basename(file_path)
    category = _extract_category_from_doc_name(doc_name)

    reader = pypdf.PdfReader(file_path)
    full_text = "\n".join([page.extract_text() or "" for page in reader.pages])
    if not full_text.strip():
        return []

    pairs: list[dict[str, Any]] = []

    # Format A1: Question: ... \n Answer: ... (case-insensitive)
    pattern_a1 = re.compile(
        r"(?:^|\n)\s*(?:Question|Q)\s*\d*[\.:\)]\s*(.*?)\s*\n\s*(?:Answer|A)\s*\d*[\.:\)]\s*(.*?)(?=\n\s*(?:Question|Q)\s*\d*[\.:\)]|\Z)",
        re.DOTALL | re.IGNORECASE,
    )
    for m in pattern_a1.finditer(full_text):
        q = _clean(m.group(1))
        a = _clean(m.group(2))
        if q and a and len(q) > 2 and len(a) > 2:
            pairs.append({
                "question": q,
                "answer": a,
                "category": category,
                "document": doc_name,
            })

    # Format A2: Q: ... \n A: ...
    if not pairs:
        pattern_a2 = re.compile(r"Q:\s*(.*?)\s*\n\s*A:\s*(.*?)(?=\n\s*Q:|\Z)", re.DOTALL)
        for m in pattern_a2.finditer(full_text):
            q = _clean(m.group(1))
            a = _clean(m.group(2))
            if q and a and len(q) > 2 and len(a) > 2:
                pairs.append({
                    "question": q,
                    "answer": a,
                    "category": category,
                    "document": doc_name,
                })

    # Format B: 1. ... \n Answer: ...
    if not pairs:
        pattern_b = re.compile(
            r"(?:^|\n)\s*\d+[\.\)]\s*(.*?)\s*\n\s*(?:Answer|A):\s*(.*?)(?=\n\s*\d+[\.\)]|\Z)",
            re.DOTALL | re.IGNORECASE,
        )
        for m in pattern_b.finditer(full_text):
            q = _clean(m.group(1))
            a = _clean(m.group(2))
            if q and a and len(q) > 2 and len(a) > 2:
                pairs.append({
                    "question": q,
                    "answer": a,
                    "category": category,
                    "document": doc_name,
                })

    # Format C: 1. Question? \n <Answer text until next numbered item>
    if not pairs:
        pattern_c = re.compile(
            r"(?:^|\n)\s*\d+[\.\)]\s*(.*?[\?\n])\s*\n(.*?)(?=\n\s*\d+[\.\)]|\Z)",
            re.DOTALL,
        )
        for m in pattern_c.finditer(full_text):
            q = _clean(m.group(1))
            a = _clean(m.group(2))
            if q and a and len(q) > 2 and len(a) > 2:
                pairs.append({
                    "question": q,
                    "answer": a,
                    "category": category,
                    "document": doc_name,
                })

    # Format D: Questions ending with ? followed by answer paragraph
    if not pairs:
        pattern_d = re.compile(
            r"(?:^|\n)\s*([A-Z0-9][^\n\r\.\?]*\?)\s*\n\s*([^\n\r]+(?:\n(?!\s*[A-Z0-9][^\n\r\.\?]*\?)[^\n\r]+)*)",
            re.DOTALL,
        )
        for m in pattern_d.finditer(full_text):
            q = _clean(m.group(1))
            a = _clean(m.group(2))
            if q and a and len(q) > 2 and len(a) > 2:
                pairs.append({
                    "question": q,
                    "answer": a,
                    "category": category,
                    "document": doc_name,
                })

    # Format E: Headings or Sections (e.g. ## Policy or 1. Title)
    if not pairs:
        pattern_e = re.compile(
            r"(?:^|\n)\s*(?:#{1,3}|\*+|\d+\.)\s*([A-Z0-9][^\n\r:]+[:\?]?)\s*\n+([^\n\r]+(?:\n(?!\s*(?:#{1,3}|\*+|\d+\.)\s*[A-Z0-9])[^\n\r]+)*)",
            re.DOTALL,
        )
        for m in pattern_e.finditer(full_text):
            q = _clean(m.group(1))
            a = _clean(m.group(2))
            if q and a and len(q) > 2 and len(a) > 2:
                pairs.append({
                    "question": q,
                    "answer": a,
                    "category": category,
                    "document": doc_name,
                })

    # Format F (Universal Paragraph Fallback): Chunk by paragraphs so no PDF is ever skipped
    if not pairs:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", full_text) if len(p.strip()) > 20]
        for i, para in enumerate(paragraphs, 1):
            clean_para = _clean(para)
            first_sentence = clean_para.split(". ")[0] + ("..." if len(clean_para) > 60 else "")
            q_title = f"{category} - Section {i}: {first_sentence[:80]}"
            pairs.append({
                "question": q_title,
                "answer": clean_para,
                "category": category,
                "document": doc_name,
            })

    return pairs


def ingest_faq_folder(
    faq_dir: Optional[str] = None,
    batch_size: int = 256,
    force: bool = False,
    reset: bool = False,
) -> dict[str, Any]:
    """
    Scan the FAQ directory, detect new or modified PDF documents via SHA-256 diff,
    and rapidly index only changed documents into ChromaDB.
    """
    if faq_dir is None:
        base_path = Path(__file__).parent.parent.parent.parent
        faq_dir = str(base_path / "FAQ")

    pdf_files = sorted(glob.glob(os.path.join(faq_dir, "*.pdf")))
    if not pdf_files:
        logger.warning("no_pdf_files_found", dir=faq_dir)
        return {"success": False, "error": f"No PDF files found in {faq_dir}"}

    _document_stats["status"] = "ingesting"

    # Check if ChromaDB collection exists and has documents
    collection_count = 0
    try:
        collection_count = get_collection_count()
    except Exception:
        pass

    # If collection is empty, force full ingestion
    if collection_count == 0 or reset:
        force = True

    cache = {} if force else _load_cache()

    docs_to_ingest: list[Document] = []
    ids_to_ingest: list[str] = []
    all_categories: set[str] = set()
    total_qa_count = 0
    changed_files: list[str] = []

    logger.info(
        "starting_smart_faq_ingestion",
        total_files=len(pdf_files),
        force=force,
        cached_files=len(cache),
    )

    current_pdf_names = {os.path.basename(f) for f in pdf_files}

    # Step 1: Detect and purge vectors for any deleted/removed PDF files
    deleted_files = [doc_name for doc_name in list(cache.keys()) if doc_name not in current_pdf_names]
    if deleted_files:
        logger.info("purging_deleted_pdf_documents", deleted_files=deleted_files)
        try:
            store = get_vector_store()
            for del_doc in deleted_files:
                try:
                    store._collection.delete(where={"document": del_doc})
                    logger.info("purged_vectors_for_deleted_file", document=del_doc)
                except Exception as ex:
                    logger.warning("failed_to_delete_doc_vectors", document=del_doc, error=str(ex))
                cache.pop(del_doc, None)
        except Exception as e:
            logger.error("error_purging_deleted_documents", error=str(e))

    # Reset collection if requested
    if reset:
        try:
            reset_collection()
            logger.info("chroma_collection_reset")
        except Exception as e:
            logger.warning("reset_collection_failed", error=str(e))

    for file_path in pdf_files:
        doc_name = os.path.basename(file_path)
        file_hash = _get_file_hash(file_path)
        mtime = os.path.getmtime(file_path)

        cached_entry = cache.get(doc_name)
        # Check if unchanged
        if (
            not force
            and cached_entry
            and cached_entry.get("hash") == file_hash
            and "qa_count" in cached_entry
        ):
            continue

        # File is new or changed: parse and prepare embeddings
        changed_files.append(doc_name)
        try:
            # Delete old vectors for this specific document if replacing/modifying
            try:
                store = get_vector_store()
                store._collection.delete(where={"document": doc_name})
            except Exception:
                pass

            qa_items = parse_pdf_document(file_path)
            category = _extract_category_from_doc_name(doc_name)

            # Update cache entry
            cache[doc_name] = {
                "hash": file_hash,
                "mtime": mtime,
                "qa_count": len(qa_items),
                "category": category,
                "last_indexed": datetime.now(timezone.utc).isoformat(),
            }

            for item in qa_items:
                q = item["question"]
                a = item["answer"]
                cat = item["category"]

                content = f"Question: {q}\nAnswer: {a}"
                doc_id = _make_doc_id(doc_name, q)

                doc = Document(
                    page_content=content,
                    metadata={
                        "document": doc_name,
                        "category": cat,
                        "question": q,
                        "source": "faq_documents",
                        "ingested_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                docs_to_ingest.append(doc)
                ids_to_ingest.append(doc_id)

            logger.info("parsed_changed_pdf_file", file=doc_name, qa_count=len(qa_items))
        except Exception as e:
            logger.error("pdf_parse_error", file=file_path, error=str(e))

    # Upsert only new/changed documents in high-performance batches of 256
    if docs_to_ingest:
        logger.info(
            "embedding_changed_documents",
            new_or_changed_files=len(changed_files),
            total_chunks=len(docs_to_ingest),
        )
        for i in range(0, len(docs_to_ingest), batch_size):
            batch_docs = docs_to_ingest[i : i + batch_size]
            batch_ids = ids_to_ingest[i : i + batch_size]
            add_documents(documents=batch_docs, ids=batch_ids)
            logger.info("ingested_qa_batch", current=min(i + batch_size, len(docs_to_ingest)), total=len(docs_to_ingest))

    # Clean cache so it strictly contains only current PDF files
    cache = {k: v for k, v in cache.items() if k in current_pdf_names}
    _save_cache(cache)

    # Automatically generate human-readable YAML knowledge catalog
    try:
        export_knowledge_to_yaml(faq_dir=faq_dir)
    except Exception as ey:
        logger.warning("yaml_export_failed", error=str(ey))

    # Compute accurate total stats across current files
    total_qa_count = sum(entry.get("qa_count", 0) for entry in cache.values())
    all_categories = sorted(list({entry.get("category") for entry in cache.values() if entry.get("category")}))

    now_iso = datetime.now(timezone.utc).isoformat()

    # Update state stats
    _document_stats["total_pdfs"] = len(pdf_files)
    _document_stats["total_qa_pairs"] = total_qa_count
    _document_stats["categories"] = all_categories
    _document_stats["last_ingested_at"] = now_iso
    _document_stats["status"] = "ready"
    _document_stats["error"] = None

    logger.info(
        "smart_ingestion_complete",
        total_pdfs=len(pdf_files),
        total_qa_pairs=total_qa_count,
        changed_files=len(changed_files),
        deleted_files=len(deleted_files),
        newly_indexed_chunks=len(docs_to_ingest),
    )

    return {
        "success": True,
        "total_pdfs": len(pdf_files),
        "total_qa_pairs": total_qa_count,
        "newly_indexed_docs": len(docs_to_ingest),
        "changed_files_count": len(changed_files),
        "deleted_files_count": len(deleted_files),
        "categories_count": len(all_categories),
        "ingested_at": now_iso,
    }


def get_document_stats() -> dict[str, Any]:
    """Return stats on ingested PDF documents and Chroma collection."""
    current_collection_count = 0
    try:
        current_collection_count = get_collection_count()
    except Exception:
        pass

    base_path = Path(__file__).parent.parent.parent.parent
    faq_dir = str(base_path / "FAQ")
    pdf_files = glob.glob(os.path.join(faq_dir, "*.pdf"))
    current_pdf_names = {os.path.basename(f) for f in pdf_files}
    
    cache = _load_cache()
    valid_cache = {k: v for k, v in cache.items() if k in current_pdf_names}
    cached_qa = sum(entry.get("qa_count", 0) for entry in valid_cache.values())
    cached_cats = sorted(list({entry.get("category") for entry in valid_cache.values() if entry.get("category")}))

    total_pdfs = len(pdf_files)
    if total_pdfs == 0:
        return {
            "total_pdfs": 0,
            "total_qa_pairs": 0,
            "collection_count": current_collection_count,
            "last_ingested_at": _document_stats["last_ingested_at"],
            "status": _document_stats["status"],
            "categories": [],
            "total_categories": 0,
            "error": _document_stats["error"],
        }

    total_qa = _document_stats["total_qa_pairs"] if _document_stats["total_qa_pairs"] > 0 else (cached_qa or current_collection_count)
    categories = _document_stats["categories"] or cached_cats

    return {
        "total_pdfs": total_pdfs,
        "total_qa_pairs": total_qa,
        "collection_count": current_collection_count,
        "last_ingested_at": _document_stats["last_ingested_at"],
        "status": _document_stats["status"],
        "categories": categories[:10],
        "total_categories": len(categories) or (25 if total_pdfs else 0),
        "error": _document_stats["error"],
    }
