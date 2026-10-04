# API Reference Documentation

This document describes the REST API endpoints implemented for the Student Focus Monitor, focusing on **Phase 5 (Authentication & Account)** and **Phase 6 (Study Session Lifecycle)**.

---

## 1. Authentication & Cookie Architecture

All protected endpoints require an authenticated user session established via the HttpOnly cookie `sfm_session`.

- **Transport**: HttpOnly, SameSite=Lax, Secure (in production).
- **Frontend Clients**: Must make requests with `credentials: "include"`.
- **Identity Source**: Current user identity is authoritatively determined server-side from `sfm_session` (or `Authorization: Bearer <token>` for external CLI tools). The client **never** supplies `user_id` as the authority.

---

## 2. Study Session Lifecycle Endpoints (Phase 6)

The canonical entity is `study_sessions`. A study session is the root parent container for all subsequent telemetry, detection events, and feedback (introduced in later phases).

### 2.1. Start Study Session

Creates a new active study session for the authenticated user.

- **Method / Path**: `POST /api/sessions`
- **Authentication**: Required (`sfm_session` cookie)
- **Request Body** (optional):
  ```json
  {
    "detector_version": "2.0.0",
    "feature_schema_version": "1.0.0"
  }
  ```
- **Lifecycle Semantics**:
  1. Authenticates current user.
  2. Verifies user has NO currently active session.
  3. Generates UUID server-side (`id`).
  4. Generates UTC timestamp server-side (`started_at`).
  5. Sets `status = "active"`.
  6. Detection-derived metrics (`focused_seconds`, `distracted_seconds`, `away_seconds`, `focus_score`) remain `null`.
- **Response**: `201 Created`
  ```json
  {
    "id": "1ddb9c9e-...",
    "user_id": "81190744-...",
    "status": "active",
    "started_at": "2026-10-03T14:05:32.787495Z",
    "ended_at": null,
    "total_duration_seconds": null,
    "focused_seconds": null,
    "distracted_seconds": null,
    "away_seconds": null,
    "focus_score": null,
    "detector_version": "2.0.0",
    "feature_schema_version": "1.0.0",
    "created_at": "2026-10-03T14:05:32.787495Z",
    "updated_at": "2026-10-03T14:05:32.787495Z"
  }
  ```
- **Error Codes**:
  - `401 Unauthorized`: Not authenticated.
  - `409 Conflict`: User already has an active study session (`"Active study session already exists"`).

---

### 2.2. Get Active Study Session

Retrieves the authenticated user's currently active study session (if any). Enables state recovery after page refresh.

- **Method / Path**: `GET /api/sessions/active`
- **Authentication**: Required (`sfm_session` cookie)
- **Response**: `200 OK`
  - If active session exists:
    ```json
    {
      "session": {
        "id": "1ddb9c9e-...",
        "user_id": "81190744-...",
        "status": "active",
        "started_at": "2026-10-03T14:05:32.787495Z",
        "ended_at": null,
        "total_duration_seconds": null,
        "focus_score": null,
        ...
      }
    }
    ```
  - If no active session exists:
    ```json
    {
      "session": null
    }
    ```
- **Error Codes**:
  - `401 Unauthorized`: Not authenticated.

---

### 2.3. Get Study Session by ID

Retrieves a specific study session by ID, strictly enforcing ownership.

- **Method / Path**: `GET /api/sessions/{session_id}`
- **Authentication**: Required (`sfm_session` cookie)
- **Authorization**: The authenticated user must own the session (`session.user_id == current_user.id`).
- **Response**: `200 OK`
  ```json
  {
    "id": "1ddb9c9e-...",
    "user_id": "81190744-...",
    "status": "active",
    "started_at": "2026-10-03T14:05:32.787495Z",
    "ended_at": null,
    "total_duration_seconds": null,
    "focus_score": null,
    ...
  }
  ```
- **Error Codes**:
  - `401 Unauthorized`: Not authenticated.
  - `404 Not Found`: Session does not exist OR belongs to another user (prevents IDOR user enumeration).

---

### 2.4. Stop Study Session

Transitions an active study session to `completed` and computes authoritative duration.

