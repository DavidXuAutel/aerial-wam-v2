"""Logitech C922 V4L2 control presets for Orin bench / deploy.

Uses ``v4l2-ctl`` on Linux; no-op with a warning elsewhere.
"""
from __future__ import annotations

import logging
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Bench defaults (24F outdoor, forward-facing buildings, 640×480 MJPEG).
PRESET_OUTDOOR_BENCH = "outdoor_bench"
PRESET_OUTDOOR_AUTOFOCUS_OFF = "outdoor_af_off"


@dataclass(frozen=True)
class C922Preset:
    name: str
    focus_automatic_continuous: int = 0
    focus_absolute: int = 0
    auto_exposure: int = 1
    exposure_time_absolute: int = 20
    brightness: int = 110
    gain: int = 0
    backlight_compensation: int = 0
    white_balance_automatic: Optional[int] = 1

    def controls(self) -> Dict[str, int]:
        out: Dict[str, int] = {
            "focus_automatic_continuous": int(self.focus_automatic_continuous),
            "focus_absolute": int(self.focus_absolute),
            "auto_exposure": int(self.auto_exposure),
            "exposure_time_absolute": int(self.exposure_time_absolute),
            "brightness": int(self.brightness),
            "gain": int(self.gain),
            "backlight_compensation": int(self.backlight_compensation),
        }
        if self.white_balance_automatic is not None:
            out["white_balance_automatic"] = int(self.white_balance_automatic)
        return out


_PRESETS: Dict[str, C922Preset] = {
    PRESET_OUTDOOR_BENCH: C922Preset(
        name=PRESET_OUTDOOR_BENCH,
        focus_absolute=0,
        exposure_time_absolute=20,
        brightness=110,
    ),
    PRESET_OUTDOOR_AUTOFOCUS_OFF: C922Preset(
        name=PRESET_OUTDOOR_AUTOFOCUS_OFF,
        focus_automatic_continuous=0,
        focus_absolute=0,
        exposure_time_absolute=40,
        brightness=100,
    ),
    "outdoor_dim": C922Preset(
        name="outdoor_dim",
        exposure_time_absolute=80,
        brightness=110,
    ),
    "outdoor_bright": C922Preset(
        name="outdoor_bright",
        exposure_time_absolute=15,
        brightness=90,
    ),
}


def list_presets() -> List[str]:
    return sorted(_PRESETS.keys())


def get_preset(name: str) -> C922Preset:
    key = str(name).strip()
    if key not in _PRESETS:
        raise KeyError(f"unknown C922 preset {key!r}; choose from {list_presets()}")
    return _PRESETS[key]


def v4l2_device_path(device: str) -> str:
    dev = str(device).strip()
    if dev.startswith("/dev/"):
        return dev
    return f"/dev/video{dev}"


def apply_v4l2_controls(
    device: str,
    controls: Dict[str, int],
    *,
    dry_run: bool = False,
) -> List[str]:
    """Apply ``v4l2-ctl --set-ctrl`` for each control. Returns commands run."""
    if not sys.platform.startswith("linux"):
        logger.warning("v4l2-ctl skipped (non-Linux host)")
        return []

    dev_path = v4l2_device_path(device)
    cmds: List[str] = []
    for name, value in controls.items():
        cmd = ["v4l2-ctl", "-d", dev_path, f"--set-ctrl={name}={int(value)}"]
        cmds.append(" ".join(cmd))
        if dry_run:
            continue
        subprocess.run(cmd, check=False, capture_output=True)
    if not dry_run:
        logger.info(
            "C922 preset applied on %s: %s",
            dev_path,
            ", ".join(f"{k}={v}" for k, v in controls.items()),
        )
    return cmds


def apply_preset(device: str, preset_name: str = PRESET_OUTDOOR_BENCH, *, dry_run: bool = False) -> C922Preset:
    preset = get_preset(preset_name)
    apply_v4l2_controls(device, preset.controls(), dry_run=dry_run)
    return preset


def read_v4l2_controls(device: str, names: Sequence[str]) -> Dict[str, Optional[int]]:
    if not sys.platform.startswith("linux"):
        return {}
    dev_path = v4l2_device_path(device)
    out: Dict[str, Optional[int]] = {}
    for name in names:
        proc = subprocess.run(
            ["v4l2-ctl", "-d", dev_path, f"--get-ctrl={name}"],
            check=False,
            capture_output=True,
            text=True,
        )
        text = (proc.stdout or proc.stderr or "").strip()
        if ":" in text:
            try:
                out[name] = int(text.split(":", 1)[1].strip())
            except ValueError:
                out[name] = None
        else:
            out[name] = None
    return out


def focus_sweep(
    device: str,
    *,
    width: int = 640,
    height: int = 480,
    focus_min: int = 0,
    focus_max: int = 250,
    focus_step: int = 5,
    exposure: int = 20,
    brightness: int = 110,
) -> Tuple[int, float, np.ndarray]:
    """Scan focus_absolute; return (best_focus, laplacian_var, bgr_frame)."""
    import cv2  # type: ignore

    apply_v4l2_controls(
        device,
        {
            "focus_automatic_continuous": 0,
            "auto_exposure": 1,
            "exposure_time_absolute": int(exposure),
            "brightness": int(brightness),
            "gain": 0,
        },
    )

    dev = str(device)
    backend = cv2.CAP_V4L2 if sys.platform.startswith("linux") else cv2.CAP_ANY
    cap = cv2.VideoCapture(int(dev) if dev.isdigit() else dev, backend)
    cap.set(cv2.CAP_PROP_FOURCC, float(cv2.VideoWriter_fourcc(*"MJPG")))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(width))
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(height))
    if not cap.isOpened():
        raise RuntimeError(f"failed to open camera {device!r} for focus sweep")

    best_focus = 0
    best_lap = -1.0
    best_bgr: Optional[np.ndarray] = None
    dev_path = v4l2_device_path(device)

    for focus in range(int(focus_min), int(focus_max) + 1, int(focus_step)):
        subprocess.run(
            ["v4l2-ctl", "-d", dev_path, f"--set-ctrl=focus_absolute={focus}"],
            check=False,
            capture_output=True,
        )
        for _ in range(4):
            cap.grab()
        ok, bgr = cap.read()
        if not ok or bgr is None:
            continue
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        lap = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        if lap > best_lap:
            best_lap = lap
            best_focus = int(focus)
            best_bgr = bgr.copy()

    cap.release()
    if best_bgr is None:
        raise RuntimeError("focus sweep produced no valid frames")

    apply_v4l2_controls(device, {"focus_absolute": best_focus})
    logger.info("focus sweep best_focus=%d laplacian=%.1f mean=%.1f", best_focus, best_lap, float(best_bgr.mean()))
    return best_focus, best_lap, best_bgr
