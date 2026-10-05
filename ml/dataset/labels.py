"""Label construction, provenance assignment, and deterministic conflict resolution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Optional, Sequence
import uuid

from ml.dataset.config import (
    CANONICAL_CATEGORIES,
    CANONICAL_FOCUS_STATES,
    DatasetConfig,
)
from ml.dataset.extract import ExtractedDetectionEvent, ExtractedTelemetrySample
from ml.dataset.feedback import FeedbackIndex

# Provenance priority ranking for resolving composite label_source
PROVENANCE_PRIORITY = {
    "human_confirmed_detection": 6,
    "human_rejected_detector_event": 5,
    "human_missed_detection": 4,
    "detector_event": 3,
    "detector_state_away": 2,
    "detector_state_focused": 2,
    "detector_state_monitoring": 2,
    "calibration": 1,
    "unlabeled": 0,
}


@dataclass
class SampleLabels:
    """Multi-label targets and provenance for a single telemetry sample."""

    # Category labels: 1 = positive, 0 = negative, None = unknown/unlabeled
    category_labels: dict[str, Optional[int]]
    focus_state_label: str
    label_distracted: Optional[int]

    # Provenance
    label_source: str
    label_quality: str
    is_labeled: bool
    is_calibration: bool
    is_excluded: bool
    exclusion_reason: Optional[str] = None


def resolve_sample_labels(
    sample: ExtractedTelemetrySample,
    overlapping_events: Sequence[ExtractedDetectionEvent],
    feedback_index: FeedbackIndex,
    config: DatasetConfig,
) -> SampleLabels:
    """
    Construct multi-label targets and assign provenance using an explicit deterministic hierarchy:
    1. Human confirmed detection (highest priority positive)
    2. Human rejected detector event (false positive: label=0, provenance=human_rejected)
    3. Authoritative unreviewed detector event (label=1, provenance=detector_event)
    4. Human missed detection window (label=1, provenance=human_missed_detection)
    5. Baseline focused/away runtime state (label=0/1, provenance=detector_state)
    6. Calibration / Ambiguous (label=None, excluded by default)
    """
    json_features = sample.features or {}
    is_calibrating = (
        sample.focus_state == "calibrating"
        or json_features.get("calibration_complete") is False
    )

    category_labels: dict[str, Optional[int]] = {}
    category_sources: dict[str, str] = {}
    category_qualities: dict[str, str] = {}

    # Map overlapping events by event_type (a sample may overlap multiple events)
    events_by_type: dict[str, list[ExtractedDetectionEvent]] = {}
    for ev in overlapping_events:
        events_by_type.setdefault(ev.event_type, []).append(ev)

    # Check for session-level missed detection feedback
    session_fbs = feedback_index.session_feedback.get(sample.session_id, [])
    missed_detection_fbs = [fb for fb in session_fbs if fb.feedback_type == "missed_detection"]

    for cat in CANONICAL_CATEGORIES:
        evs = events_by_type.get(cat, [])

        if evs:
            # Check if any overlapping event has human feedback
            has_correct = False
            has_false_pos = False

            for ev in evs:
                fb = feedback_index.event_feedback.get((sample.session_id, ev.id))
                if fb:
                    if fb.feedback_type == "correct_detection":
                        has_correct = True
                    elif fb.feedback_type == "false_positive":
                        has_false_pos = True

            if has_correct:
                category_labels[cat] = 1
                category_sources[cat] = "human_confirmed_detection"
                category_qualities[cat] = "high"
            elif has_false_pos:
                # Student explicitly flagged this detection as a false positive.
                # Label is confirmed negative (0) while provenance records the rejection.
                category_labels[cat] = 0
                category_sources[cat] = "human_rejected_detector_event"
                category_qualities[cat] = "high"
            else:
                # Unreviewed authoritative detector event
                category_labels[cat] = 1
                category_sources[cat] = "detector_event"
                category_qualities[cat] = "medium"

        else:
            # No overlapping detector event for this category
            # Check missed detection temporal window if configured
            is_missed = False
            if config.missed_detection_window_sec > 0:
                window = timedelta(seconds=config.missed_detection_window_sec)
                for mfb in missed_detection_fbs:
                    if mfb.category == cat:
                        # If sample was within [created_at - window, created_at]
                        if mfb.created_at - window <= sample.sampled_at <= mfb.created_at:
                            is_missed = True
                            break

            if is_missed:
                category_labels[cat] = 1
                category_sources[cat] = "human_missed_detection"
                category_qualities[cat] = "high"
            elif is_calibrating:
                category_labels[cat] = None
                category_sources[cat] = "calibration"
                category_qualities[cat] = "low"
            elif sample.focus_state == "away":
                if cat == "away_from_desk":
                    category_labels[cat] = 1
                    category_sources[cat] = "detector_state_away"
                    category_qualities[cat] = "medium"
                else:
                    category_labels[cat] = 0
                    category_sources[cat] = "detector_state_away"
                    category_qualities[cat] = "medium"
            elif sample.focus_state in ("focused", "distracted") and (sample.face_present is True or sample.pose_present is True):
                category_labels[cat] = 0
                category_sources[cat] = "detector_state_monitoring"
                category_qualities[cat] = "medium"
            else:
                category_labels[cat] = None
                category_sources[cat] = "unlabeled"
                category_qualities[cat] = "unlabeled"

    # Overall focus state calculation
    if is_calibrating:
        focus_state_label = "calibrating"
        label_distracted = None
    elif any(val == 1 for val in category_labels.values()):
        focus_state_label = "distracted"
        label_distracted = 1
    elif all(val == 0 for val in category_labels.values()):
        focus_state_label = "focused"
        label_distracted = 0
    else:
        focus_state_label = sample.focus_state or "unknown"
        label_distracted = None

    # Determine composite overall label_source based on highest priority
    best_source = max(
        category_sources.values(),
        key=lambda s: PROVENANCE_PRIORITY.get(s, 0),
        default="unlabeled",
    )
    if is_calibrating and PROVENANCE_PRIORITY.get(best_source, 0) < PROVENANCE_PRIORITY["calibration"]:
        best_source = "calibration"

    # Composite label quality
    if any(q == "high" for q in category_qualities.values()):
        label_quality = "high"
    elif any(q == "medium" for q in category_qualities.values()):
        label_quality = "medium"
    elif is_calibrating:
        label_quality = "low"
    else:
        label_quality = "unlabeled"

    is_labeled = any(v is not None for v in category_labels.values()) and not is_calibrating

    # Exclusions
    is_excluded = False
    exclusion_reason = None
    if is_calibrating and not config.include_calibration:
        is_excluded = True
        exclusion_reason = "calibration_sample"

    return SampleLabels(
        category_labels=category_labels,
        focus_state_label=focus_state_label,
        label_distracted=label_distracted,
        label_source=best_source,
        label_quality=label_quality,
        is_labeled=is_labeled,
        is_calibration=is_calibrating,
        is_excluded=is_excluded,
        exclusion_reason=exclusion_reason,
    )
