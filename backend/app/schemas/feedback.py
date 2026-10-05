"""Pydantic schemas for Session Feedback."""
from datetime import datetime
from typing import Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field, field_validator

CANONICAL_FEEDBACK_TYPES = {
    "correct_detection",
    "false_positive",
    "missed_detection",
    "other",
}


class SessionFeedbackCreateRequest(BaseModel):
    """Payload for submitting feedback on a detection event or session."""
    detection_event_id: Optional[uuid.UUID] = Field(
        None,
        description="ID of the specific detection event (null for missed_detection or general session feedback)",
    )
    feedback_type: str = Field(
        ...,
        description="Canonical feedback classification: correct_detection, false_positive, missed_detection, or other",
    )
    category: Optional[str] = Field(
        None,
        max_length=50,
        description="Distraction category (required for missed_detection)",
    )
    note: Optional[str] = Field(
        None,
        max_length=1000,
        description="Optional voluntary student explanation or observation (max 1000 chars)",
    )

    @field_validator("feedback_type")
    @classmethod
    def validate_feedback_type(cls, v: str) -> str:
        clean = v.strip().lower()
        if clean not in CANONICAL_FEEDBACK_TYPES:
            raise ValueError(
                f"Invalid feedback_type '{v}'. Must be one of: {sorted(CANONICAL_FEEDBACK_TYPES)}"
            )
        return clean


class SessionFeedbackResponse(BaseModel):
    """Authoritative representation of user feedback."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    detection_event_id: Optional[uuid.UUID] = None
    feedback_type: str
    category: Optional[str] = None
    note: Optional[str] = None
    created_at: datetime
