"""Authentication API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token
from app.db.models.user import User
from app.db.session import get_async_session
from app.schemas.auth import (
    DevLoginRequest,
    GoogleAuthPayload,
    GoogleAuthUrlResponse,
    TokenResponse,
)
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService, get_current_user
from app.services.google_auth import GoogleAuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


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
    response_model=TokenResponse,
    summary="Authenticate with Google OAuth / ID Token",
)
async def authenticate_google(
    payload: GoogleAuthPayload,
    db: AsyncSession = Depends(get_async_session),
) -> TokenResponse:
    """Verify Google credentials (ID token or auth code), upsert user, and issue application session token."""
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

    # Upsert user and auth identity
    user, identity, is_new = await AuthService.authenticate_or_create_google_user(
        db, google_claims
    )

    # Issue application JWT
    access_token = create_access_token(user.id)
    expires_in_seconds = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in_seconds,
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/dev-login",
    response_model=TokenResponse,
    summary="Simulated login for development and automated testing",
)
async def dev_login(
    payload: DevLoginRequest = DevLoginRequest(),
    db: AsyncSession = Depends(get_async_session),
) -> TokenResponse:
    """Authenticate or provision a mock Google user without requiring live external OAuth networks."""
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
    expires_in_seconds = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in_seconds,
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
    current_user: User = Depends(get_current_user),
) -> dict:
    """Invalidate local session for the authenticated user."""
    return {
        "status": "success",
        "message": "Successfully logged out.",
        "user_id": str(current_user.id),
    }
