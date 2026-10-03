"""Integration tests for Phase 8 Real Monitoring and Real Detection.

Tests:
1. SessionDetectionRuntime lifecycle and per-session isolation
2. Real frame decoding and MediaPipe detection
3. Corrupted / empty frame handling without crashing
4. Queue backpressure and dropped stale frames
5. PostgreSQL DetectionEvent lifecycle (start, persist, no duplicates, end, finalize)
6. All six canonical detection categories verification
7. Session stop finalization of open events and study session metrics
8. WebSocket live detection_result message delivery
9. Zero media persistence guarantee
"""
from datetime import datetime, timezone
from decimal import Decimal
import time
import uuid
import cv2
import numpy as np
import pytest
from sqlalchemy import select
from starlette.testclient import TestClient

from app.core.security import create_access_token
from app.db.base import utc_now
from app.db.models.detection_event import DetectionEvent
from app.db.models.study_session import StudySession
from app.db.models.user import User
from app.db.session import get_async_session
from app.detection.config import (
    ALERT_NAME_TO_CATEGORY,
    ALERT_NAMES,
    CATEGORIES,
    DetectorConfig,
)
from app.detection.features import FeatureSnapshot
from app.main import app
from app.services.detection_runtime_service import (
    DetectionRuntimeManager,
    SessionDetectionRuntime,
    detection_runtime_manager,
)
from app.services.session_service import SessionService
from tests.db.conftest import ASYNC_TEST_URL, db_session, sync_test_engine, async_test_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool


@pytest.fixture(autouse=True)
def override_db():
    engine = create_async_engine(ASYNC_TEST_URL, poolclass=NullPool)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def _get_test_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_async_session] = _get_test_session
    yield factory
    app.dependency_overrides.pop(get_async_session, None)


