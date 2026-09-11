#!/usr/bin/env python3
"""Apply Logitech C922 V4L2 presets on Orin (or any Linux bench host).

Examples::

  # Default outdoor bench preset on C922 (/dev/video2)
  python -m experiments.aerial.scripts.c922_setup

  # Show current controls after apply
  python -m experiments.aerial.scripts.c922_setup --show

  # Autofocus sweep then save a snapshot
  python -m experiments.aerial.scripts.c922_setup --focus-sweep --snapshot ~/c922_snap.jpg
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("c922_setup")


def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Logitech C922 V4L2 preset + optional focus sweep")
    p.add_argument("--device", default="2", help="V4L2 index or /dev/videoN (default: C922 on Orin)")
    p.add_argument(
        "--preset",
        default="outdoor_bench",
        help="Named preset (outdoor_bench, outdoor_dim, outdoor_bright, ...)",
    )
    p.add_argument("--list-presets", action="store_true", help="Print preset names and exit")
    p.add_argument("--show", action="store_true", help="Read back key v4l2 controls after apply")
    p.add_argument("--dry-run", action="store_true", help="Print v4l2-ctl commands only")
    p.add_argument("--focus-sweep", action="store_true", help="Run Laplacian focus scan")
    p.add_argument("--capture-w", type=int, default=640)
    p.add_argument("--capture-h", type=int, default=480)
    p.add_argument("--focus-min", type=int, default=0)
    p.add_argument("--focus-max", type=int, default=250)
    p.add_argument("--focus-step", type=int, default=5)
    p.add_argument("--snapshot", default=None, help="Save BGR snapshot after setup (path)")
    return p.parse_args()


def main() -> int:
    args = _parse()
    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from experiments.aerial.deploy.c922_controls import (
        apply_preset,
        focus_sweep,
        get_preset,
        list_presets,
        read_v4l2_controls,
    )

    if args.list_presets:
        for name in list_presets():
            preset = get_preset(name)
            logger.info("%s: %s", name, preset.controls())
        return 0

    preset = apply_preset(args.device, args.preset, dry_run=bool(args.dry_run))
    logger.info("applied preset %s on device %s", preset.name, args.device)

    if args.show and not args.dry_run:
        names = list(preset.controls().keys())
        current = read_v4l2_controls(args.device, names)
        for k in names:
            logger.info("  %s = %s (requested %s)", k, current.get(k), preset.controls()[k])

    bgr = None
    if args.focus_sweep and not args.dry_run:
        focus, lap, bgr = focus_sweep(
            args.device,
            width=int(args.capture_w),
            height=int(args.capture_h),
            focus_min=int(args.focus_min),
            focus_max=int(args.focus_max),
            focus_step=int(args.focus_step),
            exposure=int(preset.exposure_time_absolute),
            brightness=int(preset.brightness),
        )
        logger.info("focus_sweep: focus=%d sharpness=%.1f", focus, lap)

    if args.snapshot and not args.dry_run:
        out = Path(args.snapshot).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        if bgr is None:
            from experiments.aerial.deploy.real_camera import RealCamera, RealCameraConfig

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

        cv2.imwrite(str(out), bgr)
        logger.info("saved %s (%dx%d mean=%.1f)", out, bgr.shape[1], bgr.shape[0], float(bgr.mean()))

    return 0


if __name__ == "__main__":
    sys.exit(main())
