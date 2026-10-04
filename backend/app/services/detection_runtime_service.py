"""Detection Runtime Service for real-time camera monitoring in Phase 8.

Integrates:
- Real MediaPipe Tasks vision runtime
- Modular rule-based detector (StudentDistractionDetector)
- Asynchronous bounded queue with latest-frame-priority backpressure
- Monotonically increasing video timestamp safety
- DetectionEvent persistence in PostgreSQL upon state changes (not every frame)
- Finalization of active events and session metrics on session stop
- Ephemeral live detection result streaming over WebSocket
- Strictly NO media storage (zero frames written to disk, db, or logs)
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import logging
import time
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple
import uuid

import cv2
import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.detection_event import DetectionEvent
from app.db.models.study_session import StudySession
from app.db.session import AsyncSessionLocal
from app.detection.config import (
    ALERT_NAME_TO_CATEGORY,
    CATEGORY_TO_ALERT_NAME,
    DETECTOR_VERSION,
    FEATURE_SCHEMA_VERSION,
    DetectorConfig,
)
from app.detection.detector import StudentDistractionDetector
from app.detection.mediapipe_runtime import MediaPipeRuntime
from app.detection.trackers import MultiCategoryTracker

logger = logging.getLogger(__name__)


class SessionDetectionRuntime:
    """Isolated, session-scoped detection runtime instance.

    Guarantees:
    - Session-specific MediaPipe models, calibration, and persistence trackers
    - Non-blocking frame processing executed in a worker thread
    - Bounded queue (maxsize=1) dropping stale frames during backpressure
    - Discrete PostgreSQL event logging for distraction starts/ends
    - Ephemeral WebSocket result streaming without media persistence
    """

    def __init__(
        self,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        config: Optional[DetectorConfig] = None,
        db_session_factory: Optional[async_sessionmaker[AsyncSession]] = None,
    ) -> None:
        self.session_id: uuid.UUID = session_id
        self.user_id: uuid.UUID = user_id
        self.config: DetectorConfig = config or DetectorConfig()
        self.db_session_factory = db_session_factory or AsyncSessionLocal

        # Phase 2 Modular detector instance
        self.detector: StudentDistractionDetector = StudentDistractionDetector(
            config=self.config,
            session_id=str(session_id),
        )

        # Lazy-initialized MediaPipe runtime
        self.mediapipe_runtime: Optional[MediaPipeRuntime] = None

        # Bounded frame queue (1 frame max for real-time freshness)
        self.frame_queue: asyncio.Queue[Tuple[bytes, float]] = asyncio.Queue(maxsize=1)

        # Active PostgreSQL DetectionEvent IDs: alert_name -> DetectionEvent.id
        self.active_db_events: Dict[str, uuid.UUID] = {}
        self.event_start_times: Dict[str, float] = {}

        # WebSocket stream callback
        self.result_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None

        # Lifecycle and metrics
        self.is_running: bool = True
        self.worker_task: Optional[asyncio.Task[None]] = None
        self.frames_processed: int = 0
        self.frames_dropped_detector: int = 0
        self.error_count: int = 0
        self.last_result: Optional[Dict[str, Any]] = None

    def start(self) -> None:
        """Start the background worker task for frame processing."""
        if self.worker_task is None or self.worker_task.done():
            self.is_running = True
            self.worker_task = asyncio.create_task(self._worker_loop())
            logger.info("Started detection worker for session %s (user %s)", self.session_id, self.user_id)

    def set_result_callback(
        self,
        callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]],
    ) -> None:
        """Register or clear the WebSocket result delivery callback."""
        self.result_callback = callback

    def update_config(self, config: DetectorConfig) -> None:
        """Update detection configuration and dynamically refresh tracker persistence delays."""
        self.config = config
        self.detector.config = config
        self.detector.trackers = MultiCategoryTracker(config)
        logger.info(
            "Updated detection configuration and tracker persistence delays for session %s (user %s)",
            self.session_id,
            self.user_id,
        )

    def submit_frame(self, frame_bytes: bytes, timestamp: float) -> bool:
        """Submit a frame for processing.

        Enforces latest-frame priority: if queue is full, the stale frame is dropped.
        """
        if not self.is_running:
            return False

        if self.frame_queue.full():
            try:
                self.frame_queue.get_nowait()
                self.frames_dropped_detector += 1
            except asyncio.QueueEmpty:
                pass

        try:
            self.frame_queue.put_nowait((frame_bytes, timestamp))
            return True
        except asyncio.QueueFull:
            self.frames_dropped_detector += 1
            return False

    async def _worker_loop(self) -> None:
        """Background async loop processing frames through MediaPipe and detector."""
        while self.is_running:
            try:
                frame_bytes, timestamp = await self.frame_queue.get()
            except asyncio.CancelledError:
                break

            try:
                # Execute CPU-bound detection in thread pool to prevent blocking asyncio loop
                raw_result = await asyncio.to_thread(
                    self._process_frame_sync,
                    frame_bytes,
                    timestamp,
                )

                if raw_result is not None:
                    self.frames_processed += 1
                    # 1. Update database event lifecycle (starts / ends)
                    await self._handle_event_persistence(raw_result, timestamp)

                    # 2. Build structured detection result payload
                    result_payload = self._build_detection_result_payload(raw_result, timestamp)
                    self.last_result = result_payload

                    # 3. Stream result to active WebSocket if callback registered
                    if self.result_callback is not None:
                        try:
                            await self.result_callback(result_payload)
                        except Exception as e:
                            logger.debug("Failed sending detection result to websocket: %s", e)

            except Exception as e:
                self.error_count += 1
                logger.error("Error in detection processing for session %s: %s", self.session_id, e)
                if self.result_callback is not None:
                    try:
                        await self.result_callback({
                            "type": "detection_result",
                            "session_id": str(self.session_id),
                            "timestamp": timestamp,
                            "state": "detector_error",
                            "error": str(e),
                            "active_detections": [],
                            "metrics": {
                                "focus_score": round(self.detector.session_state.calculate_focus_score(), 2) if self.detector else 0.0,
                                "focused_seconds": round(self.detector.focused_seconds, 2) if self.detector else 0.0,
                                "distracted_seconds": round(self.detector.distracted_seconds, 2) if self.detector else 0.0,
                                "away_seconds": round(self.detector.away_seconds, 2) if self.detector else 0.0,
                                "distraction_count": self.detector.distraction_count if self.detector else 0,
                            },
                            "calibration": {
                                "complete": False,
                                "samples_collected": 0,
                                "required_samples": self.config.minimum_calibration_samples,
                                "baseline": None,
                            },
                        })
                    except Exception:
                        pass
            finally:
                self.frame_queue.task_done()

    def _process_frame_sync(
        self,
        frame_bytes: bytes,
        timestamp: float,
    ) -> Optional[Dict[str, Any]]:
        """Synchronous frame processing: decode JPEG, run MediaPipe, evaluate rules."""
        if not frame_bytes:
            return None

        # 1. Decode JPEG binary payload using OpenCV
        nparr = np.frombuffer(frame_bytes, np.uint8)
        bgr_frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if bgr_frame is None:
            logger.debug("Failed to decode JPEG frame for session %s", self.session_id)
            return None

        h, w = bgr_frame.shape[:2]
        rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)

        # 2. Lazy initialize MediaPipe runtime if needed
        if self.mediapipe_runtime is None:
            self.mediapipe_runtime = MediaPipeRuntime()

        timestamp_ms = int(timestamp * 1000)

        # 3. Execute MediaPipe detection
        face_res, hand_res, pose_res = self.mediapipe_runtime.detect(
            rgb_frame,
            timestamp_ms,
        )

        # 4. Evaluate detector orchestration (features, calibration, rules, persistence)
        result = self.detector.process_results(
            face_result=face_res,
            hand_result=hand_res,
            pose_result=pose_res,
            width=w,
            height=h,
            timestamp=timestamp,
        )

        # 5. Return result dictionary (frames are immediately discarded without storage)
        return result

    async def _handle_event_persistence(
        self,
        raw_result: Dict[str, Any],
        timestamp: float,
    ) -> None:
        """Persist newly triggered distraction events and finalize ended events."""
        newly_started = raw_result.get("newly_started", [])
        newly_ended = raw_result.get("newly_ended", [])

        if not newly_started and not newly_ended:
            return

        now_dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)

        try:
            async with self.db_session_factory() as db:
                # 1. Handle newly started distraction events
                for alert_name in newly_started:
                    category = ALERT_NAME_TO_CATEGORY.get(alert_name, alert_name.lower().replace(" ", "_"))
                    if alert_name not in self.active_db_events:
                        event_id = uuid.uuid4()
                        db_event = DetectionEvent(
                            id=event_id,
                            session_id=self.session_id,
                            event_type=category,
                            started_at=now_dt,
                            ended_at=None,
                            duration_seconds=None,
                            detector_version=DETECTOR_VERSION,
                            metadata_json={
                                "trigger_delay_sec": self.config.get_alert_delay(alert_name),
                                "thresholds": {
                                    "yaw_threshold_deg": self.config.yaw_threshold_deg,
                                    "ear_threshold": self.config.ear_threshold,
                                    "mar_threshold": self.config.mar_threshold,
                                    "hand_near_cheek_dist": self.config.hand_near_cheek_dist,
                                    "lean_back_z_delta": self.config.lean_back_z_delta,
                                },
                            },
                        )
                        db.add(db_event)
                        self.active_db_events[alert_name] = event_id
                        self.event_start_times[alert_name] = timestamp
                        logger.info("Persisted new distraction event '%s' (%s) for session %s", category, event_id, self.session_id)

                # 2. Handle ended distraction events
                for ended_item in newly_ended:
                    alert_name = ended_item["name"]
                    event_id = self.active_db_events.pop(alert_name, None)
                    self.event_start_times.pop(alert_name, None)
                    if event_id:
                        stmt = select(DetectionEvent).where(DetectionEvent.id == event_id)
                        res = await db.execute(stmt)
                        evt = res.scalars().first()
                        if evt:
                            evt.ended_at = now_dt
                            evt.duration_seconds = ended_item.get("duration_sec") or max(
                                0.0, (now_dt - evt.started_at).total_seconds()
                            )
                            logger.info("Finalized distraction event '%s' (%s) duration: %.2fs", evt.event_type, event_id, evt.duration_seconds)

                await db.commit()
        except Exception as e:
            logger.error("Error persisting detection events for session %s: %s", self.session_id, e)

    def _build_detection_result_payload(
        self,
        raw_result: Dict[str, Any],
        timestamp: float,
    ) -> Dict[str, Any]:
        """Format the authoritative detection_result message for WebSocket clients."""
        active_alerts = raw_result.get("active_alerts", [])
        active_detections = []
        for name in active_alerts:
            cat = ALERT_NAME_TO_CATEGORY.get(name, name.lower().replace(" ", "_"))
            start_t = self.event_start_times.get(name, timestamp)
            duration = max(0.0, timestamp - start_t)
            active_detections.append({
                "category": cat,
                "alert_name": name,
                "started_at": start_t,
                "duration_seconds": round(duration, 2),
            })

        focus_score = round(self.detector.session_state.calculate_focus_score(), 2)

        baseline_dict = None
        if self.detector.calibration.complete:
            baseline_dict = self.detector.calibration.baseline.to_dict()

        return {
            "type": "detection_result",
            "session_id": str(self.session_id),
            "timestamp": timestamp,
            "state": raw_result.get("state", "calibrating"),
            "active_detections": active_detections,
            "metrics": {
                "focus_score": focus_score,
                "focused_seconds": round(self.detector.focused_seconds, 2),
                "distracted_seconds": round(self.detector.distracted_seconds, 2),
                "away_seconds": round(self.detector.away_seconds, 2),
                "distraction_count": self.detector.distraction_count,
            },
            "calibration": {
                "complete": self.detector.calibration.complete,
                "samples_collected": max(len(self.detector.calibration.head_yaw), len(self.detector.calibration.shoulder_z)),
                "required_samples": self.config.minimum_calibration_samples,
                "baseline": baseline_dict,
            },
        }

    async def stop(self, db: Optional[AsyncSession] = None) -> Dict[str, Any]:
        """Stop detection runtime following strict finalization order:
        1. Stop accepting new frame submissions (is_running = False)
        2. Allow accepted detector work in queue to finalize
        3. Finalize active detection events in PostgreSQL
        4. Calculate final session metrics from detector session state
        5. Close MediaPipe vision tasks runtime
        """
        # Step 1: stop accepting new frame submissions
        self.is_running = False

        # Step 2: allow accepted detector work to finalize
        if self.worker_task and not self.worker_task.done():
            task = self.worker_task
            try:
                # Wait briefly (up to 500ms) for frame queue to empty and in-flight work to complete
                await asyncio.wait_for(self.frame_queue.join(), timeout=0.5)
            except (asyncio.TimeoutError, Exception):
                pass
            finally:
                if not task.done():
                    try:
                        current_loop = asyncio.get_running_loop()
                    except RuntimeError:
                        current_loop = None

                    if current_loop and task.get_loop() is current_loop:
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                    else:
                        task_loop = task.get_loop()
                        if not task_loop.is_closed():
                            task_loop.call_soon_threadsafe(task.cancel)

        now = time.time()
        now_dt = datetime.fromtimestamp(now, tz=timezone.utc)

        # 1. Finalize any remaining open active events in PostgreSQL
        if self.active_db_events:
            async def _finalize_open_events(session: AsyncSession) -> None:
                for alert_name, event_id in list(self.active_db_events.items()):
                    stmt = select(DetectionEvent).where(DetectionEvent.id == event_id)
                    res = await session.execute(stmt)
                    evt = res.scalars().first()
                    if evt and evt.ended_at is None:
                        evt.ended_at = now_dt
                        evt.duration_seconds = max(0.0, (now_dt - evt.started_at).total_seconds())
                await session.commit()

            try:
                if db is not None:
                    await _finalize_open_events(db)
                else:
                    async with self.db_session_factory() as session:
                        await _finalize_open_events(session)
            except Exception as e:
                logger.error("Error finalizing open detection events for session %s: %s", self.session_id, e)
            finally:
                self.active_db_events.clear()

        # 2. Compute final summary from detector session state
        summary = self.detector.finish_session(now=now)

        # 3. Release MediaPipe resources
        if self.mediapipe_runtime is not None:
            try:
                self.mediapipe_runtime.close()
            except Exception as e:
                logger.debug("Error closing mediapipe runtime for session %s: %s", self.session_id, e)
            finally:
                self.mediapipe_runtime = None

        logger.info(
            "Detection runtime stopped for session %s: frames=%d, dropped=%d, focus_score=%.2f%%",
            self.session_id,
            self.frames_processed,
            self.frames_dropped_detector,
            summary.get("focus_score", 0.0),
        )
        return summary


class DetectionRuntimeManager:
    """Singleton registry and manager for active session detection runtimes."""

    def __init__(self) -> None:
        self._runtimes: Dict[uuid.UUID, SessionDetectionRuntime] = {}
        self._lock = asyncio.Lock()

    async def get_or_create_runtime(
        self,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        config: Optional[DetectorConfig] = None,
        db_session_factory: Optional[async_sessionmaker[AsyncSession]] = None,
    ) -> SessionDetectionRuntime:
        """Retrieve existing detection runtime or initialize a new one for an active session."""
        async with self._lock:
            runtime = self._runtimes.get(session_id)
            if runtime is None:
                runtime = SessionDetectionRuntime(
                    session_id=session_id,
                    user_id=user_id,
                    config=config,
                    db_session_factory=db_session_factory,
                )
                runtime.start()
                self._runtimes[session_id] = runtime
                logger.info("Initialized new detection runtime for session %s", session_id)
            elif config is not None:
                runtime.update_config(config)
            return runtime

    def update_user_runtimes(self, user_id: uuid.UUID, config: DetectorConfig) -> None:
        """Synchronize updated detector configuration across any active runtimes for this user."""
        for runtime in self._runtimes.values():
            if runtime.user_id == user_id:
                runtime.update_config(config)

    def get_runtime(self, session_id: uuid.UUID) -> Optional[SessionDetectionRuntime]:
        """Get the active detection runtime for a session if one exists."""
        return self._runtimes.get(session_id)

    def submit_frame(self, session_id: uuid.UUID, frame_bytes: bytes) -> bool:
        """Hook callback invoked by LiveTransportManager to submit frames to detector."""
        runtime = self._runtimes.get(session_id)
        if runtime is None:
            return False
        return runtime.submit_frame(frame_bytes, time.time())

    async def stop_session_detection(
        self,
        session_id: uuid.UUID,
        db: Optional[AsyncSession] = None,
    ) -> Optional[Dict[str, Any]]:
        """Stop detection runtime for a session and return its final metrics."""
        async with self._lock:
            runtime = self._runtimes.pop(session_id, None)

        if runtime is not None:
            return await runtime.stop(db)
        return None

    async def close_all(self) -> None:
        """Shut down all active detection runtimes."""
        async with self._lock:
            runtimes = list(self._runtimes.values())
            self._runtimes.clear()

        for runtime in runtimes:
            await runtime.stop()


# Global singleton instance
detection_runtime_manager = DetectionRuntimeManager()
