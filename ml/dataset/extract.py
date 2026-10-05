"""Data extraction module for querying PostgreSQL sessions, events, telemetry, and feedback."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Sequence
import uuid

# Ensure backend directory is in sys.path when executed directly or imported
backend_path = Path(__file__).resolve().parents[2] / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from sqlalchemy import Engine, text
from app.db.session import get_sync_engine
from ml.dataset.config import DatasetConfig


@dataclass
class ExtractedUser:
    """Internal user representation for group splitting (excluded from model feature rows)."""

    id: uuid.UUID
    is_active: bool


@dataclass
class ExtractedSession:
    """Study session boundary and accounting entity."""

    id: uuid.UUID
    user_id: uuid.UUID
    status: str
    started_at: datetime
    ended_at: Optional[datetime]
    total_duration_seconds: float
    focused_seconds: float
    distracted_seconds: float
    away_seconds: float
    focus_score: Optional[float]
    detector_version: str
    feature_schema_version: str
    calibration_snapshot: Optional[dict[str, Any]] = None


@dataclass
class ExtractedTelemetrySample:
    """Numerical movement and posture telemetry sample."""

    id: uuid.UUID
    session_id: uuid.UUID
    sampled_at: datetime
    frame_index: Optional[int]
    detector_version: str
    feature_schema_version: str
    head_pitch: Optional[float]
    head_yaw: Optional[float]
    head_roll: Optional[float]
    ear: Optional[float]
    mar: Optional[float]
    min_hand_cheek_distance: Optional[float]
    shoulder_z: Optional[float]
    face_present: Optional[bool]
    pose_present: Optional[bool]
    hand_count: Optional[int]
    focus_state: Optional[str]
    features: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractedDetectionEvent:
    """Discrete distraction event emitted by the detection engine."""

    id: uuid.UUID
    session_id: uuid.UUID
    event_type: str
    started_at: datetime
    ended_at: Optional[datetime]
    duration_seconds: Optional[float]
    detector_version: str
    metadata_json: Optional[dict[str, Any]] = None


@dataclass
class ExtractedFeedback:
    """User feedback on detection events or overall session."""

    id: uuid.UUID
    session_id: uuid.UUID
    detection_event_id: Optional[uuid.UUID]
    feedback_type: str
    category: Optional[str]
    note: Optional[str]
    created_at: datetime


@dataclass
class DatasetSources:
    """Container for all raw extracted records from PostgreSQL."""

    users: dict[uuid.UUID, ExtractedUser]
    sessions: dict[uuid.UUID, ExtractedSession]
    telemetry_samples: list[ExtractedTelemetrySample]
    detection_events: list[ExtractedDetectionEvent]
    feedbacks: list[ExtractedFeedback]


def to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure datetime is UTC-aware."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def extract_from_database(
    engine: Optional[Engine] = None,
    config: Optional[DatasetConfig] = None,
) -> DatasetSources:
    """
    Read-only extraction of users, sessions, telemetry, events, and feedback from PostgreSQL.
    Guarantees no modifications are made to the database.
    """
    if engine is None:
        engine = get_sync_engine()
    cfg = config or DatasetConfig()

    users: dict[uuid.UUID, ExtractedUser] = {}
    sessions: dict[uuid.UUID, ExtractedSession] = {}
    telemetry_samples: list[ExtractedTelemetrySample] = []
    detection_events: list[ExtractedDetectionEvent] = []
    feedbacks: list[ExtractedFeedback] = []

    with engine.connect() as conn:
        # 1. Extract Users
        user_rows = conn.execute(
            text("SELECT id, is_active FROM users")
        ).mappings().fetchall()
        for row in user_rows:
            uid = row["id"] if isinstance(row["id"], uuid.UUID) else uuid.UUID(str(row["id"]))
            users[uid] = ExtractedUser(id=uid, is_active=bool(row["is_active"]))

        # 2. Extract Study Sessions
        session_query = "SELECT * FROM study_sessions WHERE 1=1"
        params: dict[str, Any] = {}
        if cfg.completed_only:
            session_query += " AND status = 'completed'"
        if cfg.start_date:
            session_query += " AND started_at >= :start_date"
            params["start_date"] = cfg.start_date
        if cfg.end_date:
            session_query += " AND started_at <= :end_date"
            params["end_date"] = cfg.end_date
        session_query += " ORDER BY started_at ASC"

        session_rows = conn.execute(text(session_query), params).mappings().fetchall()
        for row in session_rows:
            sid = row["id"] if isinstance(row["id"], uuid.UUID) else uuid.UUID(str(row["id"]))
            uid = row["user_id"] if isinstance(row["user_id"], uuid.UUID) else uuid.UUID(str(row["user_id"]))
            sessions[sid] = ExtractedSession(
                id=sid,
                user_id=uid,
                status=str(row["status"]),
                started_at=to_utc(row["started_at"]),
                ended_at=to_utc(row["ended_at"]),
                total_duration_seconds=float(row["total_duration_seconds"] or 0.0),
                focused_seconds=float(row["focused_seconds"] or 0.0),
                distracted_seconds=float(row["distracted_seconds"] or 0.0),
                away_seconds=float(row["away_seconds"] or 0.0),
                focus_score=float(row["focus_score"]) if row["focus_score"] is not None else None,
                detector_version=str(row["detector_version"] or "v4"),
                feature_schema_version=str(row["feature_schema_version"] or "telemetry_v2"),
                calibration_snapshot=row.get("calibration_snapshot") or {},
            )

        if not sessions:
            return DatasetSources(
                users=users,
                sessions=sessions,
                telemetry_samples=telemetry_samples,
                detection_events=detection_events,
                feedbacks=feedbacks,
            )

        session_ids = list(sessions.keys())

        # 3. Extract Telemetry Samples for eligible sessions
        # Using parameterized IN query with type-safe UUIDs
        telemetry_rows = conn.execute(
            text(
                """
                SELECT id, session_id, sampled_at, frame_index, detector_version,
                       feature_schema_version, head_pitch, head_yaw, head_roll,
                       ear, mar, min_hand_cheek_distance, shoulder_z,
                       face_present, pose_present, hand_count, focus_state, features
                FROM telemetry_samples
                WHERE session_id = ANY(:sids)
                ORDER BY session_id, sampled_at ASC
                """
            ),
            {"sids": session_ids},
        ).mappings().fetchall()

        for row in telemetry_rows:
            tid = row["id"] if isinstance(row["id"], uuid.UUID) else uuid.UUID(str(row["id"]))
            sid = row["session_id"] if isinstance(row["session_id"], uuid.UUID) else uuid.UUID(str(row["session_id"]))
            telemetry_samples.append(
                ExtractedTelemetrySample(
                    id=tid,
                    session_id=sid,
                    sampled_at=to_utc(row["sampled_at"]),
                    frame_index=int(row["frame_index"]) if row["frame_index"] is not None else None,
                    detector_version=str(row["detector_version"] or "v4"),
                    feature_schema_version=str(row["feature_schema_version"] or "telemetry_v2"),
                    head_pitch=float(row["head_pitch"]) if row["head_pitch"] is not None else None,
                    head_yaw=float(row["head_yaw"]) if row["head_yaw"] is not None else None,
                    head_roll=float(row["head_roll"]) if row["head_roll"] is not None else None,
                    ear=float(row["ear"]) if row["ear"] is not None else None,
                    mar=float(row["mar"]) if row["mar"] is not None else None,
                    min_hand_cheek_distance=(
                        float(row["min_hand_cheek_distance"])
                        if row["min_hand_cheek_distance"] is not None
                        else None
                    ),
                    shoulder_z=float(row["shoulder_z"]) if row["shoulder_z"] is not None else None,
                    face_present=bool(row["face_present"]) if row["face_present"] is not None else None,
                    pose_present=bool(row["pose_present"]) if row["pose_present"] is not None else None,
                    hand_count=int(row["hand_count"]) if row["hand_count"] is not None else None,
                    focus_state=str(row["focus_state"]) if row["focus_state"] is not None else None,
                    features=row.get("features") or {},
                )
            )

        # 4. Extract Detection Events
        event_rows = conn.execute(
            text(
                """
                SELECT id, session_id, event_type, started_at, ended_at,
                       duration_seconds, detector_version, metadata_json
                FROM detection_events
                WHERE session_id = ANY(:sids)
                ORDER BY session_id, started_at ASC
                """
            ),
            {"sids": session_ids},
        ).mappings().fetchall()

        for row in event_rows:
            eid = row["id"] if isinstance(row["id"], uuid.UUID) else uuid.UUID(str(row["id"]))
            sid = row["session_id"] if isinstance(row["session_id"], uuid.UUID) else uuid.UUID(str(row["session_id"]))
            detection_events.append(
                ExtractedDetectionEvent(
                    id=eid,
                    session_id=sid,
                    event_type=str(row["event_type"]),
                    started_at=to_utc(row["started_at"]),
                    ended_at=to_utc(row["ended_at"]),
                    duration_seconds=float(row["duration_seconds"]) if row["duration_seconds"] is not None else 0.0,
                    detector_version=str(row["detector_version"] or "v4"),
                    metadata_json=row.get("metadata_json") or {},
                )
            )

        # 5. Extract Session Feedback
        feedback_rows = conn.execute(
            text(
                """
                SELECT id, session_id, detection_event_id, feedback_type,
                       category, note, created_at
                FROM session_feedback
                WHERE session_id = ANY(:sids)
                ORDER BY session_id, created_at ASC
                """
            ),
            {"sids": session_ids},
        ).mappings().fetchall()

        for row in feedback_rows:
            fbid = row["id"] if isinstance(row["id"], uuid.UUID) else uuid.UUID(str(row["id"]))
            sid = row["session_id"] if isinstance(row["session_id"], uuid.UUID) else uuid.UUID(str(row["session_id"]))
            deid = (
                row["detection_event_id"]
                if row["detection_event_id"] is None or isinstance(row["detection_event_id"], uuid.UUID)
                else uuid.UUID(str(row["detection_event_id"]))
            )
            feedbacks.append(
                ExtractedFeedback(
                    id=fbid,
                    session_id=sid,
                    detection_event_id=deid,
                    feedback_type=str(row["feedback_type"]),
                    category=str(row["category"]) if row["category"] is not None else None,
                    note=str(row["note"]) if row["note"] is not None else None,
                    created_at=to_utc(row["created_at"]),
                )
            )

    return DatasetSources(
        users=users,
        sessions=sessions,
        telemetry_samples=telemetry_samples,
        detection_events=detection_events,
        feedbacks=feedbacks,
    )
