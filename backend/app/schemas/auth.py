"""Authentication Pydantic schemas."""
from typing import Optional
from pydantic import BaseModel, Field

from app.schemas.user import UserResponse


class GoogleAuthUrlResponse(BaseModel):
    """Google OAuth authorization URL response."""

    url: str
    state: str


class GoogleAuthPayload(BaseModel):
    """Google authentication payload containing either an ID token or auth code."""

    id_token: Optional[str] = Field(None, description="Google ID Token from Google Identity Services")
    code: Optional[str] = Field(None, description="Google Authorization Code from OAuth redirect flow")
    state: Optional[str] = Field(None, description="OAuth state parameter for CSRF mitigation")


class DevLoginRequest(BaseModel):
    """Development/Testing login request for local mock authentication."""

    email: str = Field(default="saurabh@example.com", description="Email for the simulated user")
    display_name: str = Field(default="Saurabh Kumar", description="Display name for the simulated user")
    google_sub: str = Field(default="google-dev-12345", description="Simulated Google provider subject ID")


class TokenResponse(BaseModel):
    """Authenticated session token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
