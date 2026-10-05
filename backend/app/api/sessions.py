"""Study Session Lifecycle API endpoints."""
from typing import Optional
import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.db.session import get_async_session
from app.schemas.session import (
    ActiveSessionResponse,
    SessionHistoryResponse,
    StudySessionCreateRequest,
    StudySessionDetailResponse,
    StudySessionResponse,
    StudySessionStopResponse,
)
from app.services.auth_service import get_current_user
from app.services.session_service import SessionService

router = APIRouter(prefix="/sessions", tags=["Study Sessions"])


@router.post(
    "",
    response_model=StudySessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new authoritative study session",
)
async def create_study_session(
    payload: Optional[StudySessionCreateRequest] = Body(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> StudySessionResponse:
    """Create a new study session in 'active' status for the authenticated user.
    
    Enforces at most one active study session per user.
    Server sets UUID and started_at timestamp.
    """
    notes = payload.notes if payload else None
    device_hint = payload.device_hint if payload else None
    session = await SessionService.create_session(
        db,
        current_user,
        notes=notes,
        device_hint=device_hint,
    )
    return StudySessionResponse.model_validate(session)


@router.get(
    "/active",
    response_model=ActiveSessionResponse,
    summary="Retrieve current user's active study session",
)
async def get_active_study_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> ActiveSessionResponse:
    """Get the currently active study session for the authenticated user, or null if none is active."""
    session = await SessionService.get_active_session(db, current_user.id)
    if not session:
        return ActiveSessionResponse(session=None)
    distraction_count = await SessionService.get_distraction_count(db, session.id)
    resp = StudySessionResponse.model_validate(session)
    resp.distraction_count = distraction_count
    return ActiveSessionResponse(session=resp)


@router.get(
    "/latest",
    response_model=ActiveSessionResponse,
    summary="Retrieve current user's most recent study session",
)
async def get_latest_study_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> ActiveSessionResponse:
    """Get the most recent study session for the authenticated user, whether active or completed."""
    session = await SessionService.get_latest_session(db, current_user.id)
    if not session:
        return ActiveSessionResponse(session=None)
    distraction_count = await SessionService.get_distraction_count(db, session.id)
    resp = StudySessionResponse.model_validate(session)
    resp.distraction_count = distraction_count
    return ActiveSessionResponse(session=resp)


@router.get(
    "/history",
    response_model=SessionHistoryResponse,
    summary="Retrieve paginated study sessions history for authenticated user",
)
async def get_session_history(
    page: int = Query(1, ge=1, description="1-indexed page number"),
    page_size: int = Query(10, ge=1, description="Items per page (max 50)"),
    status: Optional[str] = Query(None, description="Optional status filter ('active', 'completed')"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> SessionHistoryResponse:
    """Retrieve paginated historical study sessions for the authenticated user, newest first."""
    clamped_page_size = min(page_size, 50)
    items, total = await SessionService.get_session_history(
        db,
        current_user.id,
        page=page,
        page_size=clamped_page_size,
        status=status,
    )
    total_pages = max(1, (total + clamped_page_size - 1) // clamped_page_size) if total > 0 else 1
    return SessionHistoryResponse(
        items=items,
        total=total,
        page=page,
        page_size=clamped_page_size,
        total_pages=total_pages,
    )


@router.get(
    "/{session_id}",
    response_model=StudySessionDetailResponse,
    summary="Retrieve study session details by ID",
)
async def get_study_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> StudySessionDetailResponse:
    """Retrieve study session details by UUID, strictly enforcing ownership (preventing IDOR)."""
    detail = await SessionService.get_session_detail(db, session_id, current_user.id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Study session not found.",
        )
    return detail


@router.post(
    "/{session_id}/stop",
    response_model=StudySessionStopResponse,
    summary="Stop and complete an active study session",
)
async def stop_study_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> StudySessionStopResponse:
    """Stop an active study session, computing authoritative duration server-side and marking status completed."""
    session = await SessionService.stop_session(db, session_id, current_user.id)
    distraction_count = await SessionService.get_distraction_count(db, session.id)
    resp = StudySessionResponse.model_validate(session)
    resp.distraction_count = distraction_count
    return StudySessionStopResponse(
        status="success",
        session=resp,
    )


from app.schemas.feedback import SessionFeedbackCreateRequest, SessionFeedbackResponse
from app.schemas.telemetry import TelemetrySampleResponse
from app.services.feedback_service import FeedbackService
from app.db.models.telemetry_sample import TelemetrySample
from sqlalchemy import select


@router.post(
    "/{session_id}/feedback",
    response_model=SessionFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit student feedback on a detection event or session accuracy",
)
async def submit_session_feedback(
    session_id: uuid.UUID,
    payload: SessionFeedbackCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> SessionFeedbackResponse:
    """Submit human feedback (correct_detection, false_positive, missed_detection, other) for a session.
    
    Enforces user ownership, prevents duplicate submissions via idempotent upsert,
    and structures canonical distraction categories for future ML evaluation.
    """
    feedback = await FeedbackService.submit_feedback(
        db,
        user_id=current_user.id,
        session_id=session_id,
        payload=payload,
    )
    return SessionFeedbackResponse.model_validate(feedback)


@router.get(
    "/{session_id}/feedback",
    response_model=list[SessionFeedbackResponse],
    summary="Retrieve all feedback submissions for a study session",
)
async def get_session_feedbacks(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> list[SessionFeedbackResponse]:
    """Retrieve all human feedback entries submitted for the specified study session."""
    feedbacks = await FeedbackService.get_session_feedbacks(
        db,
        user_id=current_user.id,
        session_id=session_id,
    )
    return [SessionFeedbackResponse.model_validate(fb) for fb in feedbacks]


@router.get(
    "/{session_id}/telemetry",
    response_model=list[TelemetrySampleResponse],
    summary="Retrieve persisted numerical telemetry samples for diagnostic inspection",
)
async def get_session_telemetry(
    session_id: uuid.UUID,
    limit: int = Query(100, ge=1, le=1000, description="Max samples to return"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> list[TelemetrySampleResponse]:
    """Retrieve persisted numerical telemetry samples for a session owned by the authenticated user."""
    session = await SessionService.get_session_by_id(db, session_id, current_user.id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Study session not found or forbidden.",
        )
    stmt = (
        select(TelemetrySample)
        .where(TelemetrySample.session_id == session_id)
        .order_by(TelemetrySample.sampled_at.asc())
        .limit(limit)
    )
    res = await db.execute(stmt)
    samples = res.scalars().all()
    return [TelemetrySampleResponse.model_validate(s) for s in samples]
