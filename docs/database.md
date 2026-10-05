# Database Architecture & PostgreSQL Schema

This document defines the persistent PostgreSQL data layer for the **Student Focus Monitor** project, established in **Phase 4**.

---

## 1. PostgreSQL Role & Technology Stack

PostgreSQL is the single authoritative persistent storage engine for the Student Focus Monitor application.

- **RDBMS**: PostgreSQL 18+ (compatible with PostgreSQL 15+)
- **ORM & Data Layer**: SQLAlchemy 2.0 (`sqlalchemy>=2.0.0`)
- **Async Driver**: `asyncpg` (`asyncpg>=0.29.0`) for FastAPI asynchronous runtime
- **Sync Driver**: `psycopg2-binary` (`psycopg2-binary>=2.9.9`) for Alembic migrations and synchronous inspection
- **Migrations**: Alembic (`alembic>=1.13.0`)
- **Primary Keys**: UUID v4 (`uuid.uuid4`)
- **Timestamps**: Timezone-aware UTC (`TIMESTAMP WITH TIME ZONE`)

> [!IMPORTANT]
> **Privacy-First Architecture**: The PostgreSQL database stores account data, configurable alert preferences, session performance summaries, numerical movement telemetry, detection event records, and student feedback. It **never** stores raw webcam frames, video recordings, audio recordings, or media byte buffers.

---

## 2. Entity-Relationship (ER) Diagram

The following diagram represents the implemented schema and actual database relationships:

```mermaid
erDiagram
    users ||--o{ auth_identities : "1 to many (CASCADE)"
    users ||--|| user_settings : "1 to 1 (CASCADE)"
    users ||--o{ study_sessions : "1 to many (CASCADE)"
    study_sessions ||--o{ detection_events : "1 to many (CASCADE)"
    study_sessions ||--o{ telemetry_samples : "1 to many (CASCADE)"
    study_sessions ||--o{ session_feedback : "1 to many (CASCADE)"
    detection_events ||--o{ session_feedback : "0..1 to many (SET NULL)"

    users {
        uuid id PK
        varchar email UK "nullable"
        varchar display_name
        boolean is_active
        timestamptz created_at
        timestamptz updated_at
    }

    auth_identities {
        uuid id PK
        uuid user_id FK
        varchar provider
        varchar provider_subject
        varchar provider_email "nullable"
        timestamptz created_at
        timestamptz last_login_at "nullable"
    }

    user_settings {
        uuid id PK
        uuid user_id FK, UK
        float looking_away_delay_seconds
        float phone_use_delay_seconds
        float yawning_delay_seconds
        float drowsy_delay_seconds
        float leaning_back_delay_seconds
        float away_from_desk_delay_seconds
        boolean sound_alerts_enabled
        boolean banner_alerts_enabled
        boolean session_end_summary_enabled
        varchar camera_device
        varchar preview_quality
        timestamptz created_at
        timestamptz updated_at
    }

    study_sessions {
        uuid id PK
        uuid user_id FK
        timestamptz started_at
        timestamptz ended_at "nullable"
        varchar status "active|completed|cancelled"
        float total_duration_seconds
        float focused_seconds
        float distracted_seconds
        float away_seconds
        numeric focus_score "0.00 to 100.00"
        varchar detector_version
        varchar feature_schema_version
        jsonb calibration_snapshot "nullable"
        timestamptz created_at
        timestamptz updated_at
    }

    detection_events {
        uuid id PK
        uuid session_id FK
        varchar event_type "6 canonical types"
        timestamptz started_at
        timestamptz ended_at "nullable"
        float duration_seconds "nullable"
        varchar detector_version
        jsonb metadata_json "nullable"
        timestamptz created_at
        timestamptz updated_at
    }

    telemetry_samples {
        uuid id PK
        uuid session_id FK
        timestamptz sampled_at
        int frame_index
        varchar detector_version
        varchar feature_schema_version
        float head_pitch "nullable"
        float head_yaw "nullable"
        float head_roll "nullable"
        float ear "nullable"
        float mar "nullable"
        float min_hand_cheek_distance "nullable"
        float shoulder_z "nullable"
        boolean face_present
        boolean pose_present
        int hand_count
        varchar focus_state
        jsonb features
        timestamptz created_at
    }

    session_feedback {
        uuid id PK
        uuid session_id FK
        uuid detection_event_id FK "nullable"
        varchar feedback_type "correct_detection|false_positive|missed_detection|other"
        text note "nullable"
        timestamptz created_at
    }
```

