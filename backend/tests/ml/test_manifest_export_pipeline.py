"""Tests for end-to-end dataset pipeline build, manifest generation, and Parquet/CSV export."""

from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq
import pytest

from ml.dataset.build import build_ml_dataset
from ml.dataset.config import (
    ALL_DATASET_COLUMNS,
    DATASET_VERSION,
    DETECTOR_VERSION,
    DIAGNOSTIC_COLUMNS,
    FEATURE_SCHEMA_VERSION,
    MODEL_FEATURE_COLUMNS,
    PROVENANCE_COLUMNS,
    TARGET_COLUMNS,
    DatasetConfig,
)
from ml.dataset.synthetic import generate_synthetic_sources


def test_build_ml_dataset_end_to_end(tmp_path: Path):
    sources = generate_synthetic_sources(num_users=3, samples_per_session=20, seed=42)
    output_dir = tmp_path / "dataset_out"

    config = DatasetConfig(
        output_dir=output_dir,
        dataset_version=DATASET_VERSION,
        random_seed=42,
        include_calibration=False,
        export_csv=True,
    )

    result = build_ml_dataset(sources=sources, config=config)

    # 1. Output files exist
    assert (output_dir / "dataset.parquet").exists()
    assert (output_dir / "dataset.csv").exists()
    assert (output_dir / "manifest.json").exists()
    assert (output_dir / "quality_report.json").exists()
    assert (output_dir / "schema.json").exists()
    assert (output_dir / "split_summary.json").exists()

    # 2. Check Parquet integrity
    parquet_table = pq.read_table(output_dir / "dataset.parquet")
    assert parquet_table.num_rows == len(result.dataframe)
    assert set(parquet_table.column_names) == set(ALL_DATASET_COLUMNS)

    # 3. Check CSV integrity
    csv_df = pd.read_csv(output_dir / "dataset.csv")
    assert len(csv_df) == len(result.dataframe)
    assert set(csv_df.columns) == set(ALL_DATASET_COLUMNS)

    # 4. Check Manifest JSON
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["dataset_version"] == DATASET_VERSION
    assert manifest["detector_version"] == DETECTOR_VERSION
    assert manifest["feature_schema_version"] == FEATURE_SCHEMA_VERSION
    assert manifest["random_seed"] == 42
    assert manifest["is_split_valid"] is True
    assert manifest["include_calibration"] is False
    assert manifest["row_counts"]["exported_samples"] == len(result.dataframe)

    # 5. Check Quality Report JSON
    quality_report = json.loads((output_dir / "quality_report.json").read_text(encoding="utf-8"))
    assert quality_report["scientific_validity"]["pipeline_valid"] is True
    assert quality_report["scientific_validity"]["split_valid"] is True
    assert "categories" in quality_report["label_distribution"]

    # 5b. Check Split Summary JSON
    split_summary = json.loads((output_dir / "split_summary.json").read_text(encoding="utf-8"))
    assert split_summary["is_split_valid"] is True

    # 6. Check Schema Spec JSON
    schema_spec = json.loads((output_dir / "schema.json").read_text(encoding="utf-8"))
    assert schema_spec["dataset_version"] == DATASET_VERSION
    assert schema_spec["total_columns"] == len(ALL_DATASET_COLUMNS)
    assert schema_spec["model_feature_columns_count"] == len(MODEL_FEATURE_COLUMNS)
    assert schema_spec["target_columns_count"] == len(TARGET_COLUMNS)
    assert schema_spec["provenance_columns_count"] == len(PROVENANCE_COLUMNS)
    assert schema_spec["diagnostic_columns_count"] == len(DIAGNOSTIC_COLUMNS)

    # Verify column categories are unambiguous
    for col in MODEL_FEATURE_COLUMNS:
        assert schema_spec["columns"][col]["category"] == "feature"
    for col in TARGET_COLUMNS:
        assert schema_spec["columns"][col]["category"] == "target"
    for col in PROVENANCE_COLUMNS:
        assert schema_spec["columns"][col]["category"] == "provenance"
    for col in DIAGNOSTIC_COLUMNS:
        assert schema_spec["columns"][col]["category"] == "diagnostic"


