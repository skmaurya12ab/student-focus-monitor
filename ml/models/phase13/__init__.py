"""Phase 13: Offline ML Baseline Model package."""

from ml.models.phase13.config import ModelConfig, ReadinessState, MODEL_VERSION
from ml.models.phase13.train import TrainResult, train_model
from ml.models.phase13.preprocessing import build_pipeline, verify_feature_matrix, FeatureLeakageError
from ml.models.phase13.evaluate import compute_binary_metrics, predict_with_threshold, tune_classification_threshold
from ml.models.phase13.compare import evaluate_rule_detector_baseline, compare_ml_with_rules
from ml.models.phase13.interpretability import extract_interpretability

__all__ = [
    "ModelConfig",
    "ReadinessState",
    "MODEL_VERSION",
    "TrainResult",
    "train_model",
    "build_pipeline",
    "verify_feature_matrix",
    "FeatureLeakageError",
    "compute_binary_metrics",
    "predict_with_threshold",
    "tune_classification_threshold",
    "evaluate_rule_detector_baseline",
    "compare_ml_with_rules",
    "extract_interpretability",
]