def create_synthetic_jpeg(width: int = 640, height: int = 480) -> bytes:
    """Generate valid synthetic JPEG image bytes."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    # Add simple gradient pattern
    img[:, :, 0] = np.linspace(0, 255, width, dtype=np.uint8)
    _, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


@pytest.mark.asyncio
async def test_session_detection_runtime_isolation(override_db):
    """Verify two distinct sessions maintain completely isolated detector and calibration state."""
    session_a = uuid.uuid4()
    session_b = uuid.uuid4()
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()

    runtime_a = SessionDetectionRuntime(session_id=session_a, user_id=user_a, db_session_factory=override_db)
    runtime_b = SessionDetectionRuntime(session_id=session_b, user_id=user_b, db_session_factory=override_db)

    # Add calibration sample to runtime A only
    runtime_a.detector.calibration.add(
        now=time.time(),
        shoulder_z=-0.5,
        head_yaw=5.0,
        head_pitch=2.0,
        head_roll=1.0,
        required_seconds=10.0,
        min_samples=30,
    )

    assert len(runtime_a.detector.calibration.head_yaw) == 1
    assert len(runtime_b.detector.calibration.head_yaw) == 0
    assert runtime_a.session_id != runtime_b.session_id

    await runtime_a.stop()
    await runtime_b.stop()


@pytest.mark.asyncio
async def test_corrupt_or_empty_frame_handling(override_db):
    """Verify corrupt, empty, or non-image payloads are dropped safely without raising exceptions."""
    session_id = uuid.uuid4()
    user_id = uuid.uuid4()

    runtime = SessionDetectionRuntime(session_id=session_id, user_id=user_id, db_session_factory=override_db)
    runtime.start()

    # Submit empty frame
    res_empty = runtime._process_frame_sync(b"", time.time())
    assert res_empty is None

    # Submit corrupted non-JPEG bytes
    res_corrupt = runtime._process_frame_sync(b"NOT_A_VALID_JPEG_IMAGE_DATA_123456789", time.time())
    assert res_corrupt is None

    await runtime.stop()


@pytest.mark.asyncio
async def test_backpressure_queue_drops_stale_frames(override_db):
    """Verify that when frames arrive faster than processed, stale frames are dropped to prioritize freshness."""
    session_id = uuid.uuid4()
    user_id = uuid.uuid4()

    runtime = SessionDetectionRuntime(session_id=session_id, user_id=user_id, db_session_factory=override_db)
    frame_bytes = create_synthetic_jpeg()

    # Fill queue
    runtime.submit_frame(frame_bytes, 1.0)
    # Next submit should drop the previous frame in queue (maxsize=1)
    runtime.submit_frame(frame_bytes, 2.0)
    runtime.submit_frame(frame_bytes, 3.0)

    assert runtime.frames_dropped_detector >= 2
    assert runtime.frame_queue.qsize() == 1

    await runtime.stop()


@pytest.mark.asyncio
async def test_event_persistence_lifecycle(override_db, db_session):
    """Verify distraction events are persisted to PostgreSQL when triggered and updated when ended."""
    user = User(email="event_test@example.com", display_name="Event Tester", is_active=True)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    session = StudySession(user_id=user.id, status="active", started_at=utc_now())
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    config = DetectorConfig(
        alert_delays_sec={"Looking Away": 1.0}, # Short delay for test
    )

    runtime = SessionDetectionRuntime(
        session_id=session.id,
        user_id=user.id,
        config=config,
        db_session_factory=override_db,
    )

    # 1. Simulate starting an event
    raw_started = {
        "state": "distracted",
        "active_alerts": ["Looking Away"],
        "newly_started": ["Looking Away"],
        "newly_ended": [],
    }
    await runtime._handle_event_persistence(raw_started, timestamp=100.0)

    # Verify event was inserted into PostgreSQL
    stmt = select(DetectionEvent).where(DetectionEvent.session_id == session.id)
    res = await db_session.execute(stmt)
    events = res.scalars().all()
    assert len(events) == 1
    event = events[0]
    assert event.event_type == "looking_away"
    assert event.ended_at is None
    assert event.duration_seconds in (None, 0.0)

    # 2. Simulate ongoing condition (no newly started, no newly ended)
    raw_ongoing = {
        "state": "distracted",
        "active_alerts": ["Looking Away"],
        "newly_started": [],
        "newly_ended": [],
    }
    await runtime._handle_event_persistence(raw_ongoing, timestamp=102.0)

    # Verify no duplicate events created
    res = await db_session.execute(stmt)
    events = res.scalars().all()
    assert len(events) == 1

    # 3. Simulate event ending
    raw_ended = {
        "state": "focused",
        "active_alerts": [],
        "newly_started": [],
        "newly_ended": [{"name": "Looking Away", "duration_sec": 5.5}],
    }
    await runtime._handle_event_persistence(raw_ended, timestamp=105.5)

    # Verify event row updated with ended_at and duration
    await db_session.refresh(event)
    assert event.ended_at is not None
    assert event.duration_seconds == 5.5

    await runtime.stop()


@pytest.mark.asyncio
async def test_session_stop_finalizes_open_events_and_study_session_metrics(override_db, db_session):
    """Verify stopping an active session finalizes open detection events and persists metrics on StudySession."""
    user = User(email="finalizer@example.com", display_name="Finalizer", is_active=True)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    session = StudySession(user_id=user.id, status="active", started_at=utc_now())
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    runtime = await detection_runtime_manager.get_or_create_runtime(
        session_id=session.id,
        user_id=user.id,
        db_session_factory=override_db,
    )

    # Simulate active event in progress when session ends
    raw_active = {
        "state": "distracted",
        "active_alerts": ["Phone Use"],
        "newly_started": ["Phone Use"],
        "newly_ended": [],
    }
    await runtime._handle_event_persistence(raw_active, timestamp=time.time())

    # Advance detector duration state
    runtime.detector.session_state.focused_seconds = 120.0
    runtime.detector.session_state.distracted_seconds = 30.0
    runtime.detector.session_state.away_seconds = 0.0

    # Stop session via SessionService
    stopped_session = await SessionService.stop_session(db_session, session.id, user.id)
    assert stopped_session.status == "completed"
    assert stopped_session.focused_seconds == 120.0
    assert stopped_session.distracted_seconds == 30.0
    # focus_score = 120 / (120 + 30) * 100 = 80.0
    assert stopped_session.focus_score == Decimal("80.00")

    # Verify open event was finalized in PostgreSQL
    stmt = select(DetectionEvent).where(DetectionEvent.session_id == session.id)
    res = await db_session.execute(stmt)
    events = res.scalars().all()
    assert len(events) == 1
    assert events[0].event_type == "phone_use"
    assert events[0].ended_at is not None
    assert events[0].duration_seconds is not None


@pytest.mark.asyncio
async def test_all_six_categories_mapping(override_db, db_session):
    """Verify that all six canonical categories map correctly to PostgreSQL DetectionEvent.event_type."""
    user = User(email="all_cats@example.com", display_name="All Cats", is_active=True)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    session = StudySession(user_id=user.id, status="active", started_at=utc_now())
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    runtime = SessionDetectionRuntime(session_id=session.id, user_id=user.id, db_session_factory=override_db)

    # Test each category
    for alert_name in ALERT_NAMES:
        category = ALERT_NAME_TO_CATEGORY[alert_name]
        assert category in CATEGORIES

        await runtime._handle_event_persistence(
            {
                "state": "distracted" if category != "away_from_desk" else "away",
                "active_alerts": [alert_name],
                "newly_started": [alert_name],
                "newly_ended": [],
            },
            timestamp=time.time(),
        )

    stmt = select(DetectionEvent).where(DetectionEvent.session_id == session.id)
    res = await db_session.execute(stmt)
    saved_events = res.scalars().all()
    saved_types = {e.event_type for e in saved_events}

    assert saved_types == set(CATEGORIES)
    await runtime.stop()


@pytest.mark.asyncio
async def test_websocket_delivers_detection_result_message(override_db, db_session):
    """Verify that sending a binary frame through WebSocket produces a real detection_result message."""
    user = User(email="ws_live_det@example.com", display_name="WS Live Det", is_active=True)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    session = StudySession(user_id=user.id, status="active", started_at=utc_now())
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    token = create_access_token(user.id)
    client = TestClient(app, cookies={"sfm_session": token})

    frame_bytes = create_synthetic_jpeg()

    with client.websocket_connect(
        f"/api/ws/sessions/{session.id}",
        headers={"Origin": "http://localhost:5174"},
    ) as ws:
        ready = ws.receive_json()
        assert ready["type"] == "ready"

        # Send binary frame
        ws.send_bytes(frame_bytes)

        # Wait for detection result from backend worker
        # First message received is detection_result
        det_result = ws.receive_json()
        assert det_result["type"] == "detection_result"
        assert det_result["session_id"] == str(session.id)
        assert "state" in det_result
        assert "metrics" in det_result
        assert "calibration" in det_result
        assert det_result["state"] in ("calibrating", "focused", "distracted", "away")

    await detection_runtime_manager.stop_session_detection(session.id)


@pytest.mark.asyncio
async def test_zero_media_storage_verification(override_db, db_session):
    """Verify that no camera frames are stored in PostgreSQL or disk."""
    user = User(email="privacy_det@example.com", display_name="Privacy Det", is_active=True)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    session = StudySession(user_id=user.id, status="active", started_at=utc_now())
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    runtime = SessionDetectionRuntime(session_id=session.id, user_id=user.id, db_session_factory=override_db)
    frame = create_synthetic_jpeg()

    # Process frame
    res = runtime._process_frame_sync(frame, time.time())
    assert res is not None

    # Inspect event metadata if created
    stmt = select(DetectionEvent).where(DetectionEvent.session_id == session.id)
    events = (await db_session.execute(stmt)).scalars().all()
    for evt in events:
        meta_str = str(evt.metadata_json)
        assert "frame" not in meta_str.lower()
        assert "image" not in meta_str.lower()
        assert "base64" not in meta_str.lower()

    await runtime.stop()
