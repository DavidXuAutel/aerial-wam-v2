#!/usr/bin/env python3
"""Apply HJ USB 2.0 Camera V4L2 presets on Orin (or any Linux bench host).

Examples::

  # Default outdoor bench preset on /dev/video0
  python -m experiments.aerial.scripts.hj_cam_setup

  # Show current controls after apply
  python -m experiments.aerial.scripts.hj_cam_setup --show

  # Save a snapshot after tuning
  python -m experiments.aerial.scripts.hj_cam_setup --snapshot ~/hj_cam_snap.jpg
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("hj_cam_setup")


def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="HJ USB 2.0 Camera V4L2 preset + snapshot")
    p.add_argument("--device", default="0", help="V4L2 index or /dev/videoN (default: HJ on Orin)")
    p.add_argument(
        "--preset",
        default="outdoor_bench",
        help="Named preset (outdoor_bench, outdoor_bright, outdoor_dim)",
    )
    p.add_argument("--list-presets", action="store_true", help="Print preset names and exit")
    p.add_argument("--show", action="store_true", help="Read back key v4l2 controls after apply")
    p.add_argument("--dry-run", action="store_true", help="Print v4l2-ctl commands only")
    p.add_argument("--capture-w", type=int, default=640)
    p.add_argument("--capture-h", type=int, default=480)
    p.add_argument("--snapshot", default=None, help="Save BGR snapshot after setup (path)")
    return p.parse_args()


def main() -> int:
    args = _parse()
    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from experiments.aerial.deploy.hj_camera_controls import (
        apply_preset,
        get_preset,
        list_presets,
        read_controls,
    )

    if args.list_presets:
        for name in list_presets():
            preset = get_preset(name)
            logger.info("%s: %s", name, preset.controls())
        return 0

    preset = apply_preset(args.device, args.preset, dry_run=bool(args.dry_run))
    logger.info("applied preset %s on device %s", preset.name, args.device)

    if args.show and not args.dry_run:
        current = read_controls(args.device, args.preset)
        for k, v in current.items():
            logger.info("  %s = %s (requested %s)", k, v, preset.controls()[k])

    if args.snapshot and not args.dry_run:
        from experiments.aerial.deploy.real_camera import RealCamera, RealCameraConfig

        out = Path(args.snapshot).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        cam = RealCamera(
            RealCameraConfig(
                device=str(args.device),
                width=int(args.capture_w),
                height=int(args.capture_h),
                v4l2_preset=None,
            )
        )
        cam.open()
        bgr, _ = cam.read()
        cam.close()
        import cv2  # type: ignore

        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        lap = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        cv2.imwrite(str(out), bgr)
        logger.info(
            "saved %s (%dx%d mean=%.1f sharpness=%.1f)",
            out,
            bgr.shape[1],
            bgr.shape[0],
            float(bgr.mean()),
            lap,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
