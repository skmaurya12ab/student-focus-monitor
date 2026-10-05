"""Dataset exporter for Parquet, metadata JSONs, and optional CSV."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import pandas as pd
import pyarrow.parquet as pq


def export_dataset(
    df: pd.DataFrame,
    manifest: dict[str, Any],
    quality_report: dict[str, Any],
    schema_spec: dict[str, Any],
    split_summary: dict[str, Any],
    output_dir: Path,
    export_csv: bool = False,
) -> dict[str, Path]:
    """
    Write dataset files and metadata to disk.
    Verifies that the generated Parquet file is valid and can be loaded back cleanly.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Clean up stale CSV if not requesting CSV export
    if not export_csv:
        stale_csv = output_dir / "dataset.csv"
        if stale_csv.exists():
            stale_csv.unlink()

    artifacts: dict[str, Path] = {}

    # 1. Export Parquet
    parquet_path = output_dir / "dataset.parquet"
    df.to_parquet(parquet_path, engine="pyarrow", index=False)
    artifacts["dataset_parquet"] = parquet_path

    # Verify Parquet readback
    read_table = pq.read_table(parquet_path)
    if read_table.num_rows != len(df):
        raise IOError(
            f"Parquet verification failed: written rows ({len(df)}) != read rows ({read_table.num_rows})"
        )

    # 2. Export Optional CSV
    if export_csv:
        csv_path = output_dir / "dataset.csv"
        df.to_csv(csv_path, index=False)
        artifacts["dataset_csv"] = csv_path

    # 3. Export Manifest
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    artifacts["manifest"] = manifest_path

    # 4. Export Quality Report
    quality_report_path = output_dir / "quality_report.json"
    quality_report_path.write_text(json.dumps(quality_report, indent=2), encoding="utf-8")
    artifacts["quality_report"] = quality_report_path

    # 5. Export Schema Specification
    schema_path = output_dir / "schema.json"
    schema_path.write_text(json.dumps(schema_spec, indent=2), encoding="utf-8")
    artifacts["schema"] = schema_path

    # 6. Export Split Summary
    split_summary_path = output_dir / "split_summary.json"
    split_summary_path.write_text(json.dumps(split_summary, indent=2), encoding="utf-8")
    artifacts["split_summary"] = split_summary_path

    return artifacts
