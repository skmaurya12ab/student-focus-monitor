"""Authentication API endpoints."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token
from app.db.models.user import User
from app.db.session import get_async_session
from app.schemas.auth import (
    DevLoginRequest,
    GoogleAuthPayload,
    GoogleAuthUrlResponse,
    SessionAuthResponse,
)
from app.schemas.user import UserResponse
from app.services.auth_service import (
    AuthService,
    get_current_user,
    get_optional_current_user,
)
from app.services.google_auth import GoogleAuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _set_session_cookie(response: Response, access_token: str) -> None:
    """Set secure HttpOnly application session cookie."""
    max_age_seconds = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    response.set_cookie(
        key="sfm_session",
        value=access_token,
        max_age=max_age_seconds,
        httponly=True,
        secure=(settings.APP_ENV == "production"),
        samesite="lax",
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    """Clear application session cookie on logout."""
    response.delete_cookie(
        key="sfm_session",
        path="/",
        httponly=True,
        secure=(settings.APP_ENV == "production"),
        samesite="lax",
    )


@router.get(
    "/google/url",
    response_model=GoogleAuthUrlResponse,
    summary="Get Google OAuth 2.0 authorization URL",
)
def get_google_auth_url() -> GoogleAuthUrlResponse:
    """Generate and return Google OAuth authorization URL with CSRF state token."""
    auth_data = GoogleAuthService.get_authorization_url()
    return GoogleAuthUrlResponse(url=auth_data["url"], state=auth_data["state"])


@router.post(
    "/google",
    response_model=SessionAuthResponse,
    summary="Authenticate with Google OAuth / ID Token",
)
async def authenticate_google(
    payload: GoogleAuthPayload,
    response: Response,
    db: AsyncSession = Depends(get_async_session),
) -> SessionAuthResponse:
    """Verify Google credentials, authenticate authoritative identity, and set HttpOnly session cookie."""
    id_token = payload.id_token

    # If an authorization code was sent from the redirect flow, exchange it
    if not id_token and payload.code:
        token_data = await GoogleAuthService.exchange_code_for_tokens(payload.code)
        id_token = token_data.get("id_token")

    if not id_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either id_token or code must be provided.",
        )

    # Verify ID token with Google identity service
    google_claims = await GoogleAuthService.verify_id_token(id_token)

    # Authenticate or provision user with authoritative (provider, sub)
    user, identity, is_new = await AuthService.authenticate_or_create_google_user(
        db, google_claims
    )

    # Issue application session token and set secure HttpOnly cookie
    access_token = create_access_token(user.id)
    _set_session_cookie(response, access_token)

    return SessionAuthResponse(
        status="success",
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/dev-login",
    response_model=SessionAuthResponse,
    summary="Simulated login for development and automated testing",
)
async def dev_login(
    response: Response,
    payload: DevLoginRequest = DevLoginRequest(),
    db: AsyncSession = Depends(get_async_session),
) -> SessionAuthResponse:
    """Authenticate or provision a mock Google user and set HttpOnly session cookie."""
    mock_claims = {
        "sub": payload.google_sub,
        "email": payload.email,
        "name": payload.display_name,
        "email_verified": True,
    }

    user, identity, is_new = await AuthService.authenticate_or_create_google_user(
        db, mock_claims
    )

    access_token = create_access_token(user.id)
    _set_session_cookie(response, access_token)

    return SessionAuthResponse(
        status="success",
        user=UserResponse.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current authenticated user profile",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Return the profile for the currently authenticated session."""
    return UserResponse.model_validate(current_user)


@router.post(
    "/logout",
    summary="Terminate application session",
)
async def logout(
    response: Response,
    current_user: Optional[User] = Depends(get_optional_current_user),
) -> dict:
    """Invalidate application session and clear HttpOnly session cookie."""
    _clear_session_cookie(response)
    return {
        "status": "success",
        "message": "Successfully logged out.",
        "user_id": str(current_user.id) if current_user else None,
    }

