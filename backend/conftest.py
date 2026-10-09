"""
pytest configuration for backend tests.
"""
import sys
import os
from pathlib import Path

# Add backend to path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set minimal env vars for testing
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("CHROMA_PERSIST_DIRECTORY", "/tmp/test_chroma")
os.environ.setdefault("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
