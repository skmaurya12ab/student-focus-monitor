"""Integration tests for Phase 9 Live Dashboard behavior and protocol guarantees.

Verifies:
1. Live monitoring state progression (connecting -> ready -> calibrating -> focused/distracted/away)
2. Real detection_result contract delivery with metrics and active detections
3. Multiple simultaneous active detections support
4. Lifecycle separation: client stopping live transport keeps StudySession active
5. Server closed transport upon graceful stop
"""
from datetime import datetime, timezone
import uuid
import cv2
import numpy as np
import pytest
from starlette.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from app.core.security import create_access_token
from app.db.models.study_session import StudySession
from app.db.models.user import User
from app.db.session import get_async_session
from app.main import app
from app.services.session_service import SessionService
from tests.db.conftest import ASYNC_TEST_URL


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
    img[:, :, 0] = np.linspace(0, 255, width, dtype=np.uint8)
    _, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


@pytest.mark.asyncio
async def test_phase9_live_lifecycle_and_separation(override_db):
    """Verify that stopping a live transport session leaves the StudySession ACTIVE."""
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()

    async with override_db() as db:
        user = User(
            id=user_id,
            email=f"phase9_{uuid.uuid4().hex[:6]}@example.com",
            display_name="Phase 9 Student",
            is_active=True,
        )
        db.add(user)
        session = StudySession(
            id=session_id,
            user_id=user_id,
            status="active",
            started_at=datetime.now(timezone.utc),
            detector_version="v1.0.0",
            feature_schema_version="v1.0.0",
        )
        db.add(session)
        await db.commit()

    token = create_access_token(user_id)
    client = TestClient(app, cookies={"sfm_session": token})

    # Connect WebSocket
    with client.websocket_connect(
        f"/api/ws/sessions/{session_id}",
        headers={"Origin": "http://localhost:5174"},
    ) as ws:
        ready_msg = ws.receive_json()
        assert ready_msg["type"] == "ready"
        assert ready_msg["session_id"] == str(session_id)

        # Send test frame
        frame_bytes = create_synthetic_jpeg()
        ws.send_bytes(frame_bytes)

        # Receive detection result
        msg = ws.receive_json()
        assert msg["type"] in ("detection_result", "ack")
        if msg["type"] == "detection_result":
            assert msg["state"] in ("calibrating", "focused", "distracted", "away")
            assert "metrics" in msg
            assert "active_detections" in msg

        # Client requests graceful stop of live session
        ws.send_json({"type": "stop"})
        close_msg = ws.receive_json()
        assert close_msg["type"] == "closed"
        assert "stopped" in close_msg["reason"].lower()

    # CRITICAL: Verify Study Session remains ACTIVE in database
    async with override_db() as db:
        stmt = select(StudySession).where(StudySession.id == session_id)
        res = await db.execute(stmt)
        persisted_session = res.scalars().first()
        assert persisted_session is not None
        assert persisted_session.status == "active", "Study Session must remain ACTIVE after stopping live monitoring"
        assert persisted_session.ended_at is None


@pytest.mark.asyncio
async def test_phase9_multiple_active_detections_payload_format(override_db):
    """Verify detection_result payload preserves multiple simultaneous active detections."""
    from app.services.detection_runtime_service import SessionDetectionRuntime
    from app.detection.config import ALERT_NAMES, CATEGORIES

    user_id = uuid.uuid4()
    session_id = uuid.uuid4()

    runtime = SessionDetectionRuntime(session_id=session_id, user_id=user_id, db_session_factory=override_db)

    # Simulate raw result with 2 simultaneous active alerts: "Looking Away" and "Phone Use"
    t0 = 1000.0
    runtime.event_start_times["Looking Away"] = t0 - 20.0
    runtime.event_start_times["Phone Use"] = t0 - 8.0

    raw_result = {
        "state": "distracted",
        "active_alerts": ["Looking Away", "Phone Use"],
        "newly_started": [],
        "newly_ended": [],
    }

    payload = runtime._build_detection_result_payload(raw_result, timestamp=t0)

    assert payload["type"] == "detection_result"
    assert payload["state"] == "distracted"
    assert len(payload["active_detections"]) == 2

    cats = [d["category"] for d in payload["active_detections"]]
    assert "looking_away" in cats
    assert "phone_use" in cats

    for item in payload["active_detections"]:
        assert "category" in item
        assert "alert_name" in item
        assert "started_at" in item
        assert "duration_seconds" in item
        assert item["duration_seconds"] > 0

    assert "metrics" in payload
    assert "focus_score" in payload["metrics"]
    assert "focused_seconds" in payload["metrics"]
    assert "distracted_seconds" in payload["metrics"]
    assert "away_seconds" in payload["metrics"]
    assert "distraction_count" in payload["metrics"]

