"""Tests for WebSocket frame streaming, backpressure, limits, privacy, and connection management."""
import time
import uuid
import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from sqlalchemy import select

from app.core.security import create_access_token
from app.db.models.study_session import StudySession
from app.db.models.user import User
from app.db.base import utc_now
from app.db.session import get_async_session
from app.main import app
from app.services.live_transport_service import (
    live_transport_manager,
    MAX_FRAME_SIZE_BYTES,
)
from app.services.session_service import SessionService
from tests.db.conftest import ASYNC_TEST_URL
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool


@pytest.fixture(autouse=True)
def override_db():
    async def _get_test_session():
        engine = create_async_engine(ASYNC_TEST_URL, poolclass=NullPool)
        factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            yield session
        await engine.dispose()

    app.dependency_overrides[get_async_session] = _get_test_session
    yield
    app.dependency_overrides.pop(get_async_session, None)


@pytest.mark.asyncio
async def test_binary_frame_accepted_and_metrics_tracked(db_session):
    """Verify binary frame transmission updates in-memory transport metrics without persisting media."""
    user = User(email="ws_stream@example.com", display_name="WS Streamer", is_active=True)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    session = StudySession(user_id=user.id, status="active", started_at=utc_now())
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    token = create_access_token(user.id)
    client = TestClient(app, cookies={"sfm_session": token})

    synthetic_frame = b"\xff\xd8\xff\xe0" + b"\x00" * 1024  # 1 KB dummy JPEG

    with client.websocket_connect(
        f"/api/ws/sessions/{session.id}",
        headers={"Origin": "http://localhost:5174"},
    ) as ws:
        ready = ws.receive_json()
        assert ready["type"] == "ready"

        # Send 10 binary frames
        for _ in range(10):
            ws.send_bytes(synthetic_frame)

        # After 10 frames, server sends an ack
        ack = ws.receive_json()
        assert ack["type"] == "ack"
        assert ack["frames_received"] == 10
        assert ack["bytes_received"] == 10 * len(synthetic_frame)

        # Verify in-memory metrics
        metrics = live_transport_manager.get_metrics(session.id)
        assert metrics is not None
        assert metrics.frames_received == 10
        assert metrics.frames_dropped == 0


@pytest.mark.asyncio
async def test_oversized_frame_rejected(db_session):
    """Verify frames exceeding MAX_FRAME_SIZE_BYTES are discarded and trigger a warning."""
    user = User(email="ws_oversize@example.com", display_name="WS Oversize", is_active=True)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    session = StudySession(user_id=user.id, status="active", started_at=utc_now())
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    token = create_access_token(user.id)
    client = TestClient(app, cookies={"sfm_session": token})

    oversized_frame = b"\x00" * (MAX_FRAME_SIZE_BYTES + 500)

    with client.websocket_connect(
        f"/api/ws/sessions/{session.id}",
        headers={"Origin": "http://localhost:5174"},
    ) as ws:
        ws.receive_json()  # ready
        ws.send_bytes(oversized_frame)

        warning = ws.receive_json()
        assert warning["type"] == "warning"
        assert "exceeds size limit" in warning["message"]

        metrics = live_transport_manager.get_metrics(session.id)
        assert metrics.frames_dropped == 1
        assert metrics.frames_received == 0


@pytest.mark.asyncio
async def test_rate_limiting_throttle(db_session):
    """Verify sending frames beyond max_fps causes excess frames to be dropped."""
    user = User(email="ws_ratelimit@example.com", display_name="WS RateLimit", is_active=True)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    session = StudySession(user_id=user.id, status="active", started_at=utc_now())
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    token = create_access_token(user.id)
    client = TestClient(app, cookies={"sfm_session": token})

    small_frame = b"\x00" * 100

    with client.websocket_connect(
        f"/api/ws/sessions/{session.id}",
        headers={"Origin": "http://localhost:5174"},
    ) as ws:
        ws.receive_json()  # ready

        # Send 25 frames immediately in a burst (max_fps is 15)
        for _ in range(25):
            ws.send_bytes(small_frame)

        metrics = live_transport_manager.get_metrics(session.id)
        assert metrics.frames_received <= 15
        assert metrics.frames_dropped >= 10


