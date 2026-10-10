"""Model interpretability module for extracting coefficients and feature importance."""

from __future__ import annotations

from typing import Any, Sequence
import numpy as np
from sklearn.pipeline import Pipeline


def extract_interpretability(
    pipeline: Pipeline,
    feature_names: Sequence[str],
) -> dict[str, Any]:
    """
    Extract diagnostic feature interpretability from fitted scikit-learn pipeline.
    
    For Logistic Regression: extracts feature coefficients, absolute magnitude, and direction.
    For Random Forest: extracts Gini feature importances.
    """
    classifier = pipeline.named_steps.get("classifier")
    if classifier is None:
        return {"available": False, "reason": "No classifier found in pipeline steps"}

    model_class = classifier.__class__.__name__

    if hasattr(classifier, "coef_"):
        # Linear model (LogisticRegression)
        coefs = classifier.coef_[0]
        intercept = float(classifier.intercept_[0]) if hasattr(classifier, "intercept_") else 0.0

        ranked_features = []
        for name, weight in zip(feature_names, coefs):
            val = float(weight)
            ranked_features.append({
                "feature": name,
                "coefficient": float(round(val, 4)),
                "abs_magnitude": float(round(abs(val), 4)),
                "direction": "positive" if val > 0 else "negative",
            })

        # Sort by absolute magnitude descending
        ranked_features.sort(key=lambda x: x["abs_magnitude"], reverse=True)

        return {
            "available": True,
            "model_class": model_class,
            "intercept": float(round(intercept, 4)),
            "feature_ranking": ranked_features,
            "top_distraction_indicators": [f for f in ranked_features if f["direction"] == "positive"][:5],
            "top_focus_indicators": [f for f in ranked_features if f["direction"] == "negative"][:5],
            "note": (
                "Coefficients reflect standardized linear log-odds impact on distraction probability. "
                "Diagnostic interpretability only; does not prove causality."
            ),
        }

    elif hasattr(classifier, "feature_importances_"):
        # Tree-based model (RandomForestClassifier)
        importances = classifier.feature_importances_
        ranked_features = []
        for name, imp in zip(feature_names, importances):
            val = float(imp)
            ranked_features.append({
                "feature": name,
                "importance": float(round(val, 4)),
            })

        ranked_features.sort(key=lambda x: x["importance"], reverse=True)

        return {
            "available": True,
            "model_class": model_class,
            "feature_ranking": ranked_features,
            "top_features": ranked_features[:10],
            "note": (
                "Feature importances reflect mean decrease in impurity (Gini importance). "
                "Diagnostic interpretability only; does not prove causality."
            ),
        }

    return {
        "available": False,
        "reason": f"Classifier {model_class} does not provide coef_ or feature_importances_",
    }
