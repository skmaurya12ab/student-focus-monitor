# ML Dataset Pipeline Architecture & Specification (Phase 12)

> **Phase 12 Status**: Implemented & Verified.  
> **Phase Boundary Notice**: Phase 12 implements **only** the data extraction, preprocessing, label construction, leakage-safe splitting, and columnar export pipeline. It does **not** train any machine learning model, fit scikit-learn classifiers, run ML inference, or alter production rule-based detection. Model development is strictly deferred to **Phase 13**.

---

## 1. Executive Overview

The Machine Learning Dataset Pipeline converts authoritative PostgreSQL detection telemetry (`telemetry_samples`), discrete distraction events (`detection_events`), and voluntary human labeling (`session_feedback`) into a clean, reproducible, leakage-safe supervised-learning dataset.

### Core Objectives
1. **Trustworthy Movement Telemetry**: Preserve raw numerical measurements, baseline-relative geometric deltas, motion velocities, and rule/tracker activation states.
2. **Explicit Human Provenance**: Incorporate Phase 11 voluntary student labels (`correct_detection`, `false_positive`, `missed_detection`, `other`) using an explicit conflict resolution hierarchy.
3. **Leakage-Safe User Grouping**: Partition train, validation, and test splits strictly at the **user** boundary, preventing session or adjacent-sample contamination.
4. **Columnar Export**: Output Parquet files (`dataset.parquet`) alongside detailed schema specifications, reproducibility manifests, and scientific quality reports.
5. **Absolute Privacy Preservation**: Zero raw media bytes (images, video, audio, screenshots, camera paths) and zero sensitive authentication PII enter the dataset.

---

## 2. Pipeline Architecture & Data Flow

```text
PostgreSQL Database
 ├── study_sessions (Session boundaries, user grouping)
 ├── telemetry_samples (v4, telemetry_v2 numerical snapshots)
 ├── detection_events (Discrete distraction interval ground-truth)
 └── session_feedback (Human feedback: correct, false_positive, missed, other)
       ↓
[ extract.py ] Read-only SQL extraction
       ↓
[ alignment.py ] Deterministic event ↔ telemetry temporal matching
       ↓
[ feedback.py ] Feedback indexing & deduplication
       ↓
[ splits.py ] Grouped user-level splitting (no user/session leakage)
       ↓
[ features.py ] Strict allowlist flattening & missing value indicators
       ↓
[ labels.py ] Multi-label targets & deterministic conflict resolution
       ↓
[ validation.py ] Privacy audit, NaN/Inf rejection, range & monotonicity checks
       ↓
[ manifest.py ] Manifest, Quality Report, Schema Spec, Split Summary
       ↓
[ export.py ]
 ├── dataset.parquet (PyArrow columnar format)
 ├── manifest.json (Seed, version, counts, configuration)
 ├── quality_report.json (Class distribution, null rates, validity)
 ├── schema.json (Column metadata catalog)
 ├── split_summary.json (Train/val/test breakdown)
 └── dataset.csv (Optional inspection artifact)
```

---

## 3. Dataset Granularity

The canonical dataset granularity is **ONE ROW = ONE TELEMETRY SAMPLE**:
- Does not resample or interpolate synthetic time steps onto an artificial grid.
- Preserves the authoritative ~5 Hz sampling cadence established by `BufferedTelemetrySink` during active study monitoring.

---

## 4. Column Classification Schema (84 Total Columns)

To eliminate target leakage while preserving full diagnostic visibility, all dataset columns are explicitly separated into four distinct categories:

1. **MODEL INPUT FEATURES** (`category = "feature"`, 38 columns)
2. **TARGET / LABEL COLUMNS** (`category = "target"`, 8 columns)
3. **PROVENANCE METADATA** (`category = "provenance"`, 14 columns)
4. **DIAGNOSTIC DETECTOR OUTPUTS** (`category = "diagnostic"`, 24 columns)

The canonical model feature matrix intended for Phase 13 ML training strictly contains **only** `MODEL_FEATURE_COLUMNS`. It does **not** require manual filtering of rule or tracker outputs.

---

### 4.1. Canonical Model Input Features (38 Columns)

Model features are strictly limited to direct sensor measurements, stable derived geometric and motion quantities, personalized baselines, and missing value indicators:

