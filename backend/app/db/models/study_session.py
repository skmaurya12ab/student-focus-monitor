"""Study Session domain model."""
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional, Any, Dict
import uuid
from sqlalchemy import (
    String,
    Float,
    Numeric,
    DateTime,
    ForeignKey,
    CheckConstraint,
    Index,
    text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin, TimestampMixin, utc_now

if TYPE_CHECKING:
    from app.db.models.user import User
    from app.db.models.detection_event import DetectionEvent
    from app.db.models.telemetry_sample import TelemetrySample
    from app.db.models.session_feedback import SessionFeedback


class StudySession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Persisted study session entity representing completed or active study monitoring."""

    __tablename__ = "study_sessions"

    __table_args__ = (
        CheckConstraint("status IN ('active', 'completed', 'cancelled')", name="ck_study_sessions_status"),
        CheckConstraint("total_duration_seconds >= 0", name="ck_study_sessions_total_duration_non_negative"),
        CheckConstraint("focused_seconds >= 0", name="ck_study_sessions_focused_seconds_non_negative"),
        CheckConstraint("distracted_seconds >= 0", name="ck_study_sessions_distracted_seconds_non_negative"),
        CheckConstraint("away_seconds >= 0", name="ck_study_sessions_away_seconds_non_negative"),
        CheckConstraint(
            "focus_score IS NULL OR (focus_score >= 0 AND focus_score <= 100)",
            name="ck_study_sessions_focus_score_range",
        ),
        CheckConstraint("ended_at IS NULL OR ended_at >= started_at", name="ck_study_sessions_time_consistency"),
        Index("ix_study_sessions_user_started", "user_id", "started_at"),
        Index(
            "uq_study_sessions_user_active",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )


    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
        nullable=False,
        index=True,
    )

    # Duration accounting (in seconds)
    total_duration_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    focused_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    distracted_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    away_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    focus_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)

    # Detector & feature schema versions
    detector_version: Mapped[str] = mapped_column(String(20), default="v4", nullable=False)
    feature_schema_version: Mapped[str] = mapped_column(String(30), default="telemetry_v1", nullable=False)

    # Structured personal calibration baseline snapshot
    calibration_snapshot: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="study_sessions")
    detection_events: Mapped[List["DetectionEvent"]] = relationship(
        "DetectionEvent",
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    telemetry_samples: Mapped[List["TelemetrySample"]] = relationship(
        "TelemetrySample",
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    feedbacks: Mapped[List["SessionFeedback"]] = relationship(
        "SessionFeedback",
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<StudySession id={self.id} user_id={self.user_id} status={self.status!r}>"
