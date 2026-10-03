"""Tests for SQLAlchemy 2.x models creation, defaults, and typing."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
import pytest
from sqlalchemy import select

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
async def test_user_creation_and_defaults(db_session):
    """Verify User model creation, UUID generation, active flag, and UTC timestamps."""
    user = User(
        email="student@example.com",
        display_name="Test Student",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    assert isinstance(user.id, uuid.UUID)
    assert user.email == "student@example.com"
    assert user.display_name == "Test Student"
    assert user.is_active is True
    assert isinstance(user.created_at, datetime)
    assert user.created_at.tzinfo is not None
    assert isinstance(user.updated_at, datetime)
    assert user.updated_at.tzinfo is not None


@pytest.mark.asyncio
async def test_auth_identity_creation(db_session):
    """Verify AuthIdentity links to User and persists provider info."""
    user = User(email="oauth@example.com", display_name="OAuth User")
    db_session.add(user)
    await db_session.commit()

    identity = AuthIdentity(
        user_id=user.id,
        provider="google",
        provider_subject="google-sub-12345",
        provider_email="oauth@example.com",
    )
    db_session.add(identity)
    await db_session.commit()
    await db_session.refresh(identity)

    assert isinstance(identity.id, uuid.UUID)
    assert identity.user_id == user.id
    assert identity.provider == "google"
    assert identity.provider_subject == "google-sub-12345"
    assert identity.provider_email == "oauth@example.com"
    assert identity.created_at.tzinfo is not None


@pytest.mark.asyncio
async def test_user_settings_creation_and_defaults(db_session):
    """Verify UserSettings defaults for alerts, webcam, and delays."""
    user = User(email="settings@example.com", display_name="Settings User")
    db_session.add(user)
    await db_session.commit()

    settings = UserSettings(user_id=user.id)
    db_session.add(settings)
    await db_session.commit()
    await db_session.refresh(settings)

    assert isinstance(settings.id, uuid.UUID)
    assert settings.user_id == user.id
    # Default persistence delays (from Figma UI specifications)
    assert settings.looking_away_delay_seconds == 10.0
    assert settings.phone_use_delay_seconds == 6.0
    assert settings.yawning_delay_seconds == 2.0
    assert settings.drowsy_delay_seconds == 4.0
    assert settings.leaning_back_delay_seconds == 8.0
    assert settings.away_from_desk_delay_seconds == 10.0
    # Default notification preferences
    assert settings.sound_alerts_enabled is False
    assert settings.banner_alerts_enabled is False
    assert settings.session_end_summary_enabled is True
    # Default camera preferences
    assert settings.camera_device == "Integrated Camera - 720p"
    assert settings.preview_quality == "High · 30 FPS"


@pytest.mark.asyncio
async def test_study_session_creation_and_defaults(db_session):
    """Verify StudySession durations, status, score, and versioning."""
    user = User(email="session@example.com", display_name="Session User")
    db_session.add(user)
    await db_session.commit()

    now = datetime.now(timezone.utc)
    session = StudySession(
        user_id=user.id,
        started_at=now,
        status="active",
        detector_version="0.2.0",
        feature_schema_version="2026-03-modular-v1",
        calibration_snapshot={"baseline_ear": 0.32, "baseline_mar": 0.08},
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    assert isinstance(session.id, uuid.UUID)
    assert session.user_id == user.id
    assert session.status == "active"
    assert session.total_duration_seconds == 0.0
    assert session.focused_seconds == 0.0
    assert session.distracted_seconds == 0.0
    assert session.away_seconds == 0.0
    assert session.focus_score is None
    assert session.detector_version == "0.2.0"
    assert session.feature_schema_version == "2026-03-modular-v1"
    assert session.calibration_snapshot["baseline_ear"] == 0.32


@pytest.mark.asyncio
async def test_study_session_completed_metrics(db_session):
    """Verify completed StudySession with decimal focus score."""
    user = User(email="metrics@example.com", display_name="Metrics User")
    db_session.add(user)
    await db_session.commit()

    start = datetime.now(timezone.utc)
    session = StudySession(
        user_id=user.id,
        started_at=start,
        status="completed",
        total_duration_seconds=1800.0,
        focused_seconds=1530.0,
        distracted_seconds=270.0,
        away_seconds=0.0,
        focus_score=Decimal("85.00"),
        detector_version="0.2.0",
        feature_schema_version="2026-03-modular-v1",
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    assert session.status == "completed"
    assert session.total_duration_seconds == 1800.0
    assert session.focus_score == Decimal("85.00")


@pytest.mark.asyncio
async def test_detection_event_creation(db_session):
    """Verify DetectionEvent creation with canonical event type and metadata."""
    user = User(email="event@example.com", display_name="Event User")
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
        event_type="looking_away",
        started_at=now,
        ended_at=now,
        duration_seconds=4.5,
        detector_version="0.2.0",
        metadata_json={"max_yaw": 32.5, "direction": "left"},
    )
    db_session.add(event)
    await db_session.commit()
    await db_session.refresh(event)

    assert isinstance(event.id, uuid.UUID)
    assert event.session_id == session.id
    assert event.event_type == "looking_away"
    assert event.duration_seconds == 4.5
    assert event.metadata_json["direction"] == "left"


@pytest.mark.asyncio
async def test_telemetry_sample_creation(db_session):
    """Verify TelemetrySample creation with fast-path and JSONB features."""
    user = User(email="telemetry@example.com", display_name="Telemetry User")
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

    sample = TelemetrySample(
        session_id=session.id,
        sampled_at=now,
        frame_index=150,
        detector_version="0.2.0",
        feature_schema_version="2026-03-modular-v1",
        head_pitch=-2.4,
        head_yaw=12.8,
        head_roll=1.1,
        ear=0.31,
        mar=0.04,
        min_hand_cheek_distance=0.45,
        shoulder_z=-0.05,
        face_present=True,
        pose_present=True,
        hand_count=0,
        focus_state="focused",
        features={
            "head_pitch_rate": 0.1,
            "head_yaw_rate": 0.5,
            "rule_looking_away": False,
        },
    )
    db_session.add(sample)
    await db_session.commit()
    await db_session.refresh(sample)

    assert isinstance(sample.id, uuid.UUID)
    assert sample.session_id == session.id
    assert sample.frame_index == 150
    assert sample.head_yaw == 12.8
    assert sample.face_present is True
    assert sample.focus_state == "focused"
    assert sample.features["head_yaw_rate"] == 0.5


@pytest.mark.asyncio
async def test_session_feedback_creation(db_session):
    """Verify SessionFeedback with session and optional detection event link."""
    user = User(email="feedback@example.com", display_name="Feedback User")
    db_session.add(user)
    await db_session.commit()

    now = datetime.now(timezone.utc)
    session = StudySession(
        user_id=user.id,
        started_at=now,
        status="completed",
        detector_version="0.2.0",
        feature_schema_version="2026-03-modular-v1",
    )
    db_session.add(session)
    await db_session.commit()

    event = DetectionEvent(
        session_id=session.id,
        event_type="phone_use",
        started_at=now,
        ended_at=now,
        duration_seconds=3.2,
        detector_version="0.2.0",
    )
    db_session.add(event)
    await db_session.commit()

    feedback = SessionFeedback(
        session_id=session.id,
        detection_event_id=event.id,
        feedback_type="false_positive",
        note="I was scratching my chin, not using a phone.",
    )
    db_session.add(feedback)
    await db_session.commit()
    await db_session.refresh(feedback)

    assert isinstance(feedback.id, uuid.UUID)
    assert feedback.session_id == session.id
    assert feedback.detection_event_id == event.id
    assert feedback.feedback_type == "false_positive"
    assert feedback.note == "I was scratching my chin, not using a phone."