| Feature Group | Column Names | Count | Description |
|---|---|:---:|---|
| **Core Numerical** | `head_pitch`, `head_yaw`, `head_roll`, `ear`, `mar`, `min_hand_cheek_distance`, `shoulder_z` | 7 | Pure 3D solvePnP angles, Eye/Mouth Aspect Ratios, hand-to-cheek Euclidean distance, and normalized shoulder depth. |
| **Core Presence** | `face_present`, `pose_present`, `hand_count` | 3 | Physical presence booleans and integer hand landmark count. |
| **Baseline Deltas & Rates** | `head_pitch_from_baseline`, `head_yaw_from_baseline`, `head_roll_from_baseline`, `left_ear`, `right_ear`, `left_hand_cheek_distance`, `right_hand_cheek_distance`, `shoulder_z_delta`, `torso_aspect_ratio`, `torso_posture_delta`, `head_yaw_rate`, `head_pitch_rate`, `head_roll_rate`, `shoulder_z_rate`, `hand_cheek_distance_rate` | 15 | Scale-invariant posture recline, personalized deviations from median baseline, and angular/depth velocities. |
| **Baseline Medians** | `baseline_head_yaw`, `baseline_head_pitch`, `baseline_head_roll`, `baseline_shoulder_z`, `baseline_torso_aspect_ratio` | 5 | Personal calibration medians established during the first 10s of study. |
| **Missing Indicators** | `head_pitch_missing`, `head_yaw_missing`, `head_roll_missing`, `ear_missing`, `mar_missing`, `min_hand_cheek_distance_missing`, `shoulder_z_missing`, `torso_aspect_ratio_missing` | 8 | Explicit boolean flags indicating unobservable features (e.g. face occluded). |

#### Why Rule & Tracker Outputs Are Excluded from Model Features
The authoritative rule-based detector evaluates instantaneous conditions (`rule_looking_away`, `rule_phone_use`, etc.) and temporal persistence counters (`tracker_<cat>_active`, `tracker_<cat>_duration_sec`, `tracker_<cat>_persistence_met`). Including these in model features creates **severe model-input leakage**:
- The future ML model would trivially reproduce the heuristic rule detector's outputs rather than learning subtle underlying motion patterns from raw telemetry.
- A model learning `label_phone_use ← rule_phone_use` fails to improve upon the detector it is intended to evaluate or replace.
- Therefore, all rule booleans and tracker states are strictly barred from `MODEL_FEATURE_COLUMNS`.

#### Non-Zero Missing Value Semantics
Missing numerical measurements remain `None`/`null` in the canonical dataset. They are **never** replaced with `0.0`, because zero carries mathematical meaning (e.g. `head_yaw = 0.0` denotes facing directly forward, whereas `null` denotes an occluded face).

---

### 4.2. Diagnostic Columns (24 Columns)

Detector rule activations and tracker states are retained in the dataset as **diagnostic columns** (outside `MODEL_FEATURE_COLUMNS`) so that Phase 13 can perform side-by-side comparative evaluations between the ML model and the existing rule detector:

| Diagnostic Group | Column Names | Count | Description |
|---|---|:---:|---|
| **Rule Activations** | `rule_looking_away`, `rule_phone_use`, `rule_yawning`, `rule_eyes_closed`, `rule_leaning_back`, `rule_away_from_desk` | 6 | Instantaneous condition booleans evaluated by pure rule functions (diagnostic comparison only). |
| **Tracker States** | `tracker_<cat>_active`, `tracker_<cat>_duration_sec`, `tracker_<cat>_persistence_met` (for all 6 canonical categories) | 18 | Temporal persistence counters tracking duration against alert delays (diagnostic comparison only). |

---

### 4.3. Target / Label Schema (8 Columns)

The dataset supports both multi-label per-category classification and overall focus state classification:

| Column Name | Type | Permitted Values | Semantic Meaning |
|---|---|---|---|
| `label_looking_away` | `int64` | `1`, `0`, `null` | `1` = looking away confirmed/active; `0` = looking away negative; `null` = unknown/unlabeled. |
| `label_phone_use` | `int64` | `1`, `0`, `null` | `1` = phone use confirmed/active; `0` = phone use negative; `null` = unknown/unlabeled. |
| `label_yawning` | `int64` | `1`, `0`, `null` | `1` = yawning confirmed/active; `0` = yawning negative; `null` = unknown/unlabeled. |
| `label_drowsy` | `int64` | `1`, `0`, `null` | `1` = drowsiness confirmed/active; `0` = drowsiness negative; `null` = unknown/unlabeled. |
| `label_leaning_back` | `int64` | `1`, `0`, `null` | `1` = bad posture confirmed/active; `0` = posture negative; `null` = unknown/unlabeled. |
| `label_away_from_desk`| `int64` | `1`, `0`, `null` | `1` = away from desk confirmed/active; `0` = at desk negative; `null` = unknown/unlabeled. |
| `focus_state_label` | `string` | `"focused"`, `"distracted"`, `"away"`, `"calibrating"`, `"unknown"` | Authoritative overall high-level state classification. |
| `label_distracted` | `int64` | `1`, `0`, `null` | Binary target: `1` if any distraction category is active, `0` if focused, `null` if calibrating/unknown. |

