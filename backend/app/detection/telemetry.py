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


PROHIBITED_MEDIA_SUBSTRINGS = (
    "image",
    "frame_bytes",
    "video",
    "audio",
    "jpeg",
    "png",
    "raw_buffer",
    "screenshot",
    "camera",
    "webcam",
    "raw_frame",
)


def build_telemetry_payload(
    session_id: str,
    features: FeatureSnapshot,
    session_state: SessionState,
    calibration_complete: bool,
    baseline: Optional[CalibrationBaseline],
    config: DetectorConfig,
    tracker_results: Optional[dict[str, Any]] = None,
    frame_index: Optional[int] = None,
) -> dict[str, Any]:
    """
    Construct a structured telemetry record preserving schema concepts.
    Strictly contains numerical metrics, timestamps, and detection flags — NO raw media.
    """
    payload = features.to_dict()
    f_idx = frame_index if frame_index is not None else session_state.frame_count
    payload.update(
        {
            "session_id": session_id,
            "detector_version": DETECTOR_VERSION,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "frame_index": f_idx,
            "focused_seconds": round(session_state.focused_seconds, 2),
            "distracted_seconds": round(session_state.distracted_seconds, 2),
            "away_seconds": round(session_state.away_seconds, 2),
            "distraction_count": session_state.distraction_count,
            "calibration_complete": calibration_complete,
            "baseline": baseline.to_dict() if baseline else None,
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
    if tracker_results:
        payload["tracker_states"] = {
            name: {
                "active": getattr(res, "active", False),
                "duration_sec": round(float(getattr(res, "duration_sec", 0.0) or 0.0), 2),
                "persistence_met": getattr(res, "persistence_met", False),
            }
            for name, res in tracker_results.items()
        }
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


class BufferedTelemetrySink:
    """Thread-safe bounded in-memory buffer for telemetry samples, designed for async batch persistence."""

    def __init__(self, maxsize: int = 500) -> None:
        self.maxsize: int = maxsize
        self._buffer: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self.samples_generated: int = 0
        self.samples_persisted: int = 0
        self.samples_dropped: int = 0
        self.last_flush_time: Optional[float] = None
        self.is_closed: bool = False

    def emit_telemetry(self, payload: dict[str, Any]) -> None:
        with self._lock:
            if self.is_closed:
                return

        # Enforce zero raw media guarantee: strip any prohibited media keys if present
        clean_payload = {}
        for key, value in payload.items():
            key_lower = key.lower()
            if any(sub in key_lower for sub in PROHIBITED_MEDIA_SUBSTRINGS):
                continue
            clean_payload[key] = value

        with self._lock:
            if self.is_closed:
                return
            self.samples_generated += 1
            if len(self._buffer) >= self.maxsize:
                # Evict oldest sample to respect memory bound under database backpressure
                self._buffer.pop(0)
                self.samples_dropped += 1
            self._buffer.append(clean_payload)

    def emit_event(self, payload: dict[str, Any]) -> None:
        pass

    def finish_session(self, summary: dict[str, Any]) -> None:
        pass

    def close(self) -> None:
        """Close the sink so no subsequent samples are accepted."""
        with self._lock:
            self.is_closed = True

    def pending_count(self) -> int:
        with self._lock:
            return len(self._buffer)

    @property
    def qsize(self) -> int:
        return self.pending_count()

    def drain(self, limit: Optional[int] = None) -> list[dict[str, Any]]:
        with self._lock:
            if not self._buffer:
                return []
            if limit is None or limit >= len(self._buffer):
                drained = self._buffer
                self._buffer = []
                return drained
            drained = self._buffer[:limit]
            self._buffer = self._buffer[limit:]
            return drained

    def drain_batch(self, limit: int) -> list[dict[str, Any]]:
        return self.drain(limit=limit)

    def drain_all(self) -> list[dict[str, Any]]:
        return self.drain(limit=None)

    def record_persisted(self, count: int) -> None:
        with self._lock:
            self.samples_persisted += count

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "samples_generated": self.samples_generated,
                "samples_persisted": self.samples_persisted,
                "samples_dropped": self.samples_dropped,
                "pending_samples": len(self._buffer),
                "last_flush_time": self.last_flush_time,
            }

    @property
    def stats(self) -> dict[str, Any]:
        return self.get_stats()


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
