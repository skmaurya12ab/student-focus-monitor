"""Study Session Lifecycle API endpoints."""
from typing import Optional
import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.db.session import get_async_session
from app.schemas.session import (
    ActiveSessionResponse,
    StudySessionCreateRequest,
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
    return ActiveSessionResponse(
        session=StudySessionResponse.model_validate(session) if session else None
    )


@router.get(
    "/{session_id}",
    response_model=StudySessionResponse,
    summary="Retrieve study session details by ID",
)
async def get_study_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> StudySessionResponse:
    """Retrieve study session details by UUID, strictly enforcing ownership (preventing IDOR)."""
    session = await SessionService.get_session_by_id(db, session_id, current_user.id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Study session not found.",
        )
    return StudySessionResponse.model_validate(session)


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
    return StudySessionStopResponse(
        status="success",
        session=StudySessionResponse.model_validate(session),
    )
