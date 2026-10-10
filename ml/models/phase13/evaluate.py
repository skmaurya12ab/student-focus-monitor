"""Evaluation metrics and threshold tuning for Phase 13 ML models."""

from __future__ import annotations

from typing import Any, Optional, Sequence
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def compute_binary_metrics(
    y_true: Sequence[int],
    y_pred: Sequence[int],
    y_prob: Optional[Sequence[float]] = None,
) -> dict[str, Any]:
    """
    Compute binary classification metrics with safeguards for single-class cases.
    
    Returns:
        Dictionary containing precision, recall, f1, accuracy, roc_auc, pr_auc,
        confusion matrix, sample counts, and class distribution.
    """
    y_t = np.asarray(y_true, dtype=int)
    y_p = np.asarray(y_pred, dtype=int)

    total_samples = int(len(y_t))
    actual_positives = int(np.sum(y_t == 1))
    actual_negatives = int(np.sum(y_t == 0))
    pred_positives = int(np.sum(y_p == 1))
    pred_negatives = int(np.sum(y_p == 0))
    positive_rate = float(round(actual_positives / total_samples, 4)) if total_samples > 0 else 0.0

    class_dist = {
        "positive_count": actual_positives,
        "negative_count": actual_negatives,
        "positive_rate": positive_rate,
    }

    # If dataset has 0 samples, return empty metrics
    if total_samples == 0:
        return {
            "total_samples": 0,
            "class_distribution": class_dist,
            "precision": None,
            "recall": None,
            "f1": None,
            "accuracy": None,
            "roc_auc": None,
            "pr_auc": None,
            "confusion_matrix": None,
            "counts": {
                "predicted_positive": 0,
                "predicted_negative": 0,
                "actual_positive": 0,
                "actual_negative": 0,
            },
        }

    # Standard metrics
    precision = float(precision_score(y_t, y_p, zero_division=0))
    recall = float(recall_score(y_t, y_p, zero_division=0))
    f1 = float(f1_score(y_t, y_p, zero_division=0))
    acc = float(accuracy_score(y_t, y_p))

    # Confusion matrix [[TN, FP], [FN, TP]]
    cm = confusion_matrix(y_t, y_p, labels=[0, 1]).tolist()

    # ROC-AUC and PR-AUC require probabilities and both classes present in y_true
    unique_classes = np.unique(y_t)
    roc_auc = None
    pr_auc = None

    if len(unique_classes) == 2 and y_prob is not None:
        y_prob_arr = np.asarray(y_prob, dtype=float)
        try:
            roc_auc = float(round(roc_auc_score(y_t, y_prob_arr), 4))
        except Exception:
            roc_auc = None

        try:
            pr_auc = float(round(average_precision_score(y_t, y_prob_arr), 4))
        except Exception:
            pr_auc = None

    return {
        "total_samples": total_samples,
        "class_distribution": class_dist,
        "precision": float(round(precision, 4)),
        "recall": float(round(recall, 4)),
        "f1": float(round(f1, 4)),
        "accuracy": float(round(acc, 4)),
        "roc_auc": roc_auc,
        "pr_auc": pr_auc,
        "confusion_matrix": cm,
        "counts": {
            "predicted_positive": pred_positives,
            "predicted_negative": pred_negatives,
            "actual_positive": actual_positives,
            "actual_negative": actual_negatives,
        },
    }


def predict_with_threshold(
    probabilities: np.ndarray,
    threshold: float = 0.50,
) -> np.ndarray:
    """Classify probabilities as 1 if probability >= threshold, else 0."""
    return (np.asarray(probabilities) >= threshold).astype(int)


def tune_classification_threshold(
    y_true: Sequence[int],
    probabilities: np.ndarray,
    metric: str = "f1",
) -> tuple[float, float]:
    """
    Tune the classification threshold on training/validation probabilities.
    DO NOT pass test set labels to this function.
    
    Evaluates thresholds in [0.10, 0.90] at step 0.05.
    Returns (best_threshold, best_metric_score).
    """
    y_t = np.asarray(y_true, dtype=int)
    probs = np.asarray(probabilities, dtype=float)

    if len(np.unique(y_t)) < 2 or len(y_t) == 0:
        return 0.50, 0.0

    thresholds = np.arange(0.10, 0.95, 0.05)
    best_threshold = 0.50
    best_score = -1.0

    for thresh in thresholds:
        preds = (probs >= thresh).astype(int)
        if metric == "f1":
            score = float(f1_score(y_t, preds, zero_division=0))
        elif metric == "precision":
            score = float(precision_score(y_t, preds, zero_division=0))
        elif metric == "recall":
            score = float(recall_score(y_t, preds, zero_division=0))
        else:
            score = float(accuracy_score(y_t, preds))

        if score > best_score:
            best_score = score
            best_threshold = float(round(thresh, 2))

    return best_threshold, float(round(best_score, 4))
