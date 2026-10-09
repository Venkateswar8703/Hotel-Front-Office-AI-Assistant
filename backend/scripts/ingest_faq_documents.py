#!/usr/bin/env python3
"""
CLI Script to ingest all 24 PDF FAQ documents into ChromaDB.

Usage:
    python scripts/ingest_faq_documents.py
    python scripts/ingest_faq_documents.py --dir /path/to/FAQ --reset
"""
import argparse
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
load_dotenv(backend_dir.parent / ".env")

from app.core.logging import configure_logging, get_logger
from app.services.document_rag_service import ingest_faq_folder

configure_logging("INFO")
logger = get_logger("cli_ingest_documents")


def main():
    parser = argparse.ArgumentParser(description="Ingest FAQ PDF documents into ChromaDB")
    parser.add_argument(
        "--dir",
        type=str,
        default=str(backend_dir.parent / "FAQ"),
        help="Path to folder containing FAQ PDF documents",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of documents per embedding batch",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset existing vector collection before indexing",
    )

    args = parser.parse_args()

    print(f"=== Starting PDF FAQ Ingestion from: {args.dir} ===")
    result = ingest_faq_folder(
        faq_dir=args.dir,
        batch_size=args.batch_size,
        reset=args.reset,
    )

    if result.get("success"):
        print("\n" + "="*50)
        print(">>> INGESTION SUCCESSFUL! <<<")
        print(f"Total PDFs parsed:     {result['total_pdfs']}")
        print(f"Total Q&A pairs added: {result['total_qa_pairs']}")
        print(f"Categories indexed:    {result['categories_count']}")
        print(f"Ingested at:           {result['ingested_at']}")
        print("="*50 + "\n")
    else:
        print(f"\n[ERROR] Ingestion failed: {result.get('error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