---

## 3. Implemented Tables & Specifications

### 3.1. `users`
Represents an individual student account. Prepared for Phase 5 authentication without exposing auth mechanism specifics.
- **Primary Key**: `id` UUID
- **Columns**:
  - `email` `VARCHAR(255)` — Unique nullable email address
  - `display_name` `VARCHAR(100)` — Non-empty student name
  - `is_active` `BOOLEAN` — Defaults to `TRUE`
  - `created_at` / `updated_at` `TIMESTAMPTZ` — Audit timestamps
- **Constraints**:
  - `uq_users_email` UNIQUE (`email`)
- **Indexes**:
  - `ix_users_email` on (`email`)

### 3.2. `auth_identities`
Stores third-party OAuth identities (e.g. Google OAuth 2.0 / OpenID Connect) associated with a user account.
- **Primary Key**: `id` UUID
- **Foreign Keys**:
  - `user_id` -> `users.id` (`ON DELETE CASCADE`)
- **Columns**:
  - `provider` `VARCHAR(50)` — Identity provider name (e.g. `google`)
  - `provider_subject` `VARCHAR(255)` — Unique user ID from identity provider
  - `provider_email` `VARCHAR(255)` — Email reported by provider
  - `last_login_at` `TIMESTAMPTZ` — Last authentication timestamp
  - `created_at` `TIMESTAMPTZ`
- **Constraints**:
  - `uq_auth_identities_provider_subject` UNIQUE (`provider`, `provider_subject`)
- **Indexes**:
  - `ix_auth_identities_user_id` on (`user_id`)
  - `ix_auth_identities_provider_subject` on (`provider`, `provider_subject`)

### 3.3. `user_settings`
Represents student-configured alert thresholds, alert persistence delays, notification toggles, and camera device preferences (1:1 with `users`).
- **Primary Key**: `id` UUID
- **Foreign Keys**:
  - `user_id` -> `users.id` (`ON DELETE CASCADE`, UNIQUE)
- **Columns**:
  - `looking_away_delay_seconds` `FLOAT` (default: 10.0, CHECK >= 0)
  - `phone_use_delay_seconds` `FLOAT` (default: 6.0, CHECK >= 0)
  - `yawning_delay_seconds` `FLOAT` (default: 2.0, CHECK >= 0)
  - `drowsy_delay_seconds` `FLOAT` (default: 4.0, CHECK >= 0)
  - `leaning_back_delay_seconds` `FLOAT` (default: 8.0, CHECK >= 0)
  - `away_from_desk_delay_seconds` `FLOAT` (default: 10.0, CHECK >= 0)
  - `sound_alerts_enabled` `BOOLEAN` (default: `FALSE`)
  - `banner_alerts_enabled` `BOOLEAN` (default: `FALSE`)
  - `session_end_summary_enabled` `BOOLEAN` (default: `TRUE`)
  - `camera_device` `VARCHAR(100)` (default: `'Integrated Camera - 720p'`)
  - `preview_quality` `VARCHAR(50)` (default: `'High · 30 FPS'`)
  - `created_at` / `updated_at` `TIMESTAMPTZ`
- **Constraints**:
  - `uq_user_settings_user_id` UNIQUE (`user_id`)
  - 6 CHECK constraints ensuring all alert persistence delays are `>= 0`

