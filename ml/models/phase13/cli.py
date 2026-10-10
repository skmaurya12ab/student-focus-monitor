"""Command-line interface for Phase 13 Offline ML Baseline."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from ml.models.phase13.config import (
    DEFAULT_DATASET_PATH,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_PRIMARY_TARGET,
    ModelConfig,
    ReadinessState,
)
from ml.models.phase13.train import train_model


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for Phase 13 model training and evaluation."""
    parser = argparse.ArgumentParser(
        description="Phase 13: Offline ML Baseline Training and Evaluation",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help="Path to Phase 12 dataset directory or Parquet file.",
    )
    parser.add_argument(
        "--target",
        type=str,
        default=DEFAULT_PRIMARY_TARGET,
        help="Canonical target column to predict (e.g. label_distracted, label_phone_use).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory to serialize model artifact and evaluation manifest.",
    )
    parser.add_argument(
        "--model",
        choices=["logistic", "random_forest"],
        default="logistic",
        help="Model algorithm to train (default baseline is logistic regression).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Deterministic random seed for reproducibility.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.50,
        help="Fixed classification probability threshold.",
    )
    parser.add_argument(
        "--tune-threshold",
        action="store_true",
        help="Tune classification threshold on validation set (never touches test set).",
    )
    parser.add_argument(
        "--class-weight",
        choices=["none", "balanced"],
        default="none",
        help="Class weight handling strategy.",
    )
    parser.add_argument(
        "--max-iter",
        type=int,
        default=1000,
        help="Maximum solver iterations for logistic regression.",
    )

    return parser.parse_args(args)


def main(args: list[str] | None = None) -> int:
    """CLI execution entrypoint."""
    parsed = parse_args(args)

    config = ModelConfig(
        dataset_path=parsed.dataset,
        output_dir=parsed.output,
        target=parsed.target,
        model_type=parsed.model,
        random_seed=parsed.seed,
        classification_threshold=parsed.threshold,
        tune_threshold=parsed.tune_threshold,
        class_weight="balanced" if parsed.class_weight == "balanced" else None,
        max_iter=parsed.max_iter,
    )

    print("=" * 60)
    print(" STUDENT FOCUS MONITOR — FIRST ML MODEL (PHASE 13)")
    print("=" * 60)
    print(f"Dataset path     : {config.dataset_path}")
    print(f"Target column    : {config.target}")
    print(f"Model algorithm  : {config.model_type}")
    print(f"Random seed      : {config.random_seed}")
    print(f"Output directory : {config.output_dir}")
    print("-" * 60)

    result = train_model(config)

    print("\nDATA READINESS GATE:")
    print(f"  Status: {result.readiness_state.value}")

    if result.warning_messages:
        print("\nWarnings / Notes:")
        for w in result.warning_messages:
            print(f"  [!] {w}")

    if result.success and result.readiness_state == ReadinessState.A_READY:
        print("\n✓ MODEL TRAINING COMPLETED SUCCESSFULLY")
        test_m = result.evaluation.get("metrics", {}).get("test")
        if test_m and test_m.get("f1") is not None:
            print("-" * 60)
            print("TEST SET EVALUATION METRICS (UNSEEN USERS):")
            print(f"  Precision : {test_m['precision']:.4f}")
            print(f"  Recall    : {test_m['recall']:.4f}")
            print(f"  F1 Score  : {test_m['f1']:.4f}")
            print(f"  Accuracy  : {test_m['accuracy']:.4f}")
            if test_m.get("roc_auc") is not None:
                print(f"  ROC-AUC   : {test_m['roc_auc']:.4f}")
            if test_m.get("pr_auc") is not None:
                print(f"  PR-AUC    : {test_m['pr_auc']:.4f}")
            print(f"  Confusion : {test_m['confusion_matrix']}")
        else:
            print("\n  [i] Training completed, but test split metrics unavailable.")
    else:
        print("\nℹ NOTICE:")
        print("  Pipeline execution completed safely, but real data is currently")
        print("  insufficient for a scientifically defensible model evaluation.")

    print("\nSaved Artifacts:")
    for name, p in result.saved_paths.items():
        print(f"  • {name:15}: {p}")

    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
