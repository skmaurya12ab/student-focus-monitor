"""Pydantic schemas for user settings and alert delay preferences."""
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class UserSettingsResponse(BaseModel):
    """Authoritative user configuration and alert persistence delays."""
    model_config = ConfigDict(from_attributes=True)

    looking_away_delay_seconds: float = Field(..., ge=0, description="Looking away persistence delay (seconds)")
    phone_use_delay_seconds: float = Field(..., ge=0, description="Phone use persistence delay (seconds)")
    yawning_delay_seconds: float = Field(..., ge=0, description="Yawning persistence delay (seconds)")
    drowsy_delay_seconds: float = Field(..., ge=0, description="Sleeping posture / drowsiness persistence delay (seconds)")
    leaning_back_delay_seconds: float = Field(..., ge=0, description="Bad posture / leaning back persistence delay (seconds)")
    away_from_desk_delay_seconds: float = Field(..., ge=0, description="Away from seat persistence delay (seconds)")
    sound_alerts_enabled: bool = Field(..., description="Whether audible beep alerts are enabled")
    banner_alerts_enabled: bool = Field(..., description="Whether on-screen banner alerts are enabled")
    session_end_summary_enabled: bool = Field(..., description="Whether session end summary notification is enabled")
    camera_device: str = Field(..., description="Selected camera device identifier")
    preview_quality: str = Field(..., description="Camera preview quality setting")


class UserSettingsUpdateRequest(BaseModel):
    """Payload for updating user settings and persistence delays."""
    looking_away_delay_seconds: Optional[float] = Field(None, ge=0.5, le=120.0)
    phone_use_delay_seconds: Optional[float] = Field(None, ge=0.5, le=120.0)
    yawning_delay_seconds: Optional[float] = Field(None, ge=0.5, le=120.0)
    drowsy_delay_seconds: Optional[float] = Field(None, ge=0.5, le=120.0)
    leaning_back_delay_seconds: Optional[float] = Field(None, ge=0.5, le=120.0)
    away_from_desk_delay_seconds: Optional[float] = Field(None, ge=0.5, le=120.0)
    sound_alerts_enabled: Optional[bool] = None
    banner_alerts_enabled: Optional[bool] = None
    session_end_summary_enabled: Optional[bool] = None
    camera_device: Optional[str] = Field(None, max_length=100)
    preview_quality: Optional[str] = Field(None, max_length=50)
