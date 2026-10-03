"""Tests for telemetry_samples schema, fast-path features, JSONB evolution, and indexing."""
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import select

from app.db.models import User, StudySession, TelemetrySample


@pytest.mark.asyncio
async def test_synthetic_telemetry_batch_insert_and_query(db_session):
    """Verify storing numerical telemetry samples matching Phase 2 feature metrics."""
    user = User(email="telemetry_test@example.com", display_name="Telemetry Test")
    db_session.add(user)
    await db_session.commit()

    start_time = datetime.now(timezone.utc)
    session = StudySession(
        user_id=user.id,
        started_at=start_time,
        status="active",
        detector_version="0.2.0",
        feature_schema_version="2026-03-modular-v1",
    )
    db_session.add(session)
    await db_session.commit()

    # Create synthetic telemetry sequence (simulating 10 frames at 30fps)
    samples = []
    for i in range(10):
        t = start_time + timedelta(milliseconds=i * 33)
        sample = TelemetrySample(
            session_id=session.id,
            sampled_at=t,
            frame_index=i,
            detector_version="0.2.0",
            feature_schema_version="2026-03-modular-v1",
            head_pitch=-2.5 + i * 0.1,
            head_yaw=15.0 - i * 0.5,
            head_roll=0.5,
            ear=0.32,
            mar=0.05,
            min_hand_cheek_distance=0.48,
            shoulder_z=-0.02,
            face_present=True,
            pose_present=True,
            hand_count=0,
            focus_state="focused" if i < 7 else "looking_away",
            features={
                "left_ear": 0.31,
                "right_ear": 0.33,
                "left_hand_cheek_distance": 0.50,
                "right_hand_cheek_distance": 0.48,
                "head_pitch_from_baseline": -0.5,
                "head_yaw_from_baseline": 3.2,
                "head_roll_from_baseline": 0.1,
                "head_pitch_rate": 0.05,
                "head_yaw_rate": -0.2,
                "shoulder_z_rate": 0.0,
                "shoulder_z_delta": 0.01,
                "tracking_quality": 0.95,
                "rules": {
                    "looking_away": i >= 7,
                    "phone_use": False,
                    "yawning": False,
                    "drowsy": False,
                    "leaning_back": False,
                    "away_from_desk": False,
                },
                "calibration_state": "CALIBRATED",
            },
        )
        samples.append(sample)

    db_session.add_all(samples)
    await db_session.commit()

    # Query back ordered by sampled_at (leveraging composite index (session_id, sampled_at))
    query = (
        select(TelemetrySample)
        .where(TelemetrySample.session_id == session.id)
        .order_by(TelemetrySample.sampled_at.asc())
    )
    result = await db_session.execute(query)
    retrieved = result.scalars().all()

    assert len(retrieved) == 10
    assert retrieved[0].frame_index == 0
    assert retrieved[9].frame_index == 9
    assert retrieved[0].focus_state == "focused"
    assert retrieved[9].focus_state == "looking_away"
    assert retrieved[9].features["rules"]["looking_away"] is True
    assert retrieved[0].features["calibration_state"] == "CALIBRATED"
    assert retrieved[0].features["tracking_quality"] == 0.95
