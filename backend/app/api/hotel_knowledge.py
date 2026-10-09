"""
Hotel Knowledge Management API.

Endpoints to check status, upload FAQ documents (PDFs), sync FAQs, and manage front office knowledge.
"""
from __future__ import annotations

import glob
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.logging import get_logger
from app.rag.vector_store import get_collection_count, get_vector_store
from app.services.document_rag_service import (
    _load_cache,
    _save_cache,
    get_document_stats,
    ingest_faq_folder,
)
from app.services.external_hotel_service import external_hotel_service

logger = get_logger(__name__)
router = APIRouter(prefix="/api/hotel-knowledge", tags=["hotel-knowledge"])


def _get_faq_dir() -> Path:
    """Return Path to root FAQ directory."""
    base_path = Path(__file__).resolve().parent.parent.parent.parent
    faq_dir = base_path / "FAQ"
    faq_dir.mkdir(parents=True, exist_ok=True)
    return faq_dir


def _format_size(size_bytes: int) -> str:
    """Format bytes to human-readable size string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


class CustomFAQItem(BaseModel):
    category: str = "General"
    question: str = Field(..., min_length=3)
    answer: str = Field(..., min_length=3)
    intent: str = "HOTEL_INFO"


class IngestFAQRequest(BaseModel):
    faqs: List[CustomFAQItem]


@router.get("/status")
async def get_hotel_knowledge_status():
    """Get the current knowledge stats, collection count, and document metadata."""
    status = external_hotel_service.get_status()
    status["faq_documents"] = get_document_stats()
    return status


@router.get("/documents")
async def list_documents():
    """List all uploaded FAQ PDF documents with metadata, size, and extracted Q&A counts."""
    faq_dir = _get_faq_dir()
    pdf_files = sorted(glob.glob(str(faq_dir / "*.pdf")))
    current_pdf_names = {os.path.basename(f) for f in pdf_files}
    cache = _load_cache()

    # Auto-sync if disk files differ from cache or collection is uninitialized
    cached_pdf_names = set(cache.keys())
    if current_pdf_names != cached_pdf_names or get_collection_count() == 0:
        logger.info("auto_syncing_faq_directory", disk_files=len(current_pdf_names), cached_files=len(cached_pdf_names))
        try:
            ingest_faq_folder(faq_dir=str(faq_dir), force=False)
            cache = _load_cache()
        except Exception as e:
            logger.warning("auto_sync_on_list_failed", error=str(e))

    docs = []
    for f in pdf_files:
        filename = os.path.basename(f)
        stat = os.stat(f)
        cache_entry = cache.get(filename, {})
        qa_count = cache_entry.get("qa_count", 0)
        category = cache_entry.get("category") or filename.replace("Doc_", "").replace(".pdf", "").replace("_", " ").title()

        docs.append({
            "filename": filename,
            "path": f,
            "size_bytes": stat.st_size,
            "formatted_size": _format_size(stat.st_size),
            "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            "qa_count": qa_count,
            "category": category,
            "last_indexed": cache_entry.get("last_indexed"),
        })

    return {
        "documents": docs,
        "total_documents": len(docs),
        "total_qa_count": sum(d["qa_count"] for d in docs),
        "collection_count": get_collection_count() if get_collection_count else 0,
    }


@router.post("/upload")
async def upload_documents(files: List[UploadFile] = File(...)):
    """
    Upload one or more FAQ PDF files, save to FAQ/ directory,
    and automatically parse & re-index them into ChromaDB.
    """
    faq_dir = _get_faq_dir()
    saved_files = []

    for file in files:
        if not file.filename:
            continue
        filename = os.path.basename(file.filename)
        # Only accept PDF documents
        if not filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail=f"Only PDF files are supported. '{filename}' is not a PDF.",
            )

        target_path = faq_dir / filename
        try:
            with open(target_path, "wb") as f:
                content = await file.read()
                f.write(content)
            saved_files.append(filename)
            logger.info("faq_file_saved", filename=filename, size=len(content))
        except Exception as e:
            logger.error("file_upload_failed", filename=filename, error=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to save {filename}: {str(e)}")

    # Trigger automatic incremental parsing and vector re-indexing for new/changed files
    try:
        ingest_res = ingest_faq_folder(faq_dir=str(faq_dir), force=False)
        logger.info("auto_reindexed_after_upload", uploaded_files=saved_files, result=ingest_res)
    except Exception as e:
        logger.error("auto_ingest_failed", error=str(e))
        return {
            "success": False,
            "uploaded_files": saved_files,
            "error": f"Files saved, but indexing failed: {str(e)}",
        }

    return {
        "success": True,
        "uploaded_files": saved_files,
        "total_uploaded": len(saved_files),
        "ingest_result": ingest_res,
        "document_stats": get_document_stats(),
    }


@router.delete("/documents/{filename}")
async def delete_document(filename: str):
    """
    Delete a specific FAQ document from the FAQ/ directory,
    automatically purge its vector embeddings from ChromaDB, and re-index stats.
    """
    faq_dir = _get_faq_dir()
    safe_name = os.path.basename(filename)
    file_path = faq_dir / safe_name

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Document '{safe_name}' not found.")

    try:
        # 1. Delete physical file from disk
        file_path.unlink()
        logger.info("faq_file_deleted", filename=safe_name)

        # 2. Directly purge all vectors associated with this document from ChromaDB
        try:
            store = get_vector_store()
            store._collection.delete(where={"document": safe_name})
            logger.info("purged_vectors_from_chroma", document=safe_name)
        except Exception as ex:
            logger.warning("direct_chroma_delete_failed", document=safe_name, error=str(ex))

        # 3. Update cache
        cache = _load_cache()
        cache.pop(safe_name, None)
        _save_cache(cache)

        # 4. Auto re-index remaining files or reset collection if empty
        pdf_files = list(faq_dir.glob("*.pdf"))
        if pdf_files:
            ingest_res = ingest_faq_folder(faq_dir=str(faq_dir), force=False)
        else:
            from app.rag.vector_store import reset_collection
            reset_collection()
            ingest_res = {"success": True, "message": "All documents removed and ChromaDB collection reset."}

        logger.info("auto_reindexed_after_delete", deleted_file=safe_name, result=ingest_res)

        return {
            "success": True,
            "deleted_file": safe_name,
            "ingest_result": ingest_res,
            "document_stats": get_document_stats(),
        }
    except Exception as e:
        logger.error("error_deleting_document", filename=safe_name, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to delete {safe_name}: {str(e)}")


@router.post("/clear-all")
async def clear_all_documents():
    """Delete all FAQ documents and reset ChromaDB knowledge base."""
    faq_dir = _get_faq_dir()
    try:
        # Delete files in FAQ folder
        for f in glob.glob(str(faq_dir / "*")):
            try:
                if os.path.isfile(f):
                    os.unlink(f)
            except Exception:
                pass

        # Safely reset and initialize empty Chroma collection
        from app.rag.vector_store import reset_collection
        reset_collection()

        # Reset cache
        _save_cache({})

        return {
            "success": True,
            "message": "All FAQ documents and ChromaDB vector store have been cleared.",
            "document_stats": get_document_stats(),
        }
    except Exception as e:
        logger.error("error_clearing_all_documents", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to clear knowledge base: {str(e)}")


@router.post("/ingest-documents")
async def trigger_document_ingestion(force: bool = True):
    """Scan and ingest all PDF FAQ documents in the FAQ folder into ChromaDB."""
    result = ingest_faq_folder(force=force)
    if not result.get("success"):
        raise HTTPException(
            status_code=500,
            detail=result.get("error") or "Document ingestion failed"
        )
    return result


@router.post("/sync")
async def trigger_external_sync():
    """Trigger synchronization of FAQs and hotel details from the external API to ChromaDB."""
    result = await external_hotel_service.sync_faqs_to_chroma()
    if not result.get("success"):
        raise HTTPException(
            status_code=500,
            detail=result.get("error") or result.get("message") or "Sync failed"
        )
    return {
        "status": "synchronized",
        "synced_count": result.get("count"),
        "hotel_name": result.get("hotel_name"),
        "synced_at": result.get("synced_at"),
    }


@router.post("/ingest")
async def ingest_custom_faqs(request: IngestFAQRequest):
    """Directly ingest a batch of custom FAQ items into the hotel knowledge base."""
    from langchain_core.documents import Document
    from app.rag.vector_store import add_documents
    from app.services.external_hotel_service import _hash_id

    docs = []
    ids = []
    hotel_name = external_hotel_service.settings.hotel_name

    for item in request.faqs:
        content = f"Question: {item.question}\nAnswer: {item.answer}"
        doc_id = _hash_id(f"{hotel_name}_{item.question}")
        doc = Document(
            page_content=content,
            metadata={
                "category": item.category,
                "question": item.question,
                "intent": item.intent,
                "source": "hotel_cms",
                "hotel_name": hotel_name,
                "synced_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        docs.append(doc)
        ids.append(doc_id)

    if docs:
        add_documents(documents=docs, ids=ids)

    return {
        "status": "ingested",
        "count": len(docs),
        "hotel_name": hotel_name,
    }
