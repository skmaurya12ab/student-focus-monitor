"""Model training orchestrator for Phase 13 Offline ML Baseline."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Optional, Sequence
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from ml.dataset.config import (
    DIAGNOSTIC_COLUMNS,
    MODEL_FEATURE_COLUMNS,
    PROVENANCE_COLUMNS,
    TARGET_COLUMNS,
)
from ml.models.phase13.compare import compare_ml_with_rules, evaluate_rule_detector_baseline
from ml.models.phase13.config import ModelConfig, ReadinessState
from ml.models.phase13.evaluate import (
    compute_binary_metrics,
    predict_with_threshold,
    tune_classification_threshold,
)
from ml.models.phase13.interpretability import extract_interpretability
from ml.models.phase13.metadata import (
    build_evaluation_manifest,
    build_feature_schema,
    build_model_metadata,
    save_artifacts,
)
from ml.models.phase13.preprocessing import build_pipeline, verify_feature_matrix


@dataclass
class TrainResult:
    """Outcome and artifacts produced by the Phase 13 training pipeline."""

    success: bool
    readiness_state: ReadinessState
    pipeline: Optional[Pipeline]
    metadata: dict[str, Any]
    evaluation: dict[str, Any]
    feature_schema: dict[str, Any]
    saved_paths: dict[str, Path] = field(default_factory=dict)
    warning_messages: list[str] = field(default_factory=list)


def load_dataset_artifacts(dataset_path: Path) -> tuple[pd.DataFrame, Optional[dict[str, Any]]]:
    """Load Parquet dataset and optional manifest JSON from dataset directory or file."""
    path = Path(dataset_path)
    if path.is_dir():
        parquet_path = path / "dataset.parquet"
        manifest_path = path / "manifest.json"
    else:
        parquet_path = path
        manifest_path = path.parent / "manifest.json"

    if not parquet_path.exists():
        raise FileNotFoundError(f"Dataset Parquet file not found at '{parquet_path}'")

    df = pd.read_parquet(parquet_path)
    manifest = None
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            manifest = None

    return df, manifest


def extract_target_provenance(df: pd.DataFrame, target_name: str) -> dict[str, Any]:
    """
    Extract distribution of label sources and verify human vs detector pseudo-label origin.
    """
    if "label_source" not in df.columns:
        return {
            "eligible_sample_count": len(df),
            "label_source_distribution": {},
            "human_confirmed_count": 0,
            "detector_derived_count": 0,
            "independent_human_validation_available": False,
            "rule_comparison_semantics": "No label_source column present in input dataframe",
        }

    label_source_counts = {
        str(k): int(v) for k, v in df["label_source"].value_counts(dropna=False).items()
    }
    human_confirmed = int(
        df["label_source"].isin(["human_confirmed_detection", "human_rejected_detector_event"]).sum()
    )
    detector_derived = int(
        df["label_source"].isin(["detector_state_monitoring", "detector_event"]).sum()
    )
    unlabeled_count = int(df["label_source"].isin(["unlabeled"]).sum())

    return {
        "eligible_sample_count": len(df),
        "label_source_distribution": label_source_counts,
        "human_confirmed_count": human_confirmed,
        "detector_derived_count": detector_derived,
        "unlabeled_count": unlabeled_count,
        "independent_human_validation_available": bool(human_confirmed > 0),
        "rule_comparison_semantics": (
            "Rule detector comparison measures imitation and agreement with detector-derived pseudo-labels; "
            "it does NOT represent independent distraction-detection accuracy."
        ),
    }


def train_model(
    config: Optional[ModelConfig] = None,
    df_override: Optional[pd.DataFrame] = None,
    manifest_override: Optional[dict[str, Any]] = None,
) -> TrainResult:
    """
    Execute Phase 13 ML training pipeline:
    1. Pre-flight dataset audit & feature schema validation
    2. Data readiness gating (A: ready, B: insufficient data, C: broken)
    3. Strict group split preservation (no user or session leakage)
    4. scikit-learn Pipeline construction with in-pipeline median imputation & scaling
    5. Training fitted strictly on training data
    6. Leakage-safe threshold selection (tuned on val only, never test)
    7. Multi-split evaluation, confusion matrix, and rule detector baseline comparison
    8. Diagnostic interpretability ranking
    9. Privacy-safe artifact serialization
    """
    cfg = config or ModelConfig()
    cfg.validate()

    warnings: list[str] = []

    # 1. Load dataset
    if df_override is not None:
        df = df_override.copy()
        manifest = manifest_override
    else:
        try:
            df, manifest = load_dataset_artifacts(cfg.dataset_path)
        except Exception as e:
            # Case C: Pipeline broken / dataset not found
            err_msg = f"Failed to load dataset: {e}"
            data_val = {
                "pipeline_valid": False,
                "label_valid": False,
                "split_valid": False,
                "sufficient_data": False,
                "evaluation_not_valid": True,
                "validity_reason": err_msg,
            }
            model_val = {
                "model_status": "not_trained",
                "model_artifact_created": False,
                "training_completed": False,
                "validation_available": False,
                "test_evaluation_available": False,
            }
            metadata = build_model_metadata(
                config=cfg,
                dataset_manifest=None,
                evaluation_status="broken_pipeline",
                model_status="not_trained",
                model_artifact_created=False,
                model_artifact_path=None,
                target_provenance={},
            )
            evaluation = build_evaluation_manifest(
                data_validity=data_val,
                model_validity=model_val,
                target_provenance={},
            )
            schema = build_feature_schema()
            saved = save_artifacts(cfg.output_dir, None, metadata, evaluation, schema)
            return TrainResult(
                success=False,
                readiness_state=ReadinessState.C_INVALID,
                pipeline=None,
                metadata=metadata,
                evaluation=evaluation,
                feature_schema=schema,
                saved_paths=saved,
                warning_messages=[err_msg],
            )

    # 2. Target validation
    if cfg.target not in df.columns:
        raise ValueError(
            f"Target column '{cfg.target}' not found in dataset. Available target columns: "
            f"{[c for c in df.columns if c in TARGET_COLUMNS or c.startswith('label_')]}"
        )

    # 3. Filter invalid / calibration / unlabeled rows
    initial_count = len(df)
    filtered_df = df.copy()

    if "is_calibration" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["is_calibration"] != True]
    if "is_excluded" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["is_excluded"] != True]

    # Exclude null targets (cannot train on unlabeled rows)
    filtered_df = filtered_df[filtered_df[cfg.target].notna()]
    eligible_count = len(filtered_df)

    # Extract target label provenance for eligible rows
    target_prov = extract_target_provenance(filtered_df, cfg.target)

    # 4. Check for zero eligible samples
    if eligible_count == 0:
        reason = (
            f"Canonical dataset contains zero eligible samples for target '{cfg.target}' "
            f"after excluding calibration and unlabeled rows (initial={initial_count})."
        )
        warnings.append(reason)
        data_val = {
            "pipeline_valid": True,
            "label_valid": False,
            "split_valid": False,
            "sufficient_data": False,
            "evaluation_not_valid": True,
            "validity_reason": reason,
        }
        model_val = {
            "model_status": "not_trained",
            "model_artifact_created": False,
            "training_completed": False,
            "validation_available": False,
            "test_evaluation_available": False,
        }
        metadata = build_model_metadata(
            config=cfg,
            dataset_manifest=manifest,
            evaluation_status="insufficient_data",
            model_status="not_trained",
            model_artifact_created=False,
            model_artifact_path=None,
            target_provenance=target_prov,
        )
        evaluation = build_evaluation_manifest(
            data_validity=data_val,
            model_validity=model_val,
            target_provenance=target_prov,
        )
        schema = build_feature_schema()
        saved = save_artifacts(cfg.output_dir, None, metadata, evaluation, schema)
        return TrainResult(
            success=False,
            readiness_state=ReadinessState.B_INSUFFICIENT_DATA,
            pipeline=None,
            metadata=metadata,
            evaluation=evaluation,
            feature_schema=schema,
            saved_paths=saved,
            warning_messages=warnings,
        )

    # 5. Split partitioning and validation
    if "split" not in filtered_df.columns:
        raise ValueError("Dataset Parquet is missing authoritative 'split' column.")

    train_df = filtered_df[filtered_df["split"] == "train"]
    val_df = filtered_df[filtered_df["split"] == "val"]
    test_df = filtered_df[filtered_df["split"] == "test"]

    # Accounting (using short non-reversible session_hash and anonymized counts)
    def get_split_stats(sub_df: pd.DataFrame) -> dict[str, int]:
        n_samples = len(sub_df)
        n_sessions = sub_df["session_hash"].nunique() if "session_hash" in sub_df.columns else 0
        return {"samples": n_samples, "sessions": n_sessions, "users": 0}

    split_counts = {
        "train": get_split_stats(train_df),
        "val": get_split_stats(val_df),
        "test": get_split_stats(test_df),
    }

    # If manifest contains entity counts, incorporate anonymized user counts
    if manifest and "splits" in manifest:
        for s_name in ("train", "val", "test"):
            if s_name in manifest["splits"]:
                split_counts[s_name]["users"] = manifest["splits"][s_name].get("user_count", 0)

    # 6. Validate training split readiness rules
    train_samples = len(train_df)
    train_classes = np.unique(train_df[cfg.target]) if train_samples > 0 else np.array([])

    if train_samples == 0:
        reason = (
            f"Training split contains 0 samples (total eligible={eligible_count}, test={len(test_df)}, val={len(val_df)}). "
            f"Insufficient distinct students for multi-split generalization."
        )
        warnings.append(reason)
        data_val = {
            "pipeline_valid": True,
            "label_valid": True,
            "split_valid": False,
            "sufficient_data": False,
            "evaluation_not_valid": True,
            "validity_reason": reason,
        }
        model_val = {
            "model_status": "not_trained",
            "model_artifact_created": False,
            "training_completed": False,
            "validation_available": False,
            "test_evaluation_available": False,
        }
        metadata = build_model_metadata(
            config=cfg,
            dataset_manifest=manifest,
            split_counts=split_counts,
            evaluation_status="insufficient_data",
            model_status="not_trained",
            model_artifact_created=False,
            model_artifact_path=None,
            target_provenance=target_prov,
        )
        evaluation = build_evaluation_manifest(
            data_validity=data_val,
            model_validity=model_val,
            target_provenance=target_prov,
        )
        schema = build_feature_schema()
        saved = save_artifacts(cfg.output_dir, None, metadata, evaluation, schema)
        return TrainResult(
            success=False,
            readiness_state=ReadinessState.B_INSUFFICIENT_DATA,
            pipeline=None,
            metadata=metadata,
            evaluation=evaluation,
            feature_schema=schema,
            saved_paths=saved,
            warning_messages=warnings,
        )

    if len(train_classes) < 2:
        reason = (
            f"Training split contains only one class ({train_classes}). "
            f"Supervised binary classification requires both positive and negative classes."
        )
        warnings.append(reason)
        data_val = {
            "pipeline_valid": True,
            "label_valid": False,
            "split_valid": True,
            "sufficient_data": False,
            "evaluation_not_valid": True,
            "validity_reason": reason,
        }
        model_val = {
            "model_status": "not_trained",
            "model_artifact_created": False,
            "training_completed": False,
            "validation_available": False,
            "test_evaluation_available": False,
        }
        metadata = build_model_metadata(
            config=cfg,
            dataset_manifest=manifest,
            split_counts=split_counts,
            evaluation_status="insufficient_data",
            model_status="not_trained",
            model_artifact_created=False,
            model_artifact_path=None,
            target_provenance=target_prov,
        )
        evaluation = build_evaluation_manifest(
            data_validity=data_val,
            model_validity=model_val,
            target_provenance=target_prov,
        )
        schema = build_feature_schema()
        saved = save_artifacts(cfg.output_dir, None, metadata, evaluation, schema)
        return TrainResult(
            success=False,
            readiness_state=ReadinessState.B_INSUFFICIENT_DATA,
            pipeline=None,
            metadata=metadata,
            evaluation=evaluation,
            feature_schema=schema,
            saved_paths=saved,
            warning_messages=warnings,
        )

    # 7. Extract feature matrices and labels (strictly MODEL_FEATURE_COLUMNS)
    feature_cols = list(MODEL_FEATURE_COLUMNS)

    X_train = train_df[feature_cols]
    y_train = train_df[cfg.target].astype(int)

    # Validate feature matrix for leakage
    verify_feature_matrix(X_train)

    X_val = val_df[feature_cols] if len(val_df) > 0 else pd.DataFrame(columns=feature_cols)
    y_val = val_df[cfg.target].astype(int) if len(val_df) > 0 else pd.Series(dtype=int)
    if len(X_val) > 0:
        verify_feature_matrix(X_val)

    X_test = test_df[feature_cols] if len(test_df) > 0 else pd.DataFrame(columns=feature_cols)
    y_test = test_df[cfg.target].astype(int) if len(test_df) > 0 else pd.Series(dtype=int)
    if len(X_test) > 0:
        verify_feature_matrix(X_test)

    # 8. Build and fit pipeline strictly on X_train, y_train
    pipeline = build_pipeline(cfg)
    pipeline.fit(X_train, y_train)

    # 9. Threshold selection
    selected_threshold = cfg.classification_threshold
    threshold_tuned = False

    if cfg.tune_threshold and len(val_df) > 0 and len(np.unique(y_val)) == 2:
        val_probs_arr = pipeline.predict_proba(X_val)[:, 1]
        tuned_thresh, best_score = tune_classification_threshold(y_val, val_probs_arr, metric="f1")
        selected_threshold = tuned_thresh
        threshold_tuned = True

    threshold_info = {
        "classification_threshold": float(selected_threshold),
        "tuned": threshold_tuned,
        "default_threshold": 0.50,
    }

    # 10. Multi-split evaluation
    train_probs = pipeline.predict_proba(X_train)[:, 1]
    train_preds = predict_with_threshold(train_probs, selected_threshold)
    train_metrics = compute_binary_metrics(y_train, train_preds, train_probs)

    val_metrics = None
    if len(val_df) > 0:
        val_probs = pipeline.predict_proba(X_val)[:, 1]
        val_preds = predict_with_threshold(val_probs, selected_threshold)
        val_metrics = compute_binary_metrics(y_val, val_preds, val_probs)

    test_metrics = None
    if len(test_df) > 0:
        test_probs = pipeline.predict_proba(X_test)[:, 1]
        test_preds = predict_with_threshold(test_probs, selected_threshold)
        test_metrics = compute_binary_metrics(y_test, test_preds, test_probs)

    metrics_by_split = {
        "train": train_metrics,
        "val": val_metrics,
        "test": test_metrics,
    }

    class_distribution = {
        "train": train_metrics["class_distribution"],
        "val": val_metrics["class_distribution"] if val_metrics else None,
        "test": test_metrics["class_distribution"] if test_metrics else None,
    }

    # 11. Interpretability
    interpretability = extract_interpretability(pipeline, feature_cols)

    # 12. Rule-based baseline comparison (offline diagnostic)
    eval_df = test_df if len(test_df) > 0 else val_df if len(val_df) > 0 else train_df
    eval_y = y_test if len(test_df) > 0 else y_val if len(val_df) > 0 else y_train
    eval_metrics = test_metrics or val_metrics or train_metrics

    rule_metrics = evaluate_rule_detector_baseline(eval_df, eval_y, cfg.target)
    rule_comparison = compare_ml_with_rules(eval_metrics, rule_metrics)

    # 13. Construct validity blocks
    has_test_eval = test_metrics is not None and test_metrics["total_samples"] > 0
    has_val_eval = val_metrics is not None and val_metrics["total_samples"] > 0

    data_val = {
        "pipeline_valid": True,
        "label_valid": True,
        "split_valid": True,
        "sufficient_data": True,
        "evaluation_not_valid": False,
        "validity_reason": None,
    }
    model_val = {
        "model_status": "trained",
        "model_artifact_created": True,
        "training_completed": True,
        "validation_available": has_val_eval,
        "test_evaluation_available": has_test_eval,
    }

    model_joblib_path = str(cfg.output_dir / "model.joblib")
    metadata = build_model_metadata(
        config=cfg,
        dataset_manifest=manifest,
        split_counts=split_counts,
        class_distribution=class_distribution,
        evaluation_status="valid",
        selected_threshold=selected_threshold,
        model_status="trained",
        model_artifact_created=True,
        model_artifact_path=model_joblib_path,
        target_provenance=target_prov,
    )
    evaluation = build_evaluation_manifest(
        data_validity=data_val,
        model_validity=model_val,
        metrics_by_split=metrics_by_split,
        threshold_info=threshold_info,
        interpretability=interpretability,
        rule_comparison=rule_comparison,
        target_provenance=target_prov,
    )
    schema = build_feature_schema()

    saved = save_artifacts(cfg.output_dir, pipeline, metadata, evaluation, schema)

    return TrainResult(
        success=True,
        readiness_state=ReadinessState.A_READY,
        pipeline=pipeline,
        metadata=metadata,
        evaluation=evaluation,
        feature_schema=schema,
        saved_paths=saved,
        warning_messages=warnings,
    )
