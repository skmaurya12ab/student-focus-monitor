"""Tests for individual detection conditions across all 6 distraction categories."""

from app.detection.config import (
    ALERT_AWAY_FROM_DESK,
    ALERT_DROWSY,
    ALERT_LEANING_BACK,
    ALERT_LOOKING_AWAY,
    ALERT_PHONE_USE,
    ALERT_YAWNING,
    DetectorConfig,
)
from app.detection.features import FeatureSnapshot
from app.detection.rules import (
    evaluate_rules,
    is_away_from_desk,
    is_drowsy,
    is_leaning_back,
    is_looking_away,
    is_phone_use,
    is_yawning,
)


def _base_snapshot(**kwargs) -> FeatureSnapshot:
    """Helper creating a focused default snapshot."""
    defaults = {
        "timestamp": 1000.0,
        "face_present": True,
        "pose_present": True,
        "hand_count": 0,
        "head_yaw_from_baseline": 0.0,
        "head_pitch_from_baseline": 0.0,
        "head_roll_from_baseline": 0.0,
        "ear": 0.30,
        "mar": 0.20,
        "hand_cheek_distance": 0.50,
        "shoulder_z_delta": 0.0,
    }
    defaults.update(kwargs)
    return FeatureSnapshot(**defaults)


# 1. Looking Away
def test_rule_looking_away_true_and_false_and_boundary():
    cfg = DetectorConfig(yaw_threshold_deg=10.0)

    # False when within threshold
    assert not is_looking_away(_base_snapshot(head_yaw_from_baseline=5.0), cfg)
    assert not is_looking_away(_base_snapshot(head_yaw_from_baseline=-9.9), cfg)
    assert not is_looking_away(_base_snapshot(head_yaw_from_baseline=10.0), cfg)  # boundary

    # True when exceeding threshold in positive or negative yaw
    assert is_looking_away(_base_snapshot(head_yaw_from_baseline=10.1), cfg)
    assert is_looking_away(_base_snapshot(head_yaw_from_baseline=-15.0), cfg)

    # False if face absent or baseline missing
    assert not is_looking_away(_base_snapshot(face_present=False, head_yaw_from_baseline=25.0), cfg)
    assert not is_looking_away(_base_snapshot(head_yaw_from_baseline=None), cfg)


# 2. Phone Use
def test_rule_phone_use_true_and_false_and_boundary():
    cfg = DetectorConfig(hand_near_cheek_dist=0.15)

    # True when hand is closer than threshold
    assert is_phone_use(_base_snapshot(hand_cheek_distance=0.10), cfg)
    assert is_phone_use(_base_snapshot(hand_cheek_distance=0.01), cfg)

    # False at boundary or further away
    assert not is_phone_use(_base_snapshot(hand_cheek_distance=0.15), cfg)  # boundary
    assert not is_phone_use(_base_snapshot(hand_cheek_distance=0.20), cfg)

    # False if face absent or distance missing
    assert not is_phone_use(_base_snapshot(face_present=False, hand_cheek_distance=0.05), cfg)
    assert not is_phone_use(_base_snapshot(hand_cheek_distance=None), cfg)


# 3. Yawning
def test_rule_yawning_true_and_false_and_boundary():
    cfg = DetectorConfig(mar_threshold=0.55)

    # True when MAR exceeds threshold
    assert is_yawning(_base_snapshot(mar=0.56), cfg)
    assert is_yawning(_base_snapshot(mar=0.85), cfg)

    # False at boundary or below
    assert not is_yawning(_base_snapshot(mar=0.55), cfg)  # boundary
    assert not is_yawning(_base_snapshot(mar=0.40), cfg)

    # False if face absent or MAR None
    assert not is_yawning(_base_snapshot(face_present=False, mar=0.90), cfg)
    assert not is_yawning(_base_snapshot(mar=None), cfg)


# 4. Drowsy / Eyes Closed
def test_rule_drowsy_true_and_false_and_boundary():
    cfg = DetectorConfig(ear_threshold=0.21)

    # True when EAR falls below threshold
    assert is_drowsy(_base_snapshot(ear=0.20), cfg)
    assert is_drowsy(_base_snapshot(ear=0.05), cfg)

    # False at boundary or above
    assert not is_drowsy(_base_snapshot(ear=0.21), cfg)  # boundary
    assert not is_drowsy(_base_snapshot(ear=0.25), cfg)

    # False if face absent or EAR None
    assert not is_drowsy(_base_snapshot(face_present=False, ear=0.05), cfg)
    assert not is_drowsy(_base_snapshot(ear=None), cfg)


# 5. Leaning Back
def test_rule_leaning_back_true_and_false_and_boundary():
    cfg = DetectorConfig(lean_back_z_delta=0.15)

    # True when shoulder delta exceeds threshold (positive or negative depth displacement)
    assert is_leaning_back(_base_snapshot(shoulder_z_delta=0.16), cfg)
    assert is_leaning_back(_base_snapshot(shoulder_z_delta=0.30), cfg)
    assert is_leaning_back(_base_snapshot(shoulder_z_delta=-0.18), cfg)

    # False at boundary or below
    assert not is_leaning_back(_base_snapshot(shoulder_z_delta=0.15), cfg)  # boundary
    assert not is_leaning_back(_base_snapshot(shoulder_z_delta=-0.15), cfg)  # negative boundary
    assert not is_leaning_back(_base_snapshot(shoulder_z_delta=0.05), cfg)
    assert not is_leaning_back(_base_snapshot(shoulder_z_delta=-0.10), cfg)

    # False if pose absent or delta None
    assert not is_leaning_back(_base_snapshot(pose_present=False, shoulder_z_delta=0.30), cfg)
    assert not is_leaning_back(_base_snapshot(shoulder_z_delta=None), cfg)


# 6. Away From Desk
def test_rule_away_from_desk_true_and_false():
    cfg = DetectorConfig()

    # True only when BOTH face and pose are absent
    assert is_away_from_desk(_base_snapshot(face_present=False, pose_present=False), cfg)

    # False if either is present
    assert not is_away_from_desk(_base_snapshot(face_present=True, pose_present=False), cfg)
    assert not is_away_from_desk(_base_snapshot(face_present=False, pose_present=True), cfg)
    assert not is_away_from_desk(_base_snapshot(face_present=True, pose_present=True), cfg)


def test_evaluate_rules_all_categories_mapping():
    cfg = DetectorConfig()
    snap = _base_snapshot(
        head_yaw_from_baseline=20.0,  # Looking away True
        mar=0.70,                      # Yawning True
    )
    results = evaluate_rules(snap, cfg)
    assert results[ALERT_LOOKING_AWAY] is True
    assert results[ALERT_YAWNING] is True
    assert results[ALERT_PHONE_USE] is False
    assert results[ALERT_DROWSY] is False
    assert results[ALERT_LEANING_BACK] is False
    assert results[ALERT_AWAY_FROM_DESK] is False
