"""Tests for Session Feedback API endpoints and ownership enforcement."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from app.db.models.study_session import StudySession
from app.db.models.detection_event import DetectionEvent
from app.db.models.session_feedback import SessionFeedback
from app.db.session import get_async_session
from app.main import app


@pytest.mark.asyncio
async def test_feedback_unauthenticated():
    """Unauthenticated feedback requests must be rejected with 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        dummy_session_id = uuid.uuid4()
        res_post = await client.post(
            f"/api/sessions/{dummy_session_id}/feedback",
            json={"feedback_type": "correct_detection"},
        )
        assert res_post.status_code == 401

        res_get = await client.get(f"/api/sessions/{dummy_session_id}/feedback")
        assert res_get.status_code == 401


@pytest.mark.asyncio
async def test_feedback_crud_and_idempotent_upsert(db_session):
    """Test valid event feedback (correct_detection, false_positive), idempotent update, and retrieval."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Dev login
        login_res = await client.post(
            "/api/auth/dev-login",
            json={"email": "fb_user@example.com", "display_name": "Feedback User"},
        )
        assert login_res.status_code == 200
        user_id = uuid.UUID(login_res.json()["user"]["id"])

        # Create session + event
        started_dt = datetime.now(timezone.utc) - timedelta(minutes=30)
        session = StudySession(
            id=uuid.uuid4(),
            user_id=user_id,
            started_at=started_dt,
            ended_at=datetime.now(timezone.utc),
            status="completed",
            total_duration_seconds=1800.0,
            focused_seconds=1600.0,
            distracted_seconds=200.0,
            focus_score=Decimal("88.88"),
        )
        db_session.add(session)

        event = DetectionEvent(
            id=uuid.uuid4(),
            session_id=session.id,
            event_type="phone_use",
            started_at=started_dt + timedelta(minutes=5),
            ended_at=started_dt + timedelta(minutes=6),
            duration_seconds=60.0,
            detector_version="v4",
        )
        db_session.add(event)
        await db_session.commit()

        # 1. Submit correct_detection feedback
        post_res = await client.post(
            f"/api/sessions/{session.id}/feedback",
            json={
                "detection_event_id": str(event.id),
                "feedback_type": "correct_detection",
                "note": "Definitely on the phone checking messages",
            },
        )
        assert post_res.status_code == 201
        data = post_res.json()
        assert data["session_id"] == str(session.id)
        assert data["detection_event_id"] == str(event.id)
        assert data["feedback_type"] == "correct_detection"
        assert data["note"] == "Definitely on the phone checking messages"
        fb_id = data["id"]

        # 2. Re-submit as false_positive (idempotent update on same event)
        update_res = await client.post(
            f"/api/sessions/{session.id}/feedback",
            json={
                "detection_event_id": str(event.id),
                "feedback_type": "false_positive",
                "note": "Actually just scratched my ear",
            },
        )
        assert update_res.status_code in (200, 201)
        up_data = update_res.json()
        assert up_data["id"] == fb_id  # Reused same feedback record
        assert up_data["feedback_type"] == "false_positive"
        assert up_data["note"] == "Actually just scratched my ear"

        # 3. GET /api/sessions/{session_id}/feedback
        get_res = await client.get(f"/api/sessions/{session.id}/feedback")
        assert get_res.status_code == 200
        feedbacks = get_res.json()
        assert len(feedbacks) == 1
        assert feedbacks[0]["id"] == fb_id
        assert feedbacks[0]["feedback_type"] == "false_positive"

        # 4. GET /api/sessions/{session_id} includes feedback in event and feedbacks list
        detail_res = await client.get(f"/api/sessions/{session.id}")
        assert detail_res.status_code == 200
        detail_data = detail_res.json()
        assert len(detail_data["events"]) == 1
        assert detail_data["events"][0]["feedback"] is not None
        assert detail_data["events"][0]["feedback"]["feedback_type"] == "false_positive"
        assert len(detail_data["feedbacks"]) == 1

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_missed_detection_and_other_feedback(db_session):
    """Test missed_detection with structured category and other feedback."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_res = await client.post(
            "/api/auth/dev-login",
            json={"email": "missed_user@example.com", "display_name": "Missed User"},
        )
        user_id = uuid.UUID(login_res.json()["user"]["id"])

        session = StudySession(
            id=uuid.uuid4(),
            user_id=user_id,
            started_at=datetime.now(timezone.utc) - timedelta(minutes=15),
            status="completed",
            total_duration_seconds=900.0,
        )
        db_session.add(session)
        await db_session.commit()

        # 1. Submit missed_detection with canonical category
        missed_res = await client.post(
            f"/api/sessions/{session.id}/feedback",
            json={
                "feedback_type": "missed_detection",
                "category": "Looking Away",
                "note": "Looked out the window for 2 minutes",
            },
        )
        assert missed_res.status_code == 201
        m_data = missed_res.json()
        assert m_data["feedback_type"] == "missed_detection"
        assert m_data["category"] == "looking_away"  # normalized to snake_case
        assert m_data["detection_event_id"] is None
        assert m_data["note"] == "Looked out the window for 2 minutes"

        # 2. Missed detection requires category
        err_cat_res = await client.post(
            f"/api/sessions/{session.id}/feedback",
            json={
                "feedback_type": "missed_detection",
            },
        )
        assert err_cat_res.status_code == 400
        assert "requires a valid category" in err_cat_res.json()["detail"]

        # 3. Invalid category is rejected
        invalid_cat_res = await client.post(
            f"/api/sessions/{session.id}/feedback",
            json={
                "feedback_type": "missed_detection",
                "category": "eating_lunch",
            },
        )
        assert invalid_cat_res.status_code == 400
        assert "requires a valid category" in invalid_cat_res.json()["detail"]

        # 4. Submit 'other' feedback
        other_res = await client.post(
            f"/api/sessions/{session.id}/feedback",
            json={
                "feedback_type": "other",
                "note": "The camera lagged slightly around 10:15",
            },
        )
        assert other_res.status_code == 201
        o_data = other_res.json()
        assert o_data["feedback_type"] == "other"
        assert o_data["detection_event_id"] is None
        assert o_data["note"] == "The camera lagged slightly around 10:15"

        # 5. Fetch feedback list
        list_res = await client.get(f"/api/sessions/{session.id}/feedback")
        assert list_res.status_code == 200
        all_fb = list_res.json()
        assert len(all_fb) == 2

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_feedback_idor_and_ownership_enforcement(db_session):
    """Verify cross-user IDOR protection and cross-session event mismatch rejection."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # User A setup
        login_a = await client.post(
            "/api/auth/dev-login",
            json={"email": "owner_a@example.com", "display_name": "Owner A", "google_sub": "sub-a-fb"},
        )
        user_a_id = uuid.UUID(login_a.json()["user"]["id"])

        session_a = StudySession(
            id=uuid.uuid4(),
            user_id=user_a_id,
            started_at=datetime.now(timezone.utc) - timedelta(minutes=20),
            status="completed",
        )
        db_session.add(session_a)

        event_a = DetectionEvent(
            id=uuid.uuid4(),
            session_id=session_a.id,
            event_type="yawning",
            started_at=datetime.now(timezone.utc) - timedelta(minutes=10),
            duration_seconds=5.0,
            detector_version="v4",
        )
        db_session.add(event_a)

        # User B setup
        login_b = await client.post(
            "/api/auth/dev-login",
            json={"email": "attacker_b@example.com", "display_name": "Attacker B", "google_sub": "sub-b-fb"},
        )
        user_b_id = uuid.UUID(login_b.json()["user"]["id"])

        session_b = StudySession(
            id=uuid.uuid4(),
            user_id=user_b_id,
            started_at=datetime.now(timezone.utc) - timedelta(minutes=10),
            status="completed",
        )
        db_session.add(session_b)
        await db_session.commit()

        # Currently logged in as User B:

        # 1. User B tries to submit feedback for User A's session -> 404
        res_cross_session = await client.post(
            f"/api/sessions/{session_a.id}/feedback",
            json={"feedback_type": "correct_detection", "detection_event_id": str(event_a.id)},
        )
        assert res_cross_session.status_code == 404
        assert "Study session not found" in res_cross_session.json()["detail"]

        # 2. User B tries to get User A's session feedback -> 404
        res_cross_get = await client.get(f"/api/sessions/{session_a.id}/feedback")
        assert res_cross_get.status_code == 404

        # 3. User B tries to submit feedback to Session B referencing User A's event -> 400
        res_cross_event = await client.post(
            f"/api/sessions/{session_b.id}/feedback",
            json={"feedback_type": "correct_detection", "detection_event_id": str(event_a.id)},
        )
        assert res_cross_event.status_code == 404
        assert "not found in this study session" in res_cross_event.json()["detail"]

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_feedback_validation_bounds_and_malformed_ids(db_session):
    """Verify note length bounding and malformed ID validation."""
    app.dependency_overrides[get_async_session] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_res = await client.post(
            "/api/auth/dev-login",
            json={"email": "bounds_user@example.com", "display_name": "Bounds User"},
        )
        user_id = uuid.UUID(login_res.json()["user"]["id"])

        session = StudySession(
            id=uuid.uuid4(),
            user_id=user_id,
            started_at=datetime.now(timezone.utc),
            status="completed",
        )
        db_session.add(session)
        await db_session.commit()

        # 1. Note exceeding 1000 characters
        long_note = "A" * 1001
        res_long = await client.post(
            f"/api/sessions/{session.id}/feedback",
            json={"feedback_type": "other", "note": long_note},
        )
        assert res_long.status_code == 422

        # 2. Malformed session UUID
        res_malformed_session = await client.post(
            "/api/sessions/not-a-valid-uuid/feedback",
            json={"feedback_type": "other", "note": "Hello"},
        )
        assert res_malformed_session.status_code == 422

        # 3. Malformed event UUID
        res_malformed_event = await client.post(
            f"/api/sessions/{session.id}/feedback",
            json={"feedback_type": "correct_detection", "detection_event_id": "not-an-event-uuid"},
        )
        assert res_malformed_event.status_code == 422

        # 4. Unknown feedback type
        res_unknown_type = await client.post(
            f"/api/sessions/{session.id}/feedback",
            json={"feedback_type": "definitely_wrong_label"},
        )
        assert res_unknown_type.status_code == 422

    app.dependency_overrides.clear()
