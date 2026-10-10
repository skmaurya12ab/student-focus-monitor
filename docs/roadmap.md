# Project Roadmap

This document outlines the sequential development phases of the Student Focus Monitor project.

The project consists of **15 total phases** (Phase 0 through Phase 14):
- **Phase 0** is the architecture and specification phase.
- **Phases 1 through 14** are the implementation phases.

---

## Phases Overview

- **Phase 0 — Architecture and specification**
  - Define technical requirements, domain models, privacy guidelines, and architecture diagrams.

- **Phase 1 — Project bootstrap (Current Phase)**
  - Establish monorepo structure, React + Vite frontend bootstrap, FastAPI backend with health check, PostgreSQL Docker service, environment configuration, automated tests, and CI pipeline.

- **Phase 2 — Detection engine refactor**
  - Modularize the reference rule-based detector (`student_distraction_detector_v4.py`) into clean, stateless detection components and services within `backend/app/detection/`.

- **Phase 3 — Figma frontend**
  - Translate Figma design specifications into reusable UI components, layout shells, typography, and styling tokens.

- **Phase 4 — PostgreSQL schema**
  - Implement SQLAlchemy models and Alembic migrations for users, study sessions, distraction events, and telemetry.

- **Phase 5 — Google authentication**
  - Integrate Google OAuth 2.0 / OpenID Connect authentication on frontend and backend for secure session management.

- **Phase 6 — Study session lifecycle (Completed)**
  - Implement authenticated session creation, active-session lookup, get session by ID, and stop endpoints with authoritative server-generated UUIDs, timestamps, and duration calculation. Enforce single active session invariant via partial unique database index and service logic. Integrated with Figma frontend without camera/ML dependencies.

- **Phase 7 — Camera and realtime transport (Completed)**
  - Implement client-side camera capture (video only, audio strictly excluded), canvas downsampling, bounded pacing (~5 FPS), backpressure protection, and authenticated WebSocket transport (`/api/ws/sessions/{session_id}`). Backend enforces Origin validation, session ownership, active status requirement, single live connection invariant, max frame size limits (1 MB), and frame discarding without media persistence. Defines clean seam for Phase 8 detector.

- **Phase 8 — Real monitoring / Real detection (Completed)**
  - Connect live browser video frames to the modular detection engine in real-time. Employs session-isolated runtimes (`SessionDetectionRuntime`), asynchronous worker execution, bounded backpressure queue (`maxsize=1`, freshest-frame priority), strictly monotonic MediaPipe timestamps, discrete `DetectionEvent` persistence to PostgreSQL on state transitions, session stop metric finalization, and live `detection_result` WebSocket payloads without raw media storage.

- **Phase 9 — Live dashboard integration (Completed)**
  - Convert the Home / Live Dashboard into a dynamic, real-time monitoring interface preserving the approved Figma design system. Live metrics (Focused, Distracted, Away, Focus Score, Study Time, Distractions) are driven authoritatively by active session and live WebSocket `detection_result` payloads, preventing static Figma sample leaks. Employs a truthful 10-state live badge indicator, contained multi-alert notification chips with duration tracking, browser-compatible Web Audio API chime with edge-triggered deduplication (no audio spam), and a dynamic Focus Timeline representing real session state transitions. Lifecycle separation strictly maintained: stopping live monitoring keeps Study Session active.

- **Phase 10 — Session history and analytics (Completed)**
  - Convert Sessions and Analytics pages from static presentation into real historical functionality backed by PostgreSQL. Implements bounded server-side pagination, newest-first deterministic ordering, detailed session inspection with discrete `DetectionEvent`s and top causes, and aggregate analytics with date filtering (`7d`, `30d`, `all`), IANA timezone-aware date bucketing, dynamic trend lines, canonical category breakdowns, and IDOR protection. Zero mock analytics leak into production UI.

- **Phase 11 — Telemetry and user feedback (Completed)**
  - Capture trustworthy numerical and structured movement telemetry from authoritative backend detection runtime into PostgreSQL (`telemetry_samples`), capturing raw metrics, baseline-relative deltas, motion rates, tracker states, and calibration metadata under feature schema `telemetry_v2`. Provides voluntary, lightweight human labeling via Session Detail UI (`correct_detection`, `false_positive`, `missed_detection` with structured canonical category, `other`). Bounded queue buffering (`maxsize=500`, 5 Hz target cadence) and disconnect flushing preserve live detection performance. Strictly zero raw media.

- **Phase 12 — ML dataset pipeline (Completed)**
  - Build automated, leakage-safe extraction and preprocessing pipeline converting PostgreSQL `telemetry_samples`, `detection_events`, and `session_feedback` human labels into a supervised-learning dataset. Granularity: 1 row = 1 telemetry sample (~5 Hz cadence). Flattens 62 allowlisted features (raw coordinates, baseline-relative deltas, motion velocities, rule flags, multi-category tracker states, missing value indicators). Maps 6 canonical distraction targets plus overall focus state. Implements deterministic conflict resolution (human feedback precedence) and grouped user-level splitting (zero user/session leakage). Exports Parquet, schema specification, reproducibility manifest, and scientific quality report. Absolute privacy preserved: zero raw media and zero account PII. Model training and inference strictly deferred to Phase 13.

- **Phase 13 — First ML model (Completed)**
  - Build offline supervised ML baseline and evaluation pipeline consuming Phase 12 dataset artifacts. Implements strict feature schema allowlisting (38 MODEL_FEATURE_COLUMNS), leakage-safe scikit-learn Pipeline with median imputation and standard scaling fit strictly on training partitions, and primary LogisticRegression baseline with optional RandomForest challenger. Preserves grouped user splits (zero user/session contamination). Computes binary classification metrics (Precision, Recall, F1, Accuracy, ROC-AUC, PR-AUC, Confusion Matrix), leakage-safe threshold selection (validation only), feature interpretability rankings, offline rule-based detector comparison, and privacy-verified metadata/evaluation manifests without raw PII. Evaluates dataset readiness gate (real-data insufficient gating without fabrication). Live detector integration and online inference strictly deferred to Phase 14.

- **Phase 14 — ML shadow mode (Future)**
  - Deploy the ML model in shadow mode alongside the rule-based engine to compare inference accuracy before gradual rollout.
