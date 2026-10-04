"""Tests for Session History & Session Detail APIs."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from app.db.models.study_session import StudySession
from app.db.models.detection_event import DetectionEvent
from app.db.session import get_async_session
from app.main import app


@pytest.mark.asyncio
async def test_session_history_unauthenticated():
    """Unauthenticated request to /api/sessions/history must be rejected with 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/sessions/history")
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_session_history_pagination_and_ordering(db_session):
    """Verify paginated history returns newest sessions first and respects page boundaries."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_res = await client.post(
            "/api/auth/dev-login",
            json={"email": "history_user@example.com", "display_name": "History User"},
        )
        assert login_res.status_code == 200
        user_id = uuid.UUID(login_res.json()["user"]["id"])

        # Insert 15 completed sessions with incremental timestamps
        base_time = datetime(2026, 10, 1, 10, 0, 0, tzinfo=timezone.utc)
        sessions = []
        for i in range(15):
            started = base_time + timedelta(hours=i * 2)
            ended = started + timedelta(minutes=45)
            s = StudySession(
                id=uuid.uuid4(),
                user_id=user_id,
                started_at=started,
                ended_at=ended,
                status="completed",
                total_duration_seconds=2700.0,
                focused_seconds=2400.0,
                distracted_seconds=300.0,
                away_seconds=0.0,
                focus_score=Decimal("85.50"),
            )
            db_session.add(s)
            sessions.append(s)
        await db_session.commit()

        # Page 1 (default page_size = 10)
        res_p1 = await client.get("/api/sessions/history?page=1&page_size=10")
        assert res_p1.status_code == 200
        data_p1 = res_p1.json()

        assert data_p1["total"] == 15
        assert data_p1["page"] == 1
        assert data_p1["page_size"] == 10
        assert data_p1["total_pages"] == 2
        assert len(data_p1["items"]) == 10

        # Verify newest session first: session 14 should be first
        first_session = data_p1["items"][0]
        second_session = data_p1["items"][1]
        assert first_session["started_at"] > second_session["started_at"]
        assert first_session["id"] == str(sessions[14].id)

        # Page 2
        res_p2 = await client.get("/api/sessions/history?page=2&page_size=10")
        assert res_p2.status_code == 200
        data_p2 = res_p2.json()

        assert data_p2["page"] == 2
        assert len(data_p2["items"]) == 5
        # The oldest session (session 0) should be the last item on page 2
        assert data_p2["items"][-1]["id"] == str(sessions[0].id)

        # Max page size enforcement: requesting page_size=100 should be capped at 50
        res_capped = await client.get("/api/sessions/history?page=1&page_size=100")
        assert res_capped.status_code == 200
        assert res_capped.json()["page_size"] == 50

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_session_history_idor_ownership_isolation(db_session):
    """Verify User A cannot see User B's sessions or events."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create User A
        login_a = await client.post(
            "/api/auth/dev-login",
            json={"email": "user_a@example.com", "display_name": "User A", "google_sub": "google-sub-a-unique"},
        )
        user_a_id = uuid.UUID(login_a.json()["user"]["id"])

        # Insert session for User A
        session_a = StudySession(
            id=uuid.uuid4(),
            user_id=user_a_id,
            started_at=datetime.now(timezone.utc),
            status="completed",
            total_duration_seconds=1800.0,
        )
        db_session.add(session_a)
        await db_session.commit()

        # Login as User B
        login_b = await client.post(
            "/api/auth/dev-login",
            json={"email": "user_b@example.com", "display_name": "User B", "google_sub": "google-sub-b-unique"},
        )
        user_b_id = uuid.UUID(login_b.json()["user"]["id"])

        # User B fetches history: should see 0 sessions
        res_b_history = await client.get("/api/sessions/history")
        assert res_b_history.status_code == 200
        data_b = res_b_history.json()
        assert data_b["total"] == 0
        assert len(data_b["items"]) == 0

        # User B attempts to access User A's session directly by ID
        res_b_detail = await client.get(f"/api/sessions/{session_a.id}")
        assert res_b_detail.status_code == 404
        assert res_b_detail.json()["detail"] == "Study session not found."

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_session_detail_with_events_and_category_breakdown(db_session):
    """Verify session detail endpoint returns session summary, discrete events, and category causes."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_res = await client.post(
            "/api/auth/dev-login",
            json={"email": "detail_user@example.com", "display_name": "Detail User"},
        )
        user_id = uuid.UUID(login_res.json()["user"]["id"])

        session_id = uuid.uuid4()
        started_dt = datetime(2026, 10, 4, 14, 0, 0, tzinfo=timezone.utc)
        ended_dt = datetime(2026, 10, 4, 15, 0, 0, tzinfo=timezone.utc)

        session = StudySession(
            id=session_id,
            user_id=user_id,
            started_at=started_dt,
            ended_at=ended_dt,
            status="completed",
            total_duration_seconds=3600.0,
            focused_seconds=3000.0,
            distracted_seconds=500.0,
            away_seconds=100.0,
            focus_score=Decimal("83.33"),
        )
        db_session.add(session)

        # Add 3 discrete detection events
        e1 = DetectionEvent(
            id=uuid.uuid4(),
            session_id=session_id,
            event_type="phone_use",
            started_at=started_dt + timedelta(minutes=10),
            ended_at=started_dt + timedelta(minutes=12),
            duration_seconds=120.0,
            detector_version="v4",
        )
        e2 = DetectionEvent(
            id=uuid.uuid4(),
            session_id=session_id,
            event_type="looking_away",
            started_at=started_dt + timedelta(minutes=25),
            ended_at=started_dt + timedelta(minutes=27, seconds=30),
            duration_seconds=150.0,
            detector_version="v4",
        )
        e3 = DetectionEvent(
            id=uuid.uuid4(),
            session_id=session_id,
            event_type="phone_use",
            started_at=started_dt + timedelta(minutes=40),
            ended_at=started_dt + timedelta(minutes=41),
            duration_seconds=60.0,
            detector_version="v4",
        )
        db_session.add_all([e1, e2, e3])
        await db_session.commit()

        # Fetch session detail
        res = await client.get(f"/api/sessions/{session_id}")
        assert res.status_code == 200
        data = res.json()

        assert data["id"] == str(session_id)
        assert data["status"] == "completed"
        assert data["total_duration_seconds"] == 3600.0
        assert data["focused_seconds"] == 3000.0
        assert data["distracted_seconds"] == 500.0
        assert data["away_seconds"] == 100.0
        assert float(data["focus_score"]) == 83.33
        assert data["distraction_count"] == 3

        # Verify events array
        assert len(data["events"]) == 3
        assert data["events"][0]["event_type"] == "phone_use"
        assert data["events"][0]["duration_seconds"] == 120.0
        assert data["events"][1]["event_type"] == "looking_away"
        assert data["events"][1]["duration_seconds"] == 150.0
        assert data["events"][2]["event_type"] == "phone_use"
        assert data["events"][2]["duration_seconds"] == 60.0

        # Verify top causes and category breakdown
        assert "Phone Use" in data["top_causes"]
        assert "Looking Away" in data["top_causes"]
        assert len(data["category_breakdown"]) == 2

        # phone_use should have 2 events and 180s total
        phone_cat = next(c for c in data["category_breakdown"] if c["category"] == "phone_use")
        assert phone_cat["count"] == 2
        assert phone_cat["duration_seconds"] == 180.0
        assert phone_cat["label"] == "Phone Use"

    app.dependency_overrides.clear()
