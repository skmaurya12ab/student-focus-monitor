"""Tests for dataset privacy enforcement, NaN/Inf rejection, and data quality validation."""

from __future__ import annotations

import pandas as pd
import pytest

from ml.dataset.config import FEATURE_COLUMNS_ALLOWLIST, TARGET_COLUMNS, METADATA_COLUMNS
from ml.dataset.validation import (
    DataQualityValidationError,
    validate_frame_monotonicity,
    validate_no_nan_or_inf,
    validate_privacy,
    validate_ranges,
    validate_target_feature_separation,
)


def test_target_feature_separation():
    """Ensure target columns and metadata columns do not overlap with feature columns."""
    validate_target_feature_separation()
    feat_set = set(FEATURE_COLUMNS_ALLOWLIST)
    target_set = set(TARGET_COLUMNS)
    meta_set = set(METADATA_COLUMNS)

    assert not (feat_set & target_set), "Target columns leaked into features!"
    assert not (feat_set & meta_set), "Metadata columns leaked into features!"


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