- **Method / Path**: `POST /api/sessions/{session_id}/stop`
- **Authentication**: Required (`sfm_session` cookie)
- **Authorization**: The authenticated user must own the session.
- **Lifecycle Semantics**:
  1. Authenticates current user and looks up session.
  2. Verifies ownership (`404 Not Found` if session belongs to another user).
  3. Verifies session is currently in `active` status.
  4. Generates UTC timestamp server-side (`ended_at`).
  5. Computes authoritative duration:
     $$\text{total\_duration\_seconds} = \max(0.0, (\text{ended\_at} - \text{started\_at}).\text{total\_seconds}())$$
  6. Sets `status = "completed"`.
  7. Persists updates to PostgreSQL.
- **Response**: `200 OK`
  ```json
  {
    "message": "Study session completed successfully",
    "session": {
      "id": "1ddb9c9e-...",
      "user_id": "81190744-...",
      "status": "completed",
      "started_at": "2026-10-03T14:05:32.787495Z",
      "ended_at": "2026-10-03T14:07:35.741082Z",
      "total_duration_seconds": 122.95,
      "focused_seconds": null,
      "distracted_seconds": null,
      "away_seconds": null,
      "focus_score": null,
      "detector_version": "2.0.0",
      "feature_schema_version": "1.0.0",
      "created_at": "2026-10-03T14:05:32.787495Z",
      "updated_at": "2026-10-03T14:07:35.741082Z"
    }
  }
  ```
- **Error Codes**:
  - `401 Unauthorized`: Not authenticated.
  - `404 Not Found`: Session does not exist or belongs to another user.
  - `409 Conflict`: Session is not active (e.g., already completed or cancelled).

---

## 3. Concurrency & Invariant Enforcement

- **Invariant**: A user may have at most **one** active study session at any time.
- **Enforcement Layers**:
  1. **Application Service**: `SessionService.create_session` queries for an existing active session before inserting.
  2. **Database Partial Unique Index**: `CREATE UNIQUE INDEX uq_study_sessions_user_active ON study_sessions (user_id) WHERE status = 'active';`
  3. If two concurrent requests arrive simultaneously, PostgreSQL's index guarantees one commits and the second fails with a unique constraint violation, cleanly mapped to HTTP 409 Conflict.

---

---

## 4. Live Transport WebSocket Endpoint (Phase 7)

For full protocol specification, refer to [docs/websocket.md](websocket.md).

### 4.1. Live Camera Transport WebSocket

Establishes an ephemeral, bidirectional live transport channel for streaming camera preview frames.

- **Protocol / Path**: `WS /api/ws/sessions/{session_id}`
- **Authentication**: Required (`sfm_session` HttpOnly cookie or `Authorization: Bearer` header)
- **Origin Validation**: Required (`Origin` header must match configured trusted origins; wildcards rejected)
- **Authorization**:
  - The session identified by `{session_id}` must exist.
  - The session must belong to the authenticated user (`session.user_id == current_user.id`).
  - The session must be in `status = "active"`.
- **Concurrency Policy**:
  - At most **one** active live connection is permitted per active study session.
  - Concurrent connection attempts are rejected with code `1008`.
- **Payload Limits**:
  - Binary frames: Max 1,048,576 bytes (1 MB).
  - Rate limit: Max 15 FPS.
- **Privacy Guarantee**:
  - Zero media persistence: frames are ephemeral and discarded after transport handling.
- **Close Codes**:
  - `1000`: Normal closure (user stopped live session or study session completed).
  - `1008`: Policy violation (unauthenticated, untrusted origin, wrong user, session not active, or duplicate connection).

---

### 4.2. User Settings & Alert Delays Endpoints (Phase 9)

- **GET `/api/settings`**: Retrieves current authenticated user's configuration, alert persistence delays, and notification preferences.
- **PATCH `/api/settings`**: Updates alert persistence delays and notification toggles. Immediately persists to PostgreSQL and dynamically updates active live detection runtimes for the user.

---

## 5. Session History & Historical Analytics Endpoints (Phase 10)

Phase 10 converts the Sessions and Analytics features into real PostgreSQL-backed query endpoints for completed study sessions and discrete detection events.

### 5.1. Get Session History (Paginated)

Retrieves a paginated list of historical study sessions for the authenticated user, ordered deterministically by `ended_at DESC, started_at DESC, id DESC`.

