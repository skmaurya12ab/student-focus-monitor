"""Deterministic tests proving that user-configured persistence thresholds control runtime alert timing."""
import uuid
import pytest

from app.detection.config import (
    ALERT_AWAY_FROM_DESK,
    ALERT_DROWSY,
    ALERT_LEANING_BACK,
    ALERT_PHONE_USE,
    ALERT_YAWNING,
    DetectorConfig,
)
from app.detection.detector import StudentDistractionDetector
from app.detection.features import FeatureSnapshot
from app.detection.trackers import MultiCategoryTracker
from app.services.detection_runtime_service import SessionDetectionRuntime


def make_calibrated_detector(config: DetectorConfig) -> StudentDistractionDetector:
    """Helper creating a detector pre-calibrated with baseline features."""
    detector = StudentDistractionDetector(config=config)
    # Pre-populate calibration buffer to simulate completed calibration
    detector.calibration.samples = [
        FeatureSnapshot(
            timestamp=100.0 + i * 0.1,
            face_present=True,
            pose_present=True,
            head_yaw=0.0,
            ear=0.30,
            mar=0.15,
            shoulder_z=0.0,
            torso_posture_delta=0.0,
        )
        for i in range(35)
    ]
    detector.calibration.is_calibrated = True
    detector.calibration.baseline_head_yaw = 0.0
    detector.calibration.baseline_ear = 0.30
    detector.calibration.baseline_mar = 0.15
    detector.calibration.baseline_shoulder_z = 0.0
    detector.calibration.baseline_torso_aspect_ratio = 1.60
    return detector


def test_phone_use_threshold_timing_comparison():
    """Verify Configuration A (phone_use = 2s) triggers at 2s while Configuration B (phone_use = 8s) does not."""
    # Config A: 2 second delay
    config_a = DetectorConfig(
        alert_delays_sec={
            ALERT_PHONE_USE: 2.0,
            ALERT_YAWNING: 2.0,
            ALERT_DROWSY: 4.0,
            ALERT_LEANING_BACK: 8.0,
            ALERT_AWAY_FROM_DESK: 10.0,
        }
    )
    # Config B: 8 second delay
    config_b = DetectorConfig(
        alert_delays_sec={
            ALERT_PHONE_USE: 8.0,
            ALERT_YAWNING: 2.0,
            ALERT_DROWSY: 4.0,
            ALERT_LEANING_BACK: 8.0,
            ALERT_AWAY_FROM_DESK: 10.0,
        }
    )

    tracker_a = MultiCategoryTracker(config_a)
    tracker_b = MultiCategoryTracker(config_b)

    # Phone use condition active: True
    phone_condition = {ALERT_PHONE_USE: True}

    t0 = 1000.0

    # At t=0.0s: condition starts
    _, active_a_0 = tracker_a.update(phone_condition, now=t0)
    _, active_b_0 = tracker_b.update(phone_condition, now=t0)
    assert ALERT_PHONE_USE not in active_a_0
    assert ALERT_PHONE_USE not in active_b_0

    # At t=1.0s: sustained for 1.0s (< 2s, < 8s)
    _, active_a_1 = tracker_a.update(phone_condition, now=t0 + 1.0)
    _, active_b_1 = tracker_b.update(phone_condition, now=t0 + 1.0)
    assert ALERT_PHONE_USE not in active_a_1
    assert ALERT_PHONE_USE not in active_b_1

    # At t=2.0s: sustained for 2.0s (>= Config A 2s, but < Config B 8s)
    _, active_a_2 = tracker_a.update(phone_condition, now=t0 + 2.0)
    _, active_b_2 = tracker_b.update(phone_condition, now=t0 + 2.0)
    assert ALERT_PHONE_USE in active_a_2, "Config A (2s threshold) MUST be active at 2.0s"
    assert ALERT_PHONE_USE not in active_b_2, "Config B (8s threshold) MUST NOT be active at 2.0s"

    # At t=5.0s: Config A remains active, Config B still inactive
    _, active_a_5 = tracker_a.update(phone_condition, now=t0 + 5.0)
    _, active_b_5 = tracker_b.update(phone_condition, now=t0 + 5.0)
    assert ALERT_PHONE_USE in active_a_5
    assert ALERT_PHONE_USE not in active_b_5

    # At t=8.0s: Config B finally triggers!
    _, active_a_8 = tracker_a.update(phone_condition, now=t0 + 8.0)
    _, active_b_8 = tracker_b.update(phone_condition, now=t0 + 8.0)
    assert ALERT_PHONE_USE in active_a_8
    assert ALERT_PHONE_USE in active_b_8, "Config B (8s threshold) MUST become active at 8.0s"


