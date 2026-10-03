"""Tests for active session uniqueness and database-level constraint enforcement."""
import uuid
import pytest
from sqlalchemy.exc import IntegrityError

from app.db.base import utc_now
from app.db.models.study_session import StudySession
from app.db.models.user import User


@pytest.mark.asyncio
async def test_db_partial_unique_index_prevents_duplicate_active_sessions(db_session):
    """Verify that PostgreSQL partial unique index uq_study_sessions_user_active rejects
    a second active session for the same user, even bypassing service logic."""
    user = User(
        email="concurrent_db@example.com",
        display_name="Concurrent DB Student",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    # Session 1: Active
    session1 = StudySession(
        user_id=user.id,
        started_at=utc_now(),
        status="active",
        total_duration_seconds=0.0,
    )
    db_session.add(session1)
    await db_session.flush()

    # Session 2: Also Active for same user -> MUST raise IntegrityError
    session2 = StudySession(
        user_id=user.id,
        started_at=utc_now(),
        status="active",
        total_duration_seconds=0.0,
    )
    db_session.add(session2)

    with pytest.raises(IntegrityError) as exc_info:
        await db_session.flush()

    assert "uq_study_sessions_user_active" in str(exc_info.value)
    await db_session.rollback()


@pytest.mark.asyncio
async def test_db_allows_multiple_completed_sessions_for_same_user(db_session):
    """Verify that the partial unique index only applies to active sessions, allowing multiple completed sessions."""
    user = User(
        email="multiple_completed@example.com",
        display_name="History Student",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    now = utc_now()
    # Completed session 1
    s1 = StudySession(
        user_id=user.id,
        started_at=now,
        ended_at=now,
        status="completed",
        total_duration_seconds=120.0,
    )
    # Completed session 2
    s2 = StudySession(
        user_id=user.id,
        started_at=now,
        ended_at=now,
        status="completed",
        total_duration_seconds=300.0,
    )
    # Active session 3
    s3 = StudySession(
        user_id=user.id,
        started_at=now,
        status="active",
        total_duration_seconds=0.0,
    )
    db_session.add_all([s1, s2, s3])
    await db_session.flush()

    assert s1.id is not None
    assert s2.id is not None
    assert s3.id is not None
    await db_session.rollback()
