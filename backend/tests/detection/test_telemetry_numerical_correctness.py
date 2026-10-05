"""Deterministic tests for numerical correctness, baseline deltas, tracker states, and privacy in telemetry."""
import math
import pytest
from app.detection.calibration import CalibrationBaseline
from app.detection.config import (
    DETECTOR_VERSION,
    FEATURE_SCHEMA_VERSION,
    DetectorConfig,
)
from app.detection.features import FeatureSnapshot
from app.detection.session_state import SessionState
from app.detection.telemetry import (
    BufferedTelemetrySink,
    build_telemetry_payload,
)


def test_telemetry_numerical_correctness_and_baseline_deltas():
    """Verify that exact numerical values, baseline deltas, and tracker states are faithfully preserved."""
    config = DetectorConfig(telemetry_interval_sec=0.2)
    session_state = SessionState(session_id="session-num-test")
    session_state.focused_seconds = 120.0
    session_state.distracted_seconds = 15.0
    session_state.away_seconds = 5.0
    session_state.distraction_count = 3
    session_state.frame_count = 42

    features = FeatureSnapshot(
        timestamp=100.5,
        face_present=True,
        pose_present=True,
        hand_count=1,
        head_pitch=-3.2,
        head_yaw=18.5,
        head_roll=1.1,
        head_yaw_from_baseline=16.5,
        head_pitch_from_baseline=-1.2,
        head_roll_from_baseline=0.5,
        head_yaw_rate=1.8,
        head_pitch_rate=-0.4,
        shoulder_z_rate=0.03,
        ear=0.31,
        left_ear=0.30,
        right_ear=0.32,
        mar=0.42,
        hand_cheek_distance=0.18,
        left_hand_cheek_distance=0.18,
        right_hand_cheek_distance=0.65,
        shoulder_z=-0.04,
        shoulder_z_delta=0.21,
        torso_aspect_ratio=1.15,
        torso_posture_delta=0.05,
        state="distracted",
        active_alerts=["Looking Away"],
    )

    baseline = CalibrationBaseline(
        head_yaw=2.0,
        head_pitch=-2.0,
        head_roll=0.6,
        shoulder_z=-0.25,
        torso_aspect_ratio=1.10,
    )

    tracker_results = {
        "looking_away": type("TrackerMock", (), {"active": True, "duration_sec": 2.5, "persistence_met": True})(),
        "phone_use": type("TrackerMock", (), {"active": False, "duration_sec": 0.0, "persistence_met": False})(),
    }

    payload = build_telemetry_payload(
        session_id="session-num-test",
        features=features,
        session_state=session_state,
        calibration_complete=True,
        baseline=baseline,
        config=config,
        tracker_results=tracker_results,
        frame_index=42,
    )

    # 1. Scalar Top-Level Numerical Preservation
    assert payload["session_id"] == "session-num-test"
    assert payload["frame_index"] == 42
    assert payload["detector_version"] == DETECTOR_VERSION
    assert payload["feature_schema_version"] == "telemetry_v2"
    assert payload["head_yaw"] == 18.5
    assert payload["head_pitch"] == -3.2
    assert payload["head_roll"] == 1.1
    assert payload["ear"] == 0.31
    assert payload["mar"] == 0.42
    assert payload["hand_cheek_distance"] == 0.18
    assert payload["shoulder_z"] == -0.04
    assert payload["face_present"] is True
    assert payload["pose_present"] is True
    assert payload["hand_count"] == 1
    assert payload["state"] == "distracted"

    # 2. Structured Features & Baseline-Relative Deltas
    assert payload["head_yaw_from_baseline"] == 16.5
    assert payload["head_pitch_from_baseline"] == -1.2
    assert payload["head_roll_from_baseline"] == 0.5
    assert payload["shoulder_z_delta"] == 0.21
    assert payload["head_yaw_rate"] == 1.8
    assert payload["head_pitch_rate"] == -0.4
    assert payload["shoulder_z_rate"] == 0.03
    assert payload["left_ear"] == 0.30
    assert payload["right_ear"] == 0.32
    assert payload["left_hand_cheek_distance"] == 0.18
    assert payload["right_hand_cheek_distance"] == 0.65

    # 3. Baseline & Calibration Info
    assert payload["calibration_complete"] is True
    assert payload["baseline"]["head_yaw"] == 2.0
    assert payload["baseline"]["head_pitch"] == -2.0
    assert payload["baseline"]["shoulder_z"] == -0.25

    # 4. Rules & Trackers
    assert payload["tracker_states"]["looking_away"]["active"] is True
    assert payload["tracker_states"]["looking_away"]["duration_sec"] == 2.5
    assert payload["tracker_states"]["looking_away"]["persistence_met"] is True
    assert payload["tracker_states"]["phone_use"]["active"] is False

    # 5. Finite Values Verification (No NaN, no Inf)
    for k, v in payload.items():
        if isinstance(v, (int, float)):
            assert math.isfinite(v), f"Value for {k} must be finite"


