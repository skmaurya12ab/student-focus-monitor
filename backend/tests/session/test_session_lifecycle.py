"""Comprehensive backend tests for Phase 6 Study Session Lifecycle."""
import asyncio
from datetime import datetime, timezone
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from app.db.models.study_session import StudySession
from app.db.models.user import User
from app.db.session import get_async_session
from app.main import app


@pytest.mark.asyncio
async def test_create_session_authenticated(db_session):
    """Verify an authenticated user can start a study session with server-generated UUID and started_at."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Dev login
        login_res = await client.post(
            "/api/auth/dev-login",
            json={"email": "lifecycle_test@example.com", "display_name": "Lifecycle Student"},
        )
        assert login_res.status_code == 200
        user_id = login_res.json()["user"]["id"]

        # 2. Start study session
        create_res = await client.post(
            "/api/sessions",
            json={"notes": "Exam revision - Algorithms", "device_hint": "Integrated 720p"},
        )
        assert create_res.status_code == 201
        session_data = create_res.json()

        # 3. Verify server-authoritative fields
        session_id = session_data["id"]
        assert uuid.UUID(session_id)  # Must be valid UUID
        assert session_data["user_id"] == user_id
        assert session_data["status"] == "active"
        assert session_data["started_at"] is not None
        assert session_data["ended_at"] is None
        assert session_data["total_duration_seconds"] == 0.0
        assert session_data["focus_score"] is None
        assert session_data["detector_version"] == "v4"

        # 4. Verify persistence in PostgreSQL
        stmt = select(StudySession).where(StudySession.id == uuid.UUID(session_id))
        persisted = (await db_session.execute(stmt)).scalars().first()
        assert persisted is not None
        assert persisted.status == "active"
        assert persisted.user_id == uuid.UUID(user_id)

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_session_unauthenticated_returns_401(db_session):
    """Verify unauthenticated requests cannot create a study session."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/sessions", json={})
        assert res.status_code == 401
        assert "WWW-Authenticate" in res.headers

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_duplicate_active_session_rejected_with_409(db_session):
    """Verify that attempting to create a second active session returns HTTP 409 Conflict."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Dev login
        await client.post(
            "/api/auth/dev-login",
            json={"email": "duplicate_test@example.com", "display_name": "Duplicate Student"},
        )

        # First session creation succeeds
        res1 = await client.post("/api/sessions", json={})
        assert res1.status_code == 201

        # Second session creation must be rejected with 409 Conflict
        res2 = await client.post("/api/sessions", json={})
        assert res2.status_code == 409
        detail = res2.json()["detail"]
        assert "already has an active study session" in detail

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_active_session_lifecycle(db_session):
    """Verify /api/sessions/active returns null when no session is active and the active session when present."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/api/auth/dev-login",
            json={"email": "active_test@example.com", "display_name": "Active Student"},
        )

        # 1. Initially no active session
        get_res1 = await client.get("/api/sessions/active")
        assert get_res1.status_code == 200
        assert get_res1.json()["session"] is None

        # 2. Start a session
        create_res = await client.post("/api/sessions", json={})
        assert create_res.status_code == 201
        session_id = create_res.json()["id"]

        # 3. Active session is now returned
        get_res2 = await client.get("/api/sessions/active")
        assert get_res2.status_code == 200
        active_data = get_res2.json()["session"]
        assert active_data is not None
        assert active_data["id"] == session_id
        assert active_data["status"] == "active"

        # 4. Stop session
        stop_res = await client.post(f"/api/sessions/{session_id}/stop")
        assert stop_res.status_code == 200

        # 5. After stop, active session is null again
        get_res3 = await client.get("/api/sessions/active")
        assert get_res3.status_code == 200
        assert get_res3.json()["session"] is None

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_active_session_unauthenticated_returns_401(db_session):
    """Verify /api/sessions/active requires authentication."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/sessions/active")
        assert res.status_code == 401

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_session_by_id_and_ownership_idor_protection(db_session):
    """Verify GET /api/sessions/{session_id} enforces strict user ownership (prevents IDOR)."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    # User A creates a session
    async with AsyncClient(transport=transport, base_url="http://test") as client_a:
        await client_a.post(
            "/api/auth/dev-login",
            json={"email": "usera@example.com", "display_name": "User A", "google_sub": "sub-user-a"},
        )
        res_a = await client_a.post("/api/sessions", json={})
        session_a_id = res_a.json()["id"]

        # User A can retrieve session A
        own_res = await client_a.get(f"/api/sessions/{session_a_id}")
        assert own_res.status_code == 200
        assert own_res.json()["id"] == session_a_id

    # User B attempts to access User A's session
    async with AsyncClient(transport=transport, base_url="http://test") as client_b:
        await client_b.post(
            "/api/auth/dev-login",
            json={"email": "userb@example.com", "display_name": "User B", "google_sub": "sub-user-b"},
        )

        # Must return 404 (do not leak existence to unauthorized users)
        idor_res = await client_b.get(f"/api/sessions/{session_a_id}")
        assert idor_res.status_code == 404
        assert "not found" in idor_res.json()["detail"].lower()

        # Nonexistent session also returns 404
        random_id = uuid.uuid4()
        not_found_res = await client_b.get(f"/api/sessions/{random_id}")
        assert not_found_res.status_code == 404

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_stop_session_lifecycle_and_duration_calculation(db_session):
    """Verify stopping a session transitions it to completed, records ended_at, and calculates duration."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/api/auth/dev-login",
            json={"email": "duration_test@example.com", "display_name": "Duration Student", "google_sub": "sub-duration"},
        )

        # 1. Start session
        create_res = await client.post("/api/sessions", json={})
        session_id = create_res.json()["id"]

        # Wait a brief moment to ensure measurable duration
        await asyncio.sleep(0.1)

        # 2. Stop session
        stop_res = await client.post(f"/api/sessions/{session_id}/stop")
        assert stop_res.status_code == 200
        data = stop_res.json()
        assert data["status"] == "success"
        completed = data["session"]

        # 3. Validate authoritative server completion fields
        assert completed["id"] == session_id
        assert completed["status"] == "completed"
        assert completed["ended_at"] is not None
        assert completed["total_duration_seconds"] >= 0.05
        # Ensure start was before end
        started_dt = datetime.fromisoformat(completed["started_at"])
        ended_dt = datetime.fromisoformat(completed["ended_at"])
        assert ended_dt >= started_dt

        # 4. Attempting to stop already completed session must return 409 Conflict
        repeat_stop_res = await client.post(f"/api/sessions/{session_id}/stop")
        assert repeat_stop_res.status_code == 409
        assert "Only active sessions can be stopped" in repeat_stop_res.json()["detail"]

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_stop_other_user_session_denied_returns_404(db_session):
    """Verify User B cannot stop User A's session."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client_a:
        await client_a.post("/api/auth/dev-login", json={"email": "alice_stop@example.com", "display_name": "Alice", "google_sub": "sub-alice"})
        res_a = await client_a.post("/api/sessions", json={})
        session_a_id = res_a.json()["id"]

    async with AsyncClient(transport=transport, base_url="http://test") as client_b:
        await client_b.post("/api/auth/dev-login", json={"email": "bob_stop@example.com", "display_name": "Bob", "google_sub": "sub-bob"})
        stop_b_res = await client_b.post(f"/api/sessions/{session_a_id}/stop")
        assert stop_b_res.status_code == 404

    # Verify Alice's session is still active
    async with AsyncClient(transport=transport, base_url="http://test") as client_a:
        await client_a.post("/api/auth/dev-login", json={"email": "alice_stop@example.com", "display_name": "Alice", "google_sub": "sub-alice"})
        check_res = await client_a.get("/api/sessions/active")
        assert check_res.json()["session"]["id"] == session_a_id
        assert check_res.json()["session"]["status"] == "active"


    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_stop_unauthenticated_session_returns_401(db_session):
    """Verify stopping a session requires authentication."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(f"/api/sessions/{uuid.uuid4()}/stop")
        assert res.status_code == 401

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_start_new_session_after_completing_prior_session(db_session):
    """Verify that completing a session clears the active slot, allowing a subsequent session to start."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/auth/dev-login", json={"email": "sequential@example.com", "display_name": "Sequential"})

        # Session 1
        res1 = await client.post("/api/sessions", json={})
        assert res1.status_code == 201
        session1_id = res1.json()["id"]

        # Stop Session 1
        stop1 = await client.post(f"/api/sessions/{session1_id}/stop")
        assert stop1.status_code == 200

        # Session 2 succeeds immediately
        res2 = await client.post("/api/sessions", json={})
        assert res2.status_code == 201
        session2_id = res2.json()["id"]
        assert session1_id != session2_id

        # Verify active session is now Session 2
        active = await client.get("/api/sessions/active")
        assert active.json()["session"]["id"] == session2_id

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_latest_session_lifecycle_and_invariants(db_session):
    """Verify /api/sessions/latest retrieves the most recent session and satisfies duration invariants."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/api/auth/dev-login",
            json={"email": "latest_test@example.com", "display_name": "Latest Student"},
        )

        # 1. No sessions initially
        res0 = await client.get("/api/sessions/latest")
        assert res0.status_code == 200
        assert res0.json()["session"] is None

        # 2. Start session
        res1 = await client.post("/api/sessions", json={})
        session1_id = res1.json()["id"]

        # Latest should return active session 1
        res2 = await client.get("/api/sessions/latest")
        assert res2.status_code == 200
        assert res2.json()["session"]["id"] == session1_id
        assert res2.json()["session"]["status"] == "active"

        await asyncio.sleep(0.1)

        # 3. Stop session
        stop_res = await client.post(f"/api/sessions/{session1_id}/stop")
        assert stop_res.status_code == 200

        # Latest should now return completed session 1
        res3 = await client.get("/api/sessions/latest")
        assert res3.status_code == 200
        latest = res3.json()["session"]
        assert latest["id"] == session1_id
        assert latest["status"] == "completed"

        # Verify duration invariant: total_duration_seconds ≈ ended_at - started_at
        started_dt = datetime.fromisoformat(latest["started_at"])
        ended_dt = datetime.fromisoformat(latest["ended_at"])
        expected_dur = (ended_dt - started_dt).total_seconds()
        assert abs(latest["total_duration_seconds"] - expected_dur) < 0.1
        assert latest["total_duration_seconds"] >= 0.05

        # Verify metrics invariants
        assert latest["focused_seconds"] >= 0
        assert latest["distracted_seconds"] >= 0
        assert latest["away_seconds"] >= 0
        assert latest["focused_seconds"] + latest["distracted_seconds"] + latest["away_seconds"] <= latest["total_duration_seconds"] + 0.1
        assert "distraction_count" in latest

    app.dependency_overrides.clear()
