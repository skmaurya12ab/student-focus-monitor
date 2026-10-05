"""Main pipeline orchestrator and CLI entry point for building ML datasets."""

from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
import pandas as pd

# Ensure backend directory is in sys.path
backend_path = Path(__file__).resolve().parents[2] / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from ml.dataset.alignment import align_events_to_telemetry
from ml.dataset.config import (
    ALL_DATASET_COLUMNS,
    CANONICAL_CATEGORIES,
    DATASET_VERSION,
    DETECTOR_VERSION,
    DIAGNOSTIC_COLUMNS,
    FEATURE_COLUMNS_ALLOWLIST,
    FEATURE_SCHEMA_VERSION,
    METADATA_COLUMNS,
    MODEL_FEATURE_COLUMNS,
    PROVENANCE_COLUMNS,
    TARGET_COLUMNS,
    DatasetConfig,
)
from ml.dataset.export import export_dataset
from ml.dataset.extract import DatasetSources, extract_from_database
from ml.dataset.features import extract_diagnostic_features, flatten_telemetry_features
from ml.dataset.feedback import build_feedback_index
from ml.dataset.labels import resolve_sample_labels
from ml.dataset.manifest import (
    build_manifest,
    build_quality_report,
    build_schema_specification,
    build_split_summary,
)
from ml.dataset.splits import compute_grouped_user_splits
from ml.dataset.synthetic import generate_synthetic_sources
from ml.dataset.validation import (
    DataQualityValidationError,
    validate_data_split_leakage,
    validate_feature_target_leakage,
    validate_frame_monotonicity,
    validate_leakage,
    validate_no_nan_or_inf,
    validate_privacy,
    validate_ranges,
    validate_target_feature_separation,
)


@dataclass
class DatasetBuildResult:
    """Artifacts and quality metrics produced by the dataset build pipeline."""

    dataframe: pd.DataFrame
    manifest: dict[str, Any]
    quality_report: dict[str, Any]
    schema_specification: dict[str, Any]
    split_summary: dict[str, Any]
    exported_paths: dict[str, Path]


def hash_token(identifier: Any, prefix: str = "ses") -> str:
    """Produce non-reversible deterministic short hash token for safe logging/metadata."""
    raw = str(identifier).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()[:12]
    return f"{prefix}_{digest}"


