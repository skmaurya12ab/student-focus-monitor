"""Tests for feature extraction using synthetic landmarks."""

from dataclasses import dataclass
import pytest
from app.detection.calibration import CalibrationBaseline
from app.detection.features import (
    FeatureSnapshot,
    compute_hand_cheek_distances,
    compute_head_pose,
    compute_motion_rates,
    compute_shoulder_z,
    extract_features_from_landmarks,
    eye_aspect_ratio,
    mouth_aspect_ratio,
)


@dataclass
class MockLandmark:
    x: float
    y: float
    z: float = 0.0


def test_eye_aspect_ratio_open_vs_closed():
    # Synthetic eye: indices 0..5 corresponding to p1, p2, p3, p4, p5, p6
    # p1=(0, 0.5), p4=(1.0, 0.5) -> horizontal = 1.0
    # Open eye: p2=(0.3, 0.2), p6=(0.3, 0.8) -> v1 = 0.6; p3=(0.7, 0.2), p5=(0.7, 0.8) -> v2 = 0.6
    # EAR = (0.6 + 0.6) / (2 * 1.0) = 0.6
    open_eye = {
        10: MockLandmark(0.0, 0.5),  # p1
        11: MockLandmark(0.3, 0.2),  # p2
        12: MockLandmark(0.7, 0.2),  # p3
        13: MockLandmark(1.0, 0.5),  # p4
        14: MockLandmark(0.7, 0.8),  # p5
        15: MockLandmark(0.3, 0.8),  # p6
    }
    ear_open = eye_aspect_ratio(open_eye, [10, 11, 12, 13, 14, 15], 100, 100)
    assert ear_open == pytest.approx(0.6, abs=0.01)

    # Closed eye: vertical distances collapse to 0.05
    closed_eye = {
        10: MockLandmark(0.0, 0.5),
        11: MockLandmark(0.3, 0.48),
        12: MockLandmark(0.7, 0.48),
        13: MockLandmark(1.0, 0.5),
        14: MockLandmark(0.7, 0.52),
        15: MockLandmark(0.3, 0.52),
    }
    ear_closed = eye_aspect_ratio(closed_eye, [10, 11, 12, 13, 14, 15], 100, 100)
    assert ear_closed < 0.1
    assert ear_closed < ear_open


def test_mouth_aspect_ratio_closed_vs_yawn():
    # MOUTH uses: left: 61, right: 291, top: 13, bottom: 14
    # Horizontal width = 100 pixels (left=0.2, right=0.8 in 100px)
    closed_mouth = {
        61: MockLandmark(0.2, 0.5),
        291: MockLandmark(0.8, 0.5),
        13: MockLandmark(0.5, 0.49),
        14: MockLandmark(0.5, 0.51),
    }
    mar_closed = mouth_aspect_ratio(closed_mouth, 100, 100)
    assert mar_closed < 0.1

    yawn_mouth = {
        61: MockLandmark(0.2, 0.5),
        291: MockLandmark(0.8, 0.5),
        13: MockLandmark(0.5, 0.2),
        14: MockLandmark(0.5, 0.8),
    }
    mar_yawn = mouth_aspect_ratio(yawn_mouth, 100, 100)
    assert mar_yawn == pytest.approx(1.0, abs=0.01)
    assert mar_yawn > 0.55  # Default threshold


def test_compute_head_pose_synthetic():
    # Construct synthetic facial landmarks covering indices (33, 263, 1, 61, 291, 199)
    landmarks = {
        33: MockLandmark(0.35, 0.4, -0.05),
        263: MockLandmark(0.65, 0.4, -0.05),
        1: MockLandmark(0.50, 0.5, 0.0),
        61: MockLandmark(0.40, 0.7, -0.02),
        291: MockLandmark(0.60, 0.7, -0.02),
        199: MockLandmark(0.50, 0.85, -0.03),
    }
    pitch, yaw, roll = compute_head_pose(landmarks, 640, 480)
    assert isinstance(pitch, float)
    assert isinstance(yaw, float)
    assert isinstance(roll, float)


def test_compute_hand_cheek_distance():
    # Left cheek: 234, Right cheek: 454
    face = {
        234: MockLandmark(0.25, 0.5),  # Left cheek
        454: MockLandmark(0.75, 0.5),  # Right cheek
    }
    # Hand placed right on the left cheek (0.25, 0.5)
    hand_near = [[MockLandmark(0.25, 0.5)]]
    min_l, min_r, min_dist = compute_hand_cheek_distances(face, hand_near)
    assert min_l == pytest.approx(0.0, abs=1e-4)
    assert min_dist == pytest.approx(0.0, abs=1e-4)
    assert min_r > 0.4

    # Hand placed far away at (0.5, 0.95)
    hand_far = [[MockLandmark(0.5, 0.95)]]
    _, _, far_dist = compute_hand_cheek_distances(face, hand_far)
    assert far_dist > 0.3


def test_compute_shoulder_z():
    # Shoulders: LEFT=11, RIGHT=12
    pose = {
        11: MockLandmark(0.3, 0.8, -0.04),
        12: MockLandmark(0.7, 0.8, -0.06),
    }
    z = compute_shoulder_z(pose)
    assert z == pytest.approx(-0.05)


def test_compute_motion_rates():
    f1 = FeatureSnapshot(
        timestamp=100.0,
        face_present=True,
        pose_present=True,
        hand_count=0,
        head_yaw=0.0,
        shoulder_z=-0.05,
    )
    f2 = FeatureSnapshot(
        timestamp=100.5,  # dt = 0.5s
        face_present=True,
        pose_present=True,
        hand_count=0,
        head_yaw=10.0,    # delta = 10 -> rate = 20 deg/s
        shoulder_z=-0.03, # delta = 0.02 -> rate = 0.04 /s
    )
    compute_motion_rates(f2, f1)
    assert f2.head_yaw_rate == pytest.approx(20.0)
    assert f2.shoulder_z_rate == pytest.approx(0.04)


def test_missing_landmark_handling():
    # When no landmarks exist
    snapshot = extract_features_from_landmarks(
        face_landmarks=None,
        hand_landmarks_list=None,
        pose_landmarks=None,
        width=640,
        height=480,
        now=1000.0,
    )
    assert not snapshot.face_present
    assert not snapshot.pose_present
    assert snapshot.hand_count == 0
    assert snapshot.head_yaw is None
    assert snapshot.ear is None
    assert snapshot.mar is None
    assert snapshot.hand_cheek_distance is None
    assert snapshot.shoulder_z is None
    assert snapshot.head_yaw_from_baseline is None
