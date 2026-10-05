"""Pydantic schemas for Study Session Lifecycle."""
from datetime import datetime
from decimal import Decimal
from typing import Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class StudySessionCreateRequest(BaseModel):
    """Optional request payload for initiating a study session."""
    notes: Optional[str] = Field(None, max_length=500, description="Optional student study goals or notes.")
    device_hint: Optional[str] = Field(None, max_length=100, description="Optional camera device hint.")


class StudySessionResponse(BaseModel):
    """Authoritative study session representation."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    status: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    total_duration_seconds: float = 0.0
    focused_seconds: float = 0.0
    distracted_seconds: float = 0.0
    away_seconds: float = 0.0
    focus_score: Optional[Decimal] = None
    distraction_count: int = 0
    detector_version: str = "v4"
    feature_schema_version: str = "telemetry_v2"
    created_at: datetime
    updated_at: datetime


class ActiveSessionResponse(BaseModel):
    """Response containing the currently active session or null."""
    session: Optional[StudySessionResponse] = None


class StudySessionStopResponse(BaseModel):
    """Response returned upon stopping a study session."""
    status: str = "success"
    session: StudySessionResponse


from app.schemas.feedback import SessionFeedbackResponse


class DetectionEventResponse(BaseModel):
    """Discrete detection event representation for historical session detail."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    event_type: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    detector_version: str = "v4"
    metadata_json: Optional[dict] = None
    created_at: datetime
    feedback: Optional[SessionFeedbackResponse] = None


class SessionCategorySummary(BaseModel):
    """Summary of events within a single category for a session."""
    category: str
    label: str
    count: int = 0
    duration_seconds: float = 0.0


class StudySessionDetailResponse(StudySessionResponse):
    """Enriched session details with discrete events, user feedback, and top causes."""
    events: list[DetectionEventResponse] = []
    feedbacks: list[SessionFeedbackResponse] = []
    top_causes: str = ""
    category_breakdown: list[SessionCategorySummary] = []


class SessionHistoryResponse(BaseModel):
    """Paginated list of study sessions."""
    items: list[StudySessionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

