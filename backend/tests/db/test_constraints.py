"""Tests for database-level CHECK and UNIQUE constraints enforcement."""
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models import (
    User,
    AuthIdentity,
    UserSettings,
    StudySession,
    DetectionEvent,
)


@pytest.mark.asyncio
async def test_duplicate_user_email_rejected(db_session):
    """Verify unique constraint on users.email."""
    u1 = User(email="duplicate@example.com", display_name="User 1")
    db_session.add(u1)
    await db_session.commit()

    u2 = User(email="duplicate@example.com", display_name="User 2")
    db_session.add(u2)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_duplicate_auth_identity_rejected(db_session):
    """Verify unique constraint on (provider, provider_subject)."""
    user1 = User(email="u1@example.com", display_name="User 1")
    user2 = User(email="u2@example.com", display_name="User 2")
    db_session.add_all([user1, user2])
    await db_session.commit()

    id1 = AuthIdentity(
        user_id=user1.id,
        provider="google",
        provider_subject="same-google-sub",
    )
    db_session.add(id1)
    await db_session.commit()

    id2 = AuthIdentity(
        user_id=user2.id,
        provider="google",
        provider_subject="same-google-sub",
    )
    db_session.add(id2)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_one_to_one_user_settings_enforced(db_session):
    """Verify unique constraint on user_settings.user_id enforces 1:1 relationship."""
    user = User(email="u1to1@example.com", display_name="1to1 User")
    db_session.add(user)
    await db_session.commit()

    s1 = UserSettings(user_id=user.id)
    db_session.add(s1)
    await db_session.commit()

    s2 = UserSettings(user_id=user.id)
    db_session.add(s2)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "delay_field",
    [
        "looking_away_delay_seconds",
        "phone_use_delay_seconds",
        "yawning_delay_seconds",
        "drowsy_delay_seconds",
        "leaning_back_delay_seconds",
        "away_from_desk_delay_seconds",
    ],
)
async def test_user_settings_negative_delay_rejected(db_session, delay_field):
    """Verify database rejects negative alert persistence delay values."""
    user = User(email=f"neg_{delay_field}@example.com", display_name="Delay User")
    db_session.add(user)
    await db_session.commit()

    kwargs = {"user_id": user.id, delay_field: -1.0}
    settings = UserSettings(**kwargs)
    db_session.add(settings)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "duration_field",
    [
        "total_duration_seconds",
        "focused_seconds",
        "distracted_seconds",
        "away_seconds",
    ],
)
async def test_study_session_negative_duration_rejected(db_session, duration_field):
    """Verify database rejects negative duration metrics in study_sessions."""
    user = User(email=f"neg_session_{duration_field}@example.com", display_name="Duration User")
    db_session.add(user)
    await db_session.commit()

    kwargs = {
        "user_id": user.id,
        "started_at": datetime.now(timezone.utc),
        "status": "completed",
        "detector_version": "0.2.0",
        "feature_schema_version": "2026-03-modular-v1",
        duration_field: -5.0,
    }
    session = StudySession(**kwargs)
    db_session.add(session)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_score", [Decimal("-0.01"), Decimal("100.01"), Decimal("150.0")])
async def test_study_session_invalid_focus_score_rejected(db_session, invalid_score):
    """Verify database rejects focus scores outside [0, 100]."""
    user = User(email=f"score_{invalid_score}@example.com", display_name="Score User")
    db_session.add(user)
    await db_session.commit()

    session = StudySession(
        user_id=user.id,
        started_at=datetime.now(timezone.utc),
        status="completed",
        focus_score=invalid_score,
        detector_version="0.2.0",
        feature_schema_version="2026-03-modular-v1",
    )
    db_session.add(session)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_study_session_invalid_status_rejected(db_session):
    """Verify database rejects invalid study_session status strings."""
    user = User(email="bad_status@example.com", display_name="Status User")
    db_session.add(user)
    await db_session.commit()

    session = StudySession(
        user_id=user.id,
        started_at=datetime.now(timezone.utc),
        status="non_existent_status",
        detector_version="0.2.0",
        feature_schema_version="2026-03-modular-v1",
    )
    db_session.add(session)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_study_session_time_consistency_enforced(db_session):
    """Verify database rejects ended_at < started_at."""
    user = User(email="time_cons@example.com", display_name="Time User")
    db_session.add(user)
    await db_session.commit()

    start = datetime.now(timezone.utc)
    end = start - timedelta(seconds=60)
    session = StudySession(
        user_id=user.id,
        started_at=start,
        ended_at=end,
        status="completed",
        detector_version="0.2.0",
        feature_schema_version="2026-03-modular-v1",
    )
    db_session.add(session)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_detection_event_invalid_type_rejected(db_session):
    """Verify database rejects invalid detection event types."""
    user = User(email="bad_event@example.com", display_name="Event User")
    db_session.add(user)
    await db_session.commit()

    session = StudySession(
        user_id=user.id,
        started_at=datetime.now(timezone.utc),
        status="active",
        detector_version="0.2.0",
        feature_schema_version="2026-03-modular-v1",
    )
    db_session.add(session)
    await db_session.commit()

    event = DetectionEvent(
        session_id=session.id,
        event_type="playing_games",  # Not in canonical 6 categories
        started_at=datetime.now(timezone.utc),
        duration_seconds=5.0,
        detector_version="0.2.0",
    )
    db_session.add(event)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_detection_event_negative_duration_rejected(db_session):
    """Verify database rejects negative duration_seconds on detection events."""
    user = User(email="neg_ev_dur@example.com", display_name="Event Duration User")
    db_session.add(user)
    await db_session.commit()

    session = StudySession(
        user_id=user.id,
        started_at=datetime.now(timezone.utc),
        status="active",
        detector_version="0.2.0",
        feature_schema_version="2026-03-modular-v1",
    )
    db_session.add(session)
    await db_session.commit()

    event = DetectionEvent(
        session_id=session.id,
        event_type="looking_away",
        started_at=datetime.now(timezone.utc),
        duration_seconds=-2.0,
        detector_version="0.2.0",
    )
    db_session.add(event)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()
