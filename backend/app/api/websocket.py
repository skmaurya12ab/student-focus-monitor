"""WebSocket API endpoints for live camera frame transport."""
import json
import logging
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, WebSocket, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import get_async_session
from app.db.models.user import User
from app.db.models.study_session import StudySession
from app.services.auth_service import AuthService
from app.services.session_service import SessionService
from app.services.live_transport_service import (
    live_transport_manager,
    TARGET_FPS,
    MAX_FRAME_SIZE_BYTES,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["Live Transport"])


def _validate_origin(websocket: WebSocket) -> bool:
    """Validate that the WebSocket Origin header is in allowed origins."""
    origin = websocket.headers.get("origin")
    if not origin:
        # For non-browser automated tests or scripts, allow if no Origin is present in dev
        return settings.APP_ENV == "development"
    # Normalize origin without trailing slash
    norm_origin = origin.rstrip("/")
    allowed = {o.rstrip("/") for o in settings.cors_origins}
    return norm_origin in allowed


async def _resolve_websocket_user(websocket: WebSocket, db: AsyncSession) -> Optional[User]:
    """Extract and validate authentication token from cookies or Authorization header."""
    token: Optional[str] = None
    if "sfm_session" in websocket.cookies:
        token = websocket.cookies.get("sfm_session")
    elif "authorization" in websocket.headers:
        auth_hdr = websocket.headers.get("authorization", "")
        if auth_hdr.lower().startswith("bearer "):
            token = auth_hdr[7:].strip()

    if not token:
        return None

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None

    try:
        user_uuid = uuid.UUID(payload["sub"])
    except (ValueError, TypeError):
        return None

    user = await AuthService.get_user_by_id(db, user_uuid)
    if not user or not user.is_active:
        return None

    return user


@router.websocket("/sessions/{session_id}")
async def websocket_session_live_transport(
    websocket: WebSocket,
    session_id: str,
    db: AsyncSession = Depends(get_async_session),
) -> None:
    """WebSocket endpoint for streaming camera frames during an active study session.

    Protocol:
    1. Origin validation: rejects untrusted Origin with code 1008.
    2. Authentication: resolves user from sfm_session cookie or Bearer header; rejects with 1008.
    3. Session validation: verifies session exists, belongs to user, and is 'active'; rejects with 1008.
    4. Concurrency: enforces at most one active live transport per study session; rejects duplicate with 1008.
    5. Handshake: accepts connection and emits ready message.
    6. Streaming: receives binary frames, enforces size/rate limits, discards bytes, sends periodic acks.
    7. Clean closure: releases resources upon disconnect.
    """
    # 1. Validate Origin header
    if not _validate_origin(websocket):
        logger.warning(
            "Rejected WebSocket connection: untrusted origin '%s'",
            websocket.headers.get("origin"),
        )
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Untrusted Origin")
        return

    # Parse session ID
    try:
        session_uuid = uuid.UUID(session_id)
    except (ValueError, TypeError):
        logger.warning("Rejected WebSocket connection: invalid session UUID '%s'", session_id)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid session ID")
        return

    # 2. Authenticate user
    user = await _resolve_websocket_user(websocket, db)
    if not user:
        logger.warning("Rejected unauthenticated WebSocket connection for session %s", session_id)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized")
        return

    # 3. Validate study session existence and ownership (IDOR protection)
    study_session = await SessionService.get_session_by_id(db, session_uuid, user.id)
    if not study_session:
        logger.warning(
            "WebSocket rejected: session %s not found or not owned by user %s",
            session_uuid,
            user.id,
        )
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Session not found or forbidden",
        )
        return

    # 4. Validate study session active status
    if study_session.status != "active":
        logger.warning(
            "WebSocket rejected: session %s has status '%s' (must be 'active')",
            session_uuid,
            study_session.status,
        )
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason=f"Session is not active (status: {study_session.status})",
        )
        return

    # 5. Enforce single live transport connection per active study session
    registered = live_transport_manager.register_connection(session_uuid, user.id, websocket)
    if not registered:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Another live connection is already active for this session",
        )
        return

    # 6. Accept connection and emit ready payload
    await websocket.accept()

    # Phase 8/9: Load user settings and configure detection runtime
    from app.services.detection_runtime_service import detection_runtime_manager
    from app.services.settings_service import SettingsService

    user_settings = await SettingsService.get_user_settings(db, user.id)
    detector_config = SettingsService.build_detector_config(user_settings)

    runtime = await detection_runtime_manager.get_or_create_runtime(
        session_uuid, user.id, config=detector_config
    )
    runtime.set_result_callback(websocket.send_json)

    await websocket.send_json({
        "type": "ready",
        "session_id": str(session_uuid),
        "target_fps": TARGET_FPS,
        "max_frame_size_bytes": MAX_FRAME_SIZE_BYTES,
        "settings": {
            "sound_alerts_enabled": user_settings.sound_alerts_enabled,
            "banner_alerts_enabled": user_settings.banner_alerts_enabled,
            "delays": {
                "looking_away": user_settings.looking_away_delay_seconds,
                "phone_use": user_settings.phone_use_delay_seconds,
                "yawning": user_settings.yawning_delay_seconds,
                "drowsy": user_settings.drowsy_delay_seconds,
                "leaning_back": user_settings.leaning_back_delay_seconds,
                "away_from_desk": user_settings.away_from_desk_delay_seconds,
            },
        },
    })

    try:
        while True:
            message = await websocket.receive()

            if message["type"] == "websocket.disconnect":
                break

            # Handle Binary Frame Payload
            if "bytes" in message and message["bytes"]:
                frame_data = message["bytes"]
                result = live_transport_manager.handle_frame(session_uuid, frame_data)

                # Send periodic transport acknowledgement (every 10 accepted frames)
                if result.get("status") == "accepted":
                    frames_count = result.get("frames_received", 0)
                    if frames_count % 10 == 0:
                        await websocket.send_json({
                            "type": "ack",
                            "session_id": str(session_uuid),
                            "frames_received": frames_count,
                            "bytes_received": result.get("bytes_received", 0),
                        })
                elif result.get("status") == "dropped" and result.get("reason") == "oversized":
                    await websocket.send_json({
                        "type": "warning",
                        "message": "Frame dropped: payload exceeds size limit",
                    })

            # Handle JSON Control Messages
            elif "text" in message and message["text"]:
                try:
                    payload = json.loads(message["text"])
                    msg_type = payload.get("type")

                    if msg_type == "ping":
                        await websocket.send_json({
                            "type": "pong",
                            "session_id": str(session_uuid),
                            "timestamp": payload.get("timestamp"),
                        })
                    elif msg_type == "stop":
                        # Client requested graceful stop of live transport
                        await websocket.send_json({
                            "type": "closed",
                            "session_id": str(session_uuid),
                            "reason": "Client stopped live monitoring",
                        })
                        await websocket.close(code=status.WS_1000_NORMAL_CLOSURE, reason="Client stopped")
                        break
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Unknown message type '{msg_type}'",
                        })
                except json.JSONDecodeError:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Malformed JSON control message",
                    })

    except Exception as e:
        logger.info("WebSocket connection for session %s closed: %s", session_uuid, e)
    finally:
        active_rt = detection_runtime_manager.get_runtime(session_uuid)
        if active_rt:
            active_rt.set_result_callback(None)
            try:
                await active_rt.flush_telemetry()
            except Exception as e:
                logger.debug("Failed to flush telemetry on websocket disconnect: %s", e)
        live_transport_manager.unregister_connection(session_uuid, websocket, reason="Clean disconnect")