- **Method / Path**: `GET /api/sessions/history`
- **Authentication**: Required (`sfm_session` HttpOnly cookie)
- **Authorization**: Strictly restricted to sessions where `session.user_id == current_user.id`. Sessions belonging to other users are never returned.
- **Query Parameters**:
  - `page` (integer, default `1`, minimum `1`): 1-indexed page number.
  - `page_size` (integer, default `10`, minimum `1`, maximum `50`): Number of sessions per page (bounded).
  - `status` (string, optional): Filter by session status (e.g., `"completed"`, `"active"`).
- **Response**: `200 OK`
  ```json
  {
    "items": [
      {
        "id": "1ddb9c9e-5b1e-450a-8bf8-d0dfd87b3281",
        "user_id": "81190744-8840-424a-ae91-381a1792f494",
        "status": "completed",
        "started_at": "2026-10-04T10:00:00Z",
        "ended_at": "2026-10-04T11:00:00Z",
        "total_duration_seconds": 3600.0,
        "focused_seconds": 3000.0,
        "distracted_seconds": 400.0,
        "away_seconds": 200.0,
        "focus_score": 83.33,
        "distraction_count": 2,
        "detector_version": "v4",
        "feature_schema_version": "telemetry_v1",
        "created_at": "2026-10-04T10:00:00Z",
        "updated_at": "2026-10-04T11:00:00Z"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 10,
    "total_pages": 1
  }
  ```
- **Error Codes**:
  - `401 Unauthorized`: Not authenticated.
  - `422 Unprocessable Entity`: Invalid query parameters (`page < 1` or `page_size < 1`).

---

### 5.2. Get Session Detail with Discrete Events

Retrieves complete details for a specific historical session, including discrete `detection_events` and category cause summaries.

- **Method / Path**: `GET /api/sessions/{session_id}`
- **Authentication**: Required (`sfm_session` HttpOnly cookie)
- **Authorization & IDOR Protection**: The authenticated user must own the session (`session.user_id == current_user.id`). If the session belongs to another user, `404 Not Found` is returned without leaking existence.
- **Response**: `200 OK`
  ```json
  {
    "id": "1ddb9c9e-5b1e-450a-8bf8-d0dfd87b3281",
    "user_id": "81190744-8840-424a-ae91-381a1792f494",
    "status": "completed",
    "started_at": "2026-10-04T10:00:00Z",
    "ended_at": "2026-10-04T11:00:00Z",
    "total_duration_seconds": 3600.0,
    "focused_seconds": 3000.0,
    "distracted_seconds": 400.0,
    "away_seconds": 200.0,
    "focus_score": 83.33,
    "distraction_count": 2,
    "detector_version": "v4",
    "feature_schema_version": "telemetry_v1",
    "created_at": "2026-10-04T10:00:00Z",
    "updated_at": "2026-10-04T11:00:00Z",
    "top_causes": "Top causes: Phone Use · Looking Away",
    "category_breakdown": [
      {
        "category": "phone_use",
        "label": "Phone Use",
        "count": 1,
        "duration_seconds": 200.0
      },
      {
        "category": "looking_away",
        "label": "Looking Away",
        "count": 1,
        "duration_seconds": 200.0
      }
    ],
    "events": [
      {
        "id": "2fe98ab2-143f-4217-91a0-e6f778931a29",
        "session_id": "1ddb9c9e-5b1e-450a-8bf8-d0dfd87b3281",
        "event_type": "phone_use",
        "started_at": "2026-10-04T10:15:00Z",
        "ended_at": "2026-10-04T10:18:20Z",
        "duration_seconds": 200.0,
        "detector_version": "v4",
        "metadata_json": null,
        "created_at": "2026-10-04T10:15:00Z"
      }
    ]
  }
  ```
- **Error Codes**:
  - `401 Unauthorized`: Not authenticated.
  - `404 Not Found`: Session does not exist or belongs to another user.

---

### 5.3. Get Historical Focus Analytics

Aggregates historical performance metrics across completed study sessions within a specified date range and client timezone.

- **Method / Path**: `GET /api/analytics`
- **Authentication**: Required (`sfm_session` HttpOnly cookie)
- **Query Parameters**:
  - `range` (string, default `"7d"`): Supported filters: `"7d"` (last 7 days), `"30d"` (last 30 days), `"all"` (all available history).
  - `tz` (string, default `"UTC"`): IANA timezone identifier (e.g., `"America/New_York"`, `"Asia/Kolkata"`). Session daily aggregation is bucketed according to the user's local date boundaries so that late-night sessions do not shift across local midnight.
