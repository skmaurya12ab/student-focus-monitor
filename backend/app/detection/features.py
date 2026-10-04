"""Feature extraction module for transforming raw landmarks into numerical telemetry features."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

import cv2
import numpy as np

from app.detection.calibration import CalibrationBaseline
from app.detection.config import FEATURE_SCHEMA_VERSION

# Landmark indices consistent with v4 reference
LEFT_EYE: list[int] = [362, 385, 387, 263, 373, 380]
RIGHT_EYE: list[int] = [33, 160, 158, 133, 153, 144]
MOUTH: dict[str, int] = {"left": 61, "right": 291, "top": 13, "bottom": 14}

LEFT_CHEEK_IDX: int = 234
RIGHT_CHEEK_IDX: int = 454

# Pose landmark indices for shoulders (MediaPipe PoseLandmark enum values)
LEFT_SHOULDER_IDX: int = 11
RIGHT_SHOULDER_IDX: int = 12


def utc_iso(timestamp: Optional[float] = None) -> str:
    """Return an ISO-8601 formatted UTC timestamp string."""
    if timestamp is None:
        dt = datetime.now(timezone.utc)
    else:
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    return dt.isoformat()


def finite_or_none(value: Any) -> Optional[float]:
    """Convert numeric value to finite float or None for valid JSON serialization."""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if np.isfinite(v) else None


def landmark_xy(landmarks: Any, idx: int, w: int, h: int) -> np.ndarray:
    """Extract pixel (x, y) coordinates for landmark at idx."""
    lm = landmarks[idx]
    x = getattr(lm, "x", None) if hasattr(lm, "x") else lm[0]
    y = getattr(lm, "y", None) if hasattr(lm, "y") else lm[1]
    return np.array([float(x) * w, float(y) * h], dtype=np.float64)


def landmark_norm_xy(landmarks: Any, idx: int) -> np.ndarray:
    """Extract normalized [0..1] (x, y) coordinates for landmark at idx."""
    lm = landmarks[idx]
    x = getattr(lm, "x", None) if hasattr(lm, "x") else lm[0]
    y = getattr(lm, "y", None) if hasattr(lm, "y") else lm[1]
    return np.array([float(x), float(y)], dtype=np.float64)


def eye_aspect_ratio(landmarks: Any, eye_idx: Sequence[int], w: int, h: int) -> float:
    """Compute Eye Aspect Ratio (EAR) based on 6 landmark points."""
    p1, p2, p3, p4, p5, p6 = [landmark_xy(landmarks, i, w, h) for i in eye_idx]
    vertical = np.linalg.norm(p2 - p6) + np.linalg.norm(p3 - p5)
    horizontal = np.linalg.norm(p1 - p4)
    if horizontal <= 1e-9:
        return 0.0
    return float(vertical / (2.0 * horizontal))


def mouth_aspect_ratio(landmarks: Any, w: int, h: int) -> float:
    """Compute Mouth Aspect Ratio (MAR) based on 4 cardinal points."""
    left = landmark_xy(landmarks, MOUTH["left"], w, h)
    right = landmark_xy(landmarks, MOUTH["right"], w, h)
    top = landmark_xy(landmarks, MOUTH["top"], w, h)
    bottom = landmark_xy(landmarks, MOUTH["bottom"], w, h)
    horizontal = np.linalg.norm(left - right)
    if horizontal <= 1e-9:
        return 0.0
    return float(np.linalg.norm(top - bottom) / horizontal)


# Canonical 3D facial landmark model points for 6-point solvePnP head pose estimation
# Order: 1 (nose tip), 199 (chin), 33 (left eye outer), 263 (right eye outer), 61 (left mouth), 291 (right mouth)
CANONICAL_FACE_3D = np.array([
    [0.0, 0.0, 0.0],          # 1: Nose tip
    [0.0, -330.0, -65.0],     # 199: Chin
    [-225.0, 170.0, -135.0],  # 33: Left eye corner
    [225.0, 170.0, -135.0],   # 263: Right eye corner
    [-150.0, -150.0, -125.0], # 61: Left mouth corner
    [150.0, -150.0, -125.0],  # 291: Right mouth corner
], dtype=np.float64)
HEAD_POSE_LANDMARK_ORDER = (1, 199, 33, 263, 61, 291)


def compute_head_pose(landmarks: Any, w: int, h: int) -> tuple[float, float, float]:
    """
    6-point solvePnP head-pose estimation using canonical 3D facial geometry.
    Returns (pitch, yaw, roll) in degrees.
    """
    face_2d = []

    for idx in HEAD_POSE_LANDMARK_ORDER:
        lm = landmarks[idx]
        x = getattr(lm, "x", None) if hasattr(lm, "x") else lm[0]
        y = getattr(lm, "y", None) if hasattr(lm, "y") else lm[1]

        px, py = float(x) * w, float(y) * h
        face_2d.append([px, py])

    face_2d = np.array(face_2d, dtype=np.float64)

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
        CANONICAL_FACE_3D,
        face_2d,
        cam_matrix,
        dist_matrix,
        flags=cv2.SOLVEPNP_ITERATIVE,
    )

    if not success:
        raise RuntimeError("Head pose solvePnP failed.")

    rmat, _ = cv2.Rodrigues(rot_vec)
    angles, _, _, _, _, _ = cv2.RQDecomp3x3(rmat)

    pitch = float(angles[0])
    yaw = float(angles[1])
    roll = float(angles[2])

    return pitch, yaw, roll


def compute_hand_cheek_distances(
    face_landmarks: Any,
    hand_landmarks_list: Sequence[Any],
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Compute normalized minimum distance between detected hands and cheeks.
    Returns (left_cheek_dist, right_cheek_dist, min_hand_cheek_dist).
    """
    if not face_landmarks or not hand_landmarks_list:
        return None, None, None

    left_cheek = landmark_norm_xy(face_landmarks, LEFT_CHEEK_IDX)
    right_cheek = landmark_norm_xy(face_landmarks, RIGHT_CHEEK_IDX)

    distances = []
    for hand_lm in hand_landmarks_list:
        pts = []
        for lm in hand_lm:
            x = getattr(lm, "x", None) if hasattr(lm, "x") else lm[0]
            y = getattr(lm, "y", None) if hasattr(lm, "y") else lm[1]
            pts.append([float(x), float(y)])

        hand_pts = np.array(pts, dtype=np.float64)
        dist_left = float(np.min(np.linalg.norm(hand_pts - left_cheek, axis=1)))
        dist_right = float(np.min(np.linalg.norm(hand_pts - right_cheek, axis=1)))
        distance = min(dist_left, dist_right)
        distances.append((dist_left, dist_right, distance))

    if not distances:
        return None, None, None

    min_l = min(x[0] for x in distances)
    min_r = min(x[1] for x in distances)
    min_dist = min(x[2] for x in distances)
    return min_l, min_r, min_dist


