"""Rule-based detector comparison module for offline diagnostic evaluation."""

from __future__ import annotations

from typing import Any, Optional, Sequence
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score


def evaluate_rule_detector_baseline(
    df: pd.DataFrame,
    y_true: Sequence[int],
    target_name: str = "label_distracted",
) -> dict[str, Any]:
    """
    Evaluate the heuristic rule-based detector against human-supported ground truth.
    
    Diagnostic comparison ONLY:
    The rule detector outputs are retained exclusively in the DIAGNOSTIC_COLUMNS of the
    dataset artifact for offline benchmarking and MUST NEVER enter the ML feature matrix.
    """
    y_t = np.asarray(y_true, dtype=int)
    if len(y_t) == 0:
        return {"available": False, "reason": "Empty evaluation split"}

    rule_cols = [
        "rule_looking_away",
        "rule_phone_use",
        "rule_yawning",
        "rule_eyes_closed",
        "rule_leaning_back",
        "rule_away_from_desk",
    ]

    # Check if target maps to a specific category rule
    specific_rule = target_name.replace("label_", "rule_")
    if specific_rule in df.columns:
        rule_series = df[specific_rule].fillna(False).astype(bool)
        rule_name = specific_rule
    elif all(c in df.columns for c in rule_cols):
        # Overall distraction: any instantaneous rule active
        rule_series = df[rule_cols].fillna(False).any(axis=1)
        rule_name = "composite_any_rule_distracted"
    else:
        return {
            "available": False,
            "reason": f"Required rule columns not found in diagnostic partition of dataset",
        }

    y_rule = rule_series.astype(int).to_numpy()

    precision = float(precision_score(y_t, y_rule, zero_division=0))
    recall = float(recall_score(y_t, y_rule, zero_division=0))
    f1 = float(f1_score(y_t, y_rule, zero_division=0))
    acc = float(accuracy_score(y_t, y_rule))
    cm = confusion_matrix(y_t, y_rule, labels=[0, 1]).tolist()

    return {
        "available": True,
        "rule_strategy": rule_name,
        "precision": float(round(precision, 4)),
        "recall": float(round(recall, 4)),
        "f1": float(round(f1, 4)),
        "accuracy": float(round(acc, 4)),
        "confusion_matrix": cm,
        "predicted_positive_count": int(np.sum(y_rule == 1)),
        "actual_positive_count": int(np.sum(y_t == 1)),
        "note": (
            "Rule detector performance evaluated offline on the same split. "
            "Neither model nor rules are treated as absolute ground truth."
        ),
    }


def compare_ml_with_rules(
    ml_metrics: dict[str, Any],
    rule_metrics: dict[str, Any],
) -> dict[str, Any]:
    """
    Generate side-by-side comparison between the ML model and the rule baseline.
    """
    if not ml_metrics or not rule_metrics or not rule_metrics.get("available"):
        return {
            "comparison_available": False,
            "reason": rule_metrics.get("reason", "Incomplete evaluation metrics"),
        }

    ml_f1 = ml_metrics.get("f1")
    rule_f1 = rule_metrics.get("f1")
    delta_f1 = None
    if ml_f1 is not None and rule_f1 is not None:
        delta_f1 = float(round(ml_f1 - rule_f1, 4))

    return {
        "comparison_available": True,
        "ml_model": {
            "precision": ml_metrics.get("precision"),
            "recall": ml_metrics.get("recall"),
            "f1": ml_metrics.get("f1"),
            "accuracy": ml_metrics.get("accuracy"),
        },
        "rule_baseline": {
            "precision": rule_metrics.get("precision"),
            "recall": rule_metrics.get("recall"),
            "f1": rule_metrics.get("f1"),
            "accuracy": rule_metrics.get("accuracy"),
        },
        "delta_f1": delta_f1,
        "assessment": (
            "ML model outperforms rule baseline"
            if delta_f1 and delta_f1 > 0
            else "Rule baseline matches or outperforms ML baseline"
            if delta_f1 is not None
            else "Comparison indeterminate"
        ),
    }
