"""Pydantic schemas for Telemetry Samples inspection."""
from datetime import datetime
from typing import Any, Optional
import uuid
from pydantic import BaseModel, ConfigDict


class TelemetrySampleResponse(BaseModel):
    """Structured representation of a numerical telemetry sample."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    sampled_at: datetime
    frame_index: Optional[int] = None
    detector_version: str = "v4"
    feature_schema_version: str = "telemetry_v2"

    head_pitch: Optional[float] = None
    head_yaw: Optional[float] = None
    head_roll: Optional[float] = None
    ear: Optional[float] = None
    mar: Optional[float] = None
    min_hand_cheek_distance: Optional[float] = None
    shoulder_z: Optional[float] = None
    face_present: Optional[bool] = None
    pose_present: Optional[bool] = None
    hand_count: Optional[int] = None
    focus_state: Optional[str] = None

    features: dict[str, Any] = {}