@pytest.mark.asyncio
async def test_ping_pong_heartbeat(db_session):
    """Verify ping/pong control messages for stale connection detection."""
    user = User(email="ws_ping@example.com", display_name="WS Ping", is_active=True)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    session = StudySession(user_id=user.id, status="active", started_at=utc_now())
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    token = create_access_token(user.id)
    client = TestClient(app, cookies={"sfm_session": token})

    with client.websocket_connect(
        f"/api/ws/sessions/{session.id}",
        headers={"Origin": "http://localhost:5174"},
    ) as ws:
        ws.receive_json()  # ready
        ws.send_json({"type": "ping", "timestamp": 123456789})

        pong = ws.receive_json()
        assert pong["type"] == "pong"
        assert pong["timestamp"] == 123456789


@pytest.mark.asyncio
async def test_client_stop_control_message(db_session):
    """Verify client stop control message cleanly closes transport with code 1000."""
    user = User(email="ws_stop@example.com", display_name="WS Stop", is_active=True)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    session = StudySession(user_id=user.id, status="active", started_at=utc_now())
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    token = create_access_token(user.id)
    client = TestClient(app, cookies={"sfm_session": token})

    with client.websocket_connect(
        f"/api/ws/sessions/{session.id}",
        headers={"Origin": "http://localhost:5174"},
    ) as ws:
        ws.receive_json()  # ready
        ws.send_json({"type": "stop"})

        closed_msg = ws.receive_json()
        assert closed_msg["type"] == "closed"


@pytest.mark.asyncio
async def test_malformed_and_unknown_json_control_messages(db_session):
    """Verify malformed JSON or unknown message types return error without crashing."""
    user = User(email="ws_err@example.com", display_name="WS Err", is_active=True)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    session = StudySession(user_id=user.id, status="active", started_at=utc_now())
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    token = create_access_token(user.id)
    client = TestClient(app, cookies={"sfm_session": token})

    with client.websocket_connect(
        f"/api/ws/sessions/{session.id}",
        headers={"Origin": "http://localhost:5174"},
    ) as ws:
        ws.receive_json()  # ready

        # 1. Unknown type
        ws.send_json({"type": "unknown_action_type"})
        err1 = ws.receive_json()
        assert err1["type"] == "error"
        assert "Unknown message type" in err1["message"]

        # 2. Malformed text
        ws.send_text("this is not json {")
        err2 = ws.receive_json()
        assert err2["type"] == "error"
        assert "Malformed JSON" in err2["message"]


@pytest.mark.asyncio
async def test_duplicate_live_connection_rejected(db_session):
    """Verify attempting two live transport connections for the same session is rejected."""
    user = User(email="ws_duplicate@example.com", display_name="WS Duplicate", is_active=True)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    session = StudySession(user_id=user.id, status="active", started_at=utc_now())
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    token = create_access_token(user.id)
    client = TestClient(app, cookies={"sfm_session": token})

    with client.websocket_connect(
        f"/api/ws/sessions/{session.id}",
        headers={"Origin": "http://localhost:5174"},
    ) as ws1:
        ws1.receive_json()  # ready
        assert live_transport_manager.is_session_connected(session.id)

        # Second connection attempt for same session should be rejected with code 1008
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(
                f"/api/ws/sessions/{session.id}",
                headers={"Origin": "http://localhost:5174"},
            ):
                pass
        assert exc_info.value.code == 1008


@pytest.mark.asyncio
async def test_stopping_study_session_terminates_live_transport(db_session):
    """Verify completing a study session proactively terminates any active live transport connection."""
    user = User(email="ws_lifecycle_stop@example.com", display_name="WS LifeStop", is_active=True)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    session = StudySession(user_id=user.id, status="active", started_at=utc_now())
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    token = create_access_token(user.id)
    client = TestClient(app, cookies={"sfm_session": token})

    with client.websocket_connect(
        f"/api/ws/sessions/{session.id}",
        headers={"Origin": "http://localhost:5174"},
    ) as ws:
        ws.receive_json()  # ready
        assert live_transport_manager.is_session_connected(session.id)

        # Stop the session via SessionService
        stopped_session = await SessionService.stop_session(db_session, session.id, user.id)
        assert stopped_session.status == "completed"

        # Connection should now be unregistered
        assert not live_transport_manager.is_session_connected(session.id)
