"""MediaPipe Tasks API runtime adapter isolated behind a clean interface boundary."""

from __future__ import annotations

import urllib.request
from pathlib import Path
from typing import Any, Optional, Tuple

MODEL_URLS: dict[str, str] = {
    "face_landmarker.task": (
        "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
        "face_landmarker/float16/1/face_landmarker.task"
    ),
    "hand_landmarker.task": (
        "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
        "hand_landmarker/float16/1/hand_landmarker.task"
    ),
    "pose_landmarker_lite.task": (
        "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
        "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
    ),
}

DEFAULT_MODEL_DIR: Path = Path(__file__).resolve().parent / "models"


def ensure_models(target_dir: Optional[Path] = None) -> dict[str, Path]:
    """
    Ensure required MediaPipe Tasks model bundles exist locally.
    Downloads them on-demand if missing.
    """
    model_dir = target_dir or DEFAULT_MODEL_DIR
    model_dir.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}
    for filename, url in MODEL_URLS.items():
        path = model_dir / filename
        if not path.exists():
            print(f"Downloading {filename} to {path}...")
            urllib.request.urlretrieve(url, path)
        paths[filename] = path

    return paths


class MediaPipeRuntime:
    """
    Encapsulates MediaPipe Tasks vision landmarker models for video streams.
    Isolates external dependencies from core rule evaluation.
    """

    def __init__(self, model_dir: Optional[Path] = None) -> None:
        import mediapipe as mp  # Deferred import to ensure import safety

        self.mp = mp
        self.model_dir = model_dir or DEFAULT_MODEL_DIR
        self.model_paths = ensure_models(self.model_dir)

        base_options_cls = mp.tasks.BaseOptions
        running_mode = mp.tasks.vision.RunningMode.VIDEO

        face_options = mp.tasks.vision.FaceLandmarkerOptions(
            base_options=base_options_cls(
                model_asset_path=str(self.model_paths["face_landmarker.task"])
            ),
            running_mode=running_mode,
            num_faces=1,
        )
        hand_options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=base_options_cls(
                model_asset_path=str(self.model_paths["hand_landmarker.task"])
            ),
            running_mode=running_mode,
            num_hands=2,
        )
        pose_options = mp.tasks.vision.PoseLandmarkerOptions(
            base_options=base_options_cls(
                model_asset_path=str(self.model_paths["pose_landmarker_lite.task"])
            ),
            running_mode=running_mode,
        )

        self.face_landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(
            face_options
        )
        self.hand_landmarker = mp.tasks.vision.HandLandmarker.create_from_options(
            hand_options
        )
        self.pose_landmarker = mp.tasks.vision.PoseLandmarker.create_from_options(
            pose_options
        )
        self._last_timestamp_ms: int = -1

    def detect(
        self,
        rgb_frame: Any,
        timestamp_ms: int,
    ) -> Tuple[Any, Any, Any]:
        """
        Run synchronous landmark detection for video frames.
        Returns (face_result, hand_result, pose_result).
        """
        if timestamp_ms <= self._last_timestamp_ms:
            timestamp_ms = self._last_timestamp_ms + 1
        self._last_timestamp_ms = timestamp_ms

        mp_image = self.mp.Image(
            image_format=self.mp.ImageFormat.SRGB,
            data=rgb_frame,
        )

        face_result = self.face_landmarker.detect_for_video(mp_image, timestamp_ms)
        hand_result = self.hand_landmarker.detect_for_video(mp_image, timestamp_ms)
        pose_result = self.pose_landmarker.detect_for_video(mp_image, timestamp_ms)

        return face_result, hand_result, pose_result

    def close(self) -> None:
        """Release underlying vision tasks resources."""
        if hasattr(self, "face_landmarker"):
            self.face_landmarker.close()
        if hasattr(self, "hand_landmarker"):
            self.hand_landmarker.close()
        if hasattr(self, "pose_landmarker"):
            self.pose_landmarker.close()

    def __enter__(self) -> MediaPipeRuntime:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
