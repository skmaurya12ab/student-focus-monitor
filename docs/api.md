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

## 5. Phase 8/9 Detection & Future Compatibility (Phase 10+)

Phase 6 established the authoritative session container (`id`), Phase 7 established live transport, Phase 8 connected the real MediaPipe detection engine, and Phase 9 integrated the live real-time dashboard:
- **Phase 8 (Real Detection — Completed)**: Real MediaPipe detector integration into the live stream using the established `detector_hook` seam. Real `detection_events` are persisted in PostgreSQL, and final session focus scores are calculated upon session stop.
- **Phase 9 (Live Dashboard — Completed)**: Real-time dashboard integration preserving Figma design truth, repeating pulsating audio alert with Web Audio API, prominent persistent distraction banner, user-configurable persistence thresholds via `/api/settings`, dynamic session metrics, and live state progression timeline.
- **Phase 10 (Session History — Future)**: Historical session analytics, past session detail views, and timeline aggregation.
- **Phase 11 (Telemetry — Future)**: Telemetry samples will reference `telemetry_samples.session_id`.
- Zero ML or trained neural network models are used; the deterministic v4-lineage rule-based engine is the production detection engine. ML remains intentionally deferred to Phases 12–14.


