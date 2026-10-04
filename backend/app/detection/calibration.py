"""Personal calibration module for establishing user-specific baseline posture and head orientation."""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from typing import Any, Optional

import numpy as np


@dataclass
class CalibrationBaseline:
    """Stores median baseline values recorded during the personal calibration phase."""

    shoulder_z: Optional[float] = None
    head_yaw: Optional[float] = None
    head_pitch: Optional[float] = None
    head_roll: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CalibrationBuffer:
    """
    Collects natural baseline samples at session start to personalize thresholds.

    Calibration computes user-specific median baselines for shoulder depth
    and head orientation, ensuring detection rules evaluate relative deviations
    rather than brittle absolute measurements.
    """

    def __init__(
        self,
        required_seconds: float = 10.0,
        min_samples: int = 30,
    ) -> None:
        self.required_seconds = float(required_seconds)
        self.min_samples = int(min_samples)
        self.started_at: Optional[float] = None
        self.shoulder_z: deque[float] = deque(maxlen=500)
        self.head_yaw: deque[float] = deque(maxlen=500)
        self.head_pitch: deque[float] = deque(maxlen=500)
        self.head_roll: deque[float] = deque(maxlen=500)
        self.complete: bool = False
        self.baseline: CalibrationBaseline = CalibrationBaseline()

    def start(self, now: float) -> None:
        """Mark the start timestamp of calibration."""
        if self.started_at is None:
            self.started_at = now

    def reset(self) -> None:
        """Reset calibration collection state to recalibrate."""
        self.started_at = None
        self.shoulder_z.clear()
        self.head_yaw.clear()
        self.head_pitch.clear()
        self.head_roll.clear()
        self.complete = False
        self.baseline = CalibrationBaseline()

    def add(
        self,
        now: float,
        shoulder_z: Optional[float],
        head_yaw: Optional[float],
        head_pitch: Optional[float],
        head_roll: Optional[float],
        required_seconds: Optional[float] = None,
        min_samples: Optional[int] = None,
    ) -> bool:
        """
        Record a sample frame. Computes baseline when elapsed time and sample count criteria are met.
        Returns True once calibration is complete.
        """
        req_sec = self.required_seconds if required_seconds is None else required_seconds
        min_samp = self.min_samples if min_samples is None else min_samples

        self.start(now)

        if shoulder_z is not None and np.isfinite(shoulder_z):
            self.shoulder_z.append(float(shoulder_z))

        if head_yaw is not None and np.isfinite(head_yaw):
            self.head_yaw.append(float(head_yaw))

        if head_pitch is not None and np.isfinite(head_pitch):
            self.head_pitch.append(float(head_pitch))

        if head_roll is not None and np.isfinite(head_roll):
            self.head_roll.append(float(head_roll))

        elapsed = now - (self.started_at or now)

        if elapsed >= req_sec and len(self.head_yaw) >= min_samp:
            shoulder_baseline = (
                float(np.median(self.shoulder_z))
                if len(self.shoulder_z) > 0
                else None
            )
            self.baseline = CalibrationBaseline(
                shoulder_z=shoulder_baseline,
                head_yaw=float(np.median(self.head_yaw)),
                head_pitch=float(np.median(self.head_pitch))
                if self.head_pitch
                else None,
                head_roll=float(np.median(self.head_roll))
                if self.head_roll
                else None,
            )
            self.complete = True

        return self.complete

    def compute_relative_deltas(
        self,
        head_yaw: Optional[float],
        head_pitch: Optional[float],
        head_roll: Optional[float],
        shoulder_z: Optional[float],
    ) -> tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
        """
        Calculate deviations from the calibrated baseline.
        Returns (yaw_delta, pitch_delta, roll_delta, shoulder_z_delta).
        """
        if not self.complete:
            return None, None, None, None

        yaw_delta = (
            float(head_yaw - self.baseline.head_yaw)
            if head_yaw is not None and self.baseline.head_yaw is not None
            else None
        )
        pitch_delta = (
            float(head_pitch - self.baseline.head_pitch)
            if head_pitch is not None and self.baseline.head_pitch is not None
            else None
        )
        roll_delta = (
            float(head_roll - self.baseline.head_roll)
            if head_roll is not None and self.baseline.head_roll is not None
            else None
        )
        shoulder_delta = (
            float(shoulder_z - self.baseline.shoulder_z)
            if shoulder_z is not None and self.baseline.shoulder_z is not None
            else None
        )

        return yaw_delta, pitch_delta, roll_delta, shoulder_delta
