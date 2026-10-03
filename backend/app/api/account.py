"""Account and Profile API endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.db.session import get_async_session
from app.schemas.user import AccountDetailResponse, UpdateProfileRequest, UserResponse
from app.services.auth_service import AuthService, get_current_user

router = APIRouter(prefix="/account", tags=["Account"])


@router.get(
    "",
    response_model=AccountDetailResponse,
    summary="Get full account identity and authentication links",
)
async def get_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> AccountDetailResponse:
    """Retrieve account details including linked Google identity and session history count."""
    details = await AuthService.get_account_details(db, current_user.id)
    return AccountDetailResponse(
        user=UserResponse.model_validate(details["user"]),
        identities=details["identities"],
        active_sessions_count=details["active_sessions_count"],
    )


@router.patch(
    "",
    response_model=UserResponse,
    summary="Update editable profile fields",
)
async def update_profile(
    payload: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> UserResponse:
    """Update profile fields (such as display name) for the authenticated user."""
    updated_user = await AuthService.update_profile(
        db, current_user, payload.display_name
    )
    return UserResponse.model_validate(updated_user)
