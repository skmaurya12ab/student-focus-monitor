"""Detection engine configuration and category constants."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

DETECTOR_VERSION: str = "v4"
FEATURE_SCHEMA_VERSION: str = "telemetry_v2"

# Canonical human-readable alert names (v4 compatible)
ALERT_LOOKING_AWAY: str = "Looking Away"
ALERT_PHONE_USE: str = "Phone Use"
ALERT_YAWNING: str = "Yawning"
ALERT_DROWSY: str = "Drowsy/Eyes Closed"
ALERT_LEANING_BACK: str = "Leaning Back"
ALERT_AWAY_FROM_DESK: str = "Away From Desk"

ALERT_NAMES: tuple[str, ...] = (
    ALERT_LOOKING_AWAY,
    ALERT_PHONE_USE,
    ALERT_YAWNING,
    ALERT_DROWSY,
    ALERT_LEANING_BACK,
    ALERT_AWAY_FROM_DESK,
)

# Machine-readable identifiers for API / schema stability
CATEGORY_LOOKING_AWAY: str = "looking_away"
CATEGORY_PHONE_USE: str = "phone_use"
CATEGORY_YAWNING: str = "yawning"
CATEGORY_DROWSY: str = "drowsy"
CATEGORY_LEANING_BACK: str = "leaning_back"
CATEGORY_AWAY_FROM_DESK: str = "away_from_desk"

CATEGORIES: tuple[str, ...] = (
    CATEGORY_LOOKING_AWAY,
    CATEGORY_PHONE_USE,
    CATEGORY_YAWNING,
    CATEGORY_DROWSY,
    CATEGORY_LEANING_BACK,
    CATEGORY_AWAY_FROM_DESK,
)

CATEGORY_TO_ALERT_NAME: dict[str, str] = {
    CATEGORY_LOOKING_AWAY: ALERT_LOOKING_AWAY,
    CATEGORY_PHONE_USE: ALERT_PHONE_USE,
    CATEGORY_YAWNING: ALERT_YAWNING,
    CATEGORY_DROWSY: ALERT_DROWSY,
    CATEGORY_LEANING_BACK: ALERT_LEANING_BACK,
    CATEGORY_AWAY_FROM_DESK: ALERT_AWAY_FROM_DESK,
}

ALERT_NAME_TO_CATEGORY: dict[str, str] = {
    v: k for k, v in CATEGORY_TO_ALERT_NAME.items()
}


def canonicalize_category(name_or_id: str) -> str:
    """Resolve either an internal ID or human-readable alert name to its canonical alert name."""
    if name_or_id in ALERT_NAMES:
        return name_or_id
    if name_or_id in CATEGORY_TO_ALERT_NAME:
        return CATEGORY_TO_ALERT_NAME[name_or_id]
    raise ValueError(f"Unknown alert category identifier: {name_or_id}")


@dataclass
class DetectorConfig:
    """
    Centralized configuration for detection thresholds, persistence delays,
    and calibration policies.
    """

    # Feature & detection thresholds
    yaw_threshold_deg: float = 10.0
    ear_threshold: float = 0.21
    mar_threshold: float = 0.55
    hand_near_cheek_dist: float = 0.15
    lean_back_z_delta: float = 0.15

    # Time persistence before an alert triggers (in seconds)
    alert_delays_sec: dict[str, float] = field(
        default_factory=lambda: {
            ALERT_LOOKING_AWAY: 10.0,
            ALERT_PHONE_USE: 6.0,
            ALERT_YAWNING: 2.0,
            ALERT_DROWSY: 4.0,
            ALERT_LEANING_BACK: 8.0,
            ALERT_AWAY_FROM_DESK: 10.0,
        }
    )

    # Personal calibration parameters
    calibration_seconds: float = 10.0
    minimum_calibration_samples: int = 30

    # Telemetry sampling interval in seconds (5 Hz = 0.2 sec, aligned with transport cadence)
    telemetry_interval_sec: float = 0.2

    # Local desktop runner options
    draw_landmarks: bool = True
    enable_desktop_alarm: bool = True

    def get_alert_delay(self, name_or_id: str) -> float:
        """Retrieve the configured persistence delay for a category."""
        canonical = canonicalize_category(name_or_id)
        if canonical in self.alert_delays_sec:
            return float(self.alert_delays_sec[canonical])
        # Fallback to category id if stored with id keys
        cat_id = ALERT_NAME_TO_CATEGORY.get(canonical, "")
        if cat_id in self.alert_delays_sec:
            return float(self.alert_delays_sec[cat_id])
        return 10.0
