"""Session Feedback Service for managing user labels on detection events and missed detections."""
from typing import List, Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.detection_event import DetectionEvent
from app.db.models.session_feedback import SessionFeedback
from app.db.models.study_session import StudySession
from app.schemas.feedback import SessionFeedbackCreateRequest
from app.services.session_service import SessionService

# Canonical category mapping
CANONICAL_CATEGORIES = {
    "looking_away": "looking_away",
    "phone_use": "phone_use",
    "yawning": "yawning",
    "drowsy": "drowsy",
    "leaning_back": "leaning_back",
    "away_from_desk": "away_from_desk",
    # User-friendly label aliases
    "looking away": "looking_away",
    "phone use": "phone_use",
    "drowsiness": "drowsy",
    "bad posture": "leaning_back",
    "away from seat": "away_from_desk",
    "away from desk": "away_from_desk",
}


def normalize_category(raw_category: Optional[str]) -> Optional[str]:
    """Normalize and canonicalize a distraction category string."""
    if not raw_category:
        return None
    key = raw_category.strip().lower()
    return CANONICAL_CATEGORIES.get(key)


class FeedbackService:
    """Service layer managing student feedback on distraction events and session accuracy."""

    @classmethod
    async def submit_feedback(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        payload: SessionFeedbackCreateRequest,
    ) -> SessionFeedback:
        """Submit feedback for a detection event or session.

        Enforces:
        - Authenticated user owns the session (prevents IDOR).
        - If referencing an event, event belongs to the same session.
        - Canonical feedback types and distraction categories.
        - Idempotent upsert for event feedback to prevent duplicate submissions.
        - Controlled deduplication for missed detections by category.
        """
        # 1. Enforce session ownership
        study_session = await SessionService.get_session_by_id(db, session_id, user_id)
        if not study_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Study session not found or does not belong to the authenticated user.",
            )

        # 2. Event-specific feedback (correct_detection, false_positive, or event other)
        if payload.detection_event_id is not None:
            if payload.feedback_type == "missed_detection":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missed detection feedback represents an unrecorded distraction and must not reference an existing detection event.",
                )

            # Validate detection event belongs to this session
            event_stmt = select(DetectionEvent).where(
                DetectionEvent.id == payload.detection_event_id,
                DetectionEvent.session_id == session_id,
            )
            event_res = await db.execute(event_stmt)
            event = event_res.scalars().first()
            if not event:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Detection event not found in this study session.",
                )

            category = normalize_category(payload.category) or event.event_type

            # Idempotent upsert: check if feedback already exists for this (session_id, detection_event_id)
            existing_stmt = select(SessionFeedback).where(
                SessionFeedback.session_id == session_id,
                SessionFeedback.detection_event_id == payload.detection_event_id,
            )
            existing_res = await db.execute(existing_stmt)
            existing_fb = existing_res.scalars().first()

            if existing_fb:
                existing_fb.feedback_type = payload.feedback_type
                existing_fb.category = category
                existing_fb.note = payload.note
                await db.commit()
                await db.refresh(existing_fb)
                return existing_fb
            else:
                feedback = SessionFeedback(
                    session_id=session_id,
                    detection_event_id=payload.detection_event_id,
                    feedback_type=payload.feedback_type,
                    category=category,
                    note=payload.note,
                )
                db.add(feedback)
                await db.commit()
                await db.refresh(feedback)
                return feedback

        # 3. Session-level feedback (missed_detection or other)
        else:
            if payload.feedback_type == "missed_detection":
                norm_cat = normalize_category(payload.category)
                if not norm_cat:
                    valid_cats = sorted(list(set(CANONICAL_CATEGORIES.values())))
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Missed detection feedback requires a valid category. Valid options: {valid_cats}",
                    )

                # Deduplication for missed detections by category within the same session
                existing_stmt = select(SessionFeedback).where(
                    SessionFeedback.session_id == session_id,
                    SessionFeedback.feedback_type == "missed_detection",
                    SessionFeedback.category == norm_cat,
                )
                existing_res = await db.execute(existing_stmt)
                existing_fb = existing_res.scalars().first()

                if existing_fb:
                    existing_fb.note = payload.note
                    await db.commit()
                    await db.refresh(existing_fb)
                    return existing_fb
                else:
                    feedback = SessionFeedback(
                        session_id=session_id,
                        detection_event_id=None,
                        feedback_type="missed_detection",
                        category=norm_cat,
                        note=payload.note,
                    )
                    db.add(feedback)
                    await db.commit()
                    await db.refresh(feedback)
                    return feedback

            elif payload.feedback_type == "other":
                feedback = SessionFeedback(
                    session_id=session_id,
                    detection_event_id=None,
                    feedback_type="other",
                    category=normalize_category(payload.category),
                    note=payload.note,
                )
                db.add(feedback)
                await db.commit()
                await db.refresh(feedback)
                return feedback

            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Feedback type '{payload.feedback_type}' requires a detection_event_id.",
                )

    @classmethod
    async def get_session_feedbacks(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> List[SessionFeedback]:
        """Retrieve all feedback entries for a session owned by the authenticated user."""
        study_session = await SessionService.get_session_by_id(db, session_id, user_id)
        if not study_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Study session not found or does not belong to the authenticated user.",
            )

        stmt = (
            select(SessionFeedback)
            .where(SessionFeedback.session_id == session_id)
            .order_by(SessionFeedback.created_at.asc())
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())
