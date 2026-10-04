"""Settings Service managing persistence and synchronization of user configuration."""
from __future__ import annotations

import logging
from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.db.models.user_settings import UserSettings
from app.detection.config import (
    ALERT_AWAY_FROM_DESK,
    ALERT_DROWSY,
    ALERT_LEANING_BACK,
    ALERT_LOOKING_AWAY,
    ALERT_PHONE_USE,
    ALERT_YAWNING,
    DetectorConfig,
)
from app.schemas.settings import UserSettingsUpdateRequest

logger = logging.getLogger(__name__)


class SettingsService:
    """Service handling authoritative user settings retrieval and updates."""

    @staticmethod
    async def get_user_settings(db: AsyncSession, user_id: uuid.UUID) -> UserSettings:
        """Retrieve existing UserSettings or create default settings if none exist."""
        stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        result = await db.execute(stmt)
        settings = result.scalars().first()

        if not settings:
            logger.info("Initializing default UserSettings for user %s", user_id)
            settings = UserSettings(user_id=user_id)
            db.add(settings)
            await db.flush()
            await db.refresh(settings)

        return settings

    @classmethod
    async def update_user_settings(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        update_data: UserSettingsUpdateRequest,
    ) -> UserSettings:
        """Update configurable persistence delays and notification toggles."""
        settings = await cls.get_user_settings(db, user_id)

        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            if value is not None:
                setattr(settings, key, value)

        settings.updated_at = utc_now()
        await db.flush()
        await db.refresh(settings)

        # Synchronize active detection runtime(s) for this user if live monitoring is active
        try:
            from app.services.detection_runtime_service import detection_runtime_manager
            detector_config = cls.build_detector_config(settings)
            detection_runtime_manager.update_user_runtimes(user_id, detector_config)
            logger.info("Synchronized updated alert thresholds for user %s to active runtimes", user_id)
        except Exception as e:
            logger.warning("Could not synchronize runtime settings for user %s: %s", user_id, e)

        return settings

    @staticmethod
    def build_detector_config(settings: UserSettings) -> DetectorConfig:
        """Construct a DetectorConfig reflecting the user's configured persistence delays."""
        return DetectorConfig(
            alert_delays_sec={
                ALERT_LOOKING_AWAY: float(settings.looking_away_delay_seconds),
                ALERT_PHONE_USE: float(settings.phone_use_delay_seconds),
                ALERT_YAWNING: float(settings.yawning_delay_seconds),
                ALERT_DROWSY: float(settings.drowsy_delay_seconds),
                ALERT_LEANING_BACK: float(settings.leaning_back_delay_seconds),
                ALERT_AWAY_FROM_DESK: float(settings.away_from_desk_delay_seconds),
            }
        )
