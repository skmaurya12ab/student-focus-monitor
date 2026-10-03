"""Tests for telemetry generation, sinks, and zero media storage guarantees."""

import json
from pathlib import Path
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
    FileTelemetrySink,
    InMemoryTelemetrySink,
    build_telemetry_payload,
)


def test_build_telemetry_payload_and_media_exclusion():
    config = DetectorConfig()
    session_state = SessionState(session_id="session_xyz")
    session_state.focused_seconds = 45.2
    session_state.distracted_seconds = 12.1
    session_state.away_seconds = 0.0
    session_state.distraction_count = 2

    features = FeatureSnapshot(
        timestamp=1500.0,
        face_present=True,
        pose_present=True,
        hand_count=1,
        head_yaw=12.5,
        head_pitch=2.0,
        head_roll=-1.0,
        head_yaw_from_baseline=10.5,
        ear=0.25,
        mar=0.35,
        hand_cheek_distance=0.12,
        shoulder_z=-0.04,
        shoulder_z_delta=0.01,
        state="distracted",
        active_alerts=["Looking Away"],
    )

    baseline = CalibrationBaseline(
        shoulder_z=-0.05,
        head_yaw=2.0,
        head_pitch=2.0,
        head_roll=-1.0,
    )

    payload = build_telemetry_payload(
        session_id="session_xyz",
        features=features,
        session_state=session_state,
        calibration_complete=True,
        baseline=baseline,
        config=config,
    )

    # Required metadata fields
    assert payload["session_id"] == "session_xyz"
    assert payload["detector_version"] == DETECTOR_VERSION
    assert payload["schema_version"] == FEATURE_SCHEMA_VERSION
    assert payload["calibration_complete"] is True
    assert payload["focused_seconds"] == 45.2
    assert payload["distracted_seconds"] == 12.1
    assert payload["active_alerts"] == ["Looking Away"]
    assert payload["head_yaw"] == 12.5
    assert payload["hand_cheek_distance"] == 0.12

    # Verification: STRICTLY ZERO raw media or pixel buffers
    forbidden_terms = {"image", "frame", "frame_bytes", "video", "jpeg", "png", "audio", "buffer"}
    payload_keys = set(payload.keys())
    assert forbidden_terms.isdisjoint(payload_keys)

    # Valid JSON serialization check
    serialized = json.dumps(payload)
    deserialized = json.loads(serialized)
    assert deserialized["session_id"] == "session_xyz"


def test_in_memory_telemetry_sink():
    sink = InMemoryTelemetrySink()
    sink.emit_telemetry({"sample": 1})
    sink.emit_event({"event": "started"})
    sink.finish_session({"focus_score": 95.0})

    assert len(sink.telemetry_records) == 1
    assert len(sink.events) == 1
    assert sink.summary == {"focus_score": 95.0}


def test_file_telemetry_sink(tmp_path: Path):
    config = DetectorConfig()
    sink = FileTelemetrySink("test_session_abc", tmp_path, config)

    sink.emit_telemetry({"tick": 1, "state": "focused"})
    sink.emit_event({"event": "started"})
    sink.finish_session({"summary_stat": 100})

    # Verify files created on disk
    telem_file = tmp_path / "telemetry" / "test_session_abc.jsonl"
    event_file = tmp_path / "events" / "test_session_abc.jsonl"
    meta_file = tmp_path / "sessions" / "test_session_abc.json"

    assert telem_file.exists()
    assert event_file.exists()
    assert meta_file.exists()

    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    assert meta["session_id"] == "test_session_abc"
    assert meta["privacy"]["video_recorded"] is False
    assert meta["summary"]["summary_stat"] == 100
