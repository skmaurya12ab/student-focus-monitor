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
    FEATURE_SCHEMA_VERSION,
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

    # 6. Check Schema Spec JSON
    schema_spec = json.loads((output_dir / "schema.json").read_text(encoding="utf-8"))
    assert schema_spec["dataset_version"] == DATASET_VERSION
    assert schema_spec["total_columns"] == len(ALL_DATASET_COLUMNS)


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
