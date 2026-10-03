"""
Student Distraction Detection System — v4
==========================================

Purpose
-------
This version keeps the existing rule-based detection approach but restructures it
so that the detection engine can later be reused by FastAPI/WebSocket code.

Privacy
-------
- No user photos or videos are written to disk.
- The webcam frame exists only in memory while the program is running.
- Numerical feature telemetry is sampled and stored as JSONL.
- Detection events are stored separately as JSONL.
- A session metadata JSON file stores the detector/configuration snapshot.

What is improved from v3
------------------------
1. Session-specific detector state instead of global trackers/baselines.
2. Personal calibration at the beginning of a session.
3. Head orientation is evaluated relative to the user's calibrated baseline.
4. Configurable per-user alert delays remain part of the decision/policy layer.
5. Telemetry records derived numerical features, movement deltas/rates,
   detection flags, active alerts, and the threshold configuration used.
6. Detection events are explicitly logged with their duration and trigger delay.
7. No video/image recording.
8. The detector core is separated from the OpenCV desktop runner so the same
   detector can later be called by the web backend.
9. Optional desktop alarm remains available for local testing; the future web
   frontend should implement its own browser-side alarm.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
import urllib.request
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import cv2
import mediapipe as mp
import numpy as np

# Windows-only sound. The detector itself does not depend on it.
try:
    import winsound  # type: ignore
except ImportError:
    winsound = None


# ---------------------------------------------------------------------------
# MediaPipe Tasks API
# ---------------------------------------------------------------------------

BaseOptions = mp.tasks.BaseOptions
RunningMode = mp.tasks.vision.RunningMode
FaceLandmarker = mp.tasks.vision.FaceLandmarker
FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
HandLandmarker = mp.tasks.vision.HandLandmarker
HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
PoseLandmarker = mp.tasks.vision.PoseLandmarker
PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
PoseLandmark = mp.tasks.vision.PoseLandmark
drawing_utils = mp.tasks.vision.drawing_utils
FaceConnections = mp.tasks.vision.FaceLandmarksConnections
HandConnections = mp.tasks.vision.HandLandmarksConnections
PoseConnections = mp.tasks.vision.PoseLandmarksConnections


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DETECTOR_VERSION = "v4"
FEATURE_SCHEMA_VERSION = "telemetry_v1"

MODEL_DIR = Path(__file__).resolve().parent / "models"
DATA_DIR = Path(__file__).resolve().parent / "data"

MODEL_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "telemetry").mkdir(parents=True, exist_ok=True)
(DATA_DIR / "events").mkdir(parents=True, exist_ok=True)
(DATA_DIR / "sessions").mkdir(parents=True, exist_ok=True)

MODEL_URLS = {
    "face_landmarker.task":
        "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
    "hand_landmarker.task":
        "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
    "pose_landmarker_lite.task":
        "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task",
}

FACE_MODEL = MODEL_DIR / "face_landmarker.task"
HAND_MODEL = MODEL_DIR / "hand_landmarker.task"
POSE_MODEL = MODEL_DIR / "pose_landmarker_lite.task"


@dataclass
class DetectorConfig:
    """
    Detection thresholds are policy/configuration, not ML model weights.

    Alert delays are intentionally configurable per user. They should be
    persisted with sessions/telemetry so future ML training knows what
    sensitivity policy was active when a sample was collected.
    """

    # Feature/detection thresholds.
    yaw_threshold_deg: float = 10.0
    ear_threshold: float = 0.21
    mar_threshold: float = 0.55
    hand_near_cheek_dist: float = 0.15
    lean_back_z_delta: float = 0.15

    # Time persistence before an alert becomes active.
    alert_delays_sec: dict[str, float] = field(default_factory=lambda: {
        "Looking Away": 20.0,
        "Phone Use": 20.0,
        "Yawning": 2.0,
        "Drowsy/Eyes Closed": 20.0,
        "Leaning Back": 20.0,
        "Away From Desk": 20.0,
    })

    # Personal calibration.
    calibration_seconds: float = 10.0
    minimum_calibration_samples: int = 30

    # Telemetry sampling. 2 Hz = one feature row every 0.5 sec.
    telemetry_interval_sec: float = 0.5

    # Local desktop runner options.
    draw_landmarks: bool = True
    enable_desktop_alarm: bool = True


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

LEFT_EYE = [362, 385, 387, 263, 373, 380]
RIGHT_EYE = [33, 160, 158, 133, 153, 144]
MOUTH = {"left": 61, "right": 291, "top": 13, "bottom": 14}

LEFT_CHEEK_IDX = 234
RIGHT_CHEEK_IDX = 454


def utc_iso(timestamp: Optional[float] = None) -> str:
    """Return an ISO-8601 UTC timestamp."""
    if timestamp is None:
        dt = datetime.now(timezone.utc)
    else:
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    return dt.isoformat()


def finite_or_none(value: Any) -> Optional[float]:
    """Convert a numeric value to a JSON-safe float."""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if np.isfinite(v) else None


def landmark_xy(landmarks, idx: int, w: int, h: int) -> np.ndarray:
    lm = landmarks[idx]
    return np.array([lm.x * w, lm.y * h], dtype=np.float64)


def landmark_norm_xy(landmarks, idx: int) -> np.ndarray:
    lm = landmarks[idx]
    return np.array([lm.x, lm.y], dtype=np.float64)


def eye_aspect_ratio(landmarks, eye_idx, w: int, h: int) -> float:
    p1, p2, p3, p4, p5, p6 = [
        landmark_xy(landmarks, i, w, h) for i in eye_idx
    ]
    vertical = np.linalg.norm(p2 - p6) + np.linalg.norm(p3 - p5)
    horizontal = np.linalg.norm(p1 - p4)
    if horizontal <= 1e-9:
        return 0.0
    return float(vertical / (2.0 * horizontal))


def mouth_aspect_ratio(landmarks, w: int, h: int) -> float:
    left = landmark_xy(landmarks, MOUTH["left"], w, h)
    right = landmark_xy(landmarks, MOUTH["right"], w, h)
    top = landmark_xy(landmarks, MOUTH["top"], w, h)
    bottom = landmark_xy(landmarks, MOUTH["bottom"], w, h)
    horizontal = np.linalg.norm(left - right)
    if horizontal <= 1e-9:
        return 0.0
    return float(np.linalg.norm(top - bottom) / horizontal)


def compute_head_pose(landmarks, w: int, h: int) -> tuple[float, float, float]:
    """
    6-point solvePnP head-pose estimation used by the existing detector.
    Returns pitch, yaw, roll in degrees.
    """
    face_2d, face_3d = [], []

    for idx in (33, 263, 1, 61, 291, 199):
        lm = landmarks[idx]
        x, y = float(lm.x * w), float(lm.y * h)
        face_2d.append([x, y])
        face_3d.append([x, y, float(lm.z)])

    face_2d = np.array(face_2d, dtype=np.float64)
    face_3d = np.array(face_3d, dtype=np.float64)

    focal_length = float(w)
    cam_matrix = np.array(
        [
            [focal_length, 0, w / 2],
            [0, focal_length, h / 2],
            [0, 0, 1],
        ],
        dtype=np.float64,
    )
    dist_matrix = np.zeros((4, 1), dtype=np.float64)

    success, rot_vec, _ = cv2.solvePnP(
        face_3d,
        face_2d,
        cam_matrix,
        dist_matrix,
        flags=cv2.SOLVEPNP_ITERATIVE,
    )

    if not success:
        raise RuntimeError("Head pose solvePnP failed.")

    rmat, _ = cv2.Rodrigues(rot_vec)
    angles, _, _, _, _, _ = cv2.RQDecomp3x3(rmat)

    pitch = float(angles[0] * 360)
    yaw = float(angles[1] * 360)
    roll = float(angles[2] * 360)

    return pitch, yaw, roll


# ---------------------------------------------------------------------------
# Model download
# ---------------------------------------------------------------------------

def ensure_models() -> None:
    """Download MediaPipe model bundles once, exactly as the original project."""
    for filename, url in MODEL_URLS.items():
        path = MODEL_DIR / filename
        if not path.exists():
            print(f"Downloading {filename} (one-time setup)...")
            urllib.request.urlretrieve(url, path)


# ---------------------------------------------------------------------------
# Persistence tracker
# ---------------------------------------------------------------------------

class PersistenceTracker:
    """
    Tracks a condition until it persists long enough to become an alert.

    The important distinction is:
        condition starts -> not necessarily an alert
        condition persists for delay -> alert begins
        condition clears -> alert ends
    """

    def __init__(self, delay: float):
        self.delay = float(delay)
        self.condition_started_at: Optional[float] = None
        self.alert_started_at: Optional[float] = None

    @property
    def is_active(self) -> bool:
        return self.alert_started_at is not None

    def update(
        self,
        condition_is_true: bool,
        now: float,
    ) -> dict[str, Any]:
        just_started = False
        just_ended = False
        ended_duration = None

        if not condition_is_true:
            if self.alert_started_at is not None:
                ended_duration = max(0.0, now - self.alert_started_at)
                just_ended = True

            self.condition_started_at = None
            self.alert_started_at = None

            return {
                "active": False,
                "just_started": False,
                "just_ended": just_ended,
                "duration_sec": ended_duration,
            }

        if self.condition_started_at is None:
            self.condition_started_at = now

        if self.alert_started_at is None:
            sustained_for = now - self.condition_started_at

            if sustained_for >= self.delay:
                self.alert_started_at = now
                just_started = True

        duration = None
        if self.alert_started_at is not None:
            duration = max(0.0, now - self.alert_started_at)

        return {
            "active": self.alert_started_at is not None,
            "just_started": just_started,
            "just_ended": False,
            "duration_sec": duration,
        }


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------

@dataclass
class CalibrationBaseline:
    shoulder_z: Optional[float] = None
    head_yaw: Optional[float] = None
    head_pitch: Optional[float] = None
    head_roll: Optional[float] = None


class CalibrationBuffer:
    """Collects normal starting-session movement to personalize the baseline."""

    def __init__(self):
        self.started_at: Optional[float] = None
        self.shoulder_z = deque(maxlen=500)
        self.head_yaw = deque(maxlen=500)
        self.head_pitch = deque(maxlen=500)
        self.head_roll = deque(maxlen=500)
        self.complete = False
        self.baseline = CalibrationBaseline()

    def start(self, now: float) -> None:
        if self.started_at is None:
            self.started_at = now

    def add(
        self,
        now: float,
        shoulder_z: Optional[float],
        head_yaw: Optional[float],
        head_pitch: Optional[float],
        head_roll: Optional[float],
        required_seconds: float,
        min_samples: int,
    ) -> bool:
        self.start(now)

        if shoulder_z is not None and np.isfinite(shoulder_z):
            self.shoulder_z.append(float(shoulder_z))

        if head_yaw is not None and np.isfinite(head_yaw):
            self.head_yaw.append(float(head_yaw))

        if head_pitch is not None and np.isfinite(head_pitch):
            self.head_pitch.append(float(head_pitch))

        if head_roll is not None and np.isfinite(head_roll):
            self.head_roll.append(float(head_roll))

        elapsed = now - self.started_at

        # We require at least a usable number of samples rather than relying
        # on exactly one frame at startup.
        if (
            elapsed >= required_seconds
            and len(self.shoulder_z) >= min_samples
            and len(self.head_yaw) >= min_samples
        ):
            self.baseline = CalibrationBaseline(
                shoulder_z=float(np.median(self.shoulder_z)),
                head_yaw=float(np.median(self.head_yaw)),
                head_pitch=float(np.median(self.head_pitch))
                if self.head_pitch
                else None,
                head_roll=float(np.median(self.head_roll))
                if self.head_roll
                else None,
            )
            self.complete = True

        return self.complete


# ---------------------------------------------------------------------------
# Telemetry + event storage
# ---------------------------------------------------------------------------

class JsonlWriter:
    """Append-only JSON Lines writer."""

    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, payload: dict[str, Any]) -> None:
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")


class SessionDataStore:
    """
    Stores numerical telemetry and detection events.

    No image/video data is stored by this class.
    """

    def __init__(self, session_id: str, config: DetectorConfig):
        self.session_id = session_id

        self.telemetry_writer = JsonlWriter(
            DATA_DIR / "telemetry" / f"{session_id}.jsonl"
        )
        self.event_writer = JsonlWriter(
            DATA_DIR / "events" / f"{session_id}.jsonl"
        )

        self.session_meta_path = (
            DATA_DIR / "sessions" / f"{session_id}.json"
        )

        self.session_meta: dict[str, Any] = {
            "session_id": session_id,
            "detector_version": DETECTOR_VERSION,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "started_at": utc_iso(),
            "privacy": {
                "video_recorded": False,
                "images_recorded": False,
                "feature_telemetry_recorded": True,
            },
            "config": asdict(config),
        }

        self._write_meta()

    def _write_meta(self) -> None:
        self.session_meta_path.write_text(
            json.dumps(self.session_meta, indent=2),
            encoding="utf-8",
        )

    def update_meta(self, updates: dict[str, Any]) -> None:
        self.session_meta.update(updates)
        self._write_meta()

    def log_telemetry(self, payload: dict[str, Any]) -> None:
        self.telemetry_writer.write(payload)

    def log_event(self, payload: dict[str, Any]) -> None:
        self.event_writer.write(payload)

    def finish(self, summary: dict[str, Any]) -> None:
        self.session_meta.update(
            {
                "ended_at": utc_iso(),
                "summary": summary,
            }
        )
        self._write_meta()


# ---------------------------------------------------------------------------
# Feature snapshot
# ---------------------------------------------------------------------------

@dataclass
class FeatureSnapshot:
    timestamp: float

    face_present: bool
    pose_present: bool
    hand_count: int

    head_pitch: Optional[float] = None
    head_yaw: Optional[float] = None
    head_roll: Optional[float] = None

    head_yaw_from_baseline: Optional[float] = None
    head_pitch_from_baseline: Optional[float] = None
    head_roll_from_baseline: Optional[float] = None

    left_ear: Optional[float] = None
    right_ear: Optional[float] = None
    ear: Optional[float] = None
    mar: Optional[float] = None

    left_hand_cheek_distance: Optional[float] = None
    right_hand_cheek_distance: Optional[float] = None
    hand_cheek_distance: Optional[float] = None

    shoulder_z: Optional[float] = None
    shoulder_z_delta: Optional[float] = None

    head_yaw_rate: Optional[float] = None
    head_pitch_rate: Optional[float] = None
    head_roll_rate: Optional[float] = None
    shoulder_z_rate: Optional[float] = None
    hand_cheek_distance_rate: Optional[float] = None

    looking_away: bool = False
    phone_use: bool = False
    yawning: bool = False
    eyes_closed: bool = False
    leaning_back: bool = False
    away_from_desk: bool = False

    active_alerts: list[str] = field(default_factory=list)
    state: str = "focused"

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)

        # Explicitly keep a compact and stable feature naming scheme.
        result["schema_version"] = FEATURE_SCHEMA_VERSION
        result["timestamp_iso"] = utc_iso(self.timestamp)

        for key, value in list(result.items()):
            if isinstance(value, float) and not np.isfinite(value):
                result[key] = None

        return result


# ---------------------------------------------------------------------------
# Detector core
# ---------------------------------------------------------------------------

class StudentDistractionDetector:
    """
    Reusable rule-based detector.

    This class is deliberately independent from FastAPI and independent from
    cv2.imshow(). It can later become the core service used by the web backend.
    """

    ALERT_NAMES = (
        "Looking Away",
        "Phone Use",
        "Yawning",
        "Drowsy/Eyes Closed",
        "Leaning Back",
        "Away From Desk",
    )

    def __init__(
        self,
        config: Optional[DetectorConfig] = None,
        session_id: Optional[str] = None,
    ):
        self.config = config or DetectorConfig()
        self.session_id = session_id or uuid.uuid4().hex

        self.calibration = CalibrationBuffer()
        self.trackers = {
            name: PersistenceTracker(self.config.alert_delays_sec[name])
            for name in self.ALERT_NAMES
        }

        self.previous_features: Optional[FeatureSnapshot] = None
        self.last_telemetry_time: Optional[float] = None

        self.focused_seconds = 0.0
        self.distracted_seconds = 0.0
        self.away_seconds = 0.0
        self.distraction_count = 0

        self.session_started_at = time.time()
        self.frame_count = 0

        self.data_store = SessionDataStore(self.session_id, self.config)

    # -----------------------------------------------------------------------
    # Feature extraction
    # -----------------------------------------------------------------------

    def extract_features(
        self,
        face_result,
        hand_result,
        pose_result,
        width: int,
        height: int,
        now: float,
    ) -> FeatureSnapshot:
        face_present = bool(face_result.face_landmarks)
        pose_present = bool(pose_result.pose_landmarks)
        hand_count = len(hand_result.hand_landmarks) if hand_result.hand_landmarks else 0

        pitch = yaw = roll = None
        left_ear = right_ear = ear = mar = None
        left_cheek_dist = right_cheek_dist = hand_cheek_dist = None
        shoulder_z = None

        if face_present:
            landmarks = face_result.face_landmarks[0]

            pitch, yaw, roll = compute_head_pose(landmarks, width, height)

            left_ear = eye_aspect_ratio(
                landmarks, LEFT_EYE, width, height
            )
            right_ear = eye_aspect_ratio(
                landmarks, RIGHT_EYE, width, height
            )
            ear = (left_ear + right_ear) / 2.0

            mar = mouth_aspect_ratio(landmarks, width, height)

            if hand_count > 0:
                left_cheek = landmark_norm_xy(
                    landmarks, LEFT_CHEEK_IDX
                )
                right_cheek = landmark_norm_xy(
                    landmarks, RIGHT_CHEEK_IDX
                )

                distances = []

                for hand_lm in hand_result.hand_landmarks:
                    hand_center = np.mean(
                        [[lm.x, lm.y] for lm in hand_lm],
                        axis=0,
                    )

                    dist_left = float(
                        np.linalg.norm(hand_center - left_cheek)
                    )
                    dist_right = float(
                        np.linalg.norm(hand_center - right_cheek)
                    )
                    distance = min(dist_left, dist_right)
                    distances.append(
                        (dist_left, dist_right, distance)
                    )

                if distances:
                    left_cheek_dist = min(x[0] for x in distances)
                    right_cheek_dist = min(x[1] for x in distances)
                    hand_cheek_dist = min(x[2] for x in distances)

        if pose_present:
            plm = pose_result.pose_landmarks[0]
            l_shoulder_z = plm[
                PoseLandmark.LEFT_SHOULDER.value
            ].z
            r_shoulder_z = plm[
                PoseLandmark.RIGHT_SHOULDER.value
            ].z
            shoulder_z = float((l_shoulder_z + r_shoulder_z) / 2.0)

        # Build calibrated deviations.
        baseline = self.calibration.baseline

        yaw_delta = (
            yaw - baseline.head_yaw
            if yaw is not None and baseline.head_yaw is not None
            else None
        )
        pitch_delta = (
            pitch - baseline.head_pitch
            if pitch is not None and baseline.head_pitch is not None
            else None
        )
        roll_delta = (
            roll - baseline.head_roll
            if roll is not None and baseline.head_roll is not None
            else None
        )
        shoulder_delta = (
            shoulder_z - baseline.shoulder_z
            if shoulder_z is not None and baseline.shoulder_z is not None
            else None
        )

        snapshot = FeatureSnapshot(
            timestamp=now,
            face_present=face_present,
            pose_present=pose_present,
            hand_count=hand_count,
            head_pitch=finite_or_none(pitch),
            head_yaw=finite_or_none(yaw),
            head_roll=finite_or_none(roll),
            head_yaw_from_baseline=finite_or_none(yaw_delta),
            head_pitch_from_baseline=finite_or_none(pitch_delta),
            head_roll_from_baseline=finite_or_none(roll_delta),
            left_ear=finite_or_none(left_ear),
            right_ear=finite_or_none(right_ear),
            ear=finite_or_none(ear),
            mar=finite_or_none(mar),
            left_hand_cheek_distance=finite_or_none(left_cheek_dist),
            right_hand_cheek_distance=finite_or_none(right_cheek_dist),
            hand_cheek_distance=finite_or_none(hand_cheek_dist),
            shoulder_z=finite_or_none(shoulder_z),
            shoulder_z_delta=finite_or_none(shoulder_delta),
        )

        self._add_motion_rates(snapshot)

        return snapshot

    def _add_motion_rates(self, snapshot: FeatureSnapshot) -> None:
        previous = self.previous_features
        if previous is None:
            return

        dt = snapshot.timestamp - previous.timestamp
        if dt <= 1e-6:
            return

        if (
            snapshot.head_yaw is not None
            and previous.head_yaw is not None
        ):
            snapshot.head_yaw_rate = abs(
                snapshot.head_yaw - previous.head_yaw
            ) / dt

        if (
            snapshot.head_pitch is not None
            and previous.head_pitch is not None
        ):
            snapshot.head_pitch_rate = abs(
                snapshot.head_pitch - previous.head_pitch
            ) / dt

        if (
            snapshot.head_roll is not None
            and previous.head_roll is not None
        ):
            snapshot.head_roll_rate = abs(
                snapshot.head_roll - previous.head_roll
            ) / dt

        if (
            snapshot.shoulder_z is not None
            and previous.shoulder_z is not None
        ):
            snapshot.shoulder_z_rate = abs(
                snapshot.shoulder_z - previous.shoulder_z
            ) / dt

        if (
            snapshot.hand_cheek_distance is not None
            and previous.hand_cheek_distance is not None
        ):
            snapshot.hand_cheek_distance_rate = abs(
                snapshot.hand_cheek_distance
                - previous.hand_cheek_distance
            ) / dt

    # -----------------------------------------------------------------------
    # Rule evaluation
    # -----------------------------------------------------------------------

    def _conditions_from_features(
        self,
        features: FeatureSnapshot,
    ) -> dict[str, bool]:
        yaw_delta_abs = (
            abs(features.head_yaw_from_baseline)
            if features.head_yaw_from_baseline is not None
            else None
        )

        looking_away = (
            features.face_present
            and yaw_delta_abs is not None
            and yaw_delta_abs > self.config.yaw_threshold_deg
        )

        phone_use = (
            features.face_present
            and features.hand_cheek_distance is not None
            and features.hand_cheek_distance
            < self.config.hand_near_cheek_dist
        )

        yawning = (
            features.face_present
            and features.mar is not None
            and features.mar > self.config.mar_threshold
        )

        eyes_closed = (
            features.face_present
            and features.ear is not None
            and features.ear < self.config.ear_threshold
        )

        leaning_back = (
            features.pose_present
            and features.shoulder_z_delta is not None
            and features.shoulder_z_delta
            > self.config.lean_back_z_delta
        )

        away_from_desk = (
            not features.face_present
            and not features.pose_present
        )

        return {
            "Looking Away": looking_away,
            "Phone Use": phone_use,
            "Yawning": yawning,
            "Drowsy/Eyes Closed": eyes_closed,
            "Leaning Back": leaning_back,
            "Away From Desk": away_from_desk,
        }

    def _state_from_alerts(
        self,
        active_alerts: list[str],
    ) -> str:
        if any(name != "Away From Desk" for name in active_alerts):
            return "distracted"

        if "Away From Desk" in active_alerts:
            return "away"

        return "focused"

    def _log_alert_events(
        self,
        tracker_results: dict[str, dict[str, Any]],
        features: FeatureSnapshot,
        now: float,
    ) -> None:
        for name, result in tracker_results.items():
            if result["just_started"]:
                self.distraction_count += 1

                event = {
                    "event_id": uuid.uuid4().hex,
                    "session_id": self.session_id,
                    "event_type": name,
                    "event_action": "started",
                    "timestamp": now,
                    "timestamp_iso": utc_iso(now),
                    "trigger_delay_sec": self.config.alert_delays_sec[name],
                    "detector_version": DETECTOR_VERSION,
                    "feature_schema_version": FEATURE_SCHEMA_VERSION,
                    "thresholds": {
                        "yaw_threshold_deg": self.config.yaw_threshold_deg,
                        "ear_threshold": self.config.ear_threshold,
                        "mar_threshold": self.config.mar_threshold,
                        "hand_near_cheek_dist":
                            self.config.hand_near_cheek_dist,
                        "lean_back_z_delta":
                            self.config.lean_back_z_delta,
                    },
                    "feature_snapshot": {
                        "head_yaw_from_baseline":
                            features.head_yaw_from_baseline,
                        "ear": features.ear,
                        "mar": features.mar,
                        "hand_cheek_distance":
                            features.hand_cheek_distance,
                        "shoulder_z_delta":
                            features.shoulder_z_delta,
                    },
                }
                self.data_store.log_event(event)

            if result["just_ended"]:
                event = {
                    "event_id": uuid.uuid4().hex,
                    "session_id": self.session_id,
                    "event_type": name,
                    "event_action": "ended",
                    "timestamp": now,
                    "timestamp_iso": utc_iso(now),
                    "duration_sec": result["duration_sec"],
                    "trigger_delay_sec": self.config.alert_delays_sec[name],
                    "detector_version": DETECTOR_VERSION,
                    "feature_schema_version": FEATURE_SCHEMA_VERSION,
                }
                self.data_store.log_event(event)

    # -----------------------------------------------------------------------
    # Public processing API
    # -----------------------------------------------------------------------

    def process_results(
        self,
        face_result,
        hand_result,
        pose_result,
        width: int,
        height: int,
        timestamp: Optional[float] = None,
    ) -> dict[str, Any]:
        """
        Process one already-detected frame.

        This method is the future integration point for FastAPI/WebSocket.
        A web backend should be able to provide the same MediaPipe results
        without depending on this file's OpenCV display loop.
        """
        now = timestamp if timestamp is not None else time.time()
        self.frame_count += 1

        features = self.extract_features(
            face_result,
            hand_result,
            pose_result,
            width,
            height,
            now,
        )

        # Calibration phase: no distraction alerts while baseline is being built.
        if not self.calibration.complete:
            self.calibration.add(
                now=now,
                shoulder_z=features.shoulder_z,
                head_yaw=features.head_yaw,
                head_pitch=features.head_pitch,
                head_roll=features.head_roll,
                required_seconds=self.config.calibration_seconds,
                min_samples=self.config.minimum_calibration_samples,
            )

            features.active_alerts = []
            features.state = "calibrating"

            self.previous_features = features
            self._maybe_log_telemetry(features)
            return self._build_state_payload(features)

        conditions = self._conditions_from_features(features)

        tracker_results: dict[str, dict[str, Any]] = {}
        active_alerts: list[str] = []

        for name, condition in conditions.items():
            result = self.trackers[name].update(condition, now)
            tracker_results[name] = result

            if result["active"]:
                active_alerts.append(name)

        features.looking_away = conditions["Looking Away"]
        features.phone_use = conditions["Phone Use"]
        features.yawning = conditions["Yawning"]
        features.eyes_closed = conditions["Drowsy/Eyes Closed"]
        features.leaning_back = conditions["Leaning Back"]
        features.away_from_desk = conditions["Away From Desk"]

        features.active_alerts = active_alerts
        features.state = self._state_from_alerts(active_alerts)

        self._log_alert_events(tracker_results, features, now)
        self._update_session_durations(features)

        self.previous_features = features
        self._maybe_log_telemetry(features)

        return self._build_state_payload(features)

    def _update_session_durations(
        self,
        features: FeatureSnapshot,
    ) -> None:
        previous = self.previous_features
        if previous is None:
            return

        dt = features.timestamp - previous.timestamp
        if dt <= 0:
            return

        if features.state == "focused":
            self.focused_seconds += dt
        elif features.state == "distracted":
            self.distracted_seconds += dt
        elif features.state == "away":
            self.away_seconds += dt

    def _maybe_log_telemetry(
        self,
        features: FeatureSnapshot,
    ) -> None:
        now = features.timestamp

        if (
            self.last_telemetry_time is not None
            and now - self.last_telemetry_time
            < self.config.telemetry_interval_sec
        ):
            return

        self.last_telemetry_time = now

        payload = features.to_dict()
        payload.update(
            {
                "session_id": self.session_id,
                "detector_version": DETECTOR_VERSION,
                "frame_index": self.frame_count,
                "focused_seconds": self.focused_seconds,
                "distracted_seconds": self.distracted_seconds,
                "away_seconds": self.away_seconds,
                "distraction_count": self.distraction_count,
                "calibration_complete": self.calibration.complete,
                "baseline": asdict(self.calibration.baseline),
                "thresholds": {
                    "yaw_threshold_deg": self.config.yaw_threshold_deg,
                    "ear_threshold": self.config.ear_threshold,
                    "mar_threshold": self.config.mar_threshold,
                    "hand_near_cheek_dist":
                        self.config.hand_near_cheek_dist,
                    "lean_back_z_delta":
                        self.config.lean_back_z_delta,
                },
                "alert_delays_sec": self.config.alert_delays_sec,
            }
        )

        self.data_store.log_telemetry(payload)

    def _build_state_payload(
        self,
        features: FeatureSnapshot,
    ) -> dict[str, Any]:
        return {
            "type": "session_update",
            "session_id": self.session_id,
            "timestamp": features.timestamp,
            "timestamp_iso": utc_iso(features.timestamp),
            "state": features.state,
            "focused_seconds": round(self.focused_seconds, 2),
            "distracted_seconds": round(self.distracted_seconds, 2),
            "away_seconds": round(self.away_seconds, 2),
            "distraction_count": self.distraction_count,
            "active_alerts": features.active_alerts,
            "calibration_complete": self.calibration.complete,
            "features": features.to_dict(),
        }

    def finish_session(self) -> dict[str, Any]:
        """
        Finish the logical session and store its summary.

        Note: a normal production backend will eventually persist this
        summary to PostgreSQL instead of JSON.
        """
        duration = max(0.0, time.time() - self.session_started_at)

        total_tracked = (
            self.focused_seconds
            + self.distracted_seconds
            + self.away_seconds
        )

        if total_tracked > 0:
            focus_score = (
                self.focused_seconds / total_tracked
            ) * 100.0
        else:
            focus_score = 0.0

        summary = {
            "session_id": self.session_id,
            "duration_seconds": round(duration, 2),
            "focused_seconds": round(self.focused_seconds, 2),
            "distracted_seconds": round(self.distracted_seconds, 2),
            "away_seconds": round(self.away_seconds, 2),
            "focus_score": round(focus_score, 2),
            "distraction_count": self.distraction_count,
            "detector_version": DETECTOR_VERSION,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "calibration": asdict(self.calibration.baseline),
        }

        self.data_store.finish(summary)
        return summary


# ---------------------------------------------------------------------------
# Optional desktop alarm
# ---------------------------------------------------------------------------

class DesktopAlarm:
    """
    Local testing alarm.

    This is deliberately outside StudentDistractionDetector.
    The future browser app will use browser audio/visual alerts instead.
    """

    def __init__(self, enabled: bool = True):
        self.enabled = enabled and winsound is not None
        self.flag = threading.Event()

        if self.enabled:
            threading.Thread(
                target=self._worker,
                daemon=True,
            ).start()

    def _worker(self) -> None:
        while True:
            if not self.flag.is_set():
                time.sleep(0.1)
                continue

            try:
                winsound.Beep(1000, 200)  # type: ignore[union-attr]
            except Exception:
                time.sleep(0.2)

            time.sleep(0.1)

    def set_active(self, active: bool) -> None:
        if self.enabled:
            if active:
                self.flag.set()
            else:
                self.flag.clear()

    def stop(self) -> None:
        self.flag.clear()


# ---------------------------------------------------------------------------
# Optional OpenCV display
# ---------------------------------------------------------------------------

def draw_center_banner(
    display: np.ndarray,
    active_alerts: list[str],
) -> None:
    if not active_alerts:
        return

    h, w, _ = display.shape

    overlay = display.copy()
    box_w = int(w * 0.85)
    box_h = int(h * 0.32)

    x0 = (w - box_w) // 2
    y0 = (h - box_h) // 2

    cv2.rectangle(
        overlay,
        (x0, y0),
        (x0 + box_w, y0 + box_h),
        (0, 0, 255),
        -1,
    )

    cv2.addWeighted(
        overlay,
        0.75,
        display,
        0.25,
        0,
        dst=display,
    )

    title = "DISTRACTED!"
    (tw, th), _ = cv2.getTextSize(
        title,
        cv2.FONT_HERSHEY_SIMPLEX,
        1.6,
        3,
    )

    cv2.putText(
        display,
        title,
        (w // 2 - tw // 2, y0 + th + 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.6,
        (255, 255, 255),
        3,
    )

    detail = ", ".join(active_alerts)
    (dw, dh), _ = cv2.getTextSize(
        detail,
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        2,
    )

    cv2.putText(
        display,
        detail,
        (w // 2 - dw // 2, y0 + box_h - 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2,
    )


# ---------------------------------------------------------------------------
# Local reference runner
# ---------------------------------------------------------------------------

def run_local_demo() -> None:
    """
    Run the detector with the laptop camera for local testing.

    Keys:
        q -> quit
        c -> start a fresh calibration for the current session
    """
    ensure_models()

    config = DetectorConfig()

    detector = StudentDistractionDetector(config=config)
    alarm = DesktopAlarm(enabled=config.enable_desktop_alarm)

    face_options = FaceLandmarkerOptions(
        base_options=BaseOptions(
            model_asset_path=str(FACE_MODEL)
        ),
        running_mode=RunningMode.VIDEO,
        num_faces=1,
    )

    hand_options = HandLandmarkerOptions(
        base_options=BaseOptions(
            model_asset_path=str(HAND_MODEL)
        ),
        running_mode=RunningMode.VIDEO,
        num_hands=2,
    )

    pose_options = PoseLandmarkerOptions(
        base_options=BaseOptions(
            model_asset_path=str(POSE_MODEL)
        ),
        running_mode=RunningMode.VIDEO,
    )

    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        raise RuntimeError(
            "Unable to open camera. Check camera permissions/device availability."
        )

    last_timestamp_ms = 0

    try:
        with (
            FaceLandmarker.create_from_options(face_options) as face_landmarker,
            HandLandmarker.create_from_options(hand_options) as hand_landmarker,
            PoseLandmarker.create_from_options(pose_options) as pose_landmarker,
        ):
            while cap.isOpened():
                success, frame_bgr = cap.read()

                if not success:
                    print("Ignoring empty camera frame.")
                    continue

                frame_bgr = cv2.flip(frame_bgr, 1)
                h, w, _ = frame_bgr.shape

                rgb = cv2.cvtColor(
                    frame_bgr,
                    cv2.COLOR_BGR2RGB,
                )

                mp_image = mp.Image(
                    image_format=mp.ImageFormat.SRGB,
                    data=rgb,
                )

                timestamp_ms = int(time.time() * 1000)
                if timestamp_ms <= last_timestamp_ms:
                    timestamp_ms = last_timestamp_ms + 1
                last_timestamp_ms = timestamp_ms

                face_result = face_landmarker.detect_for_video(
                    mp_image,
                    timestamp_ms,
                )
                hand_result = hand_landmarker.detect_for_video(
                    mp_image,
                    timestamp_ms,
                )
                pose_result = pose_landmarker.detect_for_video(
                    mp_image,
                    timestamp_ms,
                )

                display = frame_bgr

                if config.draw_landmarks:
                    if face_result.face_landmarks:
                        drawing_utils.draw_landmarks(
                            display,
                            face_result.face_landmarks[0],
                            FaceConnections.FACE_LANDMARKS_TESSELATION,
                        )

                    if hand_result.hand_landmarks:
                        for hand_lm in hand_result.hand_landmarks:
                            drawing_utils.draw_landmarks(
                                display,
                                hand_lm,
                                HandConnections.HAND_CONNECTIONS,
                            )

                    if pose_result.pose_landmarks:
                        drawing_utils.draw_landmarks(
                            display,
                            pose_result.pose_landmarks[0],
                            PoseConnections.POSE_LANDMARKS,
                        )

                state = detector.process_results(
                    face_result=face_result,
                    hand_result=hand_result,
                    pose_result=pose_result,
                    width=w,
                    height=h,
                    timestamp=time.time(),
                )

                active_alerts = state["active_alerts"]
                alarm.set_active(bool(active_alerts))

                if active_alerts:
                    draw_center_banner(
                        display,
                        active_alerts,
                    )

                # Small status overlay for local debugging.
                status = (
                    f"state={state['state']} "
                    f"focus={state['focused_seconds']:.0f}s "
                    f"dist={state['distracted_seconds']:.0f}s "
                    f"away={state['away_seconds']:.0f}s"
                )

                cv2.putText(
                    display,
                    status,
                    (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (0, 255, 0),
                    1,
                )

                if not state["calibration_complete"]:
                    calibration_text = "CALIBRATING - stay in normal study posture"
                    cv2.putText(
                        display,
                        calibration_text,
                        (10, 50),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        (0, 255, 255),
                        1,
                    )

                cv2.imshow(
                    "Student Distraction Detector v4",
                    display,
                )

                key = cv2.waitKey(10) & 0xFF

                if key == ord("q"):
                    break

                if key == ord("c"):
                    # Rebuild calibration for the same session.
                    detector.calibration = CalibrationBuffer()
                    print("Calibration reset.")

    finally:
        alarm.stop()
        cap.release()
        cv2.destroyAllWindows()

        summary = detector.finish_session()

        print("\nSession finished.")
        print(json.dumps(summary, indent=2))
        print(f"\nSession telemetry:")
        print(
            DATA_DIR / "telemetry" / f"{detector.session_id}.jsonl"
        )
        print("Session events:")
        print(
            DATA_DIR / "events" / f"{detector.session_id}.jsonl"
        )
        print("Session metadata:")
        print(
            DATA_DIR / "sessions" / f"{detector.session_id}.json"
        )


if __name__ == "__main__":
    run_local_demo()