def build_ml_dataset(
    sources: DatasetSources,
    config: Optional[DatasetConfig] = None,
) -> DatasetBuildResult:
    """
    Execute the authoritative end-to-end dataset pipeline:
    1. Validation of configuration and feature/target separation
    2. Event-telemetry temporal alignment
    3. Feedback indexing and deduplication
    4. Grouped user-level splitting
    5. Allowlisted feature flattening & missing value indicators
    6. Multi-label generation & deterministic conflict resolution
    7. Calibration sample filtering
    8. Rigorous privacy, NaN/Inf, and data quality validation
    9. Metadata and quality report generation
    10. Columnar Parquet export
    """
    cfg = config or DatasetConfig()
    cfg.validate()

    # Step 1: Pre-flight validation
    validate_target_feature_separation()

    warnings: list[str] = []

    # Step 2: Temporal event alignment
    alignment_result = align_events_to_telemetry(
        sources.telemetry_samples, sources.detection_events
    )
    if alignment_result.unmatched_events:
        warnings.append(
            f"{len(alignment_result.unmatched_events)} detection event(s) had no overlapping telemetry samples."
        )

    # Step 3: Feedback indexing
    feedback_idx = build_feedback_index(sources.feedbacks)

    # Step 4: Grouped user-level splitting
    split_assignment = compute_grouped_user_splits(sources.sessions, cfg)
    if split_assignment.warning:
        warnings.append(split_assignment.warning)

    # Step 5 & 6: Process samples, flatten features, resolve labels
    rows: list[dict[str, Any]] = []
    excluded_count = 0

    # Map session to user for leakage validation
    session_to_user = {s.id: s.user_id for s in sources.sessions.values()}

    for sample in sources.telemetry_samples:
        session = sources.sessions.get(sample.session_id)
        if not session:
            excluded_count += 1
            continue

        overlapping = alignment_result.sample_to_events.get(sample.id, [])
        sample_labels = resolve_sample_labels(
            sample=sample,
            overlapping_events=overlapping,
            feedback_index=feedback_idx,
            config=cfg,
        )

        if sample_labels.is_excluded:
            excluded_count += 1
            continue

        # Extract allowlisted model features (strictly sensor & motion measurements)
        features_row = flatten_telemetry_features(sample)

        # Assemble full dataset row
        row: dict[str, Any] = dict(features_row)

        # Attach multi-label category targets
        for cat in CANONICAL_CATEGORIES:
            row[f"label_{cat}"] = sample_labels.category_labels.get(cat)

        row["focus_state_label"] = sample_labels.focus_state_label
        row["label_distracted"] = sample_labels.label_distracted

        # Attach provenance / metadata (strictly non-PII, no raw user_id!)
        split_name = split_assignment.session_splits.get(sample.session_id, "all")
        row["sample_id"] = str(sample.id)
        row["session_hash"] = hash_token(sample.session_id, prefix="ses")
        row["frame_index"] = sample.frame_index
        row["sampled_at"] = sample.sampled_at.isoformat()
        row["detector_version"] = sample.detector_version
        row["feature_schema_version"] = sample.feature_schema_version
        row["dataset_version"] = cfg.dataset_version
        row["split"] = split_name
        row["label_source"] = sample_labels.label_source
        row["label_quality"] = sample_labels.label_quality
        row["is_labeled"] = sample_labels.is_labeled
        row["is_calibration"] = sample_labels.is_calibration
        row["is_excluded"] = sample_labels.is_excluded
        row["exclusion_reason"] = sample_labels.exclusion_reason

        # Attach diagnostic features (retained detector outputs, not in model feature matrix)
        diagnostic_row = extract_diagnostic_features(sample)
        row.update(diagnostic_row)

        rows.append(row)

    if not rows:
        warnings.append(
            "Canonical dataset contains zero eligible samples; train/validation/test split is not valid."
        )
        df = pd.DataFrame(columns=list(ALL_DATASET_COLUMNS))
    else:
        # Convert to DataFrame with strict column ordering
        df = pd.DataFrame(rows)
        for col in ALL_DATASET_COLUMNS:
            if col not in df.columns:
                df[col] = None
        df = df[list(ALL_DATASET_COLUMNS)]

    # Step 7: Rigorous quality & privacy validation
    validate_no_nan_or_inf(df)
    privacy_stats = validate_privacy(df)
    validate_ranges(df)
    validate_data_split_leakage(df, session_to_user)
    validate_frame_monotonicity(df)

    # Step 8: Build metadata documents
    alignment_stats = {
        "total_events": alignment_result.total_events_count,
        "matched_events": alignment_result.matched_events_count,
        "unmatched_events": len(alignment_result.unmatched_events),
    }
    feedback_stats = {
        "total_feedback": feedback_idx.total_count,
        "correct_detection": feedback_idx.correct_detection_count,
        "false_positive": feedback_idx.false_positive_count,
        "missed_detection": feedback_idx.missed_detection_count,
        "other": feedback_idx.other_count,
    }

    manifest = build_manifest(
        df=df,
        config=cfg,
        split_assignment=split_assignment,
        total_raw_samples=len(sources.telemetry_samples),
        excluded_samples=excluded_count,
        total_raw_sessions=len(sources.sessions),
        total_raw_users=len(sources.users),
        warnings=warnings,
    )
    quality_report = build_quality_report(
        df=df,
        total_raw_samples=len(sources.telemetry_samples),
        excluded_samples=excluded_count,
        total_raw_sessions=len(sources.sessions),
        total_raw_users=len(sources.users),
        split_assignment=split_assignment,
        alignment_stats=alignment_stats,
        feedback_stats=feedback_stats,
        privacy_stats=privacy_stats,
        warnings=warnings,
    )
    schema_spec = build_schema_specification()
    split_summary = build_split_summary(df, split_assignment)

    # Step 9: Export Parquet and metadata
    exported_paths = export_dataset(
        df=df,
        manifest=manifest,
        quality_report=quality_report,
        schema_spec=schema_spec,
        split_summary=split_summary,
        output_dir=cfg.output_dir,
        export_csv=cfg.export_csv,
    )

    return DatasetBuildResult(
        dataframe=df,
        manifest=manifest,
        quality_report=quality_report,
        schema_specification=schema_spec,
        split_summary=split_summary,
        exported_paths=exported_paths,
    )


