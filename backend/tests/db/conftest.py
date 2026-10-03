"""Pytest fixtures for Phase 4 database testing."""
import os
import pytest
import pytest_asyncio
from typing import AsyncGenerator
from sqlalchemy import text, create_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.db.session import get_async_database_url, get_sync_database_url

# Default test database URL
TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    os.environ.get("DATABASE_URL", "postgresql://localhost:5433/student_focus_monitor_test")
)

ASYNC_TEST_URL = get_async_database_url(TEST_DB_URL)
SYNC_TEST_URL = get_sync_database_url(TEST_DB_URL)


@pytest.fixture(scope="session")
def sync_test_engine():
    """Session-scoped synchronous engine for schema inspection and Alembic."""
    engine = create_engine(SYNC_TEST_URL, poolclass=NullPool)
    yield engine
    engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def async_test_engine():
    """Function-scoped asynchronous engine with NullPool to prevent event loop mismatch."""
    engine = create_async_engine(ASYNC_TEST_URL, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(async_test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Function-scoped clean async database session.
    
    Truncates all tables before each test to ensure complete isolation.
    """
    session_factory = async_sessionmaker(
        bind=async_test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        # Clean tables before test run
        await session.execute(
            text(
                "TRUNCATE TABLE session_feedback, telemetry_samples, "
                "detection_events, study_sessions, user_settings, "
                "auth_identities, users CASCADE;"
            )
        )
        await session.commit()

        yield session

        # Rollback any pending transaction and cleanup
        await session.rollback()
        await session.execute(
            text(
                "TRUNCATE TABLE session_feedback, telemetry_samples, "
                "detection_events, study_sessions, user_settings, "
                "auth_identities, users CASCADE;"
            )
        )
        await session.commit()