def compute_shoulder_z(pose_landmarks: Any) -> Optional[float]:
    """Compute average shoulder depth z from pose landmarks."""
    if not pose_landmarks:
        return None
    try:
        l_sh = pose_landmarks[LEFT_SHOULDER_IDX]
        r_sh = pose_landmarks[RIGHT_SHOULDER_IDX]
        l_z = getattr(l_sh, "z", None) if hasattr(l_sh, "z") else l_sh[2]
        r_z = getattr(r_sh, "z", None) if hasattr(r_sh, "z") else r_sh[2]
        return float((float(l_z) + float(r_z)) / 2.0)
    except (IndexError, TypeError, KeyError):
        return None


@dataclass
class FeatureSnapshot:
    """Typed immutable snapshot of extracted numerical telemetry and condition states."""

    timestamp: float

    face_present: bool
    pose_present: bool
    hand_count: int

    # Raw orientation
    head_pitch: Optional[float] = None
    head_yaw: Optional[float] = None
    head_roll: Optional[float] = None

    # Baseline-relative orientation
    head_yaw_from_baseline: Optional[float] = None
    head_pitch_from_baseline: Optional[float] = None
    head_roll_from_baseline: Optional[float] = None

    # Facial features
    left_ear: Optional[float] = None
    right_ear: Optional[float] = None
    ear: Optional[float] = None
    mar: Optional[float] = None

    # Hand interactions
    left_hand_cheek_distance: Optional[float] = None
    right_hand_cheek_distance: Optional[float] = None
    hand_cheek_distance: Optional[float] = None

    # Posture depth
    shoulder_z: Optional[float] = None
    shoulder_z_delta: Optional[float] = None

    # Dynamic rates of change
    head_yaw_rate: Optional[float] = None
    head_pitch_rate: Optional[float] = None
    head_roll_rate: Optional[float] = None
    shoulder_z_rate: Optional[float] = None
    hand_cheek_distance_rate: Optional[float] = None

    # Instantaneous condition flags
    looking_away: bool = False
    phone_use: bool = False
    yawning: bool = False
    eyes_closed: bool = False
    leaning_back: bool = False
    away_from_desk: bool = False

    # High-level states
    active_alerts: list[str] = field(default_factory=list)
    state: str = "focused"

    def to_dict(self) -> dict[str, Any]:
        """Convert snapshot into a serializable dictionary adhering to FEATURE_SCHEMA_VERSION."""
        result = asdict(self)
        result["schema_version"] = FEATURE_SCHEMA_VERSION
        result["timestamp_iso"] = utc_iso(self.timestamp)

        for key, value in list(result.items()):
            if isinstance(value, float) and not np.isfinite(value):
                result[key] = None

        return result