---

### 4.4. Provenance & Traceability Metadata (14 Columns)

Provenance columns allow full scientific auditing without contaminating model features:

| Column Name | Type | Semantic Meaning |
|---|---|---|
| `sample_id` | `string` | Unique UUID of the telemetry sample. |
| `session_hash` | `string` | Non-reversible short SHA-256 token identifying the study session (`ses_...`). |
| `frame_index` | `int64` | Monotonically increasing processed frame sequence number within the session. |
| `sampled_at` | `string` | UTC timestamp of sample capture in ISO 8601 format. |
| `detector_version` | `string` | Detection engine algorithm version (e.g. `v4`). |
| `feature_schema_version` | `string` | Feature extractor schema version (e.g. `telemetry_v2`). |
| `dataset_version` | `string` | Dataset generation pipeline version (e.g. `dataset_v1`). |
| `split` | `string` | Partition assignment: `train`, `val`, `test`, or `all`. |
| `label_source` | `string` | Provenance: `human_confirmed_detection`, `human_rejected_detector_event`, `detector_event`, etc. |
| `label_quality` | `string` | Label confidence: `high` (human verified), `medium` (unreviewed detector), `low` (ambiguous). |
| `is_labeled` | `boolean` | True if sample has a resolved ground truth label. |
| `is_calibration` | `boolean` | True if sample was captured during the initial 10-15s personal baseline window. |
| `is_excluded` | `boolean` | True if sample was excluded from export. |
| `exclusion_reason` | `string` | Reason for exclusion (e.g. `calibration_sample`, `unreviewed_missed_window`). |

---

## 6. Label Conflict Resolution Hierarchy

When telemetry samples intersect detection events and voluntary human feedback, labels are resolved deterministically:

1. **Human Confirmed Detection** (`feedback_type = correct_detection`):
   - Category label = `1`
   - Provenance = `"human_confirmed_detection"` (Quality: High)
2. **Human Rejected Detection** (`feedback_type = false_positive`):
   - Student explicitly indicated the detector was mistaken.
   - Category label = `0` (Prevents model from learning false positives as true positives)
   - Provenance = `"human_rejected_detector_event"` (Quality: High, preserves traceability of detector error)
3. **Authoritative Detector Event** (Unreviewed event):
   - Category label = `1`
   - Provenance = `"detector_event"` (Quality: Medium)
4. **Human Missed Detection** (`feedback_type = missed_detection`):
   - When configured with a non-zero attribution window (`--missed-detection-window`), samples within `[created_at - window, created_at]` are labeled `1`.
   - Default is `0.0` (preserves missed detection at session metadata level to prevent speculative sample labeling).
   - Provenance = `"human_missed_detection"` (Quality: High)
5. **Detector Active Monitoring State**:
   - For any category without an active event during focused/distracted study:
   - Category label = `0`
   - Provenance = `"detector_state_monitoring"` (Quality: Medium)
6. **Calibration / Ambiguous**:
   - Initial calibration frames: category labels = `null`
   - Provenance = `"calibration"` (Quality: Low, excluded by default)

---

## 7. Leakage-Safe Grouped User Splitting

Adjacent telemetry samples within the same session are highly autocorrelated. Splitting samples randomly across train and test sets would cause severe data leakage and artificially inflate test accuracy.

### Grouping Invariants
- **User Disjointness**: All sessions belonging to User $A$ are assigned exclusively to **one** split (`train`, `val`, or `test`). No user appears in multiple splits.
- **Session Disjointness**: Every session belongs entirely to one split.
- **Sample Disjointness**: Every sample belongs entirely to the session's split.
- **Deterministic Seed**: User partitioning uses seeded pseudo-random shuffling (`random_seed = 42`).
- **Small-Dataset Safety Guard**: A 3-way generalization split requires at least **3 distinct users**. If fewer than 3 users exist, the pipeline assigns all rows to `split = "all"`, marks `is_split_valid = False`, and emits an honest warning in the manifest and quality report.

---

## 8. Privacy & Data Protection

