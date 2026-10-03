"""Authentication and User Account management service."""
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import decode_access_token
from app.db.base import utc_now
from app.db.models.auth_identity import AuthIdentity
from app.db.models.study_session import StudySession
from app.db.models.user import User
from app.db.models.user_settings import UserSettings
from app.db.session import get_async_session

security_bearer = HTTPBearer(auto_error=False)


class AuthService:
    """Service handling user authentication, OAuth identity linking, and profile management."""

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
        """Fetch user by primary key with auth identities preloaded."""
        stmt = (
            select(User)
            .options(selectinload(User.auth_identities), selectinload(User.settings))
            .where(User.id == user_id)
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
        """Fetch user by unique email address."""
        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        return result.scalars().first()

    @classmethod
    async def authenticate_or_create_google_user(
        cls,
        db: AsyncSession,
        google_claims: Dict[str, Any],
    ) -> Tuple[User, AuthIdentity, bool]:
        """Authenticate an existing Google user or provision a new user account with default settings."""
        sub = google_claims["sub"]
        email = google_claims.get("email")
        name = google_claims.get("name") or (email.split("@")[0] if email else "Student")

        # 1. Check for existing AuthIdentity with provider="google" and provider_subject=sub
        stmt = (
            select(AuthIdentity)
            .options(selectinload(AuthIdentity.user).selectinload(User.settings))
            .where(
                AuthIdentity.provider == "google",
                AuthIdentity.provider_subject == sub,
            )
        )
        result = await db.execute(stmt)
        identity = result.scalars().first()

        now = utc_now()

        if identity:
            user = identity.user
            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is deactivated.",
                )
            identity.last_login_at = now
            if email and identity.provider_email != email:
                identity.provider_email = email
            await db.flush()
            return user, identity, False

        # 2. Check if user with same email exists
        user = None
        if email:
            user = await cls.get_user_by_email(db, email)

        is_new = False
        if not user:
            # 3. Create brand new User
            user = User(
                display_name=name,
                email=email,
                is_active=True,
            )
            db.add(user)
            await db.flush()  # Generate user.id
            is_new = True

            # 4. Create default UserSettings for new user
            settings = UserSettings(user_id=user.id)
            db.add(settings)
            await db.flush()

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated.",
            )

        # 5. Link Google AuthIdentity
        identity = AuthIdentity(
            user_id=user.id,
            provider="google",
            provider_subject=sub,
            provider_email=email,
            last_login_at=now,
        )
        db.add(identity)
        await db.flush()

        return user, identity, is_new

    @classmethod
    async def get_account_details(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """Retrieve full account identity, active provider links, and session statistics."""
        user = await cls.get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User account not found.",
            )

        # Count active study sessions
        stmt = (
            select(func.count(StudySession.id))
            .where(StudySession.user_id == user_id, StudySession.status == "active")
        )
        res = await db.execute(stmt)
        active_count = res.scalar() or 0

        return {
            "user": user,
            "identities": user.auth_identities,
            "active_sessions_count": active_count,
        }

    @classmethod
    async def update_profile(
        cls,
        db: AsyncSession,
        user: User,
        display_name: str,
    ) -> User:
        """Update editable profile fields with validation."""
        cleaned_name = display_name.strip()
        if not cleaned_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Display name cannot be empty or whitespace.",
            )
        if len(cleaned_name) > 100:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Display name must be at most 100 characters.",
            )

        user.display_name = cleaned_name
        user.updated_at = utc_now()
        await db.flush()
        return user


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: AsyncSession = Depends(get_async_session),
) -> User:
    """FastAPI dependency: Extract and validate Bearer JWT, returning authenticated active User."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_uuid = uuid.UUID(payload["sub"])
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token subject identifier.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await AuthService.get_user_by_id(db, user_uuid)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )

    return user
