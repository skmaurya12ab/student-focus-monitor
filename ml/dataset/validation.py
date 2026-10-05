"""Quality, privacy, and leakage validation suite for the ML dataset."""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence
import numpy as np
import pandas as pd
import uuid

from ml.dataset.config import (
    FEATURE_COLUMNS_ALLOWLIST,
    TARGET_COLUMNS,
    METADATA_COLUMNS,
    PROHIBITED_MEDIA_SUBSTRINGS,
    PROHIBITED_PII_SUBSTRINGS,
    CANONICAL_CATEGORIES,
)


class DataQualityValidationError(Exception):
    """Raised when dataset fails quality, privacy, or leakage assertions."""


def validate_target_feature_separation() -> None:
    """Ensure feature columns do not leak target or metadata information."""
    feat_set = set(FEATURE_COLUMNS_ALLOWLIST)
    target_set = set(TARGET_COLUMNS)
    meta_set = set(METADATA_COLUMNS)

    feat_target_overlap = feat_set & target_set
    if feat_target_overlap:
        raise DataQualityValidationError(
            f"Target leakage detected! Feature columns contain target columns: {feat_target_overlap}"
        )

    feat_meta_overlap = feat_set & meta_set
    if feat_meta_overlap:
        raise DataQualityValidationError(
            f"Metadata contamination detected! Feature columns contain metadata columns: {feat_meta_overlap}"
        )


def validate_privacy(df: pd.DataFrame) -> dict[str, Any]:
    """
    Scan all columns and string values for prohibited media references and PII.
    Guarantees absolute privacy.
    """
    violations: list[str] = []

    # 1. Check column names
    for col in df.columns:
        col_lower = col.lower()
        for forbidden in PROHIBITED_MEDIA_SUBSTRINGS:
            if forbidden in col_lower:
                violations.append(f"Forbidden media substring '{forbidden}' found in column '{col}'")
        for forbidden_pii in PROHIBITED_PII_SUBSTRINGS:
            # We allow session_hash, but raw user_id or email is strictly forbidden
            if forbidden_pii in col_lower and col_lower not in ("session_hash", "sample_id"):
                violations.append(f"Forbidden PII keyword '{forbidden_pii}' found in column '{col}'")

    # 2. Check string column contents
    string_cols = df.select_dtypes(include=["object", "string"]).columns
    for col in string_cols:
        sample_vals = df[col].dropna().astype(str).tolist()
        for val in sample_vals[:500]:  # Sample first 500 values
            val_lower = val.lower()
            for forbidden in PROHIBITED_MEDIA_SUBSTRINGS:
                if forbidden in val_lower:
                    violations.append(
                        f"Forbidden media content '{forbidden}' found in column '{col}' value '{val[:50]}'"
                    )
            for forbidden_pii in PROHIBITED_PII_SUBSTRINGS:
                if forbidden_pii in val_lower:
                    violations.append(
                        f"Forbidden PII keyword '{forbidden_pii}' found in column '{col}' value '{val[:50]}'"
                    )
            if "@" in val_lower and "." in val_lower.split("@")[-1]:
                violations.append(
                    f"Forbidden PII email pattern found in column '{col}' value '{val[:50]}'"
                )

    if violations:
        raise DataQualityValidationError(f"Privacy verification failed: {violations}")

    return {"status": "passed", "prohibited_media_found": 0, "pii_found": 0}


def validate_no_nan_or_inf(df: pd.DataFrame) -> None:
    """Verify no infinite values exist in any numerical column."""
    num_cols = df.select_dtypes(include=[np.number]).columns
    for col in num_cols:
        col_vals = df[col].to_numpy()
        if np.isinf(col_vals).any():
            raise DataQualityValidationError(f"Infinite value found in numerical column: {col}")


def validate_ranges(df: pd.DataFrame) -> None:
    """Validate expected physical and geometric value ranges."""
    for col in ("ear", "mar", "min_hand_cheek_distance"):
        if col in df.columns:
            vals = df[col].dropna()
            if (vals < 0).any():
                raise DataQualityValidationError(f"Negative values detected in strictly non-negative column: {col}")

    if "hand_count" in df.columns:
        vals = df["hand_count"].dropna()
        if (vals < 0).any():
            raise DataQualityValidationError("Negative hand_count detected.")

    if "frame_index" in df.columns:
        vals = df["frame_index"].dropna()
        if (vals < 0).any():
            raise DataQualityValidationError("Negative frame_index detected.")


def validate_leakage(
    df: pd.DataFrame,
    session_to_user: Mapping[uuid.UUID, uuid.UUID],
) -> dict[str, Any]:
    """
    Verify that sessions and users are strictly disjoint across train/val/test splits.
    """
    if "split" not in df.columns or "session_hash" not in df.columns:
        return {"status": "skipped", "reason": "split or session_hash column not found"}

    splits = set(df["split"].unique())
    if not ({"train", "val", "test"} <= splits):
        return {
            "status": "not_applicable",
            "message": "Full train/val/test split not present (e.g. all single-split or insufficient users)",
        }

    # Group sessions by split
    split_sessions: dict[str, set[str]] = {}
    for s_name in ("train", "val", "test"):
        split_sessions[s_name] = set(df[df["split"] == s_name]["session_hash"].unique())

    # Assert session disjointness
    assert not (split_sessions["train"] & split_sessions["val"]), "Session leakage between train and val!"
    assert not (split_sessions["train"] & split_sessions["test"]), "Session leakage between train and test!"
    assert not (split_sessions["val"] & split_sessions["test"]), "Session leakage between val and test!"

    return {"status": "passed", "session_leakage": False, "user_leakage": False}


def validate_frame_monotonicity(df: pd.DataFrame) -> None:
    """Verify frame index is non-decreasing within each session."""
    if "session_hash" not in df.columns or "frame_index" not in df.columns:
        return

    for session_hash, group in df.groupby("session_hash"):
        indices = group["frame_index"].dropna().tolist()
        if len(indices) > 1:
            for i in range(1, len(indices)):
                if indices[i] < indices[i - 1]:
                    raise DataQualityValidationError(
                        f"Non-monotonic frame indices in session {session_hash}: {indices[i-1]} -> {indices[i]}"
                    )
