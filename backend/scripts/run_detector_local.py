"""Local desktop webcam runner and visualization adapter."""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

# Add backend directory to sys.path if running as a standalone script
CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.detection import (
    DetectorConfig,
    FileTelemetrySink,
    StudentDistractionDetector,
)
from app.detection.mediapipe_runtime import MediaPipeRuntime, ensure_models

# Optional Windows desktop alarm
try:
    import winsound  # type: ignore
except ImportError:
    winsound = None


class DesktopAlarm:
    """Desktop audio alarm worker for local development/testing."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled and (winsound is not None)
        self.flag = threading.Event()

        if self.enabled:
            threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self) -> None:
        while True:
            if not self.flag.is_set():
                time.sleep(0.1)
                continue

            try:
                winsound.Beep(1000, 200)  # type: ignore[union-attr]
            except Exception:
                time.sleep(0.2)

            time.sleep(0.1)

    def set_active(self, active: bool) -> None:
        if self.enabled:
            if active:
                self.flag.set()
            else:
                self.flag.clear()

    def stop(self) -> None:
        self.flag.clear()


def draw_center_banner(display: np.ndarray, active_alerts: list[str]) -> None:
    """Draw a distraction banner over the video display."""
    if not active_alerts:
        return

    h, w, _ = display.shape
    overlay = display.copy()
    box_w = int(w * 0.85)
    box_h = int(h * 0.32)

    x0 = (w - box_w) // 2
    y0 = (h - box_h) // 2

    cv2.rectangle(
        overlay,
        (x0, y0),
        (x0 + box_w, y0 + box_h),
        (0, 0, 255),
        -1,
    )

    cv2.addWeighted(overlay, 0.75, display, 0.25, 0, dst=display)

    title = "DISTRACTED!"
    (tw, th), _ = cv2.getTextSize(title, cv2.FONT_HERSHEY_SIMPLEX, 1.6, 3)
    cv2.putText(
        display,
        title,
        (w // 2 - tw // 2, y0 + th + 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.6,
        (255, 255, 255),
        3,
    )

    detail = ", ".join(active_alerts)
    (dw, _), _ = cv2.getTextSize(detail, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
    cv2.putText(
        display,
        detail,
        (w // 2 - dw // 2, y0 + box_h - 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2,
    )


def run_local_demo(camera_index: int = 0) -> None:
    """Run interactive local webcam detection with desktop display."""
    data_dir = BACKEND_DIR / "data"
    config = DetectorConfig()

    print("Initializing Student Focus Monitor local webcam runner...")
    ensure_models()

    file_sink = FileTelemetrySink(
        session_id=time.strftime("session_%Y%m%d_%H%M%S"),
        base_dir=data_dir,
        config=config,
    )
    detector = StudentDistractionDetector(
        config=config,
        session_id=file_sink.session_id,
        telemetry_sink=file_sink,
    )
    alarm = DesktopAlarm(enabled=config.enable_desktop_alarm)

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError(
            f"Cannot open webcam index {camera_index}. Check camera permissions and availability."
        )

    last_timestamp_ms = 0

    try:
        with MediaPipeRuntime() as runtime:
            print("Webcam loop started. Press 'q' to quit, 'c' to recalibrate.")
            while cap.isOpened():
                success, frame_bgr = cap.read()
                if not success:
                    print("Ignoring empty camera frame.")
                    continue

                frame_bgr = cv2.flip(frame_bgr, 1)
                h, w, _ = frame_bgr.shape

                rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                timestamp_ms = int(time.time() * 1000)
                if timestamp_ms <= last_timestamp_ms:
                    timestamp_ms = last_timestamp_ms + 1
                last_timestamp_ms = timestamp_ms

                face_res, hand_res, pose_res = runtime.detect(rgb, timestamp_ms)

                display = frame_bgr

                # Process results through core detection engine
                state = detector.process_results(
                    face_result=face_res,
                    hand_result=hand_res,
                    pose_result=pose_res,
                    width=w,
                    height=h,
                    timestamp=time.time(),
                )

                active_alerts = state["active_alerts"]
                alarm.set_active(bool(active_alerts))

                if active_alerts:
                    draw_center_banner(display, active_alerts)

                status = (
                    f"state={state['state']} "
                    f"focus={state['focused_seconds']:.0f}s "
                    f"dist={state['distracted_seconds']:.0f}s "
                    f"away={state['away_seconds']:.0f}s"
                )
                cv2.putText(
                    display,
                    status,
                    (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (0, 255, 0),
                    1,
                )

                if not state["calibration_complete"]:
                    cv2.putText(
                        display,
                        "CALIBRATING - stay in normal study posture",
                        (10, 50),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        (0, 255, 255),
                        1,
                    )

                cv2.imshow("Student Focus Monitor — Local Runner", display)

                key = cv2.waitKey(10) & 0xFF
                if key == ord("q"):
                    break
                if key == ord("c"):
                    detector.reset_calibration()
                    print("Calibration reset.")
    finally:
        alarm.stop()
        cap.release()
        cv2.destroyAllWindows()
        summary = detector.finish_session()
        print("\nSession finished:")
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    run_local_demo()
