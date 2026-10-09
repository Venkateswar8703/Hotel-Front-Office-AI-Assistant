"""
HuggingFace sentence-transformers embedding wrapper.
Uses all-MiniLM-L6-v2 by default — runs locally, no API key required.
"""
from __future__ import annotations

import os
from functools import lru_cache

from langchain_community.embeddings import HuggingFaceEmbeddings

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Ensure SentenceTransformers uses local cache without network checks
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"


@lru_cache(maxsize=1)
def get_embeddings() -> HuggingFaceEmbeddings:
    """Return a cached HuggingFace embedding model."""
    settings = get_settings()
    model_name = settings.embedding_model

    logger.info("loading_embeddings_model", model=model_name)
    embeddings = HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True, "batch_size": 256},
    )
    logger.info("embeddings_model_loaded", model=model_name)
    return embeddings
