"""Session Feedback domain model."""
from datetime import datetime
from typing import TYPE_CHECKING, Optional
import uuid
from sqlalchemy import (
    String,
    Text,
    DateTime,
    ForeignKey,
    CheckConstraint,
    Index,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.db.models.study_session import StudySession
    from app.db.models.detection_event import DetectionEvent


class SessionFeedback(Base, UUIDPrimaryKeyMixin):
    """User feedback on distraction detection events (true positives, false positives, missed events)."""

    __tablename__ = "session_feedback"

    __table_args__ = (
        CheckConstraint(
            "feedback_type IN ('correct_detection', 'false_positive', 'missed_detection', 'other')",
            name="ck_session_feedback_type",
        ),
        Index("ix_session_feedback_session_event", "session_id", "detection_event_id"),
        Index(
            "uq_session_feedback_session_event",
            "session_id",
            "detection_event_id",
            unique=True,
            postgresql_where=text("detection_event_id IS NOT NULL"),
        ),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("study_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    detection_event_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("detection_events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    feedback_type: Mapped[str] = mapped_column(String(30), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # Relationships
    session: Mapped["StudySession"] = relationship("StudySession", back_populates="feedbacks")
    detection_event: Mapped[Optional["DetectionEvent"]] = relationship(
        "DetectionEvent",
        back_populates="feedbacks",
    )

    def __repr__(self) -> str:
        return f"<SessionFeedback id={self.id} session_id={self.session_id} type={self.feedback_type!r} cat={self.category!r}>"
