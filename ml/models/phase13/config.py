"""Configuration and schema definitions for Phase 13 Offline ML Baseline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Sequence

from ml.dataset.config import (
    CANONICAL_CATEGORIES,
    DATASET_VERSION,
    DETECTOR_VERSION,
    DIAGNOSTIC_COLUMNS,
    FEATURE_SCHEMA_VERSION,
    MODEL_FEATURE_COLUMNS,
    PROHIBITED_MEDIA_SUBSTRINGS,
    PROHIBITED_PII_SUBSTRINGS,
    PROVENANCE_COLUMNS,
    TARGET_COLUMNS,
)

MODEL_VERSION: str = "model_v1"
DEFAULT_DATASET_PATH: Path = Path("data/datasets/phase12/dataset_v1")
DEFAULT_OUTPUT_DIR: Path = Path("ml/models/phase13/distracted")
DEFAULT_PRIMARY_TARGET: str = "label_distracted"


class ReadinessState(str, Enum):
    """Data readiness gate classification states."""

    A_READY = "A. READY FOR ML TRAINING"
    B_INSUFFICIENT_DATA = "B. PIPELINE READY BUT INSUFFICIENT REAL DATA"
    C_INVALID = "C. DATA INVALID / PIPELINE BROKEN"


@dataclass
class ModelConfig:
    """Configuration settings for Phase 13 ML training and evaluation."""

    dataset_path: Path = field(default_factory=lambda: DEFAULT_DATASET_PATH)
    output_dir: Path = field(default_factory=lambda: DEFAULT_OUTPUT_DIR)
    target: str = DEFAULT_PRIMARY_TARGET
    model_type: str = "logistic"  # "logistic" or "random_forest"
    random_seed: int = 42
    classification_threshold: float = 0.50
    tune_threshold: bool = False
    class_weight: Optional[str] = None  # None or "balanced"
    max_iter: int = 1000
    solver: str = "lbfgs"
    rf_n_estimators: int = 100
    rf_max_depth: Optional[int] = 6
    min_samples_per_class: int = 5

    def validate(self) -> None:
        """Validate configuration parameters."""
        if self.model_type not in ("logistic", "random_forest"):
            raise ValueError(
                f"Unsupported model_type '{self.model_type}'. Expected 'logistic' or 'random_forest'."
            )
        if not (0.0 < self.classification_threshold < 1.0):
            raise ValueError(
                f"classification_threshold must be strictly between 0 and 1, got {self.classification_threshold}"
            )
        if self.class_weight not in (None, "balanced"):
            raise ValueError(
                f"Unsupported class_weight '{self.class_weight}'. Expected None or 'balanced'."
            )
        if self.max_iter < 1:
            raise ValueError(f"max_iter must be positive, got {self.max_iter}")
        if self.rf_n_estimators < 1:
            raise ValueError(f"rf_n_estimators must be positive, got {self.rf_n_estimators}")
        if self.min_samples_per_class < 1:
            raise ValueError(
                f"min_samples_per_class must be at least 1, got {self.min_samples_per_class}"
            )
