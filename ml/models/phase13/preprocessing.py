"""Preprocessing pipeline and feature leakage validation for Phase 13 ML model."""

from __future__ import annotations

from typing import Sequence
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ml.dataset.config import (
    DIAGNOSTIC_COLUMNS,
    MODEL_FEATURE_COLUMNS,
    PROHIBITED_MEDIA_SUBSTRINGS,
    PROHIBITED_PII_SUBSTRINGS,
    PROVENANCE_COLUMNS,
    TARGET_COLUMNS,
)
from ml.models.phase13.config import ModelConfig


class FeatureLeakageError(ValueError):
    """Raised when forbidden columns or leakage occurs in the model feature matrix."""


def verify_feature_matrix(
    df: pd.DataFrame,
    expected_features: Sequence[str] = MODEL_FEATURE_COLUMNS,
) -> None:
    """
    Verify that the input feature matrix strictly contains only allowlisted MODEL_FEATURE_COLUMNS.
    Fails immediately if any target, diagnostic, provenance, or unknown column is present.
    """
    actual_cols = list(df.columns)
    expected_set = set(expected_features)

    # 1. Check for missing expected features
    missing_features = [f for f in expected_features if f not in actual_cols]
    if missing_features:
        raise FeatureLeakageError(
            f"Feature matrix is missing {len(missing_features)} expected features: {missing_features[:5]}..."
        )

    # 2. Explicitly verify no diagnostic columns (rule/tracker outputs)
    diagnostic_leaks = [c for c in actual_cols if c in DIAGNOSTIC_COLUMNS]
    if diagnostic_leaks:
        raise FeatureLeakageError(
            f"Model feature leakage detected: diagnostic/rule columns in feature matrix: {diagnostic_leaks}"
        )

    # 3. Explicitly verify no target columns
    target_leaks = [c for c in actual_cols if c in TARGET_COLUMNS or c.startswith("label_")]
    if target_leaks:
        raise FeatureLeakageError(
            f"Target leakage detected: target columns in feature matrix: {target_leaks}"
        )

    # 4. Explicitly verify no provenance or metadata columns
    provenance_leaks = [c for c in actual_cols if c in PROVENANCE_COLUMNS]
    if provenance_leaks:
        raise FeatureLeakageError(
            f"Provenance leakage detected: metadata/provenance columns in feature matrix: {provenance_leaks}"
        )

    # 5. Check for unexpected additional columns
    unexpected_cols = [c for c in actual_cols if c not in expected_set]
    if unexpected_cols:
        raise FeatureLeakageError(
            f"Feature matrix contains {len(unexpected_cols)} unauthorized columns: {unexpected_cols[:5]}..."
        )

    # 6. Check for PII or raw media keyword substrings
    for col in actual_cols:
        col_lower = col.lower()
        for pii in PROHIBITED_PII_SUBSTRINGS:
            if pii in col_lower:
                raise FeatureLeakageError(
                    f"Privacy violation: Column '{col}' contains prohibited PII token '{pii}'"
                )
        for media in PROHIBITED_MEDIA_SUBSTRINGS:
            if media in col_lower:
                raise FeatureLeakageError(
                    f"Privacy violation: Column '{col}' contains prohibited media token '{media}'"
                )

    # 7. Check for Infinite values
    for col in actual_cols:
        series = df[col]
        if pd.api.types.is_numeric_dtype(series):
            clean_vals = series.dropna().to_numpy()
            if len(clean_vals) > 0 and np.isinf(clean_vals).any():
                raise FeatureLeakageError(
                    f"Invalid feature values: Column '{col}' contains infinite values (inf or -inf)"
                )



def build_pipeline(config: ModelConfig) -> Pipeline:
    """
    Construct a leakage-safe scikit-learn Pipeline.
    
    Preprocessing stages:
    1. SimpleImputer(strategy='median'): Learns feature medians ONLY from training data.
    2. StandardScaler(): Computes mean and standard deviation ONLY from training data.
    3. Classifier: LogisticRegression or RandomForestClassifier.
    """
    if config.model_type == "logistic":
        classifier = LogisticRegression(
            random_state=config.random_seed,
            max_iter=config.max_iter,
            solver=config.solver,
            class_weight=config.class_weight,
        )
        steps = [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("classifier", classifier),
        ]
    elif config.model_type == "random_forest":
        classifier = RandomForestClassifier(
            random_state=config.random_seed,
            n_estimators=config.rf_n_estimators,
            max_depth=config.rf_max_depth,
            class_weight=config.class_weight,
        )
        steps = [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("classifier", classifier),
        ]
    else:
        raise ValueError(f"Unsupported model_type: {config.model_type}")

    return Pipeline(steps)
