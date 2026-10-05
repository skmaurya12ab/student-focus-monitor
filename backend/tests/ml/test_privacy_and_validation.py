"""Tests for dataset privacy enforcement, NaN/Inf rejection, and data quality validation."""

from __future__ import annotations

import pandas as pd
import pytest

from ml.dataset.config import (
    ALL_DATASET_COLUMNS,
    DIAGNOSTIC_COLUMNS,
    FEATURE_COLUMNS_ALLOWLIST,
    MODEL_FEATURE_COLUMNS,
    METADATA_COLUMNS,
    PROVENANCE_COLUMNS,
    TARGET_COLUMNS,
)
from ml.dataset.validation import (
    DataQualityValidationError,
    validate_data_split_leakage,
    validate_feature_target_leakage,
    validate_frame_monotonicity,
    validate_leakage,
    validate_no_nan_or_inf,
    validate_privacy,
    validate_ranges,
    validate_target_feature_separation,
)


def test_rule_and_tracker_outputs_excluded_from_model_features():
    """
    Issue 1 Regression Test:
    Assert that detector rule booleans and tracker states do NOT appear in MODEL_FEATURE_COLUMNS.
    Verifies all 7 separation invariants.
    """
    # 1. No rule_* fields in MODEL_FEATURE_COLUMNS
    rule_cols = [col for col in MODEL_FEATURE_COLUMNS if col.startswith("rule_")]
    assert not rule_cols, f"Rule columns found in MODEL_FEATURE_COLUMNS: {rule_cols}"

    # 2. No tracker_* fields in MODEL_FEATURE_COLUMNS
    tracker_cols = [col for col in MODEL_FEATURE_COLUMNS if col.startswith("tracker_")]
    assert not tracker_cols, f"Tracker columns found in MODEL_FEATURE_COLUMNS: {tracker_cols}"

    # 3. No detection event timing fields in MODEL_FEATURE_COLUMNS
    timing_cols = [
        col for col in MODEL_FEATURE_COLUMNS
        if any(term in col for term in ("started_at", "ended_at", "duration", "timing"))
    ]
    assert not timing_cols, f"Timing columns found in MODEL_FEATURE_COLUMNS: {timing_cols}"

    # 4. No feedback-derived fields in MODEL_FEATURE_COLUMNS
    feedback_cols = [
        col for col in MODEL_FEATURE_COLUMNS
        if "feedback" in col or "reviewed" in col
    ]
    assert not feedback_cols, f"Feedback columns found in MODEL_FEATURE_COLUMNS: {feedback_cols}"

    # 5. Targets remain strictly separated from model features
    assert set(MODEL_FEATURE_COLUMNS).isdisjoint(set(TARGET_COLUMNS)), "Target columns overlap with features!"

    # 6. Diagnostic and provenance fields remain available outside model features in ALL_DATASET_COLUMNS
    assert set(MODEL_FEATURE_COLUMNS).isdisjoint(set(DIAGNOSTIC_COLUMNS)), "Diagnostic columns overlap with features!"
    assert set(MODEL_FEATURE_COLUMNS).isdisjoint(set(PROVENANCE_COLUMNS)), "Provenance columns overlap with features!"
    assert set(DIAGNOSTIC_COLUMNS).issubset(set(ALL_DATASET_COLUMNS)), "Diagnostic columns missing from dataset!"
    assert set(PROVENANCE_COLUMNS).issubset(set(ALL_DATASET_COLUMNS)), "Provenance columns missing from dataset!"

    # 7. Schema validation fails if a target, provenance, diagnostic, timing, or feedback field enters features
    with pytest.raises(DataQualityValidationError, match="Detector output leakage detected"):
        validate_feature_target_leakage(list(MODEL_FEATURE_COLUMNS) + ["rule_looking_away"])

    with pytest.raises(DataQualityValidationError, match="Detector output leakage detected"):
        validate_feature_target_leakage(list(MODEL_FEATURE_COLUMNS) + ["tracker_phone_use_active"])

    with pytest.raises(DataQualityValidationError, match="Detector rule output"):
        validate_feature_target_leakage(list(MODEL_FEATURE_COLUMNS) + ["rule_novel_custom"])

    with pytest.raises(DataQualityValidationError, match="Tracker output"):
        validate_feature_target_leakage(list(MODEL_FEATURE_COLUMNS) + ["tracker_novel_custom"])

    with pytest.raises(DataQualityValidationError, match="Target leakage detected"):
        validate_feature_target_leakage(list(MODEL_FEATURE_COLUMNS) + ["label_looking_away"])

    with pytest.raises(DataQualityValidationError, match="Provenance/metadata contamination detected"):
        validate_feature_target_leakage(list(MODEL_FEATURE_COLUMNS) + ["session_hash"])

    with pytest.raises(DataQualityValidationError, match="Detection event timing field"):
        validate_feature_target_leakage(list(MODEL_FEATURE_COLUMNS) + ["event_duration_sec"])

    with pytest.raises(DataQualityValidationError, match="Human feedback-derived field"):
        validate_feature_target_leakage(list(MODEL_FEATURE_COLUMNS) + ["user_feedback_type"])


