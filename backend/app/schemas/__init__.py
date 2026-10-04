"""Pydantic schemas package for request/response serialization."""
from app.schemas.auth import (
    DevLoginRequest,
    GoogleAuthPayload,
    GoogleAuthUrlResponse,
    SessionAuthResponse,
    TokenResponse,
)
from app.schemas.session import (
    ActiveSessionResponse,
    StudySessionCreateRequest,
    StudySessionResponse,
    StudySessionStopResponse,
)
from app.schemas.settings import (
    UserSettingsResponse,
    UserSettingsUpdateRequest,
)
from app.schemas.user import (
    AccountDetailResponse,
    UpdateProfileRequest,
    UserResponse,
)

__all__ = [
    "DevLoginRequest",
    "GoogleAuthPayload",
    "GoogleAuthUrlResponse",
    "SessionAuthResponse",
    "TokenResponse",
    "UserResponse",
    "AccountDetailResponse",
    "UpdateProfileRequest",
    "StudySessionCreateRequest",
    "StudySessionResponse",
    "ActiveSessionResponse",
    "StudySessionStopResponse",
    "UserSettingsResponse",
    "UserSettingsUpdateRequest",
]
