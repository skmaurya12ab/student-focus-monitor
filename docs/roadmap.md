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

- **Phase 9 — Live dashboard integration**
  - Connect frontend monitoring UI with realtime detection streams, audio/visual distraction alerts, and focus state indicators.

- **Phase 10 — Session history and analytics**
  - Build dashboards for past session reviews, attention trends, distraction heatmaps, and productivity metrics.

- **Phase 11 — Telemetry and user feedback**
  - Anonymize numerical movement telemetry and capture user feedback on distraction alerts (true positives vs. false positives).

- **Phase 12 — ML dataset pipeline**
  - Build automated extraction and preprocessing pipelines to curate training datasets from anonymized telemetry.

- **Phase 13 — First ML model**
  - Train and evaluate the first machine learning model to classify student distraction from movement telemetry.

- **Phase 14 — ML shadow mode**
  - Deploy the ML model in shadow mode alongside the rule-based engine to compare inference accuracy before gradual rollout.
