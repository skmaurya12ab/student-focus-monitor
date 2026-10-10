"""Metadata, evaluation manifest, and schema export for Phase 13 ML model artifacts."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Optional, Sequence
import joblib
import pandas as pd
import sklearn

from ml.dataset.config import (
    DETECTOR_VERSION,
    FEATURE_SCHEMA_VERSION,
    MODEL_FEATURE_COLUMNS,
    PROHIBITED_MEDIA_SUBSTRINGS,
    PROHIBITED_PII_SUBSTRINGS,
)
from ml.models.phase13.config import MODEL_VERSION, ModelConfig


def build_model_metadata(
    config: ModelConfig,
    dataset_manifest: Optional[dict[str, Any]] = None,
    split_counts: Optional[dict[str, dict[str, int]]] = None,
    class_distribution: Optional[dict[str, dict[str, Any]]] = None,
    evaluation_status: str = "valid",
    selected_threshold: float = 0.50,
    model_status: str = "not_trained",
    model_artifact_created: bool = False,
    model_artifact_path: Optional[str] = None,
    target_provenance: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Construct model metadata artifact without exposing PII, raw user IDs, or media paths.
    """
    sp_counts = split_counts or {}
    cd_dist = class_distribution or {}

    dataset_ver = dataset_manifest.get("dataset_version", "unknown") if dataset_manifest else "unknown"

    metadata: dict[str, Any] = {
        "model_version": MODEL_VERSION,
        "dataset_version": dataset_ver,
        "detector_version": DETECTOR_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "target_name": config.target,
        "training_timestamp": datetime.now(timezone.utc).isoformat(),
        "model_class": "LogisticRegression" if config.model_type == "logistic" else "RandomForestClassifier",
        "model_status": model_status,
        "model_artifact_created": bool(model_artifact_created),
        "model_artifact_path": model_artifact_path,
        "preprocessing_pipeline": [
            {"step": "imputer", "method": "SimpleImputer(strategy='median')"},
            {"step": "scaler", "method": "StandardScaler()"},
            {
                "step": "classifier",
                "method": config.model_type,
                "class_weight": config.class_weight,
                "solver": config.solver if config.model_type == "logistic" else None,
                "max_iter": config.max_iter if config.model_type == "logistic" else None,
            },
        ],
        "random_seed": config.random_seed,
        "sample_counts": {
            "train": sp_counts.get("train", {}).get("samples", 0),
            "val": sp_counts.get("val", {}).get("samples", 0),
            "test": sp_counts.get("test", {}).get("samples", 0),
        },
        "user_counts": {
            "train": sp_counts.get("train", {}).get("users", 0),
            "val": sp_counts.get("val", {}).get("users", 0),
            "test": sp_counts.get("test", {}).get("users", 0),
        },
        "session_counts": {
            "train": sp_counts.get("train", {}).get("sessions", 0),
            "val": sp_counts.get("val", {}).get("sessions", 0),
            "test": sp_counts.get("test", {}).get("sessions", 0),
        },
        "feature_count": len(MODEL_FEATURE_COLUMNS),
        "feature_names": list(MODEL_FEATURE_COLUMNS),
        "classification_threshold": float(selected_threshold),
        "class_distribution": cd_dist,
        "evaluation_status": evaluation_status,
        "target_provenance": target_provenance or {},
        "software_versions": {
            "python": sys.version.split()[0],
            "scikit_learn": sklearn.__version__,
            "joblib": joblib.__version__,
            "pandas": pd.__version__,
        },
    }

    # Strict privacy audit on generated metadata dictionary
    raw_str = json.dumps(metadata).lower()
    for pii in PROHIBITED_PII_SUBSTRINGS:
        if pii == "user_id":
            # user_counts is allowed, raw user_id is not
            continue
        if pii in raw_str:
            raise ValueError(f"Privacy error: Metadata contains prohibited token '{pii}'")
    for media in PROHIBITED_MEDIA_SUBSTRINGS:
        if media in raw_str:
            raise ValueError(f"Privacy error: Metadata contains prohibited media token '{media}'")

    return metadata


