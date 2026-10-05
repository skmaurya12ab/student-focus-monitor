"""Feature transformation, allowlist filtering, and missing value indicators."""

from __future__ import annotations

import math
from typing import Any, Optional
import numpy as np

from ml.dataset.config import (
    CANONICAL_CATEGORIES,
    CORE_NUMERICAL_FEATURES,
    CORE_PRESENCE_FEATURES,
    FLATTENED_NUMERICAL_FEATURES,
    BASELINE_CALIBRATION_FEATURES,
    RULE_BOOLEAN_FEATURES,
    TRACKER_FEATURES,
    MISSING_INDICATOR_FEATURES,
    FEATURE_COLUMNS_ALLOWLIST,
    PROHIBITED_MEDIA_SUBSTRINGS,
    PROHIBITED_PII_SUBSTRINGS,
)
from ml.dataset.extract import ExtractedTelemetrySample


def _clean_float(val: Any, field_name: str) -> Optional[float]:
    """
    Ensure value is a finite float or None.
    Rejects NaN and Infinity strictly to prevent model corruption.
    """
    if val is None:
        return None
    try:
        f = float(val)
    except (TypeError, ValueError) as err:
        raise ValueError(f"Invalid non-float value for {field_name}: {val!r}") from err

    if math.isnan(f) or math.isinf(f) or not np.isfinite(f):
        raise ValueError(f"Forbidden NaN or Infinity detected in feature {field_name}: {val}")
    return f


def _clean_bool(val: Any) -> Optional[bool]:
    """Ensure value is a boolean or None."""
    if val is None:
        return None
    return bool(val)


def _clean_int(val: Any, field_name: str) -> Optional[int]:
    """Ensure value is an integer or None."""
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError) as err:
        raise ValueError(f"Invalid non-integer value for {field_name}: {val!r}") from err


def flatten_telemetry_features(sample: ExtractedTelemetrySample) -> dict[str, Any]:
    """
    Transform raw telemetry sample into an allowlisted, flat dictionary of model features.
    Strictly preserves None for missing values and generates explicit missing-indicator columns.
    Enforces privacy by omitting any unknown or prohibited media/PII keys.
    """
    result: dict[str, Any] = {}
    json_features = sample.features or {}

    # 1. Core numerical columns from table
    result["head_pitch"] = _clean_float(sample.head_pitch, "head_pitch")
    result["head_yaw"] = _clean_float(sample.head_yaw, "head_yaw")
    result["head_roll"] = _clean_float(sample.head_roll, "head_roll")
    result["ear"] = _clean_float(sample.ear, "ear")
    result["mar"] = _clean_float(sample.mar, "mar")
    result["min_hand_cheek_distance"] = _clean_float(sample.min_hand_cheek_distance, "min_hand_cheek_distance")
    result["shoulder_z"] = _clean_float(sample.shoulder_z, "shoulder_z")

    # 2. Core presence & count columns from table
    result["face_present"] = _clean_bool(sample.face_present)
    result["pose_present"] = _clean_bool(sample.pose_present)
    result["hand_count"] = _clean_int(sample.hand_count, "hand_count")

    # 3. Flattened numerical features from JSONB allowlist
    for feat in FLATTENED_NUMERICAL_FEATURES:
        result[feat] = _clean_float(json_features.get(feat), feat)

    # 4. Calibration baseline features from JSONB features["baseline"]
    baseline_dict = json_features.get("baseline") or {}
    if not isinstance(baseline_dict, dict):
        baseline_dict = {}

    result["baseline_head_yaw"] = _clean_float(baseline_dict.get("head_yaw"), "baseline_head_yaw")
    result["baseline_head_pitch"] = _clean_float(baseline_dict.get("head_pitch"), "baseline_head_pitch")
    result["baseline_head_roll"] = _clean_float(baseline_dict.get("head_roll"), "baseline_head_roll")
    result["baseline_shoulder_z"] = _clean_float(baseline_dict.get("shoulder_z"), "baseline_shoulder_z")
    result["baseline_torso_aspect_ratio"] = _clean_float(
        baseline_dict.get("torso_aspect_ratio"), "baseline_torso_aspect_ratio"
    )

    # 5. Rule boolean features from JSONB
    result["rule_looking_away"] = bool(json_features.get("looking_away", False))
    result["rule_phone_use"] = bool(json_features.get("phone_use", False))
    result["rule_yawning"] = bool(json_features.get("yawning", False))
    result["rule_eyes_closed"] = bool(json_features.get("eyes_closed", False))
    result["rule_leaning_back"] = bool(json_features.get("leaning_back", False))
    result["rule_away_from_desk"] = bool(json_features.get("away_from_desk", False))

    # 6. Tracker state features from JSONB features["tracker_states"]
    tracker_dict = json_features.get("tracker_states") or {}
    if not isinstance(tracker_dict, dict):
        tracker_dict = {}

    for cat in CANONICAL_CATEGORIES:
        t_state = tracker_dict.get(cat) or {}
        if not isinstance(t_state, dict):
            t_state = {}
        result[f"tracker_{cat}_active"] = bool(t_state.get("active", False))
        result[f"tracker_{cat}_duration_sec"] = _clean_float(
            t_state.get("duration_sec", 0.0), f"tracker_{cat}_duration_sec"
        ) or 0.0
        result[f"tracker_{cat}_persistence_met"] = bool(t_state.get("persistence_met", False))

    # 7. Explicit missing indicator flags
    result["head_pitch_missing"] = bool(result["head_pitch"] is None)
    result["head_yaw_missing"] = bool(result["head_yaw"] is None)
    result["head_roll_missing"] = bool(result["head_roll"] is None)
    result["ear_missing"] = bool(result["ear"] is None)
    result["mar_missing"] = bool(result["mar"] is None)
    result["min_hand_cheek_distance_missing"] = bool(result["min_hand_cheek_distance"] is None)
    result["shoulder_z_missing"] = bool(result["shoulder_z"] is None)
    result["torso_aspect_ratio_missing"] = bool(result["torso_aspect_ratio"] is None)

    # 8. Assert exact match with allowlist (no extra or missing keys)
    for col in FEATURE_COLUMNS_ALLOWLIST:
        if col not in result:
            raise KeyError(f"Feature allowlist column {col} missing in flattened dictionary.")

    # Return ordered dictionary conforming strictly to allowlist
    return {col: result[col] for col in FEATURE_COLUMNS_ALLOWLIST}
