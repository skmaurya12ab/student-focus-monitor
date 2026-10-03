"""Structured domain detection events for distraction alerts."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from typing import Any, Optional

from app.detection.config import (
    DETECTOR_VERSION,
    FEATURE_SCHEMA_VERSION,
    DetectorConfig,
)
from app.detection.features import FeatureSnapshot, utc_iso


@dataclass
class DetectionEvent:
    """Represents a discrete detection lifecycle event (started or ended)."""

    event_id: str
    session_id: str
    event_type: str
    event_action: str  # "started" | "ended"
    timestamp: float
    timestamp_iso: str
    trigger_delay_sec: float
    detector_version: str = DETECTOR_VERSION
    feature_schema_version: str = FEATURE_SCHEMA_VERSION
    duration_sec: Optional[float] = None
    thresholds: Optional[dict[str, float]] = None
    feature_snapshot: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert event object to dictionary for logging or serialization."""
        data = asdict(self)
        if self.duration_sec is None:
            data.pop("duration_sec", None)
        if self.thresholds is None:
            data.pop("thresholds", None)
        if self.feature_snapshot is None:
            data.pop("feature_snapshot", None)
        return data


def create_alert_started_event(
    session_id: str,
    event_type: str,
    now: float,
    config: DetectorConfig,
    features: FeatureSnapshot,
) -> DetectionEvent:
    """Create a structured event when a distraction alert condition activates."""
    thresholds = {
        "yaw_threshold_deg": config.yaw_threshold_deg,
        "ear_threshold": config.ear_threshold,
        "mar_threshold": config.mar_threshold,
        "hand_near_cheek_dist": config.hand_near_cheek_dist,
        "lean_back_z_delta": config.lean_back_z_delta,
    }
    feature_summary = {
        "head_yaw_from_baseline": features.head_yaw_from_baseline,
        "ear": features.ear,
        "mar": features.mar,
        "hand_cheek_distance": features.hand_cheek_distance,
        "shoulder_z_delta": features.shoulder_z_delta,
    }
    return DetectionEvent(
        event_id=uuid.uuid4().hex,
        session_id=session_id,
        event_type=event_type,
        event_action="started",
        timestamp=now,
        timestamp_iso=utc_iso(now),
        trigger_delay_sec=config.get_alert_delay(event_type),
        detector_version=DETECTOR_VERSION,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        thresholds=thresholds,
        feature_snapshot=feature_summary,
    )


def create_alert_ended_event(
    session_id: str,
    event_type: str,
    now: float,
    duration_sec: Optional[float],
    config: DetectorConfig,
) -> DetectionEvent:
    """Create a structured event when an active distraction alert clears."""
    return DetectionEvent(
        event_id=uuid.uuid4().hex,
        session_id=session_id,
        event_type=event_type,
        event_action="ended",
        timestamp=now,
        timestamp_iso=utc_iso(now),
        duration_sec=duration_sec,
        trigger_delay_sec=config.get_alert_delay(event_type),
        detector_version=DETECTOR_VERSION,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
    )
