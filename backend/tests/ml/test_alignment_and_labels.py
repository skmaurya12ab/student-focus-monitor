"""Tests for event alignment, multi-label generation, and feedback conflict resolution."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest
import uuid

from ml.dataset.alignment import align_events_to_telemetry
from ml.dataset.config import DatasetConfig
from ml.dataset.extract import (
    ExtractedDetectionEvent,
    ExtractedFeedback,
    ExtractedTelemetrySample,
)
from ml.dataset.feedback import build_feedback_index
from ml.dataset.labels import resolve_sample_labels


def test_temporal_event_alignment():
    session_id = uuid.uuid4()
    t0 = datetime(2026, 10, 5, 10, 0, 0, tzinfo=timezone.utc)

    # Event: 10:00:02 to 10:00:05
    event = ExtractedDetectionEvent(
        id=uuid.uuid4(),
        session_id=session_id,
        event_type="looking_away",
        started_at=t0 + timedelta(seconds=2),
        ended_at=t0 + timedelta(seconds=5),
        duration_seconds=3.0,
        detector_version="v4",
    )

    # 4 samples: before (1s), boundary start (2s), inside (3s), after (6s)
    s_before = ExtractedTelemetrySample(
        id=uuid.uuid4(), session_id=session_id, sampled_at=t0 + timedelta(seconds=1),
        frame_index=1, detector_version="v4", feature_schema_version="telemetry_v2",
        head_pitch=0.0, head_yaw=0.0, head_roll=0.0, ear=0.3, mar=0.2, min_hand_cheek_distance=None,
        shoulder_z=None, face_present=True, pose_present=True, hand_count=0, focus_state="focused"
    )
    s_start = ExtractedTelemetrySample(
        id=uuid.uuid4(), session_id=session_id, sampled_at=t0 + timedelta(seconds=2),
        frame_index=2, detector_version="v4", feature_schema_version="telemetry_v2",
        head_pitch=0.0, head_yaw=15.0, head_roll=0.0, ear=0.3, mar=0.2, min_hand_cheek_distance=None,
        shoulder_z=None, face_present=True, pose_present=True, hand_count=0, focus_state="distracted"
    )
    s_inside = ExtractedTelemetrySample(
        id=uuid.uuid4(), session_id=session_id, sampled_at=t0 + timedelta(seconds=3),
        frame_index=3, detector_version="v4", feature_schema_version="telemetry_v2",
        head_pitch=0.0, head_yaw=18.0, head_roll=0.0, ear=0.3, mar=0.2, min_hand_cheek_distance=None,
        shoulder_z=None, face_present=True, pose_present=True, hand_count=0, focus_state="distracted"
    )
    s_after = ExtractedTelemetrySample(
        id=uuid.uuid4(), session_id=session_id, sampled_at=t0 + timedelta(seconds=6),
        frame_index=4, detector_version="v4", feature_schema_version="telemetry_v2",
        head_pitch=0.0, head_yaw=0.0, head_roll=0.0, ear=0.3, mar=0.2, min_hand_cheek_distance=None,
        shoulder_z=None, face_present=True, pose_present=True, hand_count=0, focus_state="focused"
    )

    samples = [s_before, s_start, s_inside, s_after]
    res = align_events_to_telemetry(samples, [event])

    assert res.total_events_count == 1
    assert res.matched_events_count == 1
    assert len(res.unmatched_events) == 0

    assert len(res.sample_to_events[s_before.id]) == 0
    assert len(res.sample_to_events[s_start.id]) == 1
    assert len(res.sample_to_events[s_inside.id]) == 1
    assert len(res.sample_to_events[s_after.id]) == 0


def test_unmatched_event_is_tracked():
    session_id = uuid.uuid4()
    t0 = datetime(2026, 10, 5, 10, 0, 0, tzinfo=timezone.utc)
    # Event at 10:00:20 (no telemetry in this window)
    event = ExtractedDetectionEvent(
        id=uuid.uuid4(),
        session_id=session_id,
        event_type="phone_use",
        started_at=t0 + timedelta(seconds=20),
        ended_at=t0 + timedelta(seconds=25),
        duration_seconds=5.0,
        detector_version="v4",
    )
    sample = ExtractedTelemetrySample(
        id=uuid.uuid4(), session_id=session_id, sampled_at=t0,
        frame_index=1, detector_version="v4", feature_schema_version="telemetry_v2",
        head_pitch=0.0, head_yaw=0.0, head_roll=0.0, ear=0.3, mar=0.2, min_hand_cheek_distance=None,
        shoulder_z=None, face_present=True, pose_present=True, hand_count=0, focus_state="focused"
    )

    res = align_events_to_telemetry([sample], [event])
    assert res.matched_events_count == 0
    assert len(res.unmatched_events) == 1
    assert res.unmatched_events[0].id == event.id


def test_label_resolution_unreviewed_event():
    session_id = uuid.uuid4()
    sample = ExtractedTelemetrySample(
        id=uuid.uuid4(), session_id=session_id, sampled_at=datetime.now(timezone.utc),
        frame_index=5, detector_version="v4", feature_schema_version="telemetry_v2",
        head_pitch=0.0, head_yaw=15.0, head_roll=0.0, ear=0.3, mar=0.2, min_hand_cheek_distance=None,
        shoulder_z=None, face_present=True, pose_present=True, hand_count=0, focus_state="distracted",
        features={"calibration_complete": True}
    )
    event = ExtractedDetectionEvent(
        id=uuid.uuid4(), session_id=session_id, event_type="looking_away",
        started_at=sample.sampled_at, ended_at=sample.sampled_at, duration_seconds=1.0, detector_version="v4"
    )
    fb_index = build_feedback_index([])
    cfg = DatasetConfig()

    labels = resolve_sample_labels(sample, [event], fb_index, cfg)
    assert labels.category_labels["looking_away"] == 1
    assert labels.category_labels["phone_use"] == 0
    assert labels.focus_state_label == "distracted"
    assert labels.label_distracted == 1
    assert labels.label_source == "detector_event"
    assert labels.label_quality == "medium"


def test_label_resolution_human_correct_detection():
    session_id = uuid.uuid4()
    event_id = uuid.uuid4()
    sample = ExtractedTelemetrySample(
        id=uuid.uuid4(), session_id=session_id, sampled_at=datetime.now(timezone.utc),
        frame_index=5, detector_version="v4", feature_schema_version="telemetry_v2",
        head_pitch=0.0, head_yaw=15.0, head_roll=0.0, ear=0.3, mar=0.2, min_hand_cheek_distance=None,
        shoulder_z=None, face_present=True, pose_present=True, hand_count=0, focus_state="distracted",
        features={"calibration_complete": True}
    )
    event = ExtractedDetectionEvent(
        id=event_id, session_id=session_id, event_type="looking_away",
        started_at=sample.sampled_at, ended_at=sample.sampled_at, duration_seconds=1.0, detector_version="v4"
    )
    fb = ExtractedFeedback(
        id=uuid.uuid4(), session_id=session_id, detection_event_id=event_id,
        feedback_type="correct_detection", category="looking_away", note="Yes, true",
        created_at=sample.sampled_at + timedelta(minutes=1)
    )
    fb_index = build_feedback_index([fb])
    cfg = DatasetConfig()

    labels = resolve_sample_labels(sample, [event], fb_index, cfg)
    assert labels.category_labels["looking_away"] == 1
    assert labels.label_source == "human_confirmed_detection"
    assert labels.label_quality == "high"


def test_label_resolution_human_false_positive():
    """Verify false positive overrides category to 0 and records human_rejected provenance."""
    session_id = uuid.uuid4()
    event_id = uuid.uuid4()
    sample = ExtractedTelemetrySample(
        id=uuid.uuid4(), session_id=session_id, sampled_at=datetime.now(timezone.utc),
        frame_index=5, detector_version="v4", feature_schema_version="telemetry_v2",
        head_pitch=0.0, head_yaw=15.0, head_roll=0.0, ear=0.3, mar=0.2, min_hand_cheek_distance=None,
        shoulder_z=None, face_present=True, pose_present=True, hand_count=0, focus_state="distracted",
        features={"calibration_complete": True}
    )
    event = ExtractedDetectionEvent(
        id=event_id, session_id=session_id, event_type="looking_away",
        started_at=sample.sampled_at, ended_at=sample.sampled_at, duration_seconds=1.0, detector_version="v4"
    )
    fb = ExtractedFeedback(
        id=uuid.uuid4(), session_id=session_id, detection_event_id=event_id,
        feedback_type="false_positive", category="looking_away", note="Glare on glasses",
        created_at=sample.sampled_at + timedelta(minutes=1)
    )
    fb_index = build_feedback_index([fb])
    cfg = DatasetConfig()

    labels = resolve_sample_labels(sample, [event], fb_index, cfg)
    # The label must be 0 (confirmed negative because student marked it false positive)
    assert labels.category_labels["looking_away"] == 0
    # But provenance explicitly captures that detector fired and was rejected by human
    assert labels.label_source == "human_rejected_detector_event"
    assert labels.label_quality == "high"


def test_multi_label_overlapping_categories():
    """Verify sample overlapping two distinct categories correctly sets both labels to 1."""
    session_id = uuid.uuid4()
    sample = ExtractedTelemetrySample(
        id=uuid.uuid4(), session_id=session_id, sampled_at=datetime.now(timezone.utc),
        frame_index=10, detector_version="v4", feature_schema_version="telemetry_v2",
        head_pitch=0.0, head_yaw=15.0, head_roll=0.0, ear=0.3, mar=0.2, min_hand_cheek_distance=0.08,
        shoulder_z=None, face_present=True, pose_present=True, hand_count=1, focus_state="distracted",
        features={"calibration_complete": True}
    )
    ev1 = ExtractedDetectionEvent(
        id=uuid.uuid4(), session_id=session_id, event_type="looking_away",
        started_at=sample.sampled_at, ended_at=sample.sampled_at, duration_seconds=1.0, detector_version="v4"
    )
    ev2 = ExtractedDetectionEvent(
        id=uuid.uuid4(), session_id=session_id, event_type="phone_use",
        started_at=sample.sampled_at, ended_at=sample.sampled_at, duration_seconds=1.0, detector_version="v4"
    )
    fb_index = build_feedback_index([])
    cfg = DatasetConfig()

    labels = resolve_sample_labels(sample, [ev1, ev2], fb_index, cfg)
    assert labels.category_labels["looking_away"] == 1
    assert labels.category_labels["phone_use"] == 1
    assert labels.category_labels["yawning"] == 0
    assert labels.focus_state_label == "distracted"
    assert labels.label_distracted == 1


def test_other_feedback_does_not_create_positive_label():
    session_id = uuid.uuid4()
    sample = ExtractedTelemetrySample(
        id=uuid.uuid4(), session_id=session_id, sampled_at=datetime.now(timezone.utc),
        frame_index=1, detector_version="v4", feature_schema_version="telemetry_v2",
        head_pitch=0.0, head_yaw=0.0, head_roll=0.0, ear=0.3, mar=0.2, min_hand_cheek_distance=None,
        shoulder_z=None, face_present=True, pose_present=True, hand_count=0, focus_state="focused",
        features={"calibration_complete": True}
    )
    fb = ExtractedFeedback(
        id=uuid.uuid4(), session_id=session_id, detection_event_id=None,
        feedback_type="other", category=None, note="Lighting was dim",
        created_at=sample.sampled_at + timedelta(minutes=1)
    )
    fb_index = build_feedback_index([fb])
    cfg = DatasetConfig()

    labels = resolve_sample_labels(sample, [], fb_index, cfg)
    # Must remain negative / focused, not converted to positive distraction
    assert all(val == 0 for val in labels.category_labels.values())
    assert labels.focus_state_label == "focused"
    assert labels.label_distracted == 0
