"""Database engine and session infrastructure."""
from typing import AsyncGenerator
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


def get_sync_database_url(url: str | None = None) -> str:
    """Return a synchronous PostgreSQL connection URL suitable for psycopg2/Alembic."""
    raw_url = url or settings.DATABASE_URL
    if raw_url.startswith("postgresql+asyncpg://"):
        return raw_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    if raw_url.startswith("postgresql://"):
        return raw_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return raw_url


def get_async_database_url(url: str | None = None) -> str:
    """Return an asynchronous PostgreSQL connection URL suitable for asyncpg."""
    raw_url = url or settings.DATABASE_URL
    if raw_url.startswith("postgresql+psycopg2://"):
        return raw_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    if raw_url.startswith("postgresql://"):
        return raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return raw_url


# Global async engine & session maker
async_engine: AsyncEngine = create_async_engine(
    get_async_database_url(),
    echo=False,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


def get_sync_engine(url: str | None = None) -> Engine:
    """Create a synchronous engine for administrative operations and migrations."""
    return create_engine(
        get_sync_database_url(url),
        echo=False,
        pool_pre_ping=True,
    )


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async database session with automatic lifecycle cleanup."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
