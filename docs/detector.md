# Detection Engine Architecture & Reference Guide

> **Phase 2 Status:** Implemented & Verified.  
> This document details the modularized rule-based detection engine for the Student Focus Monitor.

---

## 1. Detector Purpose

The Student Focus Monitor detection engine analyzes visual landmarks to detect distraction behaviors, calculate real-time focus states, and log structured telemetry. It is designed to be privacy-first, deterministic, testable, and completely decoupled from UI presentation, audio hardware, or transport layers.

---

## 2. Architecture & Module Structure

The detection subsystem is located in `backend/app/detection/`:

```text
backend/app/detection/
├── __init__.py           # Public exports for the detection package
├── detector.py           # StudentDistractionDetector: high-level coordinator
├── config.py             # DetectorConfig & canonical category definitions
├── features.py           # Pure mathematical/geometric feature extraction
├── calibration.py        # Personal baseline collection and deviation calculations
├── rules.py              # Pure condition evaluations for the 6 alert categories
├── trackers.py           # Persistence tracking and activation delay logic
├── session_state.py      # Session-level duration accounting and focus scoring
├── events.py             # Structured domain events for alert lifecycles
├── telemetry.py          # Structured numerical telemetry records & sinks
└── mediapipe_runtime.py  # MediaPipe Tasks vision runtime adapter

backend/scripts/
└── run_detector_local.py # Desktop webcam runner & OpenCV visualization adapter

backend/tests/detection/
├── test_trackers.py      # Unit tests for delay thresholds and boundaries
├── test_calibration.py   # Unit tests for user baseline personalization
├── test_features.py      # Unit tests for geometric and motion features
├── test_rules.py         # Unit tests for all 6 detection rules
├── test_detector.py      # Full synthetic session orchestration & isolation tests
├── test_events.py        # Unit tests for domain event schemas
└── test_telemetry.py     # Unit tests for telemetry payloads & zero-media guarantees
```

---

## 3. Module Responsibilities

| Module | Core Responsibility | Dependency Boundary |
|---|---|---|
| `config.py` | Centralizes thresholds, delays, category IDs, and versions | No external dependencies |
| `features.py` | Transforms raw 2D/3D landmarks into numerical metrics and velocity rates | NumPy, OpenCV (solvePnP only) |
| `calibration.py` | Calculates user-specific median posture/orientation baselines | NumPy |
| `rules.py` | Pure evaluation of boolean conditions per category | Depends only on `features.py` and `config.py` |
| `trackers.py` | Evaluates condition persistence across time against delay policies | Pure time tracking |
| `events.py` | Generates structured lifecycle event records | Dataclasses, UUID |
| `session_state.py` | Computes focused/distracted/away seconds and focus score | Pure accounting logic |
| `telemetry.py` | Constructs telemetry records and manages persistence sinks | JSON Lines / In-memory |
| `mediapipe_runtime.py`| Manages MediaPipe Tasks API model loading and video detection | MediaPipe |
| `detector.py` | High-level orchestrator connecting all detection modules | Composes lower modules |
| `run_detector_local.py`| Desktop adapter with OpenCV window and audio alerts | cv2, winsound (local runner only) |

---

## 4. Detection Pipeline

Every video frame flows through a strictly sequential processing pipeline:

```text
Incoming Video Frame
       ↓
MediaPipe Runtime (Face, Hand, Pose Landmarkers)
       ↓
Feature Extraction (EAR, MAR, Head Pose, Hand Proximity, Shoulder Depth, Rates)
       ↓
Personal Calibration (Deviation from student's own calibrated baseline)
       ↓
Rule Evaluation (Instantaneous boolean evaluation for each of the 6 categories)
       ↓
Persistence Tracking (Evaluates if condition has continuously persisted >= alert delay)
       ↓
Event Generation (Emits discrete "started" or "ended" events on state transitions)
       ↓
Session State Update (Accumulates focused, distracted, or away durations)
       ↓
Telemetry Emission (Periodic numerical snapshot emitted at 2 Hz)
```

---

## 5. Supported Detection Categories

The engine supports six canonical distraction categories:

1. **Looking Away** (`looking_away`): Head yaw deviation from calibrated baseline exceeds `yaw_threshold_deg` (default: `10.0°`).
2. **Phone Use** (`phone_use`): Hand landmark centroid is within `hand_near_cheek_dist` (default: `0.15` normalized) of either cheek.
3. **Yawning** (`yawning`): Mouth Aspect Ratio (MAR) exceeds `mar_threshold` (default: `0.55`).
4. **Drowsy / Eyes Closed** (`drowsy`): Eye Aspect Ratio (EAR) falls below `ear_threshold` (default: `0.21`).
5. **Leaning Back** (`leaning_back`): Shoulder depth delta $z$ exceeds calibrated baseline by `lean_back_z_delta` (default: `0.15`).
6. **Away From Desk** (`away_from_desk`): Neither face landmarks nor pose landmarks are detected in the frame.

