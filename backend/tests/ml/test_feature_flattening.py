"""Tests for ML dataset feature extraction, allowlist filtering, and missing value indicators."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
import uuid

from ml.dataset.config import (
    MODEL_FEATURE_COLUMNS,
    FEATURE_COLUMNS_ALLOWLIST,
    CORE_NUMERICAL_FEATURES,
    FLATTENED_NUMERICAL_FEATURES,
    MISSING_INDICATOR_FEATURES,
    DIAGNOSTIC_COLUMNS,
)
from ml.dataset.extract import ExtractedTelemetrySample
from ml.dataset.features import extract_diagnostic_features, flatten_telemetry_features


def make_sample(**kwargs) -> ExtractedTelemetrySample:
    """Helper to build a sample with sensible defaults."""
    now = datetime(2026, 10, 5, 12, 0, 0, tzinfo=timezone.utc)
    defaults = {
        "id": uuid.uuid4(),
        "session_id": uuid.uuid4(),
        "sampled_at": now,
        "frame_index": 1,
        "detector_version": "v4",
        "feature_schema_version": "telemetry_v2",
        "head_pitch": -5.0,
        "head_yaw": 18.5,
        "head_roll": 1.2,
        "ear": 0.28,
        "mar": 0.21,
        "min_hand_cheek_distance": 0.12,
        "shoulder_z": -0.35,
        "face_present": True,
        "pose_present": True,
        "hand_count": 1,
        "focus_state": "focused",
        "features": {
            "head_pitch_from_baseline": -1.0,
            "head_yaw_from_baseline": 16.5,
            "head_roll_from_baseline": 0.2,
            "left_ear": 0.27,
            "right_ear": 0.29,
            "left_hand_cheek_distance": 0.12,
            "right_hand_cheek_distance": 0.35,
            "shoulder_z_delta": -0.05,
            "torso_aspect_ratio": 0.48,
            "torso_posture_delta": 0.03,
            "head_yaw_rate": 1.5,
            "head_pitch_rate": 0.2,
            "head_roll_rate": 0.1,
            "shoulder_z_rate": 0.02,
            "hand_cheek_distance_rate": 0.4,
            "baseline": {
                "head_yaw": 2.0,
                "head_pitch": -4.0,
                "head_roll": 1.0,
                "shoulder_z": -0.30,
                "torso_aspect_ratio": 0.45,
            },
            "looking_away": True,
            "phone_use": True,
            "yawning": False,
            "eyes_closed": False,
            "leaning_back": False,
            "away_from_desk": False,
            "tracker_states": {
                "looking_away": {"active": True, "duration_sec": 1.5, "persistence_met": True},
                "phone_use": {"active": True, "duration_sec": 0.8, "persistence_met": False},
            },
            # Arbitrary extra keys that must be ignored
            "internal_debug_cache": [1, 2, 3],
            "unrelated_experimental_blob": "test",
        },
    }
    defaults.update(kwargs)
    return ExtractedTelemetrySample(**defaults)


def test_flatten_telemetry_features_conforms_to_allowlist():
    sample = make_sample()
    flattened = flatten_telemetry_features(sample)

    assert set(flattened.keys()) == set(MODEL_FEATURE_COLUMNS)
    # Ensure rule_* and tracker_* are strictly absent from model features
    assert "rule_looking_away" not in flattened
    assert "tracker_looking_away_active" not in flattened
    assert not any(k.startswith("rule_") for k in flattened)
    assert not any(k.startswith("tracker_") for k in flattened)
    # Ensure unknown keys in sample.features are strictly dropped
    assert "internal_debug_cache" not in flattened
    assert "unrelated_experimental_blob" not in flattened


def test_flatten_telemetry_features_preserves_values_and_baseline_deltas():
    sample = make_sample()
    flattened = flatten_telemetry_features(sample)

    assert flattened["head_yaw"] == 18.5
    assert flattened["head_yaw_from_baseline"] == 16.5
    assert flattened["baseline_head_yaw"] == 2.0
    assert flattened["ear"] == 0.28
    assert flattened["mar"] == 0.21
    assert flattened["min_hand_cheek_distance"] == 0.12
    assert flattened["torso_aspect_ratio"] == 0.48
    assert flattened["torso_posture_delta"] == 0.03

    # Diagnostic features are extracted into a separate dictionary
    diag = extract_diagnostic_features(sample)
    assert set(diag.keys()) == set(DIAGNOSTIC_COLUMNS)
    assert diag["rule_looking_away"] is True
    assert diag["rule_phone_use"] is True
    assert diag["tracker_looking_away_active"] is True
    assert diag["tracker_looking_away_duration_sec"] == 1.5
    assert diag["tracker_looking_away_persistence_met"] is True


def test_missing_values_remain_none_and_set_missing_flags():
    """Verify non-zero null semantics: missing features remain None, not 0.0."""
    sample = make_sample(
        head_yaw=None,
        head_pitch=None,
        head_roll=None,
        ear=None,
        mar=None,
        min_hand_cheek_distance=None,
        shoulder_z=None,
        face_present=False,
        features={
            "torso_aspect_ratio": None,
            "baseline": {},
        },
    )
    flattened = flatten_telemetry_features(sample)

    assert flattened["head_yaw"] is None
    assert flattened["head_pitch"] is None
    assert flattened["ear"] is None
    assert flattened["mar"] is None
    assert flattened["min_hand_cheek_distance"] is None
    assert flattened["shoulder_z"] is None

    # Missing indicator columns must be True
    assert flattened["head_yaw_missing"] is True
    assert flattened["head_pitch_missing"] is True
    assert flattened["head_roll_missing"] is True
    assert flattened["ear_missing"] is True
    assert flattened["mar_missing"] is True
    assert flattened["min_hand_cheek_distance_missing"] is True
    assert flattened["shoulder_z_missing"] is True
    assert flattened["torso_aspect_ratio_missing"] is True


def test_nan_and_inf_are_strictly_rejected():
    sample_nan = make_sample(head_yaw=float("nan"))
    with pytest.raises(ValueError, match="Forbidden NaN or Infinity"):
        flatten_telemetry_features(sample_nan)

    sample_inf = make_sample(head_pitch=float("inf"))
    with pytest.raises(ValueError, match="Forbidden NaN or Infinity"):
        flatten_telemetry_features(sample_inf)

    sample_json_nan = make_sample(
        features={"head_yaw_from_baseline": float("nan")}
    )
    with pytest.raises(ValueError, match="Forbidden NaN or Infinity"):
        flatten_telemetry_features(sample_json_nan)
