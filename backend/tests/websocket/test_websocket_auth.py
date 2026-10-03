"""Tests for WebSocket handshake authentication, origin validation, and session ownership."""
import uuid
import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.security import create_access_token
from app.db.models.study_session import StudySession
from app.db.models.user import User
from app.db.base import utc_now
from app.db.session import get_async_session
from app.main import app
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
async def test_unauthenticated_connection_rejected(db_session):
    """Verify WebSocket handshake without credentials is closed with code 1008."""
    client = TestClient(app)
    fake_session_id = uuid.uuid4()

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            f"/api/ws/sessions/{fake_session_id}",
            headers={"Origin": "http://localhost:5174"},
        ):
            pass

    assert exc_info.value.code == 1008


@pytest.mark.asyncio
async def test_invalid_session_id_rejected(db_session):
    """Verify malformed session ID is rejected with code 1008."""
    # Create test user and token
    user = User(
        email="ws_invalid_id@example.com",
        display_name="WS User",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    token = create_access_token(user.id)
    client = TestClient(app, cookies={"sfm_session": token})

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            "/api/ws/sessions/not-a-uuid",
            headers={"Origin": "http://localhost:5174"},
        ):
            pass

    assert exc_info.value.code == 1008


@pytest.mark.asyncio
async def test_nonexistent_session_rejected(db_session):
    """Verify non-existent session is rejected with code 1008."""
    user = User(
        email="ws_nonexistent@example.com",
        display_name="WS User",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    token = create_access_token(user.id)
    client = TestClient(app, cookies={"sfm_session": token})
    nonexistent_id = uuid.uuid4()

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            f"/api/ws/sessions/{nonexistent_id}",
            headers={"Origin": "http://localhost:5174"},
        ):
            pass

    assert exc_info.value.code == 1008


@pytest.mark.asyncio
async def test_completed_session_rejected(db_session):
    """Verify live transport connection to a completed session is rejected."""
    user = User(
        email="ws_completed_session@example.com",
        display_name="WS User",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Completed session
    session = StudySession(
        user_id=user.id,
        status="completed",
        started_at=utc_now(),
        ended_at=utc_now(),
        total_duration_seconds=600.0,
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    token = create_access_token(user.id)
    client = TestClient(app, cookies={"sfm_session": token})

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            f"/api/ws/sessions/{session.id}",
            headers={"Origin": "http://localhost:5174"},
        ):
            pass

    assert exc_info.value.code == 1008


@pytest.mark.asyncio
async def test_other_user_session_rejected_idor(db_session):
    """Verify User B cannot connect to User A's active session."""
    user_a = User(email="ws_user_a@example.com", display_name="User A", is_active=True)
    user_b = User(email="ws_user_b@example.com", display_name="User B", is_active=True)
    db_session.add_all([user_a, user_b])
    await db_session.commit()
    await db_session.refresh(user_a)
    await db_session.refresh(user_b)

    # User A's active session
    session_a = StudySession(
        user_id=user_a.id,
        status="active",
        started_at=utc_now(),
    )
    db_session.add(session_a)
    await db_session.commit()
    await db_session.refresh(session_a)

    # User B attempts to connect
    token_b = create_access_token(user_b.id)
    client = TestClient(app, cookies={"sfm_session": token_b})

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            f"/api/ws/sessions/{session_a.id}",
            headers={"Origin": "http://localhost:5174"},
        ):
            pass

    assert exc_info.value.code == 1008


@pytest.mark.asyncio
async def test_unexpected_origin_rejected(db_session):
    """Verify unauthorized Origin header is rejected with code 1008."""
    user = User(email="ws_origin@example.com", display_name="WS Origin", is_active=True)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    session = StudySession(user_id=user.id, status="active", started_at=utc_now())
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    token = create_access_token(user.id)
    client = TestClient(app, cookies={"sfm_session": token})

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            f"/api/ws/sessions/{session.id}",
            headers={"Origin": "http://evil-tracker.attacker.com"},
        ):
            pass

    assert exc_info.value.code == 1008


@pytest.mark.asyncio
async def test_trusted_origin_and_cookie_auth_accepted(db_session):
    """Verify trusted Origin and HttpOnly cookie establishes live transport with ready message."""
    user = User(email="ws_trusted@example.com", display_name="WS Trusted", is_active=True)
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
        # Should receive initial ready payload
        ready_msg = ws.receive_json()
        assert ready_msg["type"] == "ready"
        assert ready_msg["session_id"] == str(session.id)
        assert ready_msg["target_fps"] == 5
        assert ready_msg["max_frame_size_bytes"] == 1048576
