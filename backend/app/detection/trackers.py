"""Persistence tracking module for managing condition activation delays and event durations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from app.detection.config import ALERT_NAMES, DetectorConfig


@dataclass
class TrackerResult:
    """State transition and duration result from a persistence tracker update."""

    active: bool
    just_started: bool
    just_ended: bool
    duration_sec: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "active": self.active,
            "just_started": self.just_started,
            "just_ended": self.just_ended,
            "duration_sec": self.duration_sec,
        }

    # Dict-like access for 100% backward compatibility with v4
    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


class PersistenceTracker:
    """
    Tracks a binary condition over time to ensure it sustains for a required
    persistence delay before triggering an active distraction alert.
    """

    def __init__(self, delay: float) -> None:
        self.delay: float = float(delay)
        self.condition_started_at: Optional[float] = None
        self.alert_started_at: Optional[float] = None

    @property
    def is_active(self) -> bool:
        """True if the alert is currently active."""
        return self.alert_started_at is not None

    def reset(self) -> None:
        """Reset condition tracking and active alert state."""
        self.condition_started_at = None
        self.alert_started_at = None

    def update(
        self,
        condition_is_true: bool,
        now: float,
    ) -> TrackerResult:
        """
        Advance tracker state by one time step `now`.

        - If condition turns false: clears condition and alert, flags `just_ended`
          and returns ended duration if alert was previously active.
        - If condition turns true: records start time. Once elapsed time >= delay,
          activates alert, flags `just_started`, and begins tracking active duration.
        """
        just_started = False
        just_ended = False
        ended_duration: Optional[float] = None

        if not condition_is_true:
            if self.alert_started_at is not None:
                ended_duration = max(0.0, now - self.alert_started_at)
                just_ended = True

            self.condition_started_at = None
            self.alert_started_at = None

            return TrackerResult(
                active=False,
                just_started=False,
                just_ended=just_ended,
                duration_sec=ended_duration,
            )

        if self.condition_started_at is None:
            self.condition_started_at = now

        if self.alert_started_at is None:
            sustained_for = now - self.condition_started_at
            if sustained_for >= self.delay:
                self.alert_started_at = now
                just_started = True

        duration: Optional[float] = None
        if self.alert_started_at is not None:
            duration = max(0.0, now - self.alert_started_at)

        return TrackerResult(
            active=self.alert_started_at is not None,
            just_started=just_started,
            just_ended=False,
            duration_sec=duration,
        )


class MultiCategoryTracker:
    """Orchestrates independent persistence trackers for all alert categories."""

    def __init__(self, config: DetectorConfig) -> None:
        self.trackers: dict[str, PersistenceTracker] = {
            name: PersistenceTracker(config.get_alert_delay(name))
            for name in ALERT_NAMES
        }

    def reset(self) -> None:
        """Reset all trackers."""
        for tracker in self.trackers.values():
            tracker.reset()

    def update(
        self,
        conditions: Mapping[str, bool],
        now: float,
    ) -> tuple[dict[str, TrackerResult], list[str]]:
        """
        Update all trackers with their respective conditions.
        Returns a mapping of TrackerResult per category and the list of active alert names.
        """
        results: dict[str, TrackerResult] = {}
        active_alerts: list[str] = []

        for name, tracker in self.trackers.items():
            condition_state = bool(conditions.get(name, False))
            res = tracker.update(condition_state, now)
            results[name] = res
            if res.active:
                active_alerts.append(name)

        return results, active_alerts
