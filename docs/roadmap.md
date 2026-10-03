# Project Roadmap

This document outlines the sequential development phases of the Student Focus Monitor project.

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

- **Phase 6 — Study session lifecycle**
  - Implement session creation, start, pause, resume, finish, and summary API endpoints and state machines.

- **Phase 7 — Camera and realtime transport**
  - Implement client-side camera capture and high-throughput, low-latency transport (WebSockets / WebRTC) between frontend and backend.

- **Phase 8 — Real monitoring**
  - Connect live video frames with the modular detection engine in real-time to compute attention scores and trigger alerts.

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