def test_yawning_threshold_timing():
    """Verify yawning delay changes when configured from 1.0s to 5.0s."""
    config_fast = DetectorConfig(alert_delays_sec={ALERT_YAWNING: 1.0})
    config_slow = DetectorConfig(alert_delays_sec={ALERT_YAWNING: 5.0})

    tracker_fast = MultiCategoryTracker(config_fast)
    tracker_slow = MultiCategoryTracker(config_slow)

    yawn_cond = {ALERT_YAWNING: True}
    t0 = 100.0

    tracker_fast.update(yawn_cond, now=t0)
    tracker_slow.update(yawn_cond, now=t0)

    # At 1.0s
    _, active_fast_1 = tracker_fast.update(yawn_cond, now=t0 + 1.0)
    _, active_slow_1 = tracker_slow.update(yawn_cond, now=t0 + 1.0)
    assert ALERT_YAWNING in active_fast_1
    assert ALERT_YAWNING not in active_slow_1

    # At 5.0s
    _, active_slow_5 = tracker_slow.update(yawn_cond, now=t0 + 5.0)
    assert ALERT_YAWNING in active_slow_5


def test_leaning_back_posture_threshold_timing():
    """Verify bad posture / leaning back delay changes when configured from 2.0s to 6.0s."""
    config_fast = DetectorConfig(alert_delays_sec={ALERT_LEANING_BACK: 2.0})
    config_slow = DetectorConfig(alert_delays_sec={ALERT_LEANING_BACK: 6.0})

    tracker_fast = MultiCategoryTracker(config_fast)
    tracker_slow = MultiCategoryTracker(config_slow)

    lean_cond = {ALERT_LEANING_BACK: True}
    t0 = 200.0

    tracker_fast.update(lean_cond, now=t0)
    tracker_slow.update(lean_cond, now=t0)

    # At 2.0s
    _, active_fast_2 = tracker_fast.update(lean_cond, now=t0 + 2.0)
    _, active_slow_2 = tracker_slow.update(lean_cond, now=t0 + 2.0)
    assert ALERT_LEANING_BACK in active_fast_2
    assert ALERT_LEANING_BACK not in active_slow_2

    # At 6.0s
    _, active_slow_6 = tracker_slow.update(lean_cond, now=t0 + 6.0)
    assert ALERT_LEANING_BACK in active_slow_6


def test_transient_detection_does_not_trigger_alert():
    """Verify that a brief distraction shorter than the configured threshold resets cleanly."""
    config = DetectorConfig(alert_delays_sec={ALERT_PHONE_USE: 4.0})
    tracker = MultiCategoryTracker(config)

    t0 = 500.0
    # Phone use for 2.0s (< 4.0s)
    tracker.update({ALERT_PHONE_USE: True}, now=t0)
    tracker.update({ALERT_PHONE_USE: True}, now=t0 + 2.0)

    # Condition clears at 2.5s
    results, active = tracker.update({ALERT_PHONE_USE: False}, now=t0 + 2.5)
    assert ALERT_PHONE_USE not in active
    assert results[ALERT_PHONE_USE].active is False
    assert results[ALERT_PHONE_USE].just_ended is False  # Never became active alert

    # Re-evaluating later at 5.0s without condition remains inactive
    _, active_after = tracker.update({ALERT_PHONE_USE: False}, now=t0 + 5.0)
    assert ALERT_PHONE_USE not in active_after


def test_cv_feature_thresholds_remain_separate_from_persistence_delays():
    """Verify adjusting alert delays does NOT modify computer-vision geometry thresholds."""
    config = DetectorConfig(
        yaw_threshold_deg=10.0,
        ear_threshold=0.21,
        mar_threshold=0.55,
        hand_near_cheek_dist=0.15,
        lean_back_z_delta=0.15,
        alert_delays_sec={
            ALERT_PHONE_USE: 1.0,
            ALERT_YAWNING: 1.0,
        },
    )
    # Underlying CV thresholds are untouched
    assert config.yaw_threshold_deg == 10.0
    assert config.ear_threshold == 0.21
    assert config.mar_threshold == 0.55
    assert config.hand_near_cheek_dist == 0.15
    assert config.lean_back_z_delta == 0.15
    # Only persistence delays changed
    assert config.get_alert_delay(ALERT_PHONE_USE) == 1.0
    assert config.get_alert_delay(ALERT_YAWNING) == 1.0


def test_runtime_update_config_updates_trackers_dynamically():
    """Verify SessionDetectionRuntime.update_config updates tracker delays on the fly."""
    session_id = uuid.uuid4()
    user_id = uuid.uuid4()
    initial_config = DetectorConfig(alert_delays_sec={ALERT_PHONE_USE: 10.0})
    runtime = SessionDetectionRuntime(session_id=session_id, user_id=user_id, config=initial_config)

    assert runtime.detector.trackers.trackers[ALERT_PHONE_USE].delay == 10.0

    # Update config to 2.0s
    updated_config = DetectorConfig(alert_delays_sec={ALERT_PHONE_USE: 2.0})
    runtime.update_config(updated_config)

    assert runtime.detector.trackers.trackers[ALERT_PHONE_USE].delay == 2.0