def test_target_feature_separation():
    """Ensure feature columns pass clean validation."""
    res = validate_feature_target_leakage(MODEL_FEATURE_COLUMNS)
    assert res["status"] == "passed"
    assert res["target_leakage"] is False
    assert res["detector_rule_leakage"] is False
    assert res["tracker_state_leakage"] is False
    assert res["provenance_leakage"] is False


def test_privacy_validation_passes_on_clean_dataframe():
    df = pd.DataFrame({
        "sample_id": ["sample-1", "sample-2"],
        "session_hash": ["ses_a1b2c3", "ses_d4e5f6"],
        "head_yaw": [15.2, 2.1],
        "ear": [0.28, 0.31],
        "focus_state_label": ["focused", "distracted"],
    })
    result = validate_privacy(df)
    assert result["status"] == "passed"


def test_privacy_validation_rejects_prohibited_media_columns():
    df = pd.DataFrame({
        "sample_id": ["sample-1"],
        "raw_frame_bytes": [b"binary_data"],
    })
    with pytest.raises(DataQualityValidationError, match="Forbidden media substring"):
        validate_privacy(df)


def test_privacy_validation_rejects_prohibited_pii_columns():
    df = pd.DataFrame({
        "sample_id": ["sample-1"],
        "user_id": ["b52a5747-18dd-4b19-a51b-e8fb58a3775f"],
    })
    with pytest.raises(DataQualityValidationError, match="Forbidden PII keyword"):
        validate_privacy(df)


def test_privacy_validation_rejects_email_pii_in_strings():
    df = pd.DataFrame({
        "sample_id": ["sample-1"],
        "note": ["student@example.com was here"],
    })
    with pytest.raises(DataQualityValidationError, match="Forbidden PII email pattern"):
        validate_privacy(df)


def test_validate_no_nan_or_inf_detects_infinite_values():
    df_inf = pd.DataFrame({
        "head_pitch": [1.0, float("inf")],
    })
    with pytest.raises(DataQualityValidationError, match="Infinite value found"):
        validate_no_nan_or_inf(df_inf)


def test_validate_ranges_rejects_negative_ear():
    df_neg = pd.DataFrame({
        "ear": [0.25, -0.05],
    })
    with pytest.raises(DataQualityValidationError, match="Negative values detected"):
        validate_ranges(df_neg)


def test_validate_frame_monotonicity():
    df_valid = pd.DataFrame({
        "session_hash": ["s1", "s1", "s1"],
        "frame_index": [0, 1, 2],
    })
    validate_frame_monotonicity(df_valid)

    df_invalid = pd.DataFrame({
        "session_hash": ["s1", "s1", "s1"],
        "frame_index": [0, 5, 2],
    })
    with pytest.raises(DataQualityValidationError, match="Non-monotonic frame indices"):
        validate_frame_monotonicity(df_invalid)
