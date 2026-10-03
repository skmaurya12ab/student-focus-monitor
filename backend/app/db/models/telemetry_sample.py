"""Telemetry Sample domain model."""
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Any, Dict
import uuid
from sqlalchemy import (
    String,
    Float,
    Integer,
    Boolean,
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


class TelemetrySample(Base, UUIDPrimaryKeyMixin):
    """Numerical movement and posture telemetry sample emitted periodically during monitoring."""

    __tablename__ = "telemetry_samples"

    __table_args__ = (
        CheckConstraint("frame_index IS NULL OR frame_index >= 0", name="ck_telemetry_samples_frame_index"),
        Index("ix_telemetry_samples_session_sampled", "session_id", "sampled_at"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("study_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sampled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    frame_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    detector_version: Mapped[str] = mapped_column(String(20), default="v4", nullable=False)
    feature_schema_version: Mapped[str] = mapped_column(String(30), default="telemetry_v1", nullable=False)

    # Core explicit numerical features
    head_pitch: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    head_yaw: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    head_roll: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ear: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mar: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    min_hand_cheek_distance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    shoulder_z: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    face_present: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    pose_present: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    hand_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    focus_state: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Extensible structured numerical payload (deltas, rates, tracking quality, rule outputs)
    features: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    # Relationships
    session: Mapped["StudySession"] = relationship("StudySession", back_populates="telemetry_samples")

    def __repr__(self) -> str:
        return f"<TelemetrySample id={self.id} session_id={self.session_id} state={self.focus_state!r}>"
