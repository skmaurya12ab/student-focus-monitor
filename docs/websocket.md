# WebSocket Live Transport Protocol Specification (Phase 7)

This document specifies the authoritative real-time WebSocket protocol for camera frame transport between the browser client and the backend server for the Student Focus Monitor.

---

## 1. Overview & Purpose

Phase 7 establishes an ephemeral live transport layer for camera frames without storing video or evaluating distraction detection:

```
Browser Camera (getUserMedia, audio: false)
      ↓
Canvas Resize & JPEG Encoding (~5 FPS)
      ↓
WebSocket Transport (/api/ws/sessions/{session_id})
      ↓
Origin Validation & Cookie Authentication
      ↓
Study Session Ownership & Active Status Check
      ↓
Ephemeral Frame Reception (In-Memory Buffer)
      ↓
Frame Discarded / Acknowledged
      ↓
(Phase 8 Detector Hook Seam - currently None)
```

---

## 2. Endpoint & Handshake

- **Endpoint URL**: `ws://<host>:<port>/api/ws/sessions/{session_id}` (or `wss://` in production)
- **Path Parameter**: `session_id` (UUID format, corresponding to an active `study_sessions.id`)
- **Protocol**: Standard WebSocket (RFC 6455)

### 2.1. Handshake Authentication & Security
1. **Origin Validation**:
   - The server inspects the `Origin` header during handshake.
   - The origin must match configured trusted origins (`settings.cors_origins`, e.g., `http://localhost:5173`, `http://localhost:5174`).
   - Wildcards (`*`) are strictly prohibited for credentialed WebSockets.
   - Untrusted origins are rejected with WebSocket close code **1008 (Policy Violation)**.
2. **Session Authentication**:
   - Normal browser clients send the HttpOnly `sfm_session` cookie automatically during the WebSocket upgrade handshake.
   - External clients/test tools may pass `Authorization: Bearer <session_token>`.
   - If unauthenticated, the connection is rejected with close code **1008 (Policy Violation)**.
3. **Session Ownership & Status**:
   - The session identified by `session_id` must exist in the database.
   - `study_session.user_id` must match the authenticated `current_user.id` (strictly prevents IDOR).
   - `study_session.status` must be `"active"`. If `"completed"` or `"cancelled"`, connection is rejected with close code **1008 (Policy Violation)**.
4. **Single Live Connection Policy**:
   - At most **one** active live WebSocket connection is allowed per active study session.
   - If a second connection is attempted while one is already active, the new connection is rejected with close code **1008 (Policy Violation)** with reason `"Concurrent live transport connection rejected"`.

---

## 3. WebSocket Message Protocol

### 3.1. Server to Client Messages (JSON)

#### Ready Message (Handshake Success)
Sent immediately upon connection acceptance before any frames are received:
```json
{
  "type": "ready",
  "session_id": "cf7a684c-7c08-41eb-811c-d70ee8740529",
  "target_fps": 5,
  "max_frame_size_bytes": 1048576,
  "timestamp": 1727967931.25
}
```

#### Acknowledgment Message
Sent periodically (every 10 received frames) for transport health monitoring:
```json
{
  "type": "ack",
  "frames_received": 10,
  "bytes_received": 142850,
  "frames_dropped": 0,
  "timestamp": 1727967933.10
}
```

#### Pong Message (Heartbeat Response)
Sent in response to a client `ping`:
```json
{
  "type": "pong",
  "timestamp": 1727967935.00
}
```

#### Error Message
Sent if an invalid payload or non-fatal transport error occurs:
```json
{
  "type": "error",
  "message": "Frame size exceeds maximum allowed limit (1048576 bytes)"
}
```

#### Closed Message
Sent before server-initiated clean shutdown (e.g. study session ended):
```json
{
  "type": "closed",
  "reason": "Study session ended",
  "code": 1000
}
```

---

### 3.2. Client to Server Messages

