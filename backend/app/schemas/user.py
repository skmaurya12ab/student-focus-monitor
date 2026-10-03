"""User and Account Pydantic schemas."""
from datetime import datetime
from typing import List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class UserBase(BaseModel):
    """Base user fields."""

    display_name: str = Field(..., min_length=1, max_length=100)
    email: Optional[str] = None


class UserResponse(BaseModel):
    """Public user response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str
    email: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AuthIdentityResponse(BaseModel):
    """Authentication identity link response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    provider_email: Optional[str] = None
    created_at: datetime
    last_login_at: Optional[datetime] = None


class AccountDetailResponse(BaseModel):
    """Detailed account information for the dedicated Account page."""

    user: UserResponse
    identities: List[AuthIdentityResponse] = Field(default_factory=list)
    active_sessions_count: int = 0


class UpdateProfileRequest(BaseModel):
    """Request payload to update editable profile fields."""

    display_name: str = Field(..., min_length=1, max_length=100, description="Display name for student profile")