> [!NOTE]
> **Detector Thresholds vs. User Alert Persistence**: The detection engine evaluates instantaneous or sliding-window rule states (e.g. EAR < 0.21, yaw > 25°). The `user_settings` table configures how long that state must continuously persist before triggering an alert notification (e.g., looking away for 10 seconds). These concepts are cleanly decoupled.

### 3.4. `study_sessions`
Stores finalized or in-progress study sessions.
- **Primary Key**: `id` UUID
- **Foreign Keys**:
  - `user_id` -> `users.id` (`ON DELETE CASCADE`)
- **Columns**:
  - `started_at` `TIMESTAMPTZ` (NOT NULL)
  - `ended_at` `TIMESTAMPTZ` (nullable)
  - `status` `VARCHAR(20)` — `active`, `completed`, or `cancelled`
  - `total_duration_seconds` `FLOAT` (default: 0.0, CHECK >= 0)
  - `focused_seconds` `FLOAT` (default: 0.0, CHECK >= 0)
  - `distracted_seconds` `FLOAT` (default: 0.0, CHECK >= 0)
  - `away_seconds` `FLOAT` (default: 0.0, CHECK >= 0)
  - `focus_score` `NUMERIC(5, 2)` — Precise decimal between 0.00 and 100.00 (CHECK: `0 <= focus_score <= 100`)
  - `detector_version` `VARCHAR(20)` — Detector release version (e.g. `'0.2.0'`)
  - `feature_schema_version` `VARCHAR(30)` — Telemetry feature schema version (e.g. `'2026-03-modular-v1'`)
  - `calibration_snapshot` `JSONB` — Baseline EAR, MAR, head pose recorded at session start
  - `created_at` / `updated_at` `TIMESTAMPTZ`
- **Constraints**:
  - `ck_study_sessions_status`: `status IN ('active', 'completed', 'cancelled')`
  - `ck_study_sessions_focus_score_range`: `focus_score IS NULL OR (focus_score >= 0 AND focus_score <= 100)`
  - `ck_study_sessions_time_consistency`: `ended_at IS NULL OR ended_at >= started_at`
  - Duration non-negative checks for `total_duration_seconds`, `focused_seconds`, `distracted_seconds`, and `away_seconds`.
- **Indexes & Unique Constraints**:
  - `ix_study_sessions_user_id` on (`user_id`)
  - `ix_study_sessions_started_at` on (`started_at`)
  - `ix_study_sessions_status` on (`status`)
  - `ix_study_sessions_user_started` composite index on (`user_id`, `started_at` DESC) for fast student history queries
  - `uq_study_sessions_user_active` **UNIQUE partial index** on (`user_id`) `WHERE status = 'active'` (enforces the invariant that a user can have at most one active study session at any time, even under concurrent requests). Added in Phase 6 migration `621aa6c6d813`.

### 3.5. `detection_events`
Stores discrete distraction alert occurrences during a session.
- **Primary Key**: `id` UUID
- **Foreign Keys**:
  - `session_id` -> `study_sessions.id` (`ON DELETE CASCADE`)
- **Columns**:
  - `event_type` `VARCHAR(50)` — Canonical 6 categories: `looking_away`, `phone_use`, `yawning`, `drowsy`, `leaning_back`, `away_from_desk`
  - `started_at` `TIMESTAMPTZ` (NOT NULL)
  - `ended_at` `TIMESTAMPTZ` (nullable for open events)
  - `duration_seconds` `FLOAT` (nullable, CHECK >= 0)
  - `detector_version` `VARCHAR(20)`
  - `metadata_json` `JSONB` — Structured event metadata (e.g. peak yaw, direction)
  - `created_at` / `updated_at` `TIMESTAMPTZ`
- **Constraints**:
  - `ck_detection_events_type`: `event_type IN ('looking_away', 'phone_use', 'yawning', 'drowsy', 'leaning_back', 'away_from_desk')`
  - `ck_detection_events_duration_non_negative`: `duration_seconds IS NULL OR duration_seconds >= 0`
  - `ck_detection_events_time_consistency`: `ended_at IS NULL OR ended_at >= started_at`
