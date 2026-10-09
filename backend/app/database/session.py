"""
Database session factory — supports PostgreSQL and SQLite.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

# Normalise URL — SQLAlchemy async requires different drivers
_raw_url = settings.effective_database_url
if _raw_url.startswith("sqlite:///") and "aiosqlite" not in _raw_url:
    _raw_url = _raw_url.replace("sqlite:///", "sqlite+aiosqlite:///")
elif _raw_url.startswith("postgresql://"):
    _raw_url = _raw_url.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(
    _raw_url,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False} if "sqlite" in _raw_url else {},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncSession:
    """FastAPI dependency — yields an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
