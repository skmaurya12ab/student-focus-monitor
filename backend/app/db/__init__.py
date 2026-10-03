"""Database package (session management, engine, base metadata, and models)."""
from app.db.base import Base, metadata
from app.db.session import (
    async_engine,
    AsyncSessionLocal,
    get_async_session,
    get_sync_engine,
    get_async_database_url,
    get_sync_database_url,
)
from app.db.models import (
    User,
    AuthIdentity,
    UserSettings,
    StudySession,
    DetectionEvent,
    TelemetrySample,
    SessionFeedback,
)

__all__ = [
    "Base",
    "metadata",
    "async_engine",
    "AsyncSessionLocal",
    "get_async_session",
    "get_sync_engine",
    "get_async_database_url",
    "get_sync_database_url",
    "User",
    "AuthIdentity",
    "UserSettings",
    "StudySession",
    "DetectionEvent",
    "TelemetrySample",
    "SessionFeedback",
]
