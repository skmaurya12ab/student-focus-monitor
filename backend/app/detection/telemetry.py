"""Numerical telemetry generation and storage sink module. Strictly zero media persistence."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional, Protocol

from app.detection.calibration import CalibrationBaseline
from app.detection.config import (
    DETECTOR_VERSION,
    FEATURE_SCHEMA_VERSION,
    DetectorConfig,
)
from app.detection.features import FeatureSnapshot, utc_iso
from app.detection.session_state import SessionState


def build_telemetry_payload(
    session_id: str,
    features: FeatureSnapshot,
    session_state: SessionState,
    calibration_complete: bool,
    baseline: CalibrationBaseline,
    config: DetectorConfig,
) -> dict[str, Any]:
    """
    Construct a structured telemetry record preserving the exact v4 schema concepts.
    Strictly contains numerical metrics, timestamps, and detection flags — NO raw media.
    """
    payload = features.to_dict()
    payload.update(
        {
            "session_id": session_id,
            "detector_version": DETECTOR_VERSION,
            "frame_index": session_state.frame_count,
            "focused_seconds": round(session_state.focused_seconds, 2),
            "distracted_seconds": round(session_state.distracted_seconds, 2),
            "away_seconds": round(session_state.away_seconds, 2),
            "distraction_count": session_state.distraction_count,
            "calibration_complete": calibration_complete,
            "baseline": baseline.to_dict(),
            "thresholds": {
                "yaw_threshold_deg": config.yaw_threshold_deg,
                "ear_threshold": config.ear_threshold,
                "mar_threshold": config.mar_threshold,
                "hand_near_cheek_dist": config.hand_near_cheek_dist,
                "lean_back_z_delta": config.lean_back_z_delta,
            },
            "alert_delays_sec": config.alert_delays_sec,
        }
    )
    return payload


class TelemetrySink(Protocol):
    """Protocol for telemetry destinations."""

    def emit_telemetry(self, payload: dict[str, Any]) -> None:
        ...

    def emit_event(self, payload: dict[str, Any]) -> None:
        ...

    def finish_session(self, summary: dict[str, Any]) -> None:
        ...


class InMemoryTelemetrySink:
    """In-memory telemetry sink for testing and stream-based ingestion without filesystem I/O."""

    def __init__(self) -> None:
        self.telemetry_records: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self.summary: Optional[dict[str, Any]] = None

    def emit_telemetry(self, payload: dict[str, Any]) -> None:
        self.telemetry_records.append(payload)

    def emit_event(self, payload: dict[str, Any]) -> None:
        self.events.append(payload)

    def finish_session(self, summary: dict[str, Any]) -> None:
        self.summary = summary


class JsonlWriter:
    """Thread-safe append-only JSON Lines file writer."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, payload: dict[str, Any]) -> None:
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")


class FileTelemetrySink:
    """Local JSON Lines file sink compatible with v4 session storage."""

    def __init__(self, session_id: str, base_dir: Path, config: DetectorConfig) -> None:
        self.session_id = session_id
        self.base_dir = base_dir

        self.telemetry_writer = JsonlWriter(
            base_dir / "telemetry" / f"{session_id}.jsonl"
        )
        self.event_writer = JsonlWriter(
            base_dir / "events" / f"{session_id}.jsonl"
        )
        self.session_meta_path = base_dir / "sessions" / f"{session_id}.json"

        self.session_meta: dict[str, Any] = {
            "session_id": session_id,
            "detector_version": DETECTOR_VERSION,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "started_at": utc_iso(),
            "privacy": {
                "video_recorded": False,
                "images_recorded": False,
                "feature_telemetry_recorded": True,
            },
            "config": asdict(config),
        }
        self._write_meta()

    def _write_meta(self) -> None:
        self.session_meta_path.parent.mkdir(parents=True, exist_ok=True)
        self.session_meta_path.write_text(
            json.dumps(self.session_meta, indent=2),
            encoding="utf-8",
        )

    def emit_telemetry(self, payload: dict[str, Any]) -> None:
        self.telemetry_writer.write(payload)

    def emit_event(self, payload: dict[str, Any]) -> None:
        self.event_writer.write(payload)

    def finish_session(self, summary: dict[str, Any]) -> None:
        self.session_meta.update(
            {
                "ended_at": utc_iso(),
                "summary": summary,
            }
        )
        self._write_meta()
