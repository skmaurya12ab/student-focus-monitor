"""Tests for Historical Focus Analytics API (GET /api/analytics)."""
from datetime import datetime, date, time, timedelta, timezone
from decimal import Decimal
import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from app.db.models.study_session import StudySession
from app.db.models.detection_event import DetectionEvent
from app.db.session import get_async_session
from app.main import app


@pytest.mark.asyncio
async def test_analytics_unauthenticated():
    """Unauthenticated request to /api/analytics must return 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/analytics")
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_analytics_empty_user(db_session):
    """User with no study sessions receives zeroed analytics without errors or synthetic data."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_res = await client.post(
            "/api/auth/dev-login",
            json={"email": "empty_analytics@example.com", "display_name": "Empty User"},
        )
        assert login_res.status_code == 200

        res = await client.get("/api/analytics?range=7d")
        assert res.status_code == 200
        data = res.json()

        assert data["range"] == "7d"
        summary = data["summary"]
        assert summary["total_study_time_seconds"] == 0.0
        assert summary["average_session_duration_seconds"] == 0.0
        assert summary["average_focus_score"] is None
        assert summary["total_distracted_seconds"] == 0.0
        assert summary["total_away_seconds"] == 0.0
        assert summary["total_distractions"] == 0
        assert summary["completed_sessions_count"] == 0

        # Trend data
        trend = data["trend"]
        assert trend["score"] == "—"
        assert len(trend["data"]) == 7
        for day in trend["data"]:
            assert day["focus_score"] is None
            assert day["study_time_seconds"] == 0.0
            assert day["session_count"] == 0

        # Breakdown data
        breakdown = data["breakdown"]
        assert breakdown["total_events"] == 0
        assert breakdown["total_distraction_seconds"] == 0.0
        for cat in breakdown["categories"]:
            assert cat["count"] == 0
            assert cat["duration_seconds"] == 0.0

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_analytics_metrics_and_formula_verification(db_session):
    """Verify exact mathematical aggregation of completed sessions and detection events."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_res = await client.post(
            "/api/auth/dev-login",
            json={"email": "analytics_calc@example.com", "display_name": "Analytics Calc"},
        )
        user_id = uuid.UUID(login_res.json()["user"]["id"])

        now_utc = datetime.now(timezone.utc)

        # Session 1: 60m, focus=80.0
        s1_id = uuid.uuid4()
        s1 = StudySession(
            id=s1_id,
            user_id=user_id,
            started_at=now_utc - timedelta(days=2),
            ended_at=now_utc - timedelta(days=2) + timedelta(minutes=60),
            status="completed",
            total_duration_seconds=3600.0,
            focused_seconds=3000.0,
            distracted_seconds=400.0,
            away_seconds=200.0,
            focus_score=Decimal("80.00"),
        )

        # Session 2: 30m, focus=60.0
        s2_id = uuid.uuid4()
        s2 = StudySession(
            id=s2_id,
            user_id=user_id,
            started_at=now_utc - timedelta(days=1),
            ended_at=now_utc - timedelta(days=1) + timedelta(minutes=30),
            status="completed",
            total_duration_seconds=1800.0,
            focused_seconds=1500.0,
            distracted_seconds=200.0,
            away_seconds=100.0,
            focus_score=Decimal("60.00"),
        )

        # Active session: 45m (should NOT be counted in completed analytics)
        s3_active = StudySession(
            id=uuid.uuid4(),
            user_id=user_id,
            started_at=now_utc - timedelta(minutes=45),
            status="active",
            total_duration_seconds=2700.0,
            focused_seconds=2000.0,
            distracted_seconds=700.0,
            away_seconds=0.0,
            focus_score=Decimal("75.00"),
        )

        db_session.add_all([s1, s2, s3_active])

        # Events for Session 1: 1 phone_use (150s), 1 looking_away (250s)
        e1 = DetectionEvent(
            id=uuid.uuid4(),
            session_id=s1_id,
            event_type="phone_use",
            started_at=now_utc - timedelta(days=2) + timedelta(minutes=10),
            ended_at=now_utc - timedelta(days=2) + timedelta(minutes=12, seconds=30),
            duration_seconds=150.0,
            detector_version="v4",
        )
        e2 = DetectionEvent(
            id=uuid.uuid4(),
            session_id=s1_id,
            event_type="looking_away",
            started_at=now_utc - timedelta(days=2) + timedelta(minutes=25),
            ended_at=now_utc - timedelta(days=2) + timedelta(minutes=29, seconds=10),
            duration_seconds=250.0,
            detector_version="v4",
        )

        # Events for Session 2: 1 phone_use (200s)
        e3 = DetectionEvent(
            id=uuid.uuid4(),
            session_id=s2_id,
            event_type="phone_use",
            started_at=now_utc - timedelta(days=1) + timedelta(minutes=5),
            ended_at=now_utc - timedelta(days=1) + timedelta(minutes=8, seconds=20),
            duration_seconds=200.0,
            detector_version="v4",
        )

        db_session.add_all([e1, e2, e3])
        await db_session.commit()

        # Query analytics
        res = await client.get("/api/analytics?range=7d")
        assert res.status_code == 200
        data = res.json()

        summary = data["summary"]
        assert summary["completed_sessions_count"] == 2
        assert summary["total_study_time_seconds"] == 5400.0  # 3600 + 1800
        assert summary["average_session_duration_seconds"] == 2700.0  # (3600 + 1800) / 2
        assert summary["average_focus_score"] == 70.0  # (80.0 + 60.0) / 2
        assert summary["total_distracted_seconds"] == 600.0  # 400 + 200
        assert summary["total_away_seconds"] == 300.0  # 200 + 100
        assert summary["total_distractions"] == 3  # 3 detection events

        # Category Breakdown
        breakdown = data["breakdown"]
        assert breakdown["total_events"] == 3
        assert breakdown["total_distraction_seconds"] == 600.0  # 150 + 250 + 200

        phone_item = next(c for c in breakdown["categories"] if c["category"] == "phone_use")
        assert phone_item["count"] == 2
        assert phone_item["duration_seconds"] == 350.0  # 150 + 200

        looking_item = next(c for c in breakdown["categories"] if c["category"] == "looking_away")
        assert looking_item["count"] == 1
        assert looking_item["duration_seconds"] == 250.0

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_analytics_timezone_local_midnight_correctness(db_session):
    """Verify sessions at late local hours (e.g. 23:30 local) are bucketed to the correct local calendar day."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_res = await client.post(
            "/api/auth/dev-login",
            json={"email": "tz_user@example.com", "display_name": "Timezone User"},
        )
        user_id = uuid.UUID(login_res.json()["user"]["id"])

        # In Asia/Kolkata (UTC+5:30), 2026-10-03 23:30 local is 2026-10-03 18:00 UTC.
        # But in UTC, 2026-10-03 18:00 UTC is also Oct 3.
        # Let's test America/New_York (UTC-4 in daylight saving):
        # 2026-10-03 23:30 New York is 2026-10-04 03:30 UTC!
        # In UTC, the date is Oct 4. In America/New_York, the date is Oct 3!
        session_dt_utc = datetime(2026, 10, 4, 3, 30, 0, tzinfo=timezone.utc)

        s = StudySession(
            id=uuid.uuid4(),
            user_id=user_id,
            started_at=session_dt_utc,
            ended_at=session_dt_utc + timedelta(minutes=20),
            status="completed",
            total_duration_seconds=1200.0,
            focused_seconds=1000.0,
            distracted_seconds=200.0,
            away_seconds=0.0,
            focus_score=Decimal("83.33"),
        )
        db_session.add(s)
        await db_session.commit()

        # Query with timezone America/New_York
        res_ny = await client.get("/api/analytics?range=30d&tz=America/New_York")
        assert res_ny.status_code == 200
        data_ny = res_ny.json()

        # Find Oct 3 and Oct 4 in daily trend
        oct3 = next((d for d in data_ny["trend"]["data"] if d["date"] == "2026-10-03"), None)
        oct4 = next((d for d in data_ny["trend"]["data"] if d["date"] == "2026-10-04"), None)

        assert oct3 is not None
        # In America/New_York, the session belongs to Oct 3!
        assert oct3["session_count"] == 1
        assert oct3["study_time_seconds"] == 1200.0
        assert oct3["focus_score"] == 83.3

        if oct4 is not None:
            assert oct4["session_count"] == 0
            assert oct4["focus_score"] is None

    app.dependency_overrides.clear()
