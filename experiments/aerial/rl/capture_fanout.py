"""Single-camera RGB fan-out: one Scene grab → WAM / VIO / YOLO branches.

Not dual cameras. Capture resolution comes from AirSim ``CaptureSettings``
(``AERIAL_CAPTURE_W/H`` or legacy ``INDOOR_CAPTURE_*``). WAM encode size is
always derived after the grab (default 224).
"""
from __future__ import annotations

import os
from typing import Optional, Tuple

import numpy as np

_CAPTURE_W = os.environ.get("AERIAL_CAPTURE_W") or os.environ.get("INDOOR_CAPTURE_W", "640")
_CAPTURE_H = os.environ.get("AERIAL_CAPTURE_H") or os.environ.get("INDOOR_CAPTURE_H", "480")
WAM_ENCODE_SIZE = int(os.environ.get("WAM_ENCODE_SIZE", "224"))

_YOLO_W = os.environ.get("AERIAL_YOLO_W", os.environ.get("INDOOR_YOLO_W", "")).strip()
_YOLO_H = os.environ.get("AERIAL_YOLO_H", os.environ.get("INDOOR_YOLO_H", "")).strip()
YOLO_WH: Optional[Tuple[int, int]] = (
    (int(_YOLO_W), int(_YOLO_H)) if _YOLO_W and _YOLO_H else None
)


def capture_wh() -> Tuple[int, int]:
    return (int(_CAPTURE_W), int(_CAPTURE_H))


def wam_encode_wh() -> Tuple[int, int]:
    return (WAM_ENCODE_SIZE, WAM_ENCODE_SIZE)


def fanout_rgb(
    capture_rgb: np.ndarray,
    *,
    wam_size: int = WAM_ENCODE_SIZE,
    yolo_wh: Optional[Tuple[int, int]] = YOLO_WH,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Split one capture into (rgb_wam, rgb_vio, rgb_yolo)."""
    import cv2  # lazy: AirSim hosts have it

    cap = np.ascontiguousarray(np.asarray(capture_rgb, dtype=np.uint8))
    rgb_vio = cap
    h, w = int(cap.shape[0]), int(cap.shape[1])
    if (h, w) != (wam_size, wam_size):
        rgb_wam = np.ascontiguousarray(
            cv2.resize(cap, (wam_size, wam_size), interpolation=cv2.INTER_AREA),
            dtype=np.uint8,
        )
    else:
        rgb_wam = cap.copy()
    if yolo_wh is None:
        rgb_yolo = cap.copy()
    else:
        yw, yh = int(yolo_wh[0]), int(yolo_wh[1])
        if (w, h) != (yw, yh):
            rgb_yolo = np.ascontiguousarray(
                cv2.resize(cap, (yw, yh), interpolation=cv2.INTER_AREA),
                dtype=np.uint8,
            )
        else:
            rgb_yolo = cap.copy()
    return rgb_wam, rgb_vio, rgb_yolo
