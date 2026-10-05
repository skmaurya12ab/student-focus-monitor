"""Study Session Lifecycle service managing session creation, retrieval, and completion."""
from datetime import datetime, timezone
from typing import Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.db.models.study_session import StudySession
from app.db.models.user import User
from app.schemas.session import (
    DetectionEventResponse,
    SessionCategorySummary,
    StudySessionDetailResponse,
    StudySessionResponse,
)


class SessionService:
    """Service handling authoritative study session lifecycle state transitions."""

    @staticmethod
    async def get_session_history(
        db: AsyncSession,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 10,
        status: Optional[str] = None,
    ) -> tuple[list[StudySessionResponse], int]:
        """Retrieve paginated study sessions for the authenticated user, newest first.
        
        Uses SQL aggregation to join distraction event counts in a single query (zero N+1).
        """
        from app.db.models.detection_event import DetectionEvent
        from sqlalchemy import func

        page = max(1, page)
        page_size = max(1, min(page_size, 50))

        # Base filter condition
        base_filter = [StudySession.user_id == user_id]
        if status:
            base_filter.append(StudySession.status == status)

        # 1. Total count query
        count_stmt = select(func.count(StudySession.id)).where(*base_filter)
        count_res = await db.execute(count_stmt)
        total_count = int(count_res.scalar() or 0)

        if total_count == 0:
            return [], 0

        # 2. Paginated items query with aggregated distraction counts
        distraction_subq = (
            select(
                DetectionEvent.session_id,
                func.count(DetectionEvent.id).label("distraction_count"),
            )
            .group_by(DetectionEvent.session_id)
            .subquery()
        )

        stmt = (
            select(
                StudySession,
                func.coalesce(distraction_subq.c.distraction_count, 0).label("distraction_count"),
            )
            .outerjoin(distraction_subq, StudySession.id == distraction_subq.c.session_id)
            .where(*base_filter)
            .order_by(StudySession.started_at.desc(), StudySession.id.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )

        res = await db.execute(stmt)
        items = []
        for session, dist_count in res.all():
            resp = StudySessionResponse.model_validate(session)
            resp.distraction_count = int(dist_count)
            items.append(resp)

        return items, total_count

    @staticmethod
    async def get_session_detail(
        db: AsyncSession,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Optional[StudySessionDetailResponse]:
        """Retrieve a specific study session by ID with its discrete detection events and top causes."""
        from app.db.models.detection_event import DetectionEvent

        session = await SessionService.get_session_by_id(db, session_id, user_id)
        if not session:
            return None

        # Fetch discrete detection events
        events_stmt = (
            select(DetectionEvent)
            .where(DetectionEvent.session_id == session_id)
            .order_by(DetectionEvent.started_at.asc(), DetectionEvent.id.asc())
        )
        events_res = await db.execute(events_stmt)
        db_events = events_res.scalars().all()

        # Fetch feedbacks for this session
        from app.db.models.session_feedback import SessionFeedback
        from app.schemas.feedback import SessionFeedbackResponse

        fb_stmt = (
            select(SessionFeedback)
            .where(SessionFeedback.session_id == session_id)
            .order_by(SessionFeedback.created_at.asc())
        )
        fb_res = await db.execute(fb_stmt)
        db_feedbacks = fb_res.scalars().all()
        feedback_responses = [SessionFeedbackResponse.model_validate(fb) for fb in db_feedbacks]

        # Map detection_event_id -> feedback
        event_feedback_map = {
            fb.detection_event_id: fb
            for fb in feedback_responses
            if fb.detection_event_id is not None
        }

        # Category breakdown & top causes
        CATEGORY_LABELS = {
            "looking_away": "Looking Away",
            "phone_use": "Phone Use",
            "yawning": "Yawning",
            "drowsy": "Drowsiness",
            "leaning_back": "Bad Posture",
            "away_from_desk": "Away From Seat",
        }

        cat_counts: dict[str, int] = {}
        cat_durations: dict[str, float] = {}

        event_responses = []
        for evt in db_events:
            evt_resp = DetectionEventResponse.model_validate(evt)
            evt_resp.feedback = event_feedback_map.get(evt.id)
            event_responses.append(evt_resp)
            c = evt.event_type
            cat_counts[c] = cat_counts.get(c, 0) + 1
            cat_durations[c] = cat_durations.get(c, 0.0) + (evt.duration_seconds or 0.0)

        # Build category breakdown
        breakdown = []
        for cat, count in sorted(cat_counts.items(), key=lambda x: x[1], reverse=True):
            breakdown.append(
                SessionCategorySummary(
                    category=cat,
                    label=CATEGORY_LABELS.get(cat, cat.replace("_", " ").title()),
                    count=count,
                    duration_seconds=round(cat_durations.get(cat, 0.0), 2),
                )
            )

        top_causes_list = [
            CATEGORY_LABELS.get(cat, cat.replace("_", " ").title())
            for cat, _ in sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        ]
        top_causes_str = " · ".join(top_causes_list) if top_causes_list else "None detected"

        base_resp = StudySessionResponse.model_validate(session)
        dump_data = base_resp.model_dump()
        dump_data["distraction_count"] = len(db_events)
        detail = StudySessionDetailResponse(
            **dump_data,
            events=event_responses,
            feedbacks=feedback_responses,
            top_causes=f"Top causes: {top_causes_str}" if top_causes_list else "No distractions",
            category_breakdown=breakdown,
        )

        return detail


    @staticmethod
    async def get_active_session(
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> Optional[StudySession]:
        """Retrieve the currently active study session for the given user, if any."""
        stmt = (
            select(StudySession)
            .where(
                StudySession.user_id == user_id,
                StudySession.status == "active",
            )
            .order_by(StudySession.started_at.desc())
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_session_by_id(
        db: AsyncSession,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Optional[StudySession]:
        """Retrieve a specific study session by ID, enforcing user ownership."""
        stmt = select(StudySession).where(
            StudySession.id == session_id,
            StudySession.user_id == user_id,
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_latest_session(
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> Optional[StudySession]:
        """Retrieve the most recent study session for the given user, whether active or completed."""
        stmt = (
            select(StudySession)
            .where(StudySession.user_id == user_id)
            .order_by(StudySession.started_at.desc())
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_distraction_count(
        db: AsyncSession,
        session_id: uuid.UUID,
    ) -> int:
        """Count discrete distraction detection events recorded for this session."""
        from app.db.models.detection_event import DetectionEvent
        from sqlalchemy import func
        stmt = select(func.count(DetectionEvent.id)).where(DetectionEvent.session_id == session_id)
        result = await db.execute(stmt)
        return int(result.scalar() or 0)

    @classmethod
    async def create_session(
        cls,
        db: AsyncSession,
        user: User,
        notes: Optional[str] = None,
        device_hint: Optional[str] = None,
    ) -> StudySession:
        """Create and start a new authoritative study session for an authenticated user.
        
        Enforces the invariant that a user can have at most one active study session at any time.
        Server generates UUID, started_at timestamp, and initial active status.
        """
        # 1. Application-level active session check
        existing_active = await cls.get_active_session(db, user.id)
        if existing_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User already has an active study session ({existing_active.id}). Complete it before starting a new one.",
            )

        now = utc_now()
        session = StudySession(
            user_id=user.id,
            started_at=now,
            ended_at=None,
            status="active",
            total_duration_seconds=0.0,
            focused_seconds=0.0,
            distracted_seconds=0.0,
            away_seconds=0.0,
            focus_score=None,
            detector_version="v4",
            feature_schema_version="telemetry_v2",
            calibration_snapshot={"device_hint": device_hint, "notes": notes} if (device_hint or notes) else None,
        )

        db.add(session)
        try:
            await db.commit()
            await db.refresh(session)
            return session
        except IntegrityError:
            await db.rollback()
            # Concurrent race condition caught by PostgreSQL partial unique index
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User already has an active study session. Duplicate active sessions are prohibited.",
            )

    @classmethod
    async def stop_session(
        cls,
        db: AsyncSession,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> StudySession:
        """Stop an active study session, transitioning it to completed with authoritative server duration.
        
        Enforces ownership and validates that the session is currently active.
        """
        # 1. Lookup session with ownership check (prevent IDOR)
        session = await cls.get_session_by_id(db, session_id, user_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Study session not found or does not belong to the authenticated user.",
            )

        # 2. Validate lifecycle state machine transition
        if session.status != "active":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot stop study session: current status is '{session.status}'. Only active sessions can be stopped.",
            )

        # 3. Set authoritative server ended timestamp
        ended = utc_now()
        session.ended_at = ended
        session.status = "completed"

        # 4. Authoritative duration derived from timestamps
        duration_seconds = (ended - session.started_at).total_seconds()
        if duration_seconds < 0.0:
            duration_seconds = 0.0
        session.total_duration_seconds = round(duration_seconds, 2)

        # Phase 8: Finalize detection runtime, open detection events, and session metrics
        from app.services.detection_runtime_service import detection_runtime_manager
        detection_summary = await detection_runtime_manager.stop_session_detection(session.id, db)
        if detection_summary:
            session.focused_seconds = round(float(detection_summary.get("focused_seconds", 0.0)), 2)
            session.distracted_seconds = round(float(detection_summary.get("distracted_seconds", 0.0)), 2)
            session.away_seconds = round(float(detection_summary.get("away_seconds", 0.0)), 2)
            focus_val = detection_summary.get("focus_score")
            if focus_val is not None:
                from decimal import Decimal
                session.focus_score = Decimal(str(round(float(focus_val), 2)))
            if detection_summary.get("calibration"):
                session.calibration_snapshot = detection_summary["calibration"]

        await db.commit()
        await db.refresh(session)

        # 5. Proactively close any active live transport connection for this session
        from app.services.live_transport_service import live_transport_manager
        await live_transport_manager.close_session_transport(
            session.id,
            code=1000,
            reason="Study session ended",
        )

        return session
