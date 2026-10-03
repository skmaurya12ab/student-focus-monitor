"""User Settings domain model."""
from typing import TYPE_CHECKING
import uuid
from sqlalchemy import String, Boolean, Float, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.user import User


class UserSettings(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """User configuration, alert persistence delays, and notification preferences."""

    __tablename__ = "user_settings"

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_settings_user_id"),
        CheckConstraint("looking_away_delay_seconds >= 0", name="ck_user_settings_looking_away_delay"),
        CheckConstraint("phone_use_delay_seconds >= 0", name="ck_user_settings_phone_use_delay"),
        CheckConstraint("yawning_delay_seconds >= 0", name="ck_user_settings_yawning_delay"),
        CheckConstraint("drowsy_delay_seconds >= 0", name="ck_user_settings_drowsy_delay"),
        CheckConstraint("leaning_back_delay_seconds >= 0", name="ck_user_settings_leaning_back_delay"),
        CheckConstraint("away_from_desk_delay_seconds >= 0", name="ck_user_settings_away_from_desk_delay"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Configurable alert persistence delays (in seconds) for the 6 canonical categories
    looking_away_delay_seconds: Mapped[float] = mapped_column(Float, default=10.0, nullable=False)
    phone_use_delay_seconds: Mapped[float] = mapped_column(Float, default=6.0, nullable=False)
    yawning_delay_seconds: Mapped[float] = mapped_column(Float, default=2.0, nullable=False)
    drowsy_delay_seconds: Mapped[float] = mapped_column(Float, default=4.0, nullable=False)
    leaning_back_delay_seconds: Mapped[float] = mapped_column(Float, default=8.0, nullable=False)
    away_from_desk_delay_seconds: Mapped[float] = mapped_column(Float, default=10.0, nullable=False)

    # Notification controls
    sound_alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    banner_alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    session_end_summary_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Webcam preferences
    camera_device: Mapped[str] = mapped_column(
        String(100),
        default="Integrated Camera - 720p",
        nullable=False,
    )
    preview_quality: Mapped[str] = mapped_column(
        String(50),
        default="High · 30 FPS",
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="settings")

    def __repr__(self) -> str:
        return f"<UserSettings id={self.id} user_id={self.user_id}>"
