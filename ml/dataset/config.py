"""Configuration constants, feature allowlists, and settings for the ML Dataset Pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence

# Canonical detector and schema versions
DATASET_VERSION: str = "dataset_v1"
DETECTOR_VERSION: str = "v4"
FEATURE_SCHEMA_VERSION: str = "telemetry_v2"

# Canonical detection categories
CANONICAL_CATEGORIES: tuple[str, ...] = (
    "looking_away",
    "phone_use",
    "yawning",
    "drowsy",
    "leaning_back",
    "away_from_desk",
)

# Canonical focus states
CANONICAL_FOCUS_STATES: tuple[str, ...] = (
    "focused",
    "distracted",
    "away",
    "calibrating",
)

# Canonical human feedback types
CANONICAL_FEEDBACK_TYPES: tuple[str, ...] = (
    "correct_detection",
    "false_positive",
    "missed_detection",
    "other",
)

# Privacy prohibited substrings (strictly forbidden in feature matrices, column names, and metadata)
PROHIBITED_MEDIA_SUBSTRINGS: tuple[str, ...] = (
    "image",
    "frame_bytes",
    "video",
    "audio",
    "jpeg",
    "png",
    "raw_buffer",
    "screenshot",
    "camera",
    "webcam",
    "raw_frame",
)

# Prohibited Personally Identifiable Information keywords in model feature tables
PROHIBITED_PII_SUBSTRINGS: tuple[str, ...] = (
    "email",
    "password",
    "token",
    "google_id",
    "auth_provider",
    "display_name",
    "user_id",  # Raw user_id must NOT appear in model feature columns
)

# Core scalar numerical features from telemetry_samples table
CORE_NUMERICAL_FEATURES: tuple[str, ...] = (
    "head_pitch",
    "head_yaw",
    "head_roll",
    "ear",
    "mar",
    "min_hand_cheek_distance",
    "shoulder_z",
)

# Core presence and integer features from telemetry_samples table
CORE_PRESENCE_FEATURES: tuple[str, ...] = (
    "face_present",
    "pose_present",
    "hand_count",
)

# Flattened numerical features extracted from telemetry_samples.features JSONB
FLATTENED_NUMERICAL_FEATURES: tuple[str, ...] = (
    "head_pitch_from_baseline",
    "head_yaw_from_baseline",
    "head_roll_from_baseline",
    "left_ear",
    "right_ear",
    "left_hand_cheek_distance",
    "right_hand_cheek_distance",
    "shoulder_z_delta",
    "torso_aspect_ratio",
    "torso_posture_delta",
    "head_yaw_rate",
    "head_pitch_rate",
    "head_roll_rate",
    "shoulder_z_rate",
    "hand_cheek_distance_rate",
)

# Calibration baseline features from telemetry_samples.features["baseline"]
BASELINE_CALIBRATION_FEATURES: tuple[str, ...] = (
    "baseline_head_yaw",
    "baseline_head_pitch",
    "baseline_head_roll",
    "baseline_shoulder_z",
    "baseline_torso_aspect_ratio",
)

# Instantaneous rule booleans from telemetry_samples.features
RULE_BOOLEAN_FEATURES: tuple[str, ...] = (
    "rule_looking_away",
    "rule_phone_use",
    "rule_yawning",
    "rule_eyes_closed",
    "rule_leaning_back",
    "rule_away_from_desk",
)

# Tracker states from telemetry_samples.features["tracker_states"]
def _get_tracker_features() -> tuple[str, ...]:
    features: list[str] = []
    for cat in CANONICAL_CATEGORIES:
        features.extend([
            f"tracker_{cat}_active",
            f"tracker_{cat}_duration_sec",
            f"tracker_{cat}_persistence_met",
        ])
    return tuple(features)

TRACKER_FEATURES: tuple[str, ...] = _get_tracker_features()

# Explicit missing indicator columns for key numerical measurements
MISSING_INDICATOR_FEATURES: tuple[str, ...] = (
    "head_pitch_missing",
    "head_yaw_missing",
    "head_roll_missing",
    "ear_missing",
    "mar_missing",
    "min_hand_cheek_distance_missing",
    "shoulder_z_missing",
    "torso_aspect_ratio_missing",
)

# Complete ordered feature allowlist for ML model inputs
FEATURE_COLUMNS_ALLOWLIST: tuple[str, ...] = (
    CORE_NUMERICAL_FEATURES
    + CORE_PRESENCE_FEATURES
    + FLATTENED_NUMERICAL_FEATURES
    + BASELINE_CALIBRATION_FEATURES
    + RULE_BOOLEAN_FEATURES
    + TRACKER_FEATURES
    + MISSING_INDICATOR_FEATURES
)

# Multi-label category target columns
TARGET_CATEGORY_COLUMNS: tuple[str, ...] = tuple(
    f"label_{cat}" for cat in CANONICAL_CATEGORIES
)

# Overall target columns
TARGET_COLUMNS: tuple[str, ...] = TARGET_CATEGORY_COLUMNS + (
    "focus_state_label",
    "label_distracted",
)

# Metadata and provenance columns (traceability without leaking into model features)
METADATA_COLUMNS: tuple[str, ...] = (
    "sample_id",
    "session_hash",
    "frame_index",
    "sampled_at",
    "detector_version",
    "feature_schema_version",
    "dataset_version",
    "split",
    "label_source",
    "label_quality",
    "is_labeled",
    "is_calibration",
    "is_excluded",
    "exclusion_reason",
)

# Complete dataset columns (features + targets + metadata)
ALL_DATASET_COLUMNS: tuple[str, ...] = (
    FEATURE_COLUMNS_ALLOWLIST
    + TARGET_COLUMNS
    + METADATA_COLUMNS
)


@dataclass
class DatasetConfig:
    """Runtime configuration options for building an ML dataset."""

    output_dir: Path = field(default_factory=lambda: Path("data/datasets/phase12/dataset_v1"))
    dataset_version: str = DATASET_VERSION
    random_seed: int = 42
    include_calibration: bool = False
    missed_detection_window_sec: float = 0.0  # 0.0 = session-level metadata only; >0 = sample-level window
    train_ratio: float = 0.70
    val_ratio: float = 0.15
    test_ratio: float = 0.15
    min_users_for_split: int = 3
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    export_csv: bool = False
    completed_only: bool = True

    def validate(self) -> None:
        """Validate split ratios and parameters."""
        total_ratio = round(self.train_ratio + self.val_ratio + self.test_ratio, 4)
        if total_ratio != 1.0:
            raise ValueError(
                f"Split ratios must sum to 1.0, got train={self.train_ratio}, val={self.val_ratio}, test={self.test_ratio} (sum={total_ratio})"
            )
        if any(r < 0 for r in (self.train_ratio, self.val_ratio, self.test_ratio)):
            raise ValueError("Split ratios cannot be negative.")
        if self.missed_detection_window_sec < 0:
            raise ValueError("missed_detection_window_sec must be non-negative.")
