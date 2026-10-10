"""Automated test suite for Phase 13 Offline ML Baseline model pipeline."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
from typing import Any
import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.pipeline import Pipeline

from ml.dataset.config import (
    ALL_DATASET_COLUMNS,
    CANONICAL_CATEGORIES,
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
from ml.models.phase13.metadata import build_feature_schema, build_model_metadata
from ml.models.phase13.preprocessing import (
    FeatureLeakageError,
    build_pipeline,
    verify_feature_matrix,
)
from ml.models.phase13.train import train_model


def make_deterministic_dataset(n_samples: int = 60, seed: int = 42) -> pd.DataFrame:
    """
    Generate a deterministic synthetic multi-user dataset for testing ML mechanics.
    MARKER: SYNTHETIC TEST ONLY — NOT PROJECT PERFORMANCE.
    """
    rng = np.random.RandomState(seed)

    rows = []
    # 3 distinct users, 6 distinct sessions
    users = ["user_1", "user_2", "user_3"]
    sessions = [f"ses_{i}" for i in range(6)]

    # Assign users to splits: user_1 -> train, user_2 -> val, user_3 -> test
    split_map = {"user_1": "train", "user_2": "val", "user_3": "test"}
    session_user_map = {
        "ses_0": "user_1",
        "ses_1": "user_1",
        "ses_2": "user_2",
        "ses_3": "user_2",
        "ses_4": "user_3",
        "ses_5": "user_3",
    }

    for i in range(n_samples):
        ses = sessions[i % len(sessions)]
        usr = session_user_map[ses]
        spl = split_map[usr]

        row: dict[str, Any] = {}

        # 38 MODEL_FEATURE_COLUMNS
        for col in MODEL_FEATURE_COLUMNS:
            if "missing" in col:
                row[col] = bool(rng.rand() > 0.9)
            elif col in ("face_present", "pose_present"):
                row[col] = True
            elif col == "hand_count":
                row[col] = int(rng.choice([0, 1, 2]))
            else:
                val = float(rng.randn() * 2.0)
                # Introduce occasional null to test imputer
                row[col] = None if rng.rand() < 0.1 else val

        # Target columns
        label_distracted = int(i % 2 == 0)
        row["label_distracted"] = label_distracted
        row["focus_state_label"] = "distracted" if label_distracted == 1 else "focused"
        for cat in CANONICAL_CATEGORIES:
            row[f"label_{cat}"] = int(label_distracted and (i % 3 == 0))

        # Provenance columns
        row["sample_id"] = f"sample_{i}"
        row["session_hash"] = ses
        row["frame_index"] = i
        row["sampled_at"] = "2026-10-10T12:00:00Z"
        row["detector_version"] = "v4"
        row["feature_schema_version"] = "telemetry_v2"
        row["dataset_version"] = "dataset_v1"
        row["split"] = spl
        row["label_source"] = "synthetic_fixture"
        row["label_quality"] = "high"
        row["is_labeled"] = True
        row["is_calibration"] = False
        row["is_excluded"] = False
        row["exclusion_reason"] = None

        # Diagnostic columns
        for diag in DIAGNOSTIC_COLUMNS:
            if diag.startswith("rule_"):
                row[diag] = bool(label_distracted and rng.rand() > 0.3)
            elif diag.endswith("_active"):
                row[diag] = False
            elif diag.endswith("_duration_sec"):
                row[diag] = 0.0
            elif diag.endswith("_persistence_met"):
                row[diag] = False

        rows.append(row)

    df = pd.DataFrame(rows)
    return df


# ==============================================================================
# 1. FEATURE SCHEMA TESTS
# ==============================================================================

def test_feature_matrix_verification_accepts_clean_matrix():
    """Verify that verify_feature_matrix accepts valid MODEL_FEATURE_COLUMNS dataframe."""
    df = make_deterministic_dataset(10)
    X = df[list(MODEL_FEATURE_COLUMNS)]
    verify_feature_matrix(X)  # Should not raise


def test_feature_matrix_fails_on_diagnostic_rule_leakage():
    """Verify that rule/tracker diagnostic columns trigger FeatureLeakageError."""
    df = make_deterministic_dataset(10)
    X = df[list(MODEL_FEATURE_COLUMNS)].copy()
    X["rule_looking_away"] = True
    with pytest.raises(FeatureLeakageError, match="diagnostic/rule columns"):
        verify_feature_matrix(X)


def test_feature_matrix_fails_on_target_leakage():
    """Verify that target columns trigger FeatureLeakageError."""
    df = make_deterministic_dataset(10)
    X = df[list(MODEL_FEATURE_COLUMNS)].copy()
    X["label_distracted"] = 1
    with pytest.raises(FeatureLeakageError, match="Target leakage detected"):
        verify_feature_matrix(X)


def test_feature_matrix_fails_on_provenance_leakage():
    """Verify that provenance/metadata columns trigger FeatureLeakageError."""
    df = make_deterministic_dataset(10)
    X = df[list(MODEL_FEATURE_COLUMNS)].copy()
    X["session_hash"] = "ses_0"
    with pytest.raises(FeatureLeakageError, match="Provenance leakage detected"):
        verify_feature_matrix(X)


def test_feature_matrix_fails_on_unexpected_column():
    """Verify that any unrecognized arbitrary column fails feature validation."""
    df = make_deterministic_dataset(10)
    X = df[list(MODEL_FEATURE_COLUMNS)].copy()
    X["arbitrary_future_leak"] = 42.0
    with pytest.raises(FeatureLeakageError, match="unauthorized columns"):
        verify_feature_matrix(X)


# ==============================================================================
# 2. PREPROCESSING & PIPELINE TESTS
# ==============================================================================

def test_pipeline_construction_and_step_sequence():
    """Verify sklearn Pipeline has SimpleImputer -> StandardScaler -> Classifier."""
    cfg = ModelConfig(model_type="logistic", random_seed=42)
    pipeline = build_pipeline(cfg)
    steps = [name for name, _ in pipeline.steps]
    assert steps == ["imputer", "scaler", "classifier"]


def test_preprocessing_fitted_only_on_training_data():
    """
    Verify that imputer and scaler learn statistics strictly from training data.
    Train on data with known medians, transform test data with extreme values,
    and verify imputer statistics match training medians only.
    """
    df_synth = make_deterministic_dataset(30, seed=10)
    train_df = df_synth[df_synth["split"] == "train"]
    val_df = df_synth[df_synth["split"] == "val"]

    X_train = train_df[list(MODEL_FEATURE_COLUMNS)]
    y_train = train_df["label_distracted"].astype(int)

    cfg = ModelConfig(model_type="logistic", random_seed=42)
    pipeline = build_pipeline(cfg)
    pipeline.fit(X_train, y_train)

    imputer = pipeline.named_steps["imputer"]
    scaler = pipeline.named_steps["scaler"]

    # Imputer statistics must equal median of training features
    expected_medians = X_train.median(numeric_only=False).to_numpy()
    np.testing.assert_allclose(imputer.statistics_, expected_medians, rtol=1e-4)


# ==============================================================================
# 3. TARGET VALIDATION TESTS
# ==============================================================================

def test_null_targets_excluded_from_training(tmp_path: Path):
    """Verify that rows with null targets are safely excluded."""
    df = make_deterministic_dataset(40)
    df.loc[0:4, "label_distracted"] = None  # Make 5 rows null
    out_dir = tmp_path / "model_out"

    cfg = ModelConfig(output_dir=out_dir, random_seed=42)
    result = train_model(cfg, df_override=df)
    assert result.success is True
    assert result.readiness_state == ReadinessState.A_READY


def test_single_class_training_set_fails_safely(tmp_path: Path):
    """Verify that a single-class training split halts cleanly with explicit reason."""
    df = make_deterministic_dataset(30)
    # Force train split to have only class 0
    df.loc[df["split"] == "train", "label_distracted"] = 0
    out_dir = tmp_path / "model_out"

    cfg = ModelConfig(output_dir=out_dir, random_seed=42)
    result = train_model(cfg, df_override=df)

    assert result.success is False
    assert result.readiness_state == ReadinessState.B_INSUFFICIENT_DATA
    assert result.evaluation["data_validity"]["evaluation_not_valid"] is True
    assert "only one class" in result.evaluation["data_validity"]["validity_reason"]


# ==============================================================================
# 4. SPLIT VALIDATION & LEAKAGE PREVENTION TESTS
# ==============================================================================

def test_grouped_user_disjointness_respected():
    """Verify that sessions across splits do not cross boundaries in test fixture."""
    df = make_deterministic_dataset(60)
    train_sessions = set(df[df["split"] == "train"]["session_hash"])
    val_sessions = set(df[df["split"] == "val"]["session_hash"])
    test_sessions = set(df[df["split"] == "test"]["session_hash"])

    assert not (train_sessions & val_sessions), "Train and Val share sessions!"
    assert not (train_sessions & test_sessions), "Train and Test share sessions!"
    assert not (val_sessions & test_sessions), "Val and Test share sessions!"


# ==============================================================================
# 5. REPRODUCIBILITY TEST
# ==============================================================================

def test_training_is_strictly_deterministic(tmp_path: Path):
    """Verify identical seed + data produces bitwise identical model coefficients."""
    df = make_deterministic_dataset(60, seed=123)

    cfg1 = ModelConfig(output_dir=tmp_path / "run1", random_seed=42, model_type="logistic")
    res1 = train_model(cfg1, df_override=df)

    cfg2 = ModelConfig(output_dir=tmp_path / "run2", random_seed=42, model_type="logistic")
    res2 = train_model(cfg2, df_override=df)

    clf1 = res1.pipeline.named_steps["classifier"]
    clf2 = res2.pipeline.named_steps["classifier"]

    np.testing.assert_array_equal(clf1.coef_, clf2.coef_)
    np.testing.assert_array_equal(clf1.intercept_, clf2.intercept_)


# ==============================================================================
# 6. METRIC CALCULATION TESTS
# ==============================================================================

def test_compute_binary_metrics_exact_values():
    """Test metric computation on small deterministic hand-crafted vectors."""
    y_true = [0, 0, 1, 1]
    y_pred = [0, 1, 0, 1]
    y_prob = [0.1, 0.8, 0.4, 0.9]

    # TN=1, FP=1, FN=1, TP=1
    metrics = compute_binary_metrics(y_true, y_pred, y_prob)

    assert metrics["accuracy"] == 0.50
    assert metrics["precision"] == 0.50
    assert metrics["recall"] == 0.50
    assert metrics["f1"] == 0.50
    assert metrics["confusion_matrix"] == [[1, 1], [1, 1]]
    assert metrics["roc_auc"] is not None


# ==============================================================================
# 7. THRESHOLD TUNING TESTS
# ==============================================================================

def test_threshold_tuning_does_not_consume_test_set(tmp_path: Path):
    """Verify threshold tuning optimizes on validation split only."""
    df = make_deterministic_dataset(60, seed=42)
    out_dir = tmp_path / "model_out"

    cfg = ModelConfig(
        output_dir=out_dir,
        random_seed=42,
        tune_threshold=True,
    )
    result = train_model(cfg, df_override=df)

    assert result.success is True
    threshold_info = result.evaluation["threshold"]
    assert threshold_info["tuned"] is True
    assert 0.1 <= threshold_info["classification_threshold"] <= 0.9


# ==============================================================================
# 8. MODEL ARTIFACT SERIALIZATION & RELOADING TESTS
# ==============================================================================

def test_model_artifact_serialization_and_reload(tmp_path: Path):
    """Verify model serializes to joblib, reloads, and produces identical predictions."""
    df = make_deterministic_dataset(60, seed=42)
    out_dir = tmp_path / "model_out"

    cfg = ModelConfig(output_dir=out_dir, random_seed=42, model_type="logistic")
    result = train_model(cfg, df_override=df)

    model_path = result.saved_paths["model_joblib"]
    assert model_path.exists()

    # Reload model
    loaded_pipeline = joblib.load(model_path)
    X_test = df[df["split"] == "test"][list(MODEL_FEATURE_COLUMNS)]

    original_preds = result.pipeline.predict(X_test)
    reloaded_preds = loaded_pipeline.predict(X_test)

    np.testing.assert_array_equal(original_preds, reloaded_preds)


# ==============================================================================
# 9. PRIVACY TESTS
# ==============================================================================

def test_model_artifacts_contain_zero_pii_or_media(tmp_path: Path):
    """Verify that serialized metadata.json and evaluation.json contain no PII or media paths."""
    df = make_deterministic_dataset(60, seed=42)
    out_dir = tmp_path / "model_out"

    cfg = ModelConfig(output_dir=out_dir, random_seed=42)
    result = train_model(cfg, df_override=df)

    for path_key in ("metadata", "evaluation", "feature_schema"):
        p = result.saved_paths[path_key]
        content = p.read_text(encoding="utf-8").lower()
        for forbidden in ("email", "password", "google_id", "camera", "webcam", "image", "video"):
            assert forbidden not in content, f"Found forbidden substring '{forbidden}' in {p.name}"


# ==============================================================================
# 10. NEGATIVE CASES TESTS
# ==============================================================================

def test_zero_rows_dataset_fails_gracefully(tmp_path: Path):
    """Verify empty dataset yields B_INSUFFICIENT_DATA and evaluation_not_valid=True."""
    df_empty = pd.DataFrame(columns=list(ALL_DATASET_COLUMNS))
    out_dir = tmp_path / "model_out"

    cfg = ModelConfig(output_dir=out_dir, random_seed=42)
    result = train_model(cfg, df_override=df_empty)

    assert result.success is False
    assert result.readiness_state == ReadinessState.B_INSUFFICIENT_DATA
    assert result.evaluation["data_validity"]["evaluation_not_valid"] is True


def test_missing_target_column_raises_clear_error(tmp_path: Path):
    """Verify missing target column raises ValueError."""
    df = make_deterministic_dataset(20)
    df = df.drop(columns=["label_distracted"])
    out_dir = tmp_path / "model_out"

    cfg = ModelConfig(output_dir=out_dir, random_seed=42, target="label_distracted")
    with pytest.raises(ValueError, match="Target column 'label_distracted' not found"):
        train_model(cfg, df_override=df)


def test_missing_dataset_file_fails_safely(tmp_path: Path):
    """Verify non-existent dataset path yields C_INVALID state and clear error."""
    non_existent = tmp_path / "does_not_exist"
    out_dir = tmp_path / "model_out"

    cfg = ModelConfig(dataset_path=non_existent, output_dir=out_dir)
    result = train_model(cfg)

    assert result.success is False
    assert result.readiness_state == ReadinessState.C_INVALID
    assert result.evaluation["data_validity"]["evaluation_not_valid"] is True


# ==============================================================================
# 11. CHALLENGER MODEL (RANDOM FOREST) TEST
# ==============================================================================

def test_random_forest_challenger_training(tmp_path: Path):
    """Verify RandomForestClassifier can be trained and evaluated."""
    df = make_deterministic_dataset(60, seed=42)
    out_dir = tmp_path / "rf_out"

    cfg = ModelConfig(output_dir=out_dir, model_type="random_forest", random_seed=42)
    result = train_model(cfg, df_override=df)

    assert result.success is True
    assert result.readiness_state == ReadinessState.A_READY
    assert result.metadata["model_class"] == "RandomForestClassifier"
    assert result.evaluation["interpretability"]["available"] is True


# ==============================================================================
# 12. RULE DETECTOR BASELINE COMPARISON TEST
# ==============================================================================

def test_rule_baseline_comparison_generation(tmp_path: Path):
    """Verify rule comparison module produces side-by-side evaluation metrics."""
    df = make_deterministic_dataset(60, seed=42)
    out_dir = tmp_path / "comp_out"

    cfg = ModelConfig(output_dir=out_dir, random_seed=42)
    result = train_model(cfg, df_override=df)

    comp = result.evaluation.get("rule_comparison")
    assert comp is not None
    assert comp["comparison_available"] is True
    assert "ml_model" in comp
    assert "rule_baseline" in comp
    assert "delta_f1" in comp


# ==============================================================================
# 13. ADDITIONAL NEGATIVE CASES & CLI ENTRYPOINT
# ==============================================================================

def test_infinite_feature_values_trigger_leakage_error():
    """Verify that infinite feature values fail validation."""
    df = make_deterministic_dataset(10)
    X = df[list(MODEL_FEATURE_COLUMNS)].copy()
    X.loc[0, "head_pitch"] = np.inf
    with pytest.raises(FeatureLeakageError, match="contains infinite values"):
        verify_feature_matrix(X)


def test_missing_feature_column_triggers_leakage_error():
    """Verify that omitting an expected model feature fails validation."""
    df = make_deterministic_dataset(10)
    X = df[list(MODEL_FEATURE_COLUMNS)].copy()
    X = X.drop(columns=["head_pitch"])
    with pytest.raises(FeatureLeakageError, match="missing 1 expected features"):
        verify_feature_matrix(X)


def test_one_class_test_set_handles_gracefully(tmp_path: Path):
    """Verify that a test set with only one class does not crash and computes safe metrics."""
    df = make_deterministic_dataset(60, seed=42)
    # Force test split to have only class 0
    df.loc[df["split"] == "test", "label_distracted"] = 0
    out_dir = tmp_path / "model_out"

    cfg = ModelConfig(output_dir=out_dir, random_seed=42)
    result = train_model(cfg, df_override=df)

    assert result.success is True
    test_metrics = result.evaluation["metrics"]["test"]
    assert test_metrics["roc_auc"] is None  # ROC-AUC cannot be calculated for 1 class
    assert test_metrics["total_samples"] > 0


def test_cli_main_execution(tmp_path: Path):
    """Verify CLI main entrypoint executes cleanly and produces artifacts."""
    from ml.models.phase13.cli import main

    df = make_deterministic_dataset(60, seed=42)
    dataset_file = tmp_path / "dataset.parquet"
    df.to_parquet(dataset_file)
    out_dir = tmp_path / "cli_model_out"

    exit_code = main([
        "--dataset", str(dataset_file),
        "--output", str(out_dir),
        "--model", "logistic",
        "--seed", "42",
    ])
    assert exit_code == 0
    assert (out_dir / "metadata.json").exists()
    assert (out_dir / "evaluation.json").exists()
    assert (out_dir / "feature_schema.json").exists()
    assert (out_dir / "model.joblib").exists()


# ==============================================================================
# 14. AUDIT CORRECTION & LABEL PROVENANCE TESTS
# ==============================================================================

def test_insufficient_data_does_not_produce_model_joblib(tmp_path: Path):
    """Verify that insufficient data produces NO model.joblib artifact and sets explicit metadata."""
    df_synth = make_deterministic_dataset(20)
    # Remove all train rows
    df_no_train = df_synth[df_synth["split"] != "train"].copy()
    out_dir = tmp_path / "model_out"

    # Pre-create a dummy model.joblib to verify it gets cleaned up
    out_dir.mkdir(parents=True, exist_ok=True)
    dummy_file = out_dir / "model.joblib"
    dummy_file.write_text("stale_binary")

    cfg = ModelConfig(output_dir=out_dir, random_seed=42)
    result = train_model(cfg, df_override=df_no_train)

    assert result.success is False
    assert result.readiness_state == ReadinessState.B_INSUFFICIENT_DATA
    assert not (out_dir / "model.joblib").exists()
    assert "model_joblib" not in result.saved_paths
    assert result.metadata["model_status"] == "not_trained"
    assert result.metadata["model_artifact_created"] is False
    assert result.metadata["model_artifact_path"] is None
    assert result.evaluation["model_validity"]["model_status"] == "not_trained"
    assert result.evaluation["model_validity"]["model_artifact_created"] is False


def test_canonical_distracted_dir_contains_no_model_joblib():
    """Verify canonical experiment output directory contains NO model.joblib binary."""
    canonical_dir = Path("ml/models/phase13/distracted")
    if canonical_dir.exists():
        assert not (canonical_dir / "model.joblib").exists(), (
            "Found model.joblib in canonical output directory when real model training is blocked!"
        )


def test_target_label_source_accounting():
    """Verify that eligible rows in dataset_v1 derive from detector monitoring and events without human labels."""
    dataset_parquet = Path("data/datasets/phase12/dataset_v1/dataset.parquet")
    if not dataset_parquet.exists():
        pytest.skip("dataset_v1 parquet artifact not found")

    df = pd.read_parquet(dataset_parquet)
    eligible = df[(df["is_calibration"] != True) & (df["is_excluded"] != True) & (df["label_distracted"].notna())]

    counts = eligible["label_source"].value_counts().to_dict()
    assert counts.get("detector_state_monitoring") == 1289
    assert counts.get("detector_event") == 307
    assert counts.get("human_confirmed_detection", 0) == 0
    assert counts.get("human_rejected_detector_event", 0) == 0


def test_detector_derived_labels_not_described_as_independent_ground_truth(tmp_path: Path):
    """Verify target provenance explicitly flags detector-derived pseudo-label semantics."""
    df_synth = make_deterministic_dataset(30)
    out_dir = tmp_path / "model_out"

    cfg = ModelConfig(output_dir=out_dir, random_seed=42)
    result = train_model(cfg, df_override=df_synth)

    provenance = result.evaluation.get("target_provenance")
    assert provenance is not None
    assert "detector_derived_count" in provenance
    assert "independent_human_validation_available" in provenance
    assert "pseudo-labels" in provenance["rule_comparison_semantics"]
    assert "NOT represent independent distraction-detection accuracy" in provenance["rule_comparison_semantics"]


def test_reports_and_metadata_use_anonymized_user_aliases(tmp_path: Path):
    """Verify that metadata and evaluation manifests contain zero raw database user UUIDs."""
    import re
    df_synth = make_deterministic_dataset(30)
    out_dir = tmp_path / "model_out"

    cfg = ModelConfig(output_dir=out_dir, random_seed=42)
    result = train_model(cfg, df_override=df_synth)

    uuid_pattern = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)

    meta_str = json.dumps(result.metadata)
    eval_str = json.dumps(result.evaluation)

    assert not uuid_pattern.search(meta_str), "Found raw UUID in metadata!"
    assert not uuid_pattern.search(eval_str), "Found raw UUID in evaluation manifest!"