The pipeline enforces the project's zero raw media principle:
- **No Images or Frames**: Pixel arrays, JPEG/PNG byte strings, base64 data, and screenshots are strictly forbidden.
- **No Media Paths**: File paths pointing to webcams, video clips, or image files are rejected.
- **No Account PII in Feature Matrix**: User emails, Google profile IDs, passwords, display names, and raw `user_id` values are omitted.
- **Anonymized Session Tokens**: Sessions are referenced via non-reversible short SHA-256 tokens (`session_hash = "ses_..."`).
- **Automated Privacy Scanner**: `validate_privacy(df)` scans all columns and string values prior to parquet export, raising `DataQualityValidationError` if any prohibited substring is found.

---

## 9. CLI Usage

## 9. CLI Usage & Calibration Policies

The dataset pipeline is executed via `ml.dataset.build`:

```bash
# 1. Build canonical ML training dataset (calibration EXCLUDED by default)
python -m ml.dataset.build --output data/datasets/phase12/dataset_v1

# 2. Build separate diagnostic calibration-inclusive dataset (does NOT replace canonical dataset)
python -m ml.dataset.build --include-calibration --output data/datasets/phase12/dataset_v1_calibration

# 3. Filter by study session start dates
python -m ml.dataset.build --start-date "2026-10-01" --end-date "2026-10-06"

# 4. Run end-to-end against deterministic synthetic test fixtures (no live DB required)
python -m ml.dataset.build --synthetic --output scratch/synthetic_dataset --export-csv
```

### Calibration Policy
- **Canonical Dataset Policy**: Initial calibration samples (`is_calibration = True`) are excluded by default (`--include-calibration` is False). This ensures models are trained strictly on active study behavior.
- **Predominant Calibration Reality**: In early deployment environments where all telemetry samples are within the initial calibration window, the canonical pipeline exports **0 rows** into `dataset_v1/dataset.parquet`. The pipeline never crashes or fabricates labels; it generates an honest empty Parquet artifact with the full 84-column schema, reporting `pipeline_valid = True`, `sufficient_data = False`, and `label_valid = False`.
- **Diagnostic Calibration Dataset**: Passing `--include-calibration` outputs into a separate destination (e.g. `data/datasets/phase12/dataset_v1_calibration`), allowing engineers to inspect baseline quality without contaminating canonical training data.

### CLI Parameters

| Flag | Default | Description |
|---|---|---|
| `--output`, `-o` | `data/datasets/phase12/dataset_v1` | Target directory for Parquet and metadata files. |
| `--dataset-version` | `dataset_v1` | Version tag for the generated dataset. |
| `--seed` | `42` | Random seed for deterministic user grouping. |
| `--include-calibration` | `False` | When passed, includes calibration samples (`is_calibration = True`). |
| `--missed-detection-window`| `0.0` | Attribution window in seconds for missed detection feedback. |
| `--train-ratio` | `0.70` | Training split ratio. |
| `--val-ratio` | `0.15` | Validation split ratio. |
| `--test-ratio` | `0.15` | Test split ratio. |
| `--export-csv` | `False` | Also outputs `dataset.csv` alongside `dataset.parquet`. |
| `--synthetic` | `False` | Uses deterministic synthetic sources for offline testing. |

---

## 10. Generated Artifacts Catalog & Reproducibility Rules

| File Name | Format | Content |
|---|---|---|
| `dataset.parquet` | Apache Parquet | Primary columnar dataset containing all 84 columns: 38 model features, 8 targets, 14 provenance metadata, and 24 diagnostic outputs. |
| `manifest.json` | JSON | Top-level reproducibility metadata: versions, seed, split ratios, row counts, entity counts, column category lists. |
| `quality_report.json` | JSON | Scientific validity assessment (`pipeline_valid`, `split_valid`, `label_valid`, `sufficient_data`), per-category positive/negative/unknown percentages, feature null rates, privacy verification status, and dual leakage validation (`data_split_leakage` and `feature_target_leakage`). |
| `schema.json` | JSON | Column specifications, data types, descriptions, nullability, and unambiguous classifications (`feature`, `target`, `provenance`, `diagnostic`). |
| `split_summary.json` | JSON | Train/val/test breakdown: sample counts, user counts, session counts, and positive category distributions per split. |
| `dataset.csv` | CSV | Optional human-readable tabular export for debugging. |

### Reproducibility Guarantees
1. **Deterministic User Grouping**: Identical random seeds produce identical split assignments across all runs.
2. **PyArrow Parquet Integrity**: Export automatically verifies that read-back row count and schema strictly match written tables.
3. **Dual Leakage Verification**: Pipeline assertions enforce zero user/session leakage across splits and zero feature/target/diagnostic leakage into model features.
4. **Clean Directory Invariant**: Export cleans up stale artifacts (such as previous `.csv` files) to ensure reproducibility.
