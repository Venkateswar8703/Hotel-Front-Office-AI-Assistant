"""
Application configuration — loaded from .env via Pydantic Settings.
"""
from __future__ import annotations

from enum import Enum
from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(str, Enum):
    MOCK = "mock"
    GEMINI = "gemini"
    BEDROCK = "bedrock"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    secret_key: str = "dev-secret-key-change-in-production"
    allowed_origins: str = "http://localhost:5173,http://localhost:3000"

    # LLM
    llm_provider: LLMProvider = LLMProvider.MOCK
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-1.5-pro"
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_default_region: str = "us-east-1"
    bedrock_model_id: str = "amazon.nova-micro-v1:0"


    # Database
    database_url: Optional[str] = None

    # Chroma / Vector DB
    chroma_persist_directory: str = "./chroma_db"
    chroma_collection_name: str = "hotel_faqs"

    # Embeddings
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # RAG
    rag_top_k: int = 5
    rag_similarity_threshold: float = 0.40

    # Hotel Identity & External API
    hotel_name: str = "Grand Horizon Hotel & Suites"
    hotel_website_url: Optional[str] = "https://grandhorizonhotel.com"
    external_hotel_api_url: Optional[str] = None
    external_hotel_api_key: Optional[str] = None
    external_sync_enabled: bool = True

    # Redis
    redis_url: Optional[str] = None

    # LangSmith / Observability
    langchain_tracing_v2: bool = False
    langchain_api_key: Optional[str] = None
    langchain_endpoint: str = "https://api.smith.langchain.com"
    langchain_project: str = "hotel-ai-concierge"
    langsmith_api_key: Optional[str] = None
    langsmith_project: Optional[str] = None
    langsmith_endpoint: Optional[str] = None
    langsmith_tracing: Optional[bool] = None

    @property
    def effective_langsmith_api_key(self) -> Optional[str]:
        return self.langsmith_api_key or self.langchain_api_key

    @property
    def effective_langsmith_project(self) -> str:
        return self.langsmith_project or self.langchain_project or "hotel-ai-concierge"

    @property
    def effective_langsmith_endpoint(self) -> str:
        return self.langsmith_endpoint or self.langchain_endpoint or "https://api.smith.langchain.com"

    @property
    def is_langsmith_enabled(self) -> bool:
        if self.langsmith_tracing is not None:
            return self.langsmith_tracing
        if self.langchain_tracing_v2:
            return True
        return bool(self.effective_langsmith_api_key)

    # Rate limiting
    rate_limit_per_minute: int = 30

    # PostgreSQL (used by docker-compose)
    postgres_db: str = "hotel_concierge"
    postgres_user: str = "hotel_user"
    postgres_password: str = "hotel_pass"

    @property
    def effective_database_url(self) -> str:
        """Use PostgreSQL if set, otherwise SQLite for local dev."""
        if self.database_url:
            return self.database_url
        return "sqlite+aiosqlite:///./hotel_concierge.db"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