def test_telemetry_null_handling_not_zero():
    """Verify missing metrics result in None/null, NOT misleading 0.0."""
    config = DetectorConfig()
    session_state = SessionState(session_id="session-null-test")

    # Features when no face is present (EAR and head pose are None)
    features = FeatureSnapshot(
        timestamp=10.0,
        face_present=False,
        pose_present=False,
        hand_count=0,
        head_pitch=None,
        head_yaw=None,
        head_roll=None,
        ear=None,
        mar=None,
        hand_cheek_distance=None,
        shoulder_z=None,
        state="away",
    )

    payload = build_telemetry_payload(
        session_id="session-null-test",
        features=features,
        session_state=session_state,
        calibration_complete=False,
        baseline=None,
        config=config,
        frame_index=1,
    )

    assert payload["ear"] is None
    assert payload["mar"] is None
    assert payload["head_pitch"] is None
    assert payload["head_yaw"] is None
    assert payload["hand_cheek_distance"] is None
    assert payload["shoulder_z"] is None
    assert payload["face_present"] is False
    assert payload["pose_present"] is False
    assert payload["hand_count"] == 0
    assert payload["state"] == "away"


def test_telemetry_strict_privacy_exclusion():
    """Verify absolutely NO media, buffers, frames, audio, or image data are present in telemetry."""
    config = DetectorConfig()
    session_state = SessionState(session_id="session-privacy-test")
    features = FeatureSnapshot(timestamp=1.0, face_present=True, pose_present=True, hand_count=0)

    payload = build_telemetry_payload(
        session_id="session-privacy-test",
        features=features,
        session_state=session_state,
        calibration_complete=True,
        baseline=None,
        config=config,
    )

    forbidden_substrings = [
        "image", "frame_bytes", "video", "jpeg", "png", "audio",
        "buffer", "screenshot", "pix", "raw_frame", "camera_feed"
    ]

    def check_keys(d, prefix=""):
        if isinstance(d, dict):
            for k, v in d.items():
                lower_k = k.lower()
                for bad in forbidden_substrings:
                    assert bad not in lower_k, f"Forbidden key '{k}' found at path '{prefix}{k}'"
                check_keys(v, prefix=f"{prefix}{k}.")

    check_keys(payload)

    # Test BufferedTelemetrySink strips any injected forbidden key
    sink = BufferedTelemetrySink(maxsize=10)
    dirty_payload = payload.copy()
    dirty_payload["image_buffer"] = b"binary_image_data"
    dirty_payload["webcam_frame"] = "base64_encoded_jpeg"
    sink.emit_telemetry(dirty_payload)

    samples = sink.drain_all()
    assert len(samples) == 1
    assert "image_buffer" not in samples[0]
    assert "webcam_frame" not in samples[0]
