"""User Settings and alert thresholds API router."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.db.session import get_async_session
from app.schemas.settings import UserSettingsResponse, UserSettingsUpdateRequest
from app.services.auth_service import get_current_user
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get(
    "",
    response_model=UserSettingsResponse,
    summary="Get current user configuration and alert delays",
)
async def get_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> UserSettingsResponse:
    """Retrieve persisted configuration and alert persistence thresholds for authenticated user."""
    settings = await SettingsService.get_user_settings(db, current_user.id)
    return UserSettingsResponse.model_validate(settings)


@router.patch(
    "",
    response_model=UserSettingsResponse,
    summary="Update user configuration and alert delays",
)
async def update_settings(
    payload: UserSettingsUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> UserSettingsResponse:
    """Update alert persistence delays and notification toggles.
    
    Persists changes to PostgreSQL and immediately synchronizes active live detection runtimes.
    """
    settings = await SettingsService.update_user_settings(db, current_user.id, payload)
    await db.commit()
    return UserSettingsResponse.model_validate(settings)