def build_evaluation_manifest(
    data_validity: dict[str, Any],
    model_validity: dict[str, Any],
    metrics_by_split: Optional[dict[str, Any]] = None,
    threshold_info: Optional[dict[str, Any]] = None,
    interpretability: Optional[dict[str, Any]] = None,
    rule_comparison: Optional[dict[str, Any]] = None,
    target_provenance: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Construct the experiment evaluation manifest distinguishing data validity, model validity,
    and target provenance.
    """
    return {
        "evaluation_timestamp": datetime.now(timezone.utc).isoformat(),
        "model_version": MODEL_VERSION,
        "data_validity": {
            "pipeline_valid": bool(data_validity.get("pipeline_valid", True)),
            "label_valid": bool(data_validity.get("label_valid", True)),
            "split_valid": bool(data_validity.get("split_valid", True)),
            "sufficient_data": bool(data_validity.get("sufficient_data", True)),
            "evaluation_not_valid": bool(data_validity.get("evaluation_not_valid", False)),
            "validity_reason": data_validity.get("validity_reason"),
        },
        "model_validity": {
            "model_status": model_validity.get("model_status", "not_trained"),
            "model_artifact_created": bool(model_validity.get("model_artifact_created", False)),
            "training_completed": bool(model_validity.get("training_completed", False)),
            "validation_available": bool(model_validity.get("validation_available", False)),
            "test_evaluation_available": bool(model_validity.get("test_evaluation_available", False)),
        },
        "target_provenance": target_provenance or {},
        "threshold": threshold_info or {"classification_threshold": 0.50, "tuned": False},
        "metrics": metrics_by_split or {},
        "interpretability": interpretability or {"available": False},
        "rule_comparison": rule_comparison or {"comparison_available": False},
    }


def build_feature_schema() -> dict[str, Any]:
    """Construct static feature schema artifact cataloging allowlisted model features."""
    features_spec = []
    for f in MODEL_FEATURE_COLUMNS:
        if "missing" in f:
            dtype = "bool"
        elif f in ("face_present", "pose_present"):
            dtype = "bool"
        elif f == "hand_count":
            dtype = "int64"
        else:
            dtype = "float64"

        features_spec.append({
            "name": f,
            "data_type": dtype,
            "category": "model_feature",
        })

    return {
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "model_feature_columns_count": len(MODEL_FEATURE_COLUMNS),
        "features": features_spec,
    }


def save_artifacts(
    output_dir: Path,
    pipeline: Optional[Any],
    metadata: dict[str, Any],
    evaluation: dict[str, Any],
    feature_schema: dict[str, Any],
) -> dict[str, Path]:
    """
    Write model artifacts to local output directory.
    
    Artifacts:
      - model.joblib (if pipeline is trained)
      - metadata.json
      - evaluation.json
      - feature_schema.json
    
    If pipeline is None, ensures any stale model.joblib is removed.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    saved_paths = {}

    model_path = output_dir / "model.joblib"
    if pipeline is not None:
        joblib.dump(pipeline, model_path)
        saved_paths["model_joblib"] = model_path
    else:
        # Clean up any stale model binary to avoid claiming a trained model exists
        if model_path.exists():
            model_path.unlink()

    metadata_path = output_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    saved_paths["metadata"] = metadata_path

    eval_path = output_dir / "evaluation.json"
    eval_path.write_text(json.dumps(evaluation, indent=2), encoding="utf-8")
    saved_paths["evaluation"] = eval_path

    schema_path = output_dir / "feature_schema.json"
    schema_path.write_text(json.dumps(feature_schema, indent=2), encoding="utf-8")
    saved_paths["feature_schema"] = schema_path

    return saved_paths