def main() -> None:
    """Command-line interface entry point."""
    parser = argparse.ArgumentParser(
        description="Build reproducible, leakage-safe ML dataset from Student Focus Monitor telemetry & feedback."
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("data/datasets/phase12/dataset_v1"),
        help="Output directory for parquet and metadata files",
    )
    parser.add_argument(
        "--dataset-version",
        type=str,
        default=DATASET_VERSION,
        help="Dataset version identifier (default: dataset_v1)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic user splitting (default: 42)",
    )
    parser.add_argument(
        "--include-calibration",
        action="store_true",
        default=False,
        help="Include initial calibration samples in export (default: False)",
    )
    parser.add_argument(
        "--missed-detection-window",
        type=float,
        default=0.0,
        help="Temporal attribution window in seconds for missed detection feedback (default: 0.0)",
    )
    parser.add_argument(
        "--train-ratio",
        type=float,
        default=0.70,
        help="Training split ratio (default: 0.70)",
    )
    parser.add_argument(
        "--val-ratio",
        type=float,
        default=0.15,
        help="Validation split ratio (default: 0.15)",
    )
    parser.add_argument(
        "--test-ratio",
        type=float,
        default=0.15,
        help="Test split ratio (default: 0.15)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Filter sessions started on or after ISO date string",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="Filter sessions started on or before ISO date string",
    )
    parser.add_argument(
        "--export-csv",
        action="store_true",
        default=False,
        help="Also export dataset as CSV for manual inspection",
    )
    parser.add_argument(
        "--synthetic",
        action="store_true",
        default=False,
        help="Use deterministic synthetic fixtures instead of querying PostgreSQL database",
    )

    args = parser.parse_args()

    config = DatasetConfig(
        output_dir=args.output,
        dataset_version=args.dataset_version,
        random_seed=args.seed,
        include_calibration=args.include_calibration,
        missed_detection_window_sec=args.missed_detection_window,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        start_date=args.start_date,
        end_date=args.end_date,
        export_csv=args.export_csv,
    )

    print("=" * 60)
    print(" STUDENT FOCUS MONITOR — ML DATASET PIPELINE (PHASE 12)")
    print("=" * 60)
    print(f"Output directory : {config.output_dir}")
    print(f"Dataset version  : {config.dataset_version}")
    print(f"Random seed      : {config.random_seed}")
    print(f"Split ratios     : {config.train_ratio} / {config.val_ratio} / {config.test_ratio}")
    print(f"Calibration data : {'Included' if config.include_calibration else 'Excluded (default)'}")
    print(f"Data source      : {'Synthetic test fixtures' if args.synthetic else 'PostgreSQL'}")
    print("-" * 60)

    try:
        if args.synthetic:
            sources = generate_synthetic_sources(num_users=3, samples_per_session=25, seed=args.seed)
        else:
            sources = extract_from_database(config=config)

        print(f"Read {len(sources.telemetry_samples)} telemetry samples across {len(sources.sessions)} sessions.")
        print("Executing pipeline...")

        result = build_ml_dataset(sources=sources, config=config)

        print("\n✓ DATASET PIPELINE COMPLETED SUCCESSFULLY")
        print("-" * 60)
        print(f"Total exported samples : {len(result.dataframe)}")
        print(f"Model feature columns  : {len(MODEL_FEATURE_COLUMNS)}")
        print(f"Target columns count   : {len(TARGET_COLUMNS)}")
        print(f"Provenance columns     : {len(PROVENANCE_COLUMNS)}")
        print(f"Diagnostic columns     : {len(DIAGNOSTIC_COLUMNS)}")
        print(f"Total columns count    : {len(ALL_DATASET_COLUMNS)}")
        print(f"Split validity         : {result.split_summary.get('is_split_valid')}")
        if result.manifest.get("warnings"):
            print("\nWarnings:")
            for w in result.manifest["warnings"]:
                print(f"  [!] {w}")
        print("\nGenerated Artifacts:")
        for name, path in result.exported_paths.items():
            print(f"  • {name:16}: {path}")
        print("=" * 60)

    except Exception as exc:
        print(f"\n[ERROR] Dataset pipeline failed: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