- **Aggregation Definitions & Metric Sources of Truth**:
  - `total_study_time_seconds`: `SUM(study_sessions.total_duration_seconds)` for completed sessions in range.
  - `average_session_duration_seconds`: `AVG(study_sessions.total_duration_seconds)` for completed sessions in range (or `0.0` if 0 completed sessions).
  - `average_focus_score`: `AVG(study_sessions.focus_score)` across completed sessions in range (or `null` if 0 completed sessions).
  - `total_distracted_seconds`: `SUM(study_sessions.distracted_seconds)`.
  - `total_away_seconds`: `SUM(study_sessions.away_seconds)`.
  - `total_distractions`: `COUNT(detection_events.id)` for completed sessions in range.
  - `category_breakdown`: Aggregated event counts and durations grouped by `detection_events.event_type` for the 6 canonical categories (`looking_away`, `phone_use`, `yawning`, `drowsy`, `leaning_back`, `away_from_desk`).
  - `daily_trends`: Continuous daily buckets over the range. Days with no sessions explicitly have `focus_score = null` (not 0%) and `session_count = 0`.
- **Response**: `200 OK`
  ```json
  {
    "range": "7d",
    "start_date": "2026-09-28",
    "end_date": "2026-10-04",
    "timezone": "UTC",
    "summary": {
      "total_study_time_seconds": 7200.0,
      "average_session_duration_seconds": 3600.0,
      "average_focus_score": 85.0,
      "total_distracted_seconds": 600.0,
      "total_away_seconds": 200.0,
      "total_distractions": 4,
      "completed_sessions_count": 2
    },
    "trend": {
      "title": "Focus Score Trend",
      "subtitle": "Weekly focus score · last 7 days",
      "badge_text": "This week",
      "score": "85%",
      "change_text": "+5% vs last week",
      "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
      "data": [...],
      "trend_lines": [...],
      "points": [...]
    },
    "breakdown": {
      "title": "Distraction Breakdown",
      "categories": [
        {
          "id": "phone_use",
          "category": "phone_use",
          "label": "Phone use",
          "count": 2,
          "duration_seconds": 300.0,
          "duration": "5m",
          "percent_width": 100.0
        }
      ],
      "footer_summary": "4 detected events · 10m distracted",
      "total_distraction_seconds": 600.0,
      "total_events": 4
    },
    "comparison": {
      "title": "Comparison",
      "rows": [
        {
          "id": "comp-today",
          "period": "Today",
          "score": "85%",
          "duration": "2h 00m"
        }
      ],
      "date_range": "Sep 28 — Oct 04, 2026"
    }
  }
  ```
- **Empty State Behavior**:
  When a user has no completed sessions, the endpoint returns `completed_sessions_count: 0`, `average_focus_score: null`, `score: "—"`, and empty arrays for categories, points, and comparison rows. The frontend renders "No analytics available yet." without leaking any mock values.
- **Error Codes**:
  - `401 Unauthorized`: Not authenticated.
  - `422 Unprocessable Entity`: Invalid date range parameter.

---

## 6. Detection & Future Compatibility (Phase 11+)

Phase 6 established the authoritative session container (`id`), Phase 7 established live transport, Phase 8 connected the real MediaPipe detection engine, Phase 9 integrated the live real-time dashboard, and Phase 10 integrated historical session queries and focus analytics:
- **Phase 8 (Real Detection — Completed)**: Real MediaPipe detector integration into the live stream using the established `detector_hook` seam. Real `detection_events` are persisted in PostgreSQL, and final session focus scores are calculated upon session stop.
- **Phase 9 (Live Dashboard — Completed)**: Real-time dashboard integration preserving Figma design truth, repeating pulsating audio alert with Web Audio API, prominent persistent distraction banner, user-configurable persistence thresholds via `/api/settings`, dynamic session metrics, and live state progression timeline.
- **Phase 10 (Session History & Analytics — Completed)**: Real PostgreSQL-backed historical session browsing with server-side bounded pagination, session detail view with discrete `DetectionEvent`s and canonical category breakdowns, and historical focus analytics with date-range filtering, timezone-aware bucketing, dynamic trend lines, and IDOR protection.
- **Phase 11 (Telemetry — Future)**: Telemetry samples will reference `telemetry_samples.session_id`.
- Zero ML or trained neural network models are used; the deterministic v4-lineage rule-based engine is the production detection engine. ML remains intentionally deferred to Phases 12–14.



