"""Modular rule-based student distraction detection engine package."""

from app.detection.calibration import CalibrationBaseline, CalibrationBuffer
from app.detection.config import (
    ALERT_AWAY_FROM_DESK,
    ALERT_DROWSY,
    ALERT_LEANING_BACK,
    ALERT_LOOKING_AWAY,
    ALERT_NAMES,
    ALERT_PHONE_USE,
    ALERT_YAWNING,
    CATEGORIES,
    CATEGORY_AWAY_FROM_DESK,
    CATEGORY_DROWSY,
    CATEGORY_LEANING_BACK,
    CATEGORY_LOOKING_AWAY,
    CATEGORY_PHONE_USE,
    CATEGORY_YAWNING,
    DETECTOR_VERSION,
    FEATURE_SCHEMA_VERSION,
    DetectorConfig,
)
from app.detection.detector import StudentDistractionDetector
from app.detection.events import DetectionEvent
from app.detection.features import FeatureSnapshot
from app.detection.session_state import SessionState
from app.detection.telemetry import (
    FileTelemetrySink,
    InMemoryTelemetrySink,
    TelemetrySink,
)
from app.detection.trackers import MultiCategoryTracker, PersistenceTracker, TrackerResult

__all__ = [
    "ALERT_AWAY_FROM_DESK",
    "ALERT_DROWSY",
    "ALERT_LEANING_BACK",
    "ALERT_LOOKING_AWAY",
    "ALERT_NAMES",
    "ALERT_PHONE_USE",
    "ALERT_YAWNING",
    "CATEGORIES",
    "CATEGORY_AWAY_FROM_DESK",
    "CATEGORY_DROWSY",
    "CATEGORY_LEANING_BACK",
    "CATEGORY_LOOKING_AWAY",
    "CATEGORY_PHONE_USE",
    "CATEGORY_YAWNING",
    "CalibrationBaseline",
    "CalibrationBuffer",
    "DETECTOR_VERSION",
    "DetectionEvent",
    "DetectorConfig",
    "FEATURE_SCHEMA_VERSION",
    "FeatureSnapshot",
    "FileTelemetrySink",
    "InMemoryTelemetrySink",
    "MultiCategoryTracker",
    "PersistenceTracker",
    "SessionState",
    "StudentDistractionDetector",
    "TelemetrySink",
    "TrackerResult",
]
