"""Tests for telemetry sampling cadence, bounded queue backpressure, and flush lifecycle."""
import asyncio
from datetime import datetime, timezone
import pytest
from app.detection.config import DetectorConfig
from app.detection.detector import StudentDistractionDetector
from app.detection.features import FeatureSnapshot
from app.detection.telemetry import BufferedTelemetrySink, InMemoryTelemetrySink


def test_telemetry_sampling_cadence():
    """Verify detector respects telemetry_interval_sec and does not emit on every frame."""
    config = DetectorConfig(telemetry_interval_sec=0.2)
    sink = InMemoryTelemetrySink()
    detector = StudentDistractionDetector(config=config, telemetry_sink=sink)

    # Frame 1 at t=100.0 -> should emit telemetry
    t0 = 100.0
    f1 = FeatureSnapshot(timestamp=t0, face_present=True, pose_present=True, hand_count=0)
    detector._maybe_emit_telemetry(f1)
    assert len(sink.telemetry_records) == 1
    assert detector.last_telemetry_time == t0

    # Rapid Frame 2 at t=100.05 (< 0.2s elapsed) -> should NOT emit
    f2 = FeatureSnapshot(timestamp=t0 + 0.05, face_present=True, pose_present=True, hand_count=0)
    detector._maybe_emit_telemetry(f2)
    assert len(sink.telemetry_records) == 1

    # Rapid Frame 3 at t=100.15 (< 0.2s elapsed) -> should NOT emit
    f3 = FeatureSnapshot(timestamp=t0 + 0.15, face_present=True, pose_present=True, hand_count=0)
    detector._maybe_emit_telemetry(f3)
    assert len(sink.telemetry_records) == 1

    # Frame 4 at t=100.21 (>= 0.2s elapsed) -> SHOULD emit
    f4 = FeatureSnapshot(timestamp=t0 + 0.21, face_present=True, pose_present=True, hand_count=0)
    detector._maybe_emit_telemetry(f4)
    assert len(sink.telemetry_records) == 2
    assert detector.last_telemetry_time == t0 + 0.21


def test_bounded_queue_backpressure_and_drop_oldest():
    """Verify BufferedTelemetrySink caps memory growth and drops oldest records under backpressure."""
    max_size = 50
    sink = BufferedTelemetrySink(maxsize=max_size)

    # Emit 80 samples
    for i in range(80):
        sink.emit_telemetry({"frame_index": i, "sampled_at": datetime.now(timezone.utc)})

    stats = sink.stats
    assert stats["samples_generated"] == 80
    assert stats["pending_samples"] == max_size
    assert stats["samples_dropped"] == 30

    # Drain all samples
    drained = sink.drain_all()
    assert len(drained) == max_size
    # First retained sample should be frame_index 30 (0..29 dropped)
    assert drained[0]["frame_index"] == 30
    assert drained[-1]["frame_index"] == 79
    assert sink.qsize == 0


def test_drain_batch_and_stats():
    """Verify drain_batch retrieves up to limit and increments persisted count correctly."""
    sink = BufferedTelemetrySink(maxsize=100)
    for i in range(25):
        sink.emit_telemetry({"frame_index": i})

    batch = sink.drain_batch(limit=10)
    assert len(batch) == 10
    assert sink.qsize == 15
    assert batch[0]["frame_index"] == 0
    assert batch[-1]["frame_index"] == 9

    # Record persistence
    sink.record_persisted(10)
    stats = sink.stats
    assert stats["samples_persisted"] == 10
    assert stats["pending_samples"] == 15


def test_sink_closed_rejects_new_samples():
    """Verify that once sink is closed (session ended), no new samples are buffered."""
    sink = BufferedTelemetrySink(maxsize=10)
    sink.emit_telemetry({"frame_index": 1})
    assert sink.qsize == 1

    sink.close()
    assert sink.is_closed is True

    # Attempt to emit after close
    sink.emit_telemetry({"frame_index": 2})
    assert sink.qsize == 1  # Still 1, 2nd sample rejected
