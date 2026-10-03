"""Tests for database foreign keys, relationships, and ON DELETE cascade behaviors."""
import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.models import (
    User,
    AuthIdentity,
    UserSettings,
    StudySession,
    DetectionEvent,
    TelemetrySample,
    SessionFeedback,
)


@pytest.mark.asyncio
async def test_fk_invalid_user_id_rejected(db_session):
    """Verify foreign key constraint when referencing a non-existent user."""
    fake_user_id = uuid.uuid4()
    session = StudySession(
        user_id=fake_user_id,
        started_at=datetime.now(timezone.utc),
        status="active",
        detector_version="0.2.0",
        feature_schema_version="2026-03-modular-v1",
    )
    db_session.add(session)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_fk_invalid_session_id_rejected(db_session):
    """Verify foreign key constraint when referencing a non-existent study session."""
    fake_session_id = uuid.uuid4()
    event = DetectionEvent(
        session_id=fake_session_id,
        event_type="looking_away",
        started_at=datetime.now(timezone.utc),
        detector_version="0.2.0",
    )
    db_session.add(event)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_delete_user_cascades_all_children(db_session):
    """Verify deleting a User cascades to delete settings, auth, sessions, events, telemetry, and feedback."""
    # 1. Create full hierarchy
    user = User(email="cascade@example.com", display_name="Cascade User")
    db_session.add(user)
    await db_session.commit()

    identity = AuthIdentity(
        user_id=user.id,
        provider="google",
        provider_subject="casc-sub",
    )
    settings = UserSettings(user_id=user.id)
    now = datetime.now(timezone.utc)
    session = StudySession(
        user_id=user.id,
        started_at=now,
        status="completed",
        detector_version="0.2.0",
        feature_schema_version="2026-03-modular-v1",
    )
    db_session.add_all([identity, settings, session])
    await db_session.commit()

    event = DetectionEvent(
        session_id=session.id,
        event_type="phone_use",
        started_at=now,
        detector_version="0.2.0",
    )
    sample = TelemetrySample(
        session_id=session.id,
        sampled_at=now,
        detector_version="0.2.0",
        feature_schema_version="2026-03-modular-v1",
    )
    db_session.add_all([event, sample])
    await db_session.commit()

    feedback = SessionFeedback(
        session_id=session.id,
        detection_event_id=event.id,
        feedback_type="correct_detection",
    )
    db_session.add(feedback)
    await db_session.commit()

    # 2. Delete user
    await db_session.delete(user)
    await db_session.commit()

    # 3. Assert all child tables are now empty of this hierarchy
    assert (await db_session.execute(select(AuthIdentity).where(AuthIdentity.user_id == user.id))).scalar_one_or_none() is None
    assert (await db_session.execute(select(UserSettings).where(UserSettings.user_id == user.id))).scalar_one_or_none() is None
    assert (await db_session.execute(select(StudySession).where(StudySession.user_id == user.id))).scalar_one_or_none() is None
    assert (await db_session.execute(select(DetectionEvent).where(DetectionEvent.session_id == session.id))).scalar_one_or_none() is None
    assert (await db_session.execute(select(TelemetrySample).where(TelemetrySample.session_id == session.id))).scalar_one_or_none() is None
    assert (await db_session.execute(select(SessionFeedback).where(SessionFeedback.session_id == session.id))).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_delete_session_cascades_children(db_session):
    """Verify deleting a StudySession cascades to its detection events, telemetry, and feedback."""
    user = User(email="session_cascade@example.com", display_name="Session Cascade")
    db_session.add(user)
    await db_session.commit()

    now = datetime.now(timezone.utc)
    session = StudySession(
        user_id=user.id,
        started_at=now,
        status="active",
        detector_version="0.2.0",
        feature_schema_version="2026-03-modular-v1",
    )
    db_session.add(session)
    await db_session.commit()

    event = DetectionEvent(
        session_id=session.id,
        event_type="yawning",
        started_at=now,
        detector_version="0.2.0",
    )
    sample = TelemetrySample(
        session_id=session.id,
        sampled_at=now,
        detector_version="0.2.0",
        feature_schema_version="2026-03-modular-v1",
    )
    db_session.add_all([event, sample])
    await db_session.commit()

    feedback = SessionFeedback(
        session_id=session.id,
        detection_event_id=event.id,
        feedback_type="correct_detection",
    )
    db_session.add(feedback)
    await db_session.commit()

    # Delete session
    await db_session.delete(session)
    await db_session.commit()

    # Verify children are deleted, but User remains
    assert (await db_session.execute(select(DetectionEvent).where(DetectionEvent.id == event.id))).scalar_one_or_none() is None
    assert (await db_session.execute(select(TelemetrySample).where(TelemetrySample.id == sample.id))).scalar_one_or_none() is None
    assert (await db_session.execute(select(SessionFeedback).where(SessionFeedback.id == feedback.id))).scalar_one_or_none() is None
    assert (await db_session.execute(select(User).where(User.id == user.id))).scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_delete_event_sets_feedback_event_id_to_null(db_session):
    """Verify deleting a DetectionEvent does NOT delete SessionFeedback, but sets detection_event_id to NULL."""
    user = User(email="setnull@example.com", display_name="SetNull User")
    db_session.add(user)
    await db_session.commit()

    now = datetime.now(timezone.utc)
    session = StudySession(
        user_id=user.id,
        started_at=now,
        status="active",
        detector_version="0.2.0",
        feature_schema_version="2026-03-modular-v1",
    )
    db_session.add(session)
    await db_session.commit()

    event = DetectionEvent(
        session_id=session.id,
        event_type="drowsy",
        started_at=now,
        detector_version="0.2.0",
    )
    db_session.add(event)
    await db_session.commit()

    feedback = SessionFeedback(
        session_id=session.id,
        detection_event_id=event.id,
        feedback_type="false_positive",
        note="Not drowsy, just reading notes below screen.",
    )
    db_session.add(feedback)
    await db_session.commit()

    # Delete event
    await db_session.delete(event)
    await db_session.commit()

    # Verify feedback still exists, but detection_event_id is now NULL
    fb = (await db_session.execute(select(SessionFeedback).where(SessionFeedback.id == feedback.id))).scalar_one()
    assert fb is not None
    assert fb.detection_event_id is None
    assert fb.feedback_type == "false_positive"