---

## 6. Personal Calibration

Universal body and camera geometries do not fit every student. The calibration system personalizes baselines:
- During the first `calibration_seconds` (default: `10.0s`) of a session, samples of shoulder depth ($z$), head yaw, head pitch, and head roll are gathered in `CalibrationBuffer`.
- Once at least `minimum_calibration_samples` (default: `30`) are collected, medians are computed:
  $$\text{baseline} = (\text{median}(z), \text{median}(\text{yaw}), \text{median}(\text{pitch}), \text{median}(\text{roll}))$$
- All subsequent rule conditions evaluate deviations relative to this baseline:
  $$\Delta \text{yaw} = \text{yaw} - \text{baseline.yaw}, \quad \Delta z = z - \text{baseline.}z$$

---

## 7. Persistence Tracking & Alert Delays

A temporary glance or blink must not trigger a false alert. Condition persistence is tracked via `PersistenceTracker`:
- When a condition becomes true, `condition_started_at` is recorded.
- An alert is only activated when:
  $$\text{now} - \text{condition\_started\_at} \ge \text{alert\_delay}$$
- Default delays:
  - Yawning: `2.0s`
  - Looking Away, Phone Use, Drowsy, Leaning Back, Away From Desk: `20.0s`
- When the condition becomes false, the alert immediately deactivates, emitting an "ended" event with the total active duration.

---

## 8. Session State Accounting & Focus Scoring

The engine tracks duration based on the active state:
- **Calibrating**: During initial baseline capture.
- **Focused**: When no distraction alerts are active.
- **Distracted**: When any alert other than "Away From Desk" is active.
- **Away**: When "Away From Desk" is active (and no higher priority alert is active).

At session completion, the focus score is calculated:
$$\text{Focus Score} = \left( \frac{\text{focused\_seconds}}{\text{focused\_seconds} + \text{distracted\_seconds} + \text{away\_seconds}} \right) \times 100$$

---

## 9. Telemetry & Privacy Guarantees

- **No Media Persistence**: The detection engine never writes video, webcam pictures, audio, or raw frame buffers to disk or telemetry logs.
- **Pure Numerical Data**: Telemetry records contain numerical metrics (angles, aspect ratios, rates of change), state strings, timestamps, and configuration snapshots.
- **Pluggable Sinks**: Sinks implement `TelemetrySink`:
  - `InMemoryTelemetrySink`: For testing and real-time streaming without filesystem side-effects.
  - `FileTelemetrySink`: Appends JSON Lines to `data/telemetry/<session_id>.jsonl` and `data/events/<session_id>.jsonl`.

---

## 10. MediaPipe Runtime Boundary

MediaPipe vision tasks (`FaceLandmarker`, `HandLandmarker`, `PoseLandmarker`) are encapsulated within `MediaPipeRuntime`.
- Pure unit tests import only `features.py`, `rules.py`, `calibration.py`, and `detector.py`, running without GPU, camera, or model downloads.
- Models are downloaded only when `ensure_models()` or `MediaPipeRuntime()` is explicitly invoked.

---

## 11. Versioning

- **Detector Engine Version**: `DETECTOR_VERSION = "v4"`
- **Feature Schema Version**: `FEATURE_SCHEMA_VERSION = "telemetry_v2"` (updated in Phase 11 with baseline-relative deltas, motion rates, and tracker states)

---

## 12. Phase 8 Real Detection Integration & Live Runtime

In Phase 8, the modular detection engine is actively connected to the Phase 7 live WebSocket transport (`/api/ws/sessions/{session_id}`):

```text
Browser Camera (getUserMedia, audio: false)
      ↓
JPEG Frame Bytes via WebSocket
      ↓
LiveTransportManager (detector_hook)
      ↓
DetectionRuntimeManager (Session-scoped isolation)
      ↓
SessionDetectionRuntime Worker (asyncio bounded queue, maxsize=1)
      ↓
OpenCV Decode & RGB Conversion
      ↓
MediaPipeRuntime (Face, Hand, Pose Landmarkers with monotonic timestamps)
      ↓
StudentDistractionDetector.process_results(...)
      ↓
Event Lifecycle Management (Discrete DetectionEvent creation & finalization)
      ↓
PostgreSQL Persistence (detection_events table on state transitions only)
      ↓
WebSocket detection_result Emitted to Browser
```