#### 1. Binary Frame Payload (Camera Frames)
- **Format**: Raw binary bytes of a JPEG or WebP encoded image (`Uint8Array` / `Blob`).
- **Resolution**: Scaled to ~480x360 px for optimal transport efficiency.
- **Max Frame Size**: **1,048,576 bytes (1 MB)**. Oversized frames are dropped by the server.
- **Pacing**: Paced at ~5 FPS (~200 ms interval).
- **Backpressure Protection**: The client checks `websocket.bufferedAmount === 0` before sending a new frame. If network congestion delays transmission, the tick is dropped rather than buffering stale frames.

#### 2. Ping Message (JSON)
```json
{
  "type": "ping"
}
```

#### 3. Stop Message (JSON)
Signals client-initiated live transport termination:
```json
{
  "type": "stop"
}
```

#### Detection Result Message (Phase 8 Real Detection)
Sent by the backend detection runtime to stream live detector results to the client:
```json
{
  "type": "detection_result",
  "session_id": "cf7a684c-7c08-41eb-811c-d70ee8740529",
  "timestamp": 1727967931.50,
  "state": "calibrating",
  "active_detections": [
    {
      "category": "looking_away",
      "started_at": 1727967911.50,
      "duration_seconds": 20.0
    }
  ],
  "new_events": [
    {
      "event_id": "14f2e964-b86a-4d7a-8b89-29178ad3a6cc",
      "category": "looking_away",
      "started_at": 1727967911.50
    }
  ],
  "ended_events": [],
  "metrics": {
    "focus_score": 85.0,
    "focused_seconds": 120.0,
    "distracted_seconds": 20.0,
    "away_seconds": 0.0
  }
}
```
State values: `"calibrating"`, `"focused"`, `"distracted"`, `"away"`, `"detector_error"`.

---

## 4. Connection State Machine

The client live transport lifecycle is represented by explicit, disjoint states:

```
                 [idle]
                   │
                   ▼ (user clicks Start Live Session)
           [starting_camera] ──(denied)──► [permission_denied]
                   │         ──(missing)─► [camera_unavailable]
                   ▼
            [camera_ready]
                   │
                   ▼
             [connecting] ────(error)────► [connection_error]
                   │
                   ▼ (receives "ready")
              [connected] ◄──┐
                   │         │ (reconnect)
                   ▼         │
             [disconnected] ─┘ (bounded retries: 3 attempts)
                   │
                   ▼ (user stops live or session ends)
               [stopping] ──► [idle]
```

---

## 5. Lifecycle Independence

### Rule 1: Live Disconnection does NOT terminate Study Session
- If the WebSocket closes unexpectedly or network drops, the persistent `study_sessions` row in PostgreSQL remains `status = "active"`.
- The frontend shows `STANDBY` / `disconnected` and allows reconnection using the **exact same `session_id`**.

### Rule 2: Stopping Live Session leaves Study Session ACTIVE
- Clicking `#btn-start-live-session` (when in "Stop Live Session" state) tears down the camera tracks and closes the WebSocket cleanly.
- The Study Session container remains active. The session timer continues running.

### Rule 3: Ending Study Session proactively terminates Live Transport
- Clicking `#btn-start-study-session` (when in "End Study Session" state) transitions the database session to `status = "completed"`.
- The backend's `SessionService.stop_session` proactively calls `live_transport_manager.close_session_transport(session_id, code=1000, reason="Study session ended")`.
- The frontend context stops video tracks and resets transport to `idle`.
- Completed sessions strictly reject future WebSocket handshakes.

---

## 6. Privacy & Security Guarantees

1. **NO Persistent Media Storage**:
   - Zero image frames written to disk.
   - Zero image frames stored in PostgreSQL.
   - Zero image bytes logged in server application logs.
   - In-memory frame buffers are dereferenced and garbage collected immediately after transport handling.