- **Indexes**:
  - `ix_detection_events_session_id` on (`session_id`)
  - `ix_detection_events_type` on (`event_type`)
  - `ix_detection_events_started_at` on (`started_at`)
  - `ix_detection_events_session_started` composite on (`session_id`, `started_at`)
  - `ix_detection_events_session_type` composite on (`session_id`, `event_type`)

### 3.6. `telemetry_samples`
Stores high-frequency numerical telemetry points extracted during monitoring for analytics and ML datasets.
- **Primary Key**: `id` UUID
- **Foreign Keys**:
  - `session_id` -> `study_sessions.id` (`ON DELETE CASCADE`)
- **Columns**:
  - `sampled_at` `TIMESTAMPTZ` (NOT NULL)
  - `frame_index` `INTEGER` (CHECK >= 0)
  - `detector_version` `VARCHAR(20)`
  - `feature_schema_version` `VARCHAR(30)`
  - `head_pitch` `FLOAT`, `head_yaw` `FLOAT`, `head_roll` `FLOAT` (Fast-path indexed metrics)
  - `ear` `FLOAT`, `mar` `FLOAT`
  - `min_hand_cheek_distance` `FLOAT`, `shoulder_z` `FLOAT`
  - `face_present` `BOOLEAN`, `pose_present` `BOOLEAN`, `hand_count` `INTEGER`
  - `focus_state` `VARCHAR(30)` (e.g. `'focused'`, `'looking_away'`)
  - `features` `JSONB` (Extensible payload for motion rates, rule outputs, calibration states, and future ML features)
  - `created_at` `TIMESTAMPTZ`
- **Constraints**:
  - `ck_telemetry_samples_frame_index`: `frame_index >= 0`
- **Indexes**:
  - `ix_telemetry_samples_session_id` on (`session_id`)
  - `ix_telemetry_samples_sampled_at` on (`sampled_at`)
  - `ix_telemetry_samples_session_sampled` composite index on (`session_id`, `sampled_at` ASC) for streaming retrieval

### 3.7. `session_feedback`
Stores explicit human feedback and alert labeling workflows (Phase 11).
- **Primary Key**: `id` UUID
- **Foreign Keys**:
  - `session_id` -> `study_sessions.id` (`ON DELETE CASCADE`)
  - `detection_event_id` -> `detection_events.id` (`ON DELETE SET NULL`, nullable)
- **Columns**:
  - `feedback_type` `VARCHAR(50)` — `correct_detection`, `false_positive`, `missed_detection`, or `other`
  - `category` `VARCHAR(50)` — Canonical category (e.g. `phone_use`, `looking_away`, `yawning`, `drowsy`, `leaning_back`, `away_from_desk`) for missed detections. Added in migration `d8b5c2a1e3f4`.
  - `note` `TEXT` (nullable, bounded to 1000 characters)
  - `created_at` `TIMESTAMPTZ`
- **Constraints**:
  - `ck_session_feedback_type`: `feedback_type IN ('correct_detection', 'false_positive', 'missed_detection', 'other')`
- **Indexes & Unique Constraints**:
  - `ix_session_feedback_session_id` on (`session_id`)
  - `ix_session_feedback_event_id` on (`detection_event_id`)
  - `uq_session_feedback_session_event` **UNIQUE partial index** on (`session_id`, `detection_event_id`) `WHERE detection_event_id IS NOT NULL`. Added in migration `d8b5c2a1e3f4`.

---

## 4. Telemetry Storage Strategy & Privacy Boundary