def compute_motion_rates(
    current: FeatureSnapshot,
    previous: Optional[FeatureSnapshot],
) -> None:
    """Mutate current snapshot in-place to calculate velocity rates of change."""
    if previous is None:
        return

    dt = current.timestamp - previous.timestamp
    if dt <= 1e-6:
        return

    if current.head_yaw is not None and previous.head_yaw is not None:
        current.head_yaw_rate = abs(current.head_yaw - previous.head_yaw) / dt

    if current.head_pitch is not None and previous.head_pitch is not None:
        current.head_pitch_rate = abs(current.head_pitch - previous.head_pitch) / dt

    if current.head_roll is not None and previous.head_roll is not None:
        current.head_roll_rate = abs(current.head_roll - previous.head_roll) / dt

    if current.shoulder_z is not None and previous.shoulder_z is not None:
        current.shoulder_z_rate = abs(current.shoulder_z - previous.shoulder_z) / dt

    if (
        current.hand_cheek_distance is not None
        and previous.hand_cheek_distance is not None
    ):
        current.hand_cheek_distance_rate = (
            abs(current.hand_cheek_distance - previous.hand_cheek_distance) / dt
        )


def extract_features_from_landmarks(
    face_landmarks: Optional[Sequence[Any]],
    hand_landmarks_list: Optional[Sequence[Any]],
    pose_landmarks: Optional[Sequence[Any]],
    width: int,
    height: int,
    now: float,
    baseline: Optional[CalibrationBaseline] = None,
    previous_snapshot: Optional[FeatureSnapshot] = None,
) -> FeatureSnapshot:
    """
    Authoritative pure function to extract all numerical features from raw landmark sets.
    """
    face_present = bool(face_landmarks)
    pose_present = False
    if pose_landmarks:
        try:
            l_sh = pose_landmarks[LEFT_SHOULDER_IDX]
            r_sh = pose_landmarks[RIGHT_SHOULDER_IDX]
            l_vis = getattr(l_sh, "visibility", None)
            r_vis = getattr(r_sh, "visibility", None)
            if l_vis is not None and r_vis is not None:
                pose_present = float(l_vis) >= 0.4 and float(r_vis) >= 0.4
            else:
                pose_present = True
        except (IndexError, TypeError, KeyError):
            pose_present = bool(pose_landmarks)
    hand_count = len(hand_landmarks_list) if hand_landmarks_list else 0

    pitch = yaw = roll = None
    left_ear = right_ear = ear = mar = None
    left_cheek_dist = right_cheek_dist = hand_cheek_dist = None
    shoulder_z = None

    if face_present and face_landmarks is not None:
        landmarks = face_landmarks
        pitch, yaw, roll = compute_head_pose(landmarks, width, height)
        left_ear = eye_aspect_ratio(landmarks, LEFT_EYE, width, height)
        right_ear = eye_aspect_ratio(landmarks, RIGHT_EYE, width, height)
        ear = (left_ear + right_ear) / 2.0
        mar = mouth_aspect_ratio(landmarks, width, height)

        if hand_count > 0 and hand_landmarks_list is not None:
            left_cheek_dist, right_cheek_dist, hand_cheek_dist = compute_hand_cheek_distances(
                landmarks, hand_landmarks_list
            )

    if pose_present and pose_landmarks is not None:
        shoulder_z = compute_shoulder_z(pose_landmarks)

    yaw_delta = pitch_delta = roll_delta = shoulder_delta = None
    if baseline is not None:
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

    compute_motion_rates(snapshot, previous_snapshot)
    return snapshot
