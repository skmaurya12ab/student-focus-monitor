"""Tests for StudentDistractionDetector orchestration and session state isolation."""

import pytest
from app.detection.config import (
    ALERT_LOOKING_AWAY,
    DetectorConfig,
)
from app.detection.detector import StudentDistractionDetector
from app.detection.features import FeatureSnapshot
from app.detection.telemetry import InMemoryTelemetrySink


def _make_feature(
    timestamp: float,
    yaw: float = 0.0,
    shoulder_z: float = -0.04,
    ear: float = 0.30,
    mar: float = 0.20,
    hand_dist: float = 0.50,
    face_present: bool = True,
    pose_present: bool = True,
) -> FeatureSnapshot:
    return FeatureSnapshot(
        timestamp=timestamp,
        face_present=face_present,
        pose_present=pose_present,
        hand_count=0,
        head_yaw=yaw,
        head_pitch=0.0,
        head_roll=0.0,
        shoulder_z=shoulder_z,
        ear=ear,
        mar=mar,
        hand_cheek_distance=hand_dist,
    )


def test_detector_orchestration_complete_synthetic_session():
    # Fast calibration: 2s, 5 samples; Alert delay: 5s
    cfg = DetectorConfig(
        calibration_seconds=2.0,
        minimum_calibration_samples=5,
        alert_delays_sec={
            ALERT_LOOKING_AWAY: 5.0,
        },
    )
    sink = InMemoryTelemetrySink()
    detector = StudentDistractionDetector(
        config=cfg,
        session_id="synthetic_session_01",
        telemetry_sink=sink,
    )

    t = 1000.0

    # Step 1: Calibration (send 6 frames over 2.5s)
    for i in range(6):
        t += 0.5
        payload = detector.process_features(_make_feature(timestamp=t, yaw=0.0, shoulder_z=-0.04))
        if not detector.calibration.complete:
            assert payload["state"] == "calibrating"

    assert detector.calibration.complete
    assert detector.calibration.baseline.head_yaw == pytest.approx(0.0)

    # Step 2: Normal focused work for 3 seconds (t = 1003.5 to 1006.5)
    for _ in range(6):
        t += 0.5
        payload = detector.process_features(_make_feature(timestamp=t, yaw=0.0))
        assert payload["state"] == "focused"
        assert payload["active_alerts"] == []

    focused_before = detector.focused_seconds
    assert focused_before > 0.0

    # Step 3: Student turns head (yaw = 25.0 deg > 10.0 deg threshold)
    # Feed frames for 4.0s (less than 5.0s alert delay)
    for _ in range(8):
        t += 0.5
        payload = detector.process_features(_make_feature(timestamp=t, yaw=25.0))
        assert payload["state"] == "focused"  # Still focused because delay has not elapsed
        assert payload["active_alerts"] == []

    # Step 4: Advance past 5.0s delay (another 1.5s -> total 5.5s looking away)
    payload = detector.process_features(_make_feature(timestamp=t + 1.5, yaw=25.0))
    t += 1.5

    assert payload["state"] == "distracted"
    assert ALERT_LOOKING_AWAY in payload["active_alerts"]
    assert detector.distraction_count == 1

    # Verify event emitted to telemetry sink
    started_events = [e for e in sink.events if e.get("event_action") == "started"]
    assert len(started_events) == 1
    assert started_events[0]["event_type"] == ALERT_LOOKING_AWAY

    # Step 5: Student returns attention forward (yaw = 0.0)
    t += 1.0
    payload = detector.process_features(_make_feature(timestamp=t, yaw=0.0))
    assert payload["state"] == "focused"
    assert payload["active_alerts"] == []

    ended_events = [e for e in sink.events if e.get("event_action") == "ended"]
    assert len(ended_events) == 1
    assert ended_events[0]["event_type"] == ALERT_LOOKING_AWAY
    assert ended_events[0]["duration_sec"] > 0

    # Step 6: Finish session
    summary = detector.finish_session(now=t + 1.0)
    assert summary["session_id"] == "synthetic_session_01"
    assert summary["distraction_count"] == 1
    assert summary["focused_seconds"] > 0
    assert summary["distracted_seconds"] > 0
    assert 0.0 < summary["focus_score"] < 100.0


def test_cross_instance_state_isolation():
    """Verify two detector instances own independent state with zero cross-leakage."""
    cfg = DetectorConfig(
        calibration_seconds=1.0,
        minimum_calibration_samples=2,
        alert_delays_sec={ALERT_LOOKING_AWAY: 2.0},
    )

    sink1 = InMemoryTelemetrySink()
    sink2 = InMemoryTelemetrySink()

    det1 = StudentDistractionDetector(config=cfg, session_id="session_1", telemetry_sink=sink1)
    det2 = StudentDistractionDetector(config=cfg, session_id="session_2", telemetry_sink=sink2)

    # Calibrate both
    det1.process_features(_make_feature(timestamp=100.0, yaw=0.0))
    det1.process_features(_make_feature(timestamp=101.5, yaw=0.0))
    det2.process_features(_make_feature(timestamp=100.0, yaw=0.0))
    det2.process_features(_make_feature(timestamp=101.5, yaw=0.0))

    assert det1.calibration.complete
    assert det2.calibration.complete

    # Det1 triggers looking away alert
    det1.process_features(_make_feature(timestamp=102.0, yaw=30.0))
    det1.process_features(_make_feature(timestamp=105.0, yaw=30.0))  # Alert active in det1

    # Det2 stays focused
    det2.process_features(_make_feature(timestamp=102.0, yaw=0.0))
    det2.process_features(_make_feature(timestamp=105.0, yaw=0.0))

    # Assertions on Det 1
    assert det1.session_state.distraction_count == 1
    assert det1.session_state.current_state == "distracted"
    assert len(sink1.events) == 1

    # Assertions on Det 2 (must be completely clean)
    assert det2.session_state.distraction_count == 0
    assert det2.session_state.current_state == "focused"
    assert len(sink2.events) == 0
    assert det2.session_state.distracted_seconds == 0.0