### 4.1. Structured Hybrid Design
To balance fast analytical queries against future ML schema evolution, `telemetry_samples` employs a hybrid design:
1. **Fast-path columns**: Core scalar coordinates (`head_pitch`, `head_yaw`, `head_roll`, `ear`, `mar`, `min_hand_cheek_distance`, `shoulder_z`, presence flags) are stored in typed PostgreSQL columns.
2. **JSONB payload (`features`)**: Evolving derived metrics (`head_yaw_from_baseline`, `head_pitch_from_baseline`, `head_roll_from_baseline`, `shoulder_z_delta`, `torso_aspect_ratio`, `torso_posture_delta`, `head_yaw_rate`, `head_pitch_rate`, `shoulder_z_rate`, `tracker_states`, `calibration_state`, `baseline`) are stored in JSONB without requiring database schema migrations for new ML features. Versioned deliberately under `FEATURE_SCHEMA_VERSION = "telemetry_v2"`.

### 4.2. Privacy Guarantees
- **No media storage**: Neither `telemetry_samples` nor any other table in the database contains fields for raw images, image bytes, video files, audio files, or camera frame buffers.
- **Automated enforcement**: The test suite includes `backend/tests/db/test_privacy.py` and `backend/tests/detection/test_telemetry_numerical_correctness.py`, which introspect the SQLAlchemy metadata and live PostgreSQL tables to guarantee that no prohibited media columns exist.

---

## 5. Alembic Migrations

Alembic manages all database migrations deterministically.

### 5.1. Directory Structure & Migration History
```
backend/
├── alembic/
│   ├── env.py                  # Loads Base.metadata and configures sync PostgreSQL engine
│   ├── script.py.mako          # Migration template
│   └── versions/
│       ├── b30bb576b11d_initial_schema.py  # Phase 4: Initial tables, constraints, indexes
│       ├── 621aa6c6d813_add_unique_partial_index_on_active_study_session.py  # Phase 6: Active session uniqueness
│       └── d8b5c2a1e3f4_add_session_feedback_category_and_unique_event.py   # Phase 11: category column & partial unique index
├── alembic.ini                 # Alembic configuration
```

### 5.2. Migration Commands
To apply migrations against the active database:
```bash
cd backend
alembic upgrade head
```

To roll back the initial migration:
```bash
cd backend
alembic downgrade base
```

To view current revision:
```bash
cd backend
alembic current
```

---

## 6. Local Development & Testing Setup

### 6.1. Environment Configuration
The database connection string is configured via the `DATABASE_URL` environment variable:

```bash
# Example local development URL (sync for Alembic / asyncpg translation handled in session.py):
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/student_focus_monitor
```

### 6.2. Test Suite Execution
To run all database tests (model validation, DB-level constraints, cascade relationships, telemetry, privacy, and migration round-trip):
```bash
cd backend
pytest tests/db -v
```

---

## 7. Future Integration Boundaries

| Phase | Boundary / Responsibility |
|---|---|
| **Phase 4 (CURRENT)** | PostgreSQL schema, SQLAlchemy 2.x models, Alembic migrations, database-level constraints, foreign keys, telemetry structure, privacy tests. |
| **Phase 5 (FUTURE)** | Google OAuth 2.0 / OpenID Connect authentication flow, JWT tokens, session credentials. Uses `users` and `auth_identities`. |
| **Phase 6 (FUTURE)** | Study session REST APIs (`/sessions/start`, `/sessions/stop`), session accounting persistence. Uses `study_sessions`. |
| **Phase 7 (COMPLETED)** | WebRTC / WebSocket low-latency transport for frame streaming between React frontend and FastAPI backend. |
| **Phase 8 (COMPLETED)** | Real monitoring orchestrator connecting frame transport with the modular detection engine; discrete DetectionEvent persistence. |
| **Phase 10 (FUTURE)** | Session history, attention trends, and analytics aggregation endpoints. |
| **Phase 11 (FUTURE)** | Anonymized telemetry export and user feedback UI/endpoints. Uses `session_feedback`. |
| **Phase 12–14 (FUTURE)** | Machine learning dataset extraction, offline model training, and ML shadow mode inference. |
