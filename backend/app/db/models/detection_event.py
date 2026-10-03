"""Detection Event domain model."""
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional, Any, Dict
import uuid
from sqlalchemy import (
    String,
    Float,
    DateTime,
    ForeignKey,
    CheckConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.db.models.study_session import StudySession
    from app.db.models.session_feedback import SessionFeedback


class DetectionEvent(Base, UUIDPrimaryKeyMixin):
    """Discrete distraction event emitted by the detection engine."""

    __tablename__ = "detection_events"

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('looking_away', 'phone_use', 'yawning', 'drowsy', 'leaning_back', 'away_from_desk')",
            name="ck_detection_events_type",
        ),
        CheckConstraint("duration_seconds IS NULL OR duration_seconds >= 0", name="ck_detection_events_duration_non_negative"),
        CheckConstraint("ended_at IS NULL OR ended_at >= started_at", name="ck_detection_events_time_consistency"),
        Index("ix_detection_events_session_started", "session_id", "started_at"),
        Index("ix_detection_events_session_type", "session_id", "event_type"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("study_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    detector_version: Mapped[str] = mapped_column(String(20), default="v4", nullable=False)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # Relationships
    session: Mapped["StudySession"] = relationship("StudySession", back_populates="detection_events")
    feedbacks: Mapped[List["SessionFeedback"]] = relationship(
        "SessionFeedback",
        back_populates="detection_event",
    )

    def __repr__(self) -> str:
        return f"<DetectionEvent id={self.id} session_id={self.session_id} type={self.event_type!r}>"
