"""Synthetic dataset fixture generator for deterministic testing and pipeline verification."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid

from ml.dataset.config import CANONICAL_CATEGORIES
from ml.dataset.extract import (
    DatasetSources,
    ExtractedDetectionEvent,
    ExtractedFeedback,
    ExtractedSession,
    ExtractedTelemetrySample,
    ExtractedUser,
)


def generate_synthetic_sources(
    num_users: int = 3,
    samples_per_session: int = 20,
    seed: int = 42,
) -> DatasetSources:
    """
    Generate a deterministic synthetic DatasetSources containing:
    - Multiple distinct users (for leakage-safe split verification)
    - Multiple sessions per user
    - Calibration samples
    - True positive events with human correct_detection feedback
    - False positive events with human false_positive feedback
    - Unreviewed detector events
    - Session-level missed detection feedback
    - Other general product notes
    - Missing numerical features (e.g. face absent, occluded landmarks)
    """
    base_time = datetime(2026, 10, 1, 10, 0, 0, tzinfo=timezone.utc)

    users: dict[uuid.UUID, ExtractedUser] = {}
    sessions: dict[uuid.UUID, ExtractedSession] = {}
    telemetry_samples: list[ExtractedTelemetrySample] = []
    detection_events: list[ExtractedDetectionEvent] = []
    feedbacks: list[ExtractedFeedback] = []

    user_ids = [uuid.uuid5(uuid.NAMESPACE_DNS, f"synthetic-user-{i}") for i in range(num_users)]
    for uid in user_ids:
        users[uid] = ExtractedUser(id=uid, is_active=True)

    session_counter = 0

    for u_idx, uid in enumerate(user_ids):
        # Create 2 sessions for each user
        for s_idx in range(2):
            session_counter += 1
            session_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"synthetic-session-{session_counter}")
            session_start = base_time + timedelta(hours=session_counter * 2)
            session_duration = samples_per_session * 0.2  # 0.2s interval (5 Hz)
            session_end = session_start + timedelta(seconds=session_duration)

            sessions[session_id] = ExtractedSession(
                id=session_id,
                user_id=uid,
                status="completed",
                started_at=session_start,
                ended_at=session_end,
                total_duration_seconds=session_duration,
                focused_seconds=session_duration * 0.7,
                distracted_seconds=session_duration * 0.3,
                away_seconds=0.0,
                focus_score=70.0,
                detector_version="v4",
                feature_schema_version="telemetry_v2",
                calibration_snapshot={
                    "baseline": {
                        "head_yaw": 2.0,
                        "head_pitch": -5.0,
                        "head_roll": 1.0,
                        "shoulder_z": -0.4,
                        "torso_aspect_ratio": 0.45,
                    }
                },
            )

            # Define 2 detection events for this session:
            # Event 1: looking_away (seconds 1.0 to 2.5)
            # Event 2: phone_use (seconds 2.0 to 3.5) -> overlapping with event 1!
            ev1_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"event-{session_counter}-1")
            ev1_start = session_start + timedelta(seconds=1.0)
            ev1_end = session_start + timedelta(seconds=2.5)
            ev1 = ExtractedDetectionEvent(
                id=ev1_id,
                session_id=session_id,
                event_type="looking_away",
                started_at=ev1_start,
                ended_at=ev1_end,
                duration_seconds=1.5,
                detector_version="v4",
            )
            detection_events.append(ev1)

            ev2_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"event-{session_counter}-2")
            ev2_start = session_start + timedelta(seconds=2.0)
            ev2_end = session_start + timedelta(seconds=3.5)
            ev2 = ExtractedDetectionEvent(
                id=ev2_id,
                session_id=session_id,
                event_type="phone_use",
                started_at=ev2_start,
                ended_at=ev2_end,
                duration_seconds=1.5,
                detector_version="v4",
            )
            detection_events.append(ev2)

            # User 0 session 0: Event 1 confirmed correct, Event 2 flagged false positive
            if u_idx == 0 and s_idx == 0:
                fb1 = ExtractedFeedback(
                    id=uuid.uuid5(uuid.NAMESPACE_DNS, f"feedback-{session_counter}-1"),
                    session_id=session_id,
                    detection_event_id=ev1_id,
                    feedback_type="correct_detection",
                    category="looking_away",
                    note="Confirmed looking away",
                    created_at=session_end + timedelta(minutes=1),
                )
                feedbacks.append(fb1)

                fb2 = ExtractedFeedback(
                    id=uuid.uuid5(uuid.NAMESPACE_DNS, f"feedback-{session_counter}-2"),
                    session_id=session_id,
                    detection_event_id=ev2_id,
                    feedback_type="false_positive",
                    category="phone_use",
                    note="I was just scratching my chin",
                    created_at=session_end + timedelta(minutes=2),
                )
                feedbacks.append(fb2)

                # Also session-level missed detection feedback
                fb_missed = ExtractedFeedback(
                    id=uuid.uuid5(uuid.NAMESPACE_DNS, f"feedback-{session_counter}-3"),
                    session_id=session_id,
                    detection_event_id=None,
                    feedback_type="missed_detection",
                    category="yawning",
                    note="I yawned twice and it was missed",
                    created_at=session_end + timedelta(minutes=3),
                )
                feedbacks.append(fb_missed)

                # And other note
                fb_other = ExtractedFeedback(
                    id=uuid.uuid5(uuid.NAMESPACE_DNS, f"feedback-{session_counter}-4"),
                    session_id=session_id,
                    detection_event_id=None,
                    feedback_type="other",
                    category=None,
                    note="Great session UI!",
                    created_at=session_end + timedelta(minutes=4),
                )
                feedbacks.append(fb_other)

            # Generate telemetry samples
            for frame_idx in range(samples_per_session):
                sample_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"sample-{session_counter}-{frame_idx}")
                sample_time = session_start + timedelta(seconds=frame_idx * 0.2)

                # Frame 0 to 2: calibration period
                is_calib = frame_idx < 3
                focus_state = "calibrating" if is_calib else "focused"

                # Check if sample is inside event intervals
                in_ev1 = ev1_start <= sample_time <= ev1_end
                in_ev2 = ev2_start <= sample_time <= ev2_end

                if in_ev1 or in_ev2:
                    focus_state = "distracted"

                # Simulate some missing data at frame 15 (e.g. user briefly looked down, face lost)
                face_present = not (frame_idx == 15)
                head_yaw = (18.5 if in_ev1 else 2.0) if face_present else None
                ear = (0.28 if not in_ev2 else 0.25) if face_present else None
                min_hand_dist = (0.08 if in_ev2 else 0.35) if face_present else None

                features_dict = {
                    "head_pitch_from_baseline": 0.5 if face_present else None,
                    "head_yaw_from_baseline": (16.5 if in_ev1 else 0.0) if face_present else None,
                    "head_roll_from_baseline": 0.1 if face_present else None,
                    "left_ear": ear,
                    "right_ear": ear,
                    "left_hand_cheek_distance": min_hand_dist,
                    "right_hand_cheek_distance": min_hand_dist,
                    "shoulder_z_delta": -0.02,
                    "torso_aspect_ratio": 0.46,
                    "torso_posture_delta": 0.02,
                    "head_yaw_rate": 1.2 if in_ev1 else 0.0,
                    "head_pitch_rate": 0.3,
                    "head_roll_rate": 0.1,
                    "shoulder_z_rate": 0.01,
                    "hand_cheek_distance_rate": 0.5 if in_ev2 else 0.0,
                    "looking_away": in_ev1,
                    "phone_use": in_ev2,
                    "yawning": False,
                    "eyes_closed": False,
                    "leaning_back": False,
                    "away_from_desk": False,
                    "calibration_complete": not is_calib,
                    "baseline": {
                        "head_yaw": 2.0,
                        "head_pitch": -5.0,
                        "head_roll": 1.0,
                        "shoulder_z": -0.4,
                        "torso_aspect_ratio": 0.45,
                    },
                    "tracker_states": {
                        "looking_away": {"active": in_ev1, "duration_sec": 1.0 if in_ev1 else 0.0, "persistence_met": in_ev1},
                        "phone_use": {"active": in_ev2, "duration_sec": 1.0 if in_ev2 else 0.0, "persistence_met": in_ev2},
                    },
                }

                telemetry_samples.append(
                    ExtractedTelemetrySample(
                        id=sample_id,
                        session_id=session_id,
                        sampled_at=sample_time,
                        frame_index=frame_idx,
                        detector_version="v4",
                        feature_schema_version="telemetry_v2",
                        head_pitch=-5.0 if face_present else None,
                        head_yaw=head_yaw,
                        head_roll=1.0 if face_present else None,
                        ear=ear,
                        mar=0.22 if face_present else None,
                        min_hand_cheek_distance=min_hand_dist,
                        shoulder_z=-0.42,
                        face_present=face_present,
                        pose_present=True,
                        hand_count=1 if in_ev2 else 0,
                        focus_state=focus_state,
                        features=features_dict,
                    )
                )

    return DatasetSources(
        users=users,
        sessions=sessions,
        telemetry_samples=telemetry_samples,
        detection_events=detection_events,
        feedbacks=feedbacks,
    )
