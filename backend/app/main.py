"""
Hotel AI Concierge — FastAPI Application Entry Point
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api import chat, complaints, escalations, guests, health, maintenance, service_requests, hotel_knowledge
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.database.init_db import init_db

# ─── Startup ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup / shutdown lifecycle."""
    settings = get_settings()
    configure_logging("DEBUG" if settings.app_env == "development" else "INFO")
    logger = get_logger("startup")

    logger.info("hotel_concierge_starting", env=settings.app_env, provider=settings.llm_provider.value)

    # Initialize database (create tables, seed demo data)
    try:
        await init_db()
        logger.info("database_initialized")
    except Exception as e:
        logger.error("database_init_failed", error=str(e))

    # Initialize LangSmith tracing (if key is configured or enabled)
    from app.core.langsmith import setup_langsmith
    setup_langsmith()

    logger.info("hotel_concierge_ready")
    yield
    logger.info("hotel_concierge_shutdown")


# ─── App ──────────────────────────────────────────────────────────────────────

settings = get_settings()

app = FastAPI(
    title="Hotel AI Concierge API",
    description=(
        "AI-powered hotel guest assistance system with RAG knowledge base, "
        "LangGraph orchestration, and mock hotel service tools."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── Rate Limiting ────────────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ─── CORS ─────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Request Timing Middleware ────────────────────────────────────────────────

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    elapsed = round((time.monotonic() - start) * 1000, 1)
    response.headers["X-Process-Time-Ms"] = str(elapsed)
    return response

# ─── Global Exception Handler ─────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger = get_logger("error_handler")
    logger.error("unhandled_exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again or contact the front desk."},
    )

# ─── Routers ──────────────────────────────────────────────────────────────────

app.include_router(chat.router)
app.include_router(health.router)
app.include_router(service_requests.router)
app.include_router(maintenance.router)
app.include_router(complaints.router)
app.include_router(escalations.router)
app.include_router(guests.router)
app.include_router(hotel_knowledge.router)

# ─── Observability & LangSmith ────────────────────────────────────────────────

@app.get("/api/observability/langsmith", tags=["observability"])
async def langsmith_status():
    """Return LangSmith tracing connectivity and configuration status."""
    from app.core.langsmith import get_langsmith_status
    return get_langsmith_status()

# ─── Root ─────────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "name": "Hotel AI Concierge API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
        "observability": "/api/observability/langsmith",
    }
