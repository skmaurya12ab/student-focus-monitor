"""High-level detection engine orchestrator composing features, calibration, rules, tracking, and telemetry."""

from __future__ import annotations

import time
import uuid
from typing import Any, Optional, Sequence

from app.detection.calibration import CalibrationBuffer
from app.detection.config import (
    ALERT_NAMES,
    DetectorConfig,
)
from app.detection.events import (
    create_alert_ended_event,
    create_alert_started_event,
)
from app.detection.features import (
    FeatureSnapshot,
    extract_features_from_landmarks,
    utc_iso,
)
from app.detection.rules import evaluate_rules
from app.detection.session_state import SessionState
from app.detection.telemetry import (
    InMemoryTelemetrySink,
    TelemetrySink,
    build_telemetry_payload,
)
from app.detection.trackers import MultiCategoryTracker


class StudentDistractionDetector:
    """
    Core rule-based distraction detection engine.

    Strictly decoupled from UI, audio, database, and network protocols.
    Composes modular sub-systems for feature extraction, calibration,
    condition evaluation, persistence tracking, session duration accounting,
    and telemetry logging.
    """

    ALERT_NAMES: tuple[str, ...] = ALERT_NAMES

    def __init__(
        self,
        config: Optional[DetectorConfig] = None,
        session_id: Optional[str] = None,
        telemetry_sink: Optional[TelemetrySink] = None,
    ) -> None:
        self.config: DetectorConfig = config or DetectorConfig()
        self.session_id: str = session_id or uuid.uuid4().hex

        # Modular components
        self.session_state: SessionState = SessionState(session_id=self.session_id)
        self.calibration: CalibrationBuffer = CalibrationBuffer(
            required_seconds=self.config.calibration_seconds,
            min_samples=self.config.minimum_calibration_samples,
        )
        self.trackers: MultiCategoryTracker = MultiCategoryTracker(self.config)
        self.telemetry_sink: TelemetrySink = telemetry_sink or InMemoryTelemetrySink()

        self.previous_features: Optional[FeatureSnapshot] = None
        self.last_telemetry_time: Optional[float] = None

    @property
    def focused_seconds(self) -> float:
        return self.session_state.focused_seconds

    @property
    def distracted_seconds(self) -> float:
        return self.session_state.distracted_seconds

    @property
    def away_seconds(self) -> float:
        return self.session_state.away_seconds

    @property
    def distraction_count(self) -> int:
        return self.session_state.distraction_count

    @property
    def frame_count(self) -> int:
        return self.session_state.frame_count

    def reset_calibration(self) -> None:
        """Reset the calibration buffer to recalculate baselines."""
        self.calibration.reset()

    def process_features(
        self,
        features: FeatureSnapshot,
        timestamp: Optional[float] = None,
    ) -> dict[str, Any]:
        """
        Evaluate an already-extracted feature snapshot through calibration,
        rules, persistence tracking, session duration updates, and telemetry.
        """
        now = timestamp if timestamp is not None else features.timestamp
        features.timestamp = now

        # Calibration stage
        if not self.calibration.complete:
            self.calibration.add(
                now=now,
                shoulder_z=features.shoulder_z,
                head_yaw=features.head_yaw,
                head_pitch=features.head_pitch,
                head_roll=features.head_roll,
                torso_aspect_ratio=features.torso_aspect_ratio,
                required_seconds=self.config.calibration_seconds,
                min_samples=self.config.minimum_calibration_samples,
            )

            features.active_alerts = []
            features.state = "calibrating"

            dt = (now - self.previous_features.timestamp) if self.previous_features else 0.0
            self.session_state.record_step("calibrating", dt)

            self.previous_features = features
            self._maybe_emit_telemetry(features)
            return self._build_state_payload(features)

        # Recompute baseline deltas if baseline just became available
        if features.head_yaw_from_baseline is None and self.calibration.complete:
            yd, pd, rd, sd = self.calibration.compute_relative_deltas(
                features.head_yaw,
                features.head_pitch,
                features.head_roll,
                features.shoulder_z,
            )
            features.head_yaw_from_baseline = yd
            features.head_pitch_from_baseline = pd
            features.head_roll_from_baseline = rd
            features.shoulder_z_delta = sd
            features.torso_posture_delta = self.calibration.compute_posture_delta(
                features.torso_aspect_ratio
            )

        # 1. Rule evaluation
        conditions = evaluate_rules(features, self.config)

        # 2. Persistence tracking
        tracker_results, active_alerts = self.trackers.update(conditions, now)

        # 3. Update feature snapshot condition flags
        features.looking_away = conditions["Looking Away"]
        features.phone_use = conditions["Phone Use"]
        features.yawning = conditions["Yawning"]
        features.eyes_closed = conditions["Drowsy/Eyes Closed"]
        features.leaning_back = conditions["Leaning Back"]
        features.away_from_desk = conditions["Away From Desk"]

        features.active_alerts = active_alerts
        new_state = self.session_state.state_from_alerts(active_alerts)
        features.state = new_state

        # 4. Event generation
        for name, res in tracker_results.items():
            if res.just_started:
                self.session_state.record_distraction_started()
                evt = create_alert_started_event(
                    session_id=self.session_id,
                    event_type=name,
                    now=now,
                    config=self.config,
                    features=features,
                )
                self.telemetry_sink.emit_event(evt.to_dict())

            if res.just_ended:
                evt = create_alert_ended_event(
                    session_id=self.session_id,
                    event_type=name,
                    now=now,
                    duration_sec=res.duration_sec,
                    config=self.config,
                )
                self.telemetry_sink.emit_event(evt.to_dict())

        # 5. Session state duration accounting
        dt = (now - self.previous_features.timestamp) if self.previous_features else 0.0
        self.session_state.record_step(new_state, dt)

        self.previous_features = features
        self._maybe_emit_telemetry(features)
        return self._build_state_payload(features, tracker_results=tracker_results)

    def process_results(
        self,
        face_result: Any,
        hand_result: Any,
        pose_result: Any,
        width: int,
        height: int,
        timestamp: Optional[float] = None,
    ) -> dict[str, Any]:
        """
        Process one frame of MediaPipe Tasks detection results.
        Extracts features and delegates to process_features.
        """
        now = timestamp if timestamp is not None else time.time()

        face_landmarks = (
            face_result.face_landmarks[0]
            if getattr(face_result, "face_landmarks", None)
            else None
        )
        hand_landmarks_list = (
            hand_result.hand_landmarks
            if getattr(hand_result, "hand_landmarks", None)
            else None
        )
        pose_landmarks = (
            pose_result.pose_landmarks[0]
            if getattr(pose_result, "pose_landmarks", None)
            else None
        )

        features = extract_features_from_landmarks(
            face_landmarks=face_landmarks,
            hand_landmarks_list=hand_landmarks_list,
            pose_landmarks=pose_landmarks,
            width=width,
            height=height,
            now=now,
            baseline=self.calibration.baseline if self.calibration.complete else None,
            previous_snapshot=self.previous_features,
        )

        return self.process_features(features, timestamp=now)

    def _maybe_emit_telemetry(self, features: FeatureSnapshot) -> None:
        """Sample and emit numerical telemetry at the configured sampling interval."""
        now = features.timestamp

        if (
            self.last_telemetry_time is not None
            and (now - self.last_telemetry_time) < self.config.telemetry_interval_sec
        ):
            return

        self.last_telemetry_time = now
        payload = build_telemetry_payload(
            session_id=self.session_id,
            features=features,
            session_state=self.session_state,
            calibration_complete=self.calibration.complete,
            baseline=self.calibration.baseline,
            config=self.config,
        )
        self.telemetry_sink.emit_telemetry(payload)

    def _build_state_payload(
        self,
        features: FeatureSnapshot,
        tracker_results: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Build the structured update payload returned to callers per frame."""
        newly_started = [name for name, r in tracker_results.items() if getattr(r, "just_started", False)] if tracker_results else []
        newly_ended = [
            {"name": name, "duration_sec": getattr(r, "duration_sec", None)}
            for name, r in tracker_results.items()
            if getattr(r, "just_ended", False)
        ] if tracker_results else []

        return {
            "type": "session_update",
            "session_id": self.session_id,
            "timestamp": features.timestamp,
            "timestamp_iso": utc_iso(features.timestamp),
            "state": features.state,
            "focused_seconds": round(self.session_state.focused_seconds, 2),
            "distracted_seconds": round(self.session_state.distracted_seconds, 2),
            "away_seconds": round(self.session_state.away_seconds, 2),
            "distraction_count": self.session_state.distraction_count,
            "active_alerts": features.active_alerts,
            "calibration_complete": self.calibration.complete,
            "newly_started": newly_started,
            "newly_ended": newly_ended,
            "features": features.to_dict(),
        }

    def finish_session(self, now: Optional[float] = None) -> dict[str, Any]:
        """Finalize the active session and emit summary metrics."""
        summary = self.session_state.compute_summary(
            baseline=self.calibration.baseline,
            now=now,
        )
        self.telemetry_sink.finish_session(summary)
        return summary
