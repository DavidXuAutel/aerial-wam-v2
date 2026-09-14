#!/usr/bin/env python3
"""SJCAM 4000 capture helper for Orin bench (no v4l2 exposure controls)."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("sjcam_setup")


def main() -> int:
    p = argparse.ArgumentParser(description="SJCAM 4000 snapshot (default /dev/video2)")
    p.add_argument("--device", default="2")
    p.add_argument("--capture-w", type=int, default=1280)
    p.add_argument("--capture-h", type=int, default=720)
    p.add_argument("--snapshot", default="~/sjcam_snap.jpg")
    args = p.parse_args()

    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from experiments.aerial.deploy.real_camera import RealCamera, RealCameraConfig

    cam = RealCamera(
        RealCameraConfig(
            device=str(args.device),
            width=int(args.capture_w),
            height=int(args.capture_h),
            v4l2_preset=None,
            v4l2_profile="sjcam",
        )
    )
    cam.open()
    bgr, _ = cam.read()
    cam.close()

    import cv2  # type: ignore

    out = Path(args.snapshot).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    lap = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    cv2.imwrite(str(out), bgr)
    logger.info("saved %s (%dx%d mean=%.1f sharpness=%.1f)", out, bgr.shape[1], bgr.shape[0], float(bgr.mean()), lap)
    return 0


if __name__ == "__main__":
    sys.exit(main())