def test_include_calibration_toggle(tmp_path: Path):
    sources = generate_synthetic_sources(num_users=3, samples_per_session=20, seed=42)

    # Default: calibration excluded
    cfg_excluded = DatasetConfig(output_dir=tmp_path / "out_excl", include_calibration=False)
    res_excluded = build_ml_dataset(sources=sources, config=cfg_excluded)

    # Opt-in: calibration included
    cfg_included = DatasetConfig(output_dir=tmp_path / "out_incl", include_calibration=True)
    res_included = build_ml_dataset(sources=sources, config=cfg_included)

    # When calibration is included, total rows must be strictly greater
    assert len(res_included.dataframe) > len(res_excluded.dataframe)
    assert (res_included.dataframe["is_calibration"] == True).any()
    assert not (res_excluded.dataframe["is_calibration"] == True).any()


def test_all_calibration_samples_excluded_generates_valid_empty_artifact(tmp_path: Path):
    """
    Issue 2 Regression Test:
    When input data contains only calibration telemetry and include_calibration=False,
    the pipeline must not crash; it must produce a valid 0-row Parquet artifact,
    valid schema.json, and honest manifest and quality_report reporting pipeline_valid=True
    and sufficient_data=False.
    """
    from datetime import datetime, timezone
    import uuid
    from ml.dataset.extract import ExtractedSession, ExtractedTelemetrySample, DatasetSources

    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    now = datetime(2026, 10, 5, 12, 0, 0, tzinfo=timezone.utc)

    session = ExtractedSession(
        id=session_id,
        user_id=user_id,
        status="completed",
        started_at=now,
        ended_at=now,
        total_duration_seconds=10.0,
        focused_seconds=10.0,
        distracted_seconds=0.0,
        away_seconds=0.0,
        focus_score=100.0,
        detector_version="v4",
        feature_schema_version="telemetry_v2",
    )

    # Sample inside calibration window (first 5 seconds, calibration_complete=False)
    calib_sample = ExtractedTelemetrySample(
        id=uuid.uuid4(),
        session_id=session_id,
        sampled_at=now,
        frame_index=1,
        detector_version="v4",
        feature_schema_version="telemetry_v2",
        head_pitch=0.0,
        head_yaw=0.0,
        head_roll=0.0,
        ear=0.3,
        mar=0.2,
        min_hand_cheek_distance=None,
        shoulder_z=None,
        face_present=True,
        pose_present=True,
        hand_count=0,
        focus_state="calibrating",
        features={"calibration_complete": False},
    )

    sources = DatasetSources(
        users={user_id: user_id},
        sessions={session_id: session},
        telemetry_samples=[calib_sample],
        detection_events=[],
        feedbacks=[],
    )

    output_dir = tmp_path / "out_empty_calib"
    cfg = DatasetConfig(output_dir=output_dir, include_calibration=False)

    result = build_ml_dataset(sources=sources, config=cfg)

    # Must produce valid 0-row DataFrame
    assert len(result.dataframe) == 0
    assert (output_dir / "dataset.parquet").exists()
    assert (output_dir / "manifest.json").exists()
    assert (output_dir / "quality_report.json").exists()
    assert (output_dir / "schema.json").exists()

    # Read back Parquet and verify column schema
    read_table = pq.read_table(output_dir / "dataset.parquet")
    assert read_table.num_rows == 0
    assert set(read_table.column_names) == set(ALL_DATASET_COLUMNS)

    # Verify manifest accounting
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["row_counts"]["exported_samples"] == 0
    assert manifest["row_counts"]["excluded_samples"] == 1
    assert manifest["include_calibration"] is False
    assert manifest["is_split_valid"] is False

    # Verify quality report distinction
    quality_report = json.loads((output_dir / "quality_report.json").read_text(encoding="utf-8"))
    assert quality_report["scientific_validity"]["pipeline_valid"] is True
    assert quality_report["scientific_validity"]["split_valid"] is False
    assert quality_report["scientific_validity"]["label_valid"] is False
    assert quality_report["scientific_validity"]["sufficient_data"] is False

    # Verify split summary reporting
    split_summary = json.loads((output_dir / "split_summary.json").read_text(encoding="utf-8"))
    assert split_summary["is_split_valid"] is False
    assert "zero eligible samples" in split_summary["warning"]

