"""USB / V4L2 camera capture for Orin companion-computer deploy.

Returns a native BGR frame plus a WAM-sized RGB ``uint8`` tensor ``[H,W,3]``.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class RealCameraConfig:
    device: str = "0"
    width: int = 1280
    height: int = 720
    wam_size: int = 224
    fps: int = 30
    fourcc: str = "MJPG"
    warmup_frames: int = 3
    fisheye_calib: Optional[str] = None
    # Apply C922 v4l2 preset before open (None = skip). Orin C922 default: outdoor_bench.
    v4l2_preset: Optional[str] = "outdoor_bench"


def _fourcc_to_int(fourcc: str) -> int:
    import cv2  # type: ignore

    tag = fourcc.strip().upper()
    if not tag:
        return 0
    if len(tag) != 4:
        raise ValueError(f"fourcc must be 4 chars, got {fourcc!r}")
    return int(cv2.VideoWriter_fourcc(*tag))


def _fourcc_from_int(code: int) -> str:
    return "".join(chr(int((int(code) >> (8 * i)) & 0xFF)) for i in range(4))


class RealCamera:
    """Thin OpenCV capture wrapper."""

    def __init__(self, config: Optional[RealCameraConfig] = None) -> None:
        self.config = config or RealCameraConfig()
        self._cap: Optional[object] = None
        self._undistort: Optional[object] = None

    def open(self) -> None:
        import sys

        import cv2  # type: ignore

        if self.config.v4l2_preset:
            from experiments.aerial.deploy.c922_controls import apply_preset

            apply_preset(self.config.device, self.config.v4l2_preset)

        dev = self.config.device
        backend = cv2.CAP_V4L2 if sys.platform.startswith("linux") else cv2.CAP_ANY
        if dev.isdigit():
            self._cap = cv2.VideoCapture(int(dev), backend)
        else:
            self._cap = cv2.VideoCapture(dev, backend)
        if not self._cap.isOpened():
            raise RuntimeError(f"failed to open camera device {dev!r}")

        fcc = _fourcc_to_int(self.config.fourcc)
        if fcc:
            self._cap.set(cv2.CAP_PROP_FOURCC, float(fcc))
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(self.config.width))
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(self.config.height))
        self._cap.set(cv2.CAP_PROP_FPS, float(self.config.fps))

        for _ in range(max(0, int(self.config.warmup_frames))):
            self._cap.grab()

        actual_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = float(self._cap.get(cv2.CAP_PROP_FPS))
        actual_fcc = _fourcc_from_int(int(self._cap.get(cv2.CAP_PROP_FOURCC)))
        logger.info(
            "Camera open device=%s requested=%dx%d@%dfps %s actual=%dx%d@%.1ffps %s wam=%d",
            dev,
            self.config.width,
            self.config.height,
            self.config.fps,
            self.config.fourcc or "default",
            actual_w,
            actual_h,
            actual_fps,
            actual_fcc,
            self.config.wam_size,
        )
        if actual_w != int(self.config.width) or actual_h != int(self.config.height):
            logger.warning(
                "Camera resolution mismatch: requested %dx%d got %dx%d",
                self.config.width,
                self.config.height,
                actual_w,
                actual_h,
            )

        calib_path = self.config.fisheye_calib
        if calib_path:
            from experiments.aerial.deploy.fisheye_undistort import (
                FisheyeCalibration,
                FisheyeUndistorter,
            )

            calib = FisheyeCalibration.load(Path(calib_path))
            if calib.image_size != (actual_w, actual_h):
                logger.warning(
                    "fisheye calib size %s != capture %dx%d",
                    calib.image_size,
                    actual_w,
                    actual_h,
                )
            self._undistort = FisheyeUndistorter(calib)

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
        self._cap = None
        self._undistort = None

    def read(self) -> Tuple[np.ndarray, np.ndarray]:
        """Return ``(native_bgr, wam_rgb)``."""
        if self._cap is None:
            raise RuntimeError("camera not open")
        import cv2  # type: ignore

        ok, bgr = self._cap.read()
        if not ok or bgr is None:
            raise RuntimeError("camera read failed")
        if self._undistort is not None:
            bgr = self._undistort.apply(bgr)
        bgr = np.ascontiguousarray(bgr)
        sz = int(self.config.wam_size)
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        if rgb.shape[0] != sz or rgb.shape[1] != sz:
            rgb = cv2.resize(rgb, (sz, sz), interpolation=cv2.INTER_AREA)
        return bgr, np.ascontiguousarray(rgb, dtype=np.uint8)


class MockCamera:
    """Bench placeholder when no camera is wired."""

    def __init__(self, wam_size: int = 224) -> None:
        self._wam_size = int(wam_size)

    def open(self) -> None:
        logger.warning("MockCamera — synthetic frames only")

    def close(self) -> None:
        return None

    def read(self) -> Tuple[np.ndarray, np.ndarray]:
        sz = self._wam_size
        rgb = np.zeros((sz, sz, 3), dtype=np.uint8)
        bgr = rgb[:, :, ::-1].copy()
        return bgr, rgb
