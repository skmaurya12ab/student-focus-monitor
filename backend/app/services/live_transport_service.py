"""Live Transport Service for ephemeral camera frame transmission over WebSocket.

Phase 7 Transport Layer:
- Manages active live transport connections bound to Phase 6 active study sessions.
- Enforces strict single-connection policy per active study session.
- Enforces frame size boundaries (default <= 1MB) and rate limits (default <= 15 FPS).
- Strictly ephemeral: frames are discarded immediately after transport accounting.
- Never writes image bytes to disk, database, or logs.
- Seam for future Phase 8 detector integration (detector_hook is None in Phase 7).
"""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import time
from typing import Any, Callable, Dict, List, Optional
import uuid
from fastapi import WebSocket

logger = logging.getLogger(__name__)

# Transport constants
TARGET_FPS = 5
MAX_ALLOWED_FPS = 15
MAX_FRAME_SIZE_BYTES = 1024 * 1024  # 1 MB


@dataclass
class LiveTransportMetrics:
    """In-memory ephemeral metrics for a live WebSocket connection."""

    session_id: uuid.UUID
    user_id: uuid.UUID
    connected_at: datetime
    frames_received: int = 0
    frames_dropped: int = 0
    bytes_received: int = 0
    last_frame_at: Optional[datetime] = None
    close_reason: Optional[str] = None


class LiveTransportManager:
    """Registry and manager for active live WebSocket transport sessions."""

    def __init__(
        self,
        max_frame_size_bytes: int = MAX_FRAME_SIZE_BYTES,
        max_fps: int = MAX_ALLOWED_FPS,
        detector_hook: Optional[Callable[[uuid.UUID, bytes], None]] = None,
    ) -> None:
        self.max_frame_size_bytes = max_frame_size_bytes
        self.max_fps = max_fps
        # Phase 8 seam: In Phase 7, detector_hook is strictly None
        self.detector_hook = detector_hook

        self._active_connections: Dict[uuid.UUID, WebSocket] = {}
        self._metrics: Dict[uuid.UUID, LiveTransportMetrics] = {}
        self._frame_timestamps: Dict[uuid.UUID, List[float]] = {}
        self._lock = asyncio.Lock()

    def is_session_connected(self, session_id: uuid.UUID) -> bool:
        """Check if a live transport WebSocket is currently connected for this session."""
        return session_id in self._active_connections

    def get_metrics(self, session_id: uuid.UUID) -> Optional[LiveTransportMetrics]:
        """Retrieve current in-memory metrics for a session."""
        return self._metrics.get(session_id)

    def register_connection(
        self,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        websocket: WebSocket,
    ) -> bool:
        """Register a new live transport connection.

        Enforces the invariant: at most ONE active live transport connection
        per active study session. Returns False if a connection already exists.
        """
        if session_id in self._active_connections:
            logger.warning(
                "Rejected duplicate live connection attempt for session %s (user %s)",
                session_id,
                user_id,
            )
            return False

        self._active_connections[session_id] = websocket
        self._metrics[session_id] = LiveTransportMetrics(
            session_id=session_id,
            user_id=user_id,
            connected_at=datetime.now(timezone.utc),
        )
        self._frame_timestamps[session_id] = []
        logger.info(
            "Live transport connection registered for session %s (user %s)",
            session_id,
            user_id,
        )
        return True

    def unregister_connection(
        self,
        session_id: uuid.UUID,
        websocket: Optional[WebSocket] = None,
        reason: Optional[str] = None,
    ) -> None:
        """Unregister a connection upon close or disconnect."""
        existing = self._active_connections.get(session_id)
        if existing and (websocket is None or existing == websocket):
            self._active_connections.pop(session_id, None)
            self._frame_timestamps.pop(session_id, None)
            metrics = self._metrics.get(session_id)
            if metrics:
                metrics.close_reason = reason
            logger.info(
                "Live transport connection unregistered for session %s (reason: %s)",
                session_id,
                reason or "clean close",
            )

    def handle_frame(self, session_id: uuid.UUID, frame_bytes: bytes) -> Dict[str, Any]:
        """Validate and handle an incoming camera frame payload.

        Enforces size limits and frame rate pacing. Immediately discards
        frame data without persistent storage.
        """
        metrics = self._metrics.get(session_id)
        if not metrics:
            return {"status": "rejected", "reason": "unregistered_session"}

        now = time.monotonic()

        # 1. Enforce payload size limit
        if len(frame_bytes) > self.max_frame_size_bytes:
            metrics.frames_dropped += 1
            logger.warning(
                "Frame dropped for session %s: size %d bytes exceeds limit %d bytes",
                session_id,
                len(frame_bytes),
                self.max_frame_size_bytes,
            )
            return {
                "status": "dropped",
                "reason": "oversized",
                "size_bytes": len(frame_bytes),
                "max_size_bytes": self.max_frame_size_bytes,
            }

        # 2. Enforce frame rate boundary (sliding 1-second window)
        timestamps = self._frame_timestamps.setdefault(session_id, [])
        # Prune timestamps older than 1 second
        cutoff = now - 1.0
        while timestamps and timestamps[0] < cutoff:
            timestamps.pop(0)

        if len(timestamps) >= self.max_fps:
            metrics.frames_dropped += 1
            logger.debug(
                "Frame rate throttle for session %s: %d fps exceeds max %d fps",
                session_id,
                len(timestamps),
                self.max_fps,
            )
            return {
                "status": "dropped",
                "reason": "rate_limited",
                "current_fps": len(timestamps),
                "max_fps": self.max_fps,
            }

        timestamps.append(now)

        # 3. Accept frame and update in-memory accounting
        metrics.frames_received += 1
        metrics.bytes_received += len(frame_bytes)
        metrics.last_frame_at = datetime.now(timezone.utc)

        # 4. Phase 8 Seam (NOT IMPLEMENTED IN PHASE 7)
        if self.detector_hook is not None:
            try:
                self.detector_hook(session_id, frame_bytes)
            except Exception as e:
                logger.error("Error in detector hook for session %s: %s", session_id, e)

        # 5. Strictly discard frame bytes: no disk, no DB, no logs
        return {
            "status": "accepted",
            "frames_received": metrics.frames_received,
            "bytes_received": metrics.bytes_received,
        }

    async def close_session_transport(
        self,
        session_id: uuid.UUID,
        code: int = 1000,
        reason: str = "Study session completed",
    ) -> None:
        """Proactively close any active WebSocket connection for a given session."""
        ws = self._active_connections.get(session_id)
        if ws:
            try:
                await ws.close(code=code, reason=reason)
            except Exception as e:
                logger.debug("Error closing websocket for session %s: %s", session_id, e)
            finally:
                self.unregister_connection(session_id, ws, reason=reason)


# Global singleton instance for live transport management
live_transport_manager = LiveTransportManager()

# Phase 8: Connect LiveTransportManager detector_hook to DetectionRuntimeManager
from app.services.detection_runtime_service import detection_runtime_manager
live_transport_manager.detector_hook = detection_runtime_manager.submit_frame