### 12.1. Key Phase 8 Architecture Guarantees
1. **Per-Session State Isolation**: `SessionDetectionRuntime` is strictly tied to `session_id`. Each session maintains its own `StudentDistractionDetector`, `MediaPipeRuntime`, calibration buffer, persistence trackers, and duration counters. Cross-session or cross-student state contamination is impossible.
2. **Non-Blocking CPU Execution**: MediaPipe inference runs off the asyncio event loop via `asyncio.to_thread` inside a dedicated per-session worker task.
3. **Bounded Backpressure Queue**: The submission queue is configured with `maxsize=1`. If the detector worker is busy processing a frame, `submit_frame` drops stale frames and enqueues the freshest incoming frame, guaranteeing real-time freshness over processing stale historical frames.
4. **Controlled DB Persistence Frequency**: Rows in PostgreSQL `detection_events` are inserted ONLY when an alert condition's persistence delay is satisfied (event start) and updated when the condition ends (event end) or session stops. Zero writes occur on raw frames.
5. **Session Stop Finalization**: Calling `POST /api/sessions/{session_id}/stop` safely stops frame ingestion, finalizes any in-progress distraction events, persists authoritative duration and focus metrics to `study_sessions`, and releases MediaPipe vision resources.
6. **Privacy Integrity**: Zero image frames, pixels, or screenshots are written to PostgreSQL, disk, or logs. Only canonical categories, timestamps, and numerical metrics are stored.

---

## 13. Phase 11 Telemetry & User Feedback Ingestion

In Phase 11, the authoritative backend detection pipeline captures trustworthy numerical and structured telemetry into PostgreSQL (`telemetry_samples`), coupled with human labels from `session_feedback`:

1. **Authoritative Backend Origin**:
   Telemetry originates directly from the backend detection pipeline (`camera frame → MediaPipe → calibration → rules → tracker state → telemetry sample → persistence`). It is never reconstructed or approximated on the frontend.
2. **Numerical & Baseline-Relative Retention**:
   - Both raw values (e.g. `head_yaw = 18.5`) and baseline-relative deltas (e.g. `head_yaw_from_baseline = 16.5`, `shoulder_z_delta = 0.21`) are preserved.
   - Dynamic motion rates (`head_yaw_rate`, `head_pitch_rate`, `shoulder_z_rate`) and multi-category tracker states are captured in the JSONB `features` payload.
   - Non-zero null semantics: missing features are stored as `null`/`None`, never converted into misleading zeros.
3. **Deliberate Sampling & Bounded Buffering**:
   - Samples are emitted at ~5 Hz target cadence (`telemetry_interval_sec = 0.2`), matching processed inference frames rather than raw camera frame rates.
   - `BufferedTelemetrySink` manages an in-memory queue (`maxsize = 500`), evicting oldest samples under high database load to protect memory bounds.
   - Telemetry batches are persisted asynchronously without blocking vision inference.
   - Clean shutdown flushes all buffered samples upon WebSocket disconnect or session stop.
4. **Strict Zero Raw Media Guarantee**:
   All telemetry pipelines strip any prohibited media keys (`image`, `video`, `jpeg`, `png`, `frame_bytes`, `audio`, `raw_buffer`, `camera`).

---

## 14. Phase 12 ML Dataset Pipeline Integration

In Phase 12, detector telemetry (`telemetry_samples`), discrete distraction events (`detection_events`), and human labels (`session_feedback`) are converted into a row-oriented, leakage-safe supervised-learning dataset:
- **Explicit Schema Separation (84 Total Columns)**:
  - **Model Feature Columns (38 columns)**: Direct 3D angles, aspect ratios, distances, depth, presence indicators, baseline deltas, motion velocity rates, baseline medians, and missing indicators. Strictly **excludes** detector rule and tracker outputs.
  - **Diagnostic Columns (24 columns)**: Retains all 6 instantaneous rule booleans (`rule_*`) and 18 tracker states (`tracker_*`) outside the model feature matrix so Phase 13 can perform side-by-side comparative evaluations against the rule detector without causing target leakage.
  - **Target Columns (8 columns)**: Maps the 6 canonical distractions (`looking_away`, `phone_use`, `yawning`, `drowsy`, `leaning_back`, `away_from_desk`) into discrete `1`/`0`/`null` labels plus overall `focus_state_label` and binary `label_distracted`.
  - **Provenance Columns (14 columns)**: Traceability tokens (`sample_id`, `session_hash`, `split`, `label_source`, `label_quality`, etc.) for scientific auditing without PII.
- **Why Rule & Tracker Outputs Are Excluded from Model Features**:
  Rule outputs (`rule_*`) and tracker states (`tracker_*`) are already decisions of the authoritative detector that Phase 13 is intended to learn or improve upon. Including them in model features allows the ML model to trivially reproduce heuristic rule thresholds instead of learning from movement kinematics.
- **Deterministic Alignment**: Temporal interval matching associates events with telemetry samples.
- **Label Conflict Resolution**: Human feedback takes precedence (`correct_detection` confirms positive, `false_positive` overrides to negative `0` while recording human-rejected provenance).
- **Grouped User Splitting**: Partitions data strictly at the user boundary to prevent session/sample leakage.
- **Calibration Policy**: Canonical training dataset excludes initial calibration frames by default; diagnostic calibration data can be generated in a separate artifact directory.
- Detailed technical reference: see [docs/ml-dataset.md](ml-dataset.md).


