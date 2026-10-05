"""Temporal alignment between telemetry samples and detection events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Sequence
import uuid

from ml.dataset.extract import ExtractedDetectionEvent, ExtractedTelemetrySample


@dataclass
class AlignmentResult:
    """Outcome of temporal event-to-telemetry alignment."""

    # sample_id -> list of overlapping events
    sample_to_events: dict[uuid.UUID, list[ExtractedDetectionEvent]]
    total_events_count: int
    matched_events_count: int
    unmatched_events: list[ExtractedDetectionEvent]


def compute_event_interval(event: ExtractedDetectionEvent) -> tuple[datetime, datetime]:
    """
    Compute start and end timestamps for a detection event.
    If ended_at is null, projects end time using duration_seconds.
    """
    start = event.started_at
    if event.ended_at is not None:
        end = event.ended_at
    else:
        dur = max(0.0, float(event.duration_seconds or 0.0))
        end = start + timedelta(seconds=dur)
    return start, end


def align_events_to_telemetry(
    telemetry_samples: Sequence[ExtractedTelemetrySample],
    detection_events: Sequence[ExtractedDetectionEvent],
) -> AlignmentResult:
    """
    Align telemetry samples with detection events deterministically based on UTC timestamps.
    A telemetry sample falls inside an event interval if event_start <= sampled_at <= event_end.
    """
    # Group samples by session_id
    samples_by_session: dict[uuid.UUID, list[ExtractedTelemetrySample]] = {}
    for sample in telemetry_samples:
        samples_by_session.setdefault(sample.session_id, []).append(sample)

    # Group events by session_id
    events_by_session: dict[uuid.UUID, list[ExtractedDetectionEvent]] = {}
    for event in detection_events:
        events_by_session.setdefault(event.session_id, []).append(event)

    sample_to_events: dict[uuid.UUID, list[ExtractedDetectionEvent]] = {
        sample.id: [] for sample in telemetry_samples
    }
    matched_event_ids: set[uuid.UUID] = set()
    unmatched_events: list[ExtractedDetectionEvent] = []

    for session_id, events in events_by_session.items():
        session_samples = samples_by_session.get(session_id, [])
        if not session_samples:
            for ev in events:
                unmatched_events.append(ev)
            continue

        for event in events:
            ev_start, ev_end = compute_event_interval(event)
            event_matched = False

            for sample in session_samples:
                if ev_start <= sample.sampled_at <= ev_end:
                    sample_to_events[sample.id].append(event)
                    event_matched = True

            if event_matched:
                matched_event_ids.add(event.id)
            else:
                unmatched_events.append(event)

    return AlignmentResult(
        sample_to_events=sample_to_events,
        total_events_count=len(detection_events),
        matched_events_count=len(matched_event_ids),
        unmatched_events=unmatched_events,
    )