2. **Audio/Microphone Exclusion**:
   - `getUserMedia` requests `{ video: true, audio: false }`. No microphone access is ever requested or captured.
3. **No Credential Leakage**:
   - No JWTs or session secrets in the WebSocket URL.
   - Authentication relies solely on standard browser HttpOnly cookies.

---

## 7. Phase 8 Detector Integration
In Phase 8, `LiveTransportManager` connects incoming frames directly to `DetectionRuntimeManager.submit_frame`:
```python
# Phase 8 Integration:
live_transport_manager.detector_hook = detection_runtime_manager.submit_frame
```
Frames are received by the session-scoped detector runtime without modifying transport protocol or auth. The detector worker processes frames asynchronously via MediaPipe and broadcasts structured `detection_result` payloads back over the active WebSocket.

---

## 8. Phase 9 Live Dashboard Integration & Real-Time Corrections

In Phase 9, the frontend Home dashboard consumes live WebSocket payloads and manages real-time monitoring state:

1. **Truthful 12-Condition Live Badge State Machine**:
   - `STANDBY`: Camera transport idle, awaiting user action.
   - `STARTING CAMERA`: Hardware video acquisition initiated.
   - `CONNECTING (Initial)`: WebSocket handshake in progress.
   - `CONNECTING (Reconnecting)`: WebSocket reconnection attempt after dropped link.
   - `CALIBRATING`: Live stream active; calibrating baseline posture (`samples_collected` / `required_samples`).
   - `LIVE / FOCUSED`: Normal focused monitoring state.
   - `LIVE / DISTRACTED`: One or more sustained distraction detectors triggered.
   - `LIVE / AWAY`: Student has vacated desk.
   - `LIVE DISCONNECTED`: Transport interrupted unexpectedly while session active.
   - `CAMERA ERROR (Permission Denied)`: User denied camera access permission.
   - `CAMERA ERROR (Hardware Unavailable)`: Webcam hardware unavailable or in use by another process.
   - `DETECTOR ERROR`: Runtime detector processing exception or transport error.

2. **Persistent Distraction Banner**:
   - Prominent on-screen banner ("YOU ARE DISTRACTED") visible continuously while in a distracted state.
   - Displays consolidated active detector reasons (e.g., `Phone Use • Looking Away`) and elapsed active duration.
   - Synchronized strictly with authoritative `detection_result` messages; automatically disappears when focus is restored.
   - Does NOT use arbitrary frontend timeout timers.

3. **Repeating / Pulsating Web Audio API Alert Feedback**:
   - Browser-compatible Web Audio API synthesis (GainNode = 1.0 maximum application-level volume).
   - AudioContext unlocked from user interaction gestures (e.g. clicking *Start Live Session*).
   - Beeps in pulsating pulses (~250ms tone + 550ms pause) continuously while distracted.
   - Stops immediately when focus returns, live monitoring stops, or socket disconnects.
   - Single managed timer prevents overlapping sound loops across incoming messages or multiple simultaneous detectors.
   - If sound alerts are disabled in Settings (`sound_alerts_enabled: false`), audio is suppressed while visual banner remains fully functional.

4. **User-Configurable Alert Delays (Persistence Thresholds)**:
   - Configured via Settings UI (`/api/settings` GET/PATCH) and stored in PostgreSQL `user_settings`.
   - Loaded authoritatively into `SessionDetectionRuntime` and `MultiCategoryTracker` at WebSocket connection.
   - Alert thresholds define *how long a detected condition must persist* before becoming an alert (e.g. 2s vs 8s).
   - Underlying computer-vision feature thresholds (EAR 0.21, MAR 0.55, yaw 10°, hand proximity 0.15) remain strictly separate.

5. **Focus Timeline State Progression**:
   - Real-time slice recording of focus progression (`focused`, `distracted`, `away`, `calibrating`).
   - A brand new session begins with a clean, short initial timeline (no fabricated historical data).
   - Segments scale proportionally to actual recorded durations.


