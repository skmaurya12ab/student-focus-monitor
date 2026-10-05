"""Human feedback interpretation and indexing module."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence
import uuid

from ml.dataset.config import CANONICAL_CATEGORIES, CANONICAL_FEEDBACK_TYPES
from ml.dataset.extract import ExtractedFeedback


@dataclass
class FeedbackIndex:
    """Indexed user feedback records for fast event and session lookups."""

    # (session_id, detection_event_id) -> ExtractedFeedback
    event_feedback: dict[tuple[uuid.UUID, uuid.UUID], ExtractedFeedback] = field(default_factory=dict)
    # session_id -> list of session-level feedbacks (detection_event_id is None)
    session_feedback: dict[uuid.UUID, list[ExtractedFeedback]] = field(default_factory=dict)

    # Statistics
    total_count: int = 0
    correct_detection_count: int = 0
    false_positive_count: int = 0
    missed_detection_count: int = 0
    other_count: int = 0


def build_feedback_index(feedbacks: Sequence[ExtractedFeedback]) -> FeedbackIndex:
    """
    Build structured index from extracted feedback records.
    Deduplicates by choosing the most recent feedback if multiple exist for the same event.
    """
    index = FeedbackIndex()
    # Sort feedbacks chronologically so later submissions overwrite earlier ones deterministically
    sorted_fbs = sorted(feedbacks, key=lambda fb: fb.created_at)

    for fb in sorted_fbs:
        index.total_count += 1
        fb_type = fb.feedback_type

        if fb_type == "correct_detection":
            index.correct_detection_count += 1
        elif fb_type == "false_positive":
            index.false_positive_count += 1
        elif fb_type == "missed_detection":
            index.missed_detection_count += 1
        elif fb_type == "other":
            index.other_count += 1

        if fb.detection_event_id is not None:
            key = (fb.session_id, fb.detection_event_id)
            index.event_feedback[key] = fb
        else:
            index.session_feedback.setdefault(fb.session_id, []).append(fb)

    return index
