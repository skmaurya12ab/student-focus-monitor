# Privacy & Data Protection Architecture

> **Absolute Privacy Principle**: The Student Focus Monitor is architected from the ground up to protect student visual and auditory privacy. Under no circumstances does the system store, persist, archive, transmit to cloud media buckets, or retain raw webcam images, video streams, audio recordings, or media byte buffers.

---

## 1. Zero Raw Media Guarantee

The Student Focus Monitor processes camera frames strictly in ephemeral memory for instantaneous geometric landmark extraction:

```
Webcam Frame (Browser Memory)
      ↓
Transported via Encrypted WebSocket (/api/ws/sessions/{session_id})
      ↓
Decoded in ephemeral RAM by OpenCV / MediaPipe Tasks
      ↓
Landmarks extracted (x, y, z normalized floats)
      ↓
RAW FRAME IMMEDIATELY DISCARDED FROM RAM
      ↓
Feature extraction (EAR, MAR, head pose angles, distances)
      ↓
Rule evaluation & Tracker updates
      ↓
Numerical Telemetry Persisted (Numbers, timestamps, flags only)
```

### Prohibited Artifacts (Strictly Never Stored)
- Webcam images (JPEG, PNG, WebP)
- Video streams or recordings (MP4, MKV, AVI, WebM)
- Ephemeral pixel frame buffers on disk or database
- Screenshots of the student
- Microphone or audio recordings
- Filesystem media paths to captured images

### Automated Privacy Enforcement
The test suite continuously enforces this architecture through automated schema introspection and payload auditing:
1. `backend/tests/db/test_privacy.py`: Introspects SQLAlchemy metadata and PostgreSQL table columns to guarantee that no column contains media or image byte representations.
2. `backend/tests/detection/test_telemetry.py` & `backend/tests/detection/test_telemetry_numerical_correctness.py`: Scans every telemetry sample dictionary recursively for prohibited substrings (`image`, `video`, `jpeg`, `png`, `frame_bytes`, `audio`, `raw_buffer`, `screenshot`, `camera`).
3. `BufferedTelemetrySink`: Actively filters and strips any prohibited keys prior to buffering or database insertion.

---

## 2. Numerical Telemetry Storage (`telemetry_samples`)

Telemetry is preserved exclusively as numerical measurements, baseline deltas, motion rates, and canonical detection flags:

- **Scalar Metrics**:
  - `head_pitch`, `head_yaw`, `head_roll` (degrees)
  - `ear` (Eye Aspect Ratio, float)
  - `mar` (Mouth Aspect Ratio, float)
  - `min_hand_cheek_distance` (normalized Euclidean distance)
  - `shoulder_z` (normalized depth)
  - `face_present`, `pose_present` (boolean presence indicators)
  - `hand_count` (integer count)
  - `focus_state` (canonical string: `focused`, `distracted`, `away`, `calibrating`)
- **JSONB Features (`features`)**:
  - Baseline-relative posture differences (`head_yaw_from_baseline`, `shoulder_z_delta`, `torso_posture_delta`)
  - Motion velocities (`head_yaw_rate`, `head_pitch_rate`, `shoulder_z_rate`)
  - Rule activation booleans and persistence tracker states
  - Personal calibration status and medians
- **Null Semantics**:
  - If a metric is not available (e.g., face occluded), it is stored as `NULL`/`None`, never converted into a misleading zero.

---

## 3. User Feedback & Voluntary Human Labeling (`session_feedback`)

- **Voluntary Participation**: Students provide feedback voluntarily on historical sessions. Feedback prompts never interrupt active study monitoring.
- **Bounded Inputs**: User notes are strictly limited to 1000 characters and are not indexed for text search.
- **Ownership & IDOR Protection**: Feedback records are accessible and mutable only by the authenticated owner of the study session. Cross-user access is blocked with HTTP 404/403.
- **Zero Media Association**: Feedback labels reference only `session_id`, `detection_event_id`, canonical distraction categories, and numerical telemetry timestamps.

---

## 4. Authentication & Network Boundary

- Authentication uses HttpOnly, Secure, SameSite=Lax cookies (`sfm_session`).
- Tokens are never stored in browser `localStorage`, session storage, or URL query parameters.
- WebSockets enforce strict `Origin` header matching against configured trusted origins. Wildcard origins are rejected.
