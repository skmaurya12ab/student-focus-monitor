"""Session state accounting module for tracking focus, distraction, and away durations."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Optional, Sequence

from app.detection.calibration import CalibrationBaseline
from app.detection.config import (
    ALERT_AWAY_FROM_DESK,
    DETECTOR_VERSION,
    FEATURE_SCHEMA_VERSION,
)


@dataclass
class SessionState:
    """
    Encapsulates all mutable state for a single study monitoring session.
    Guarantees strict isolation across multiple concurrent sessions.
    """

    session_id: str
    session_started_at: float = field(default_factory=time.time)
    session_ended_at: Optional[float] = None

    focused_seconds: float = 0.0
    distracted_seconds: float = 0.0
    away_seconds: float = 0.0
    distraction_count: int = 0
    frame_count: int = 0

    current_state: str = "calibrating"

    @staticmethod
    def state_from_alerts(active_alerts: Sequence[str]) -> str:
        """
        Determine session state according to active alerts:
        - If any distraction alert other than 'Away From Desk' is active -> 'distracted'
        - If 'Away From Desk' is active -> 'away'
        - Otherwise -> 'focused'
        """
        if any(alert != ALERT_AWAY_FROM_DESK for alert in active_alerts):
            return "distracted"

        if ALERT_AWAY_FROM_DESK in active_alerts:
            return "away"

        return "focused"

    def record_step(self, new_state: str, dt: float) -> None:
        """
        Advance duration accounting based on the elapsed time delta `dt`
        and the newly resolved state.
        """
        self.frame_count += 1
        self.current_state = new_state

        if dt <= 0:
            return

        if new_state == "focused":
            self.focused_seconds += dt
        elif new_state == "distracted":
            self.distracted_seconds += dt
        elif new_state == "away":
            self.away_seconds += dt

    def record_distraction_started(self) -> None:
        """Increment count of triggered distraction episodes."""
        self.distraction_count += 1

    def calculate_focus_score(self) -> float:
        """
        Calculate focus score as a percentage of total tracked time:
        focus_score = (focused_seconds / total_tracked) * 100.0
        """
        total_tracked = self.focused_seconds + self.distracted_seconds + self.away_seconds
        if total_tracked > 0:
            return float((self.focused_seconds / total_tracked) * 100.0)
        return 0.0

    def compute_summary(
        self,
        baseline: Optional[CalibrationBaseline] = None,
        now: Optional[float] = None,
    ) -> dict[str, Any]:
        """Produce the canonical end-of-session summary dictionary."""
        end_time = now if now is not None else time.time()
        self.session_ended_at = end_time
        duration = max(0.0, end_time - self.session_started_at)
        focus_score = self.calculate_focus_score()

        return {
            "session_id": self.session_id,
            "duration_seconds": round(duration, 2),
            "focused_seconds": round(self.focused_seconds, 2),
            "distracted_seconds": round(self.distracted_seconds, 2),
            "away_seconds": round(self.away_seconds, 2),
            "focus_score": round(focus_score, 2),
            "distraction_count": self.distraction_count,
            "detector_version": DETECTOR_VERSION,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "calibration": baseline.to_dict() if baseline else asdict(CalibrationBaseline()),
        }
