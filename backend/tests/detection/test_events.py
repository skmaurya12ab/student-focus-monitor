"""Tests for structured detection event generation and serialization."""

import json
from app.detection.config import (
    ALERT_LOOKING_AWAY,
    DETECTOR_VERSION,
    FEATURE_SCHEMA_VERSION,
    DetectorConfig,
)
from app.detection.events import (
    create_alert_ended_event,
    create_alert_started_event,
)
from app.detection.features import FeatureSnapshot


def test_create_alert_started_event():
    config = DetectorConfig()
    features = FeatureSnapshot(
        timestamp=1000.0,
        face_present=True,
        pose_present=True,
        hand_count=0,
        head_yaw_from_baseline=15.0,
        ear=0.28,
        mar=0.15,
        hand_cheek_distance=0.40,
        shoulder_z_delta=0.01,
    )
    event = create_alert_started_event(
        session_id="test_session_123",
        event_type=ALERT_LOOKING_AWAY,
        now=1000.0,
        config=config,
        features=features,
    )

    assert event.session_id == "test_session_123"
    assert event.event_type == ALERT_LOOKING_AWAY
    assert event.event_action == "started"
    assert event.trigger_delay_sec == config.get_alert_delay(ALERT_LOOKING_AWAY)
    assert event.detector_version == DETECTOR_VERSION
    assert event.feature_schema_version == FEATURE_SCHEMA_VERSION
    assert event.duration_sec is None
    assert event.thresholds["yaw_threshold_deg"] == 10.0
    assert event.feature_snapshot["head_yaw_from_baseline"] == 15.0

    # Serialization test
    d = event.to_dict()
    assert "duration_sec" not in d
    serialized = json.dumps(d)
    assert "started" in serialized
    assert "test_session_123" in serialized


def test_create_alert_ended_event():
    config = DetectorConfig()
    event = create_alert_ended_event(
        session_id="test_session_123",
        event_type=ALERT_LOOKING_AWAY,
        now=1025.0,
        duration_sec=5.0,
        config=config,
    )

    assert event.session_id == "test_session_123"
    assert event.event_type == ALERT_LOOKING_AWAY
    assert event.event_action == "ended"
    assert event.timestamp == 1025.0
    assert event.duration_sec == 5.0
    assert event.trigger_delay_sec == config.get_alert_delay(ALERT_LOOKING_AWAY)

    d = event.to_dict()
    assert d["duration_sec"] == 5.0
    serialized = json.dumps(d)
    assert "ended" in serialized
