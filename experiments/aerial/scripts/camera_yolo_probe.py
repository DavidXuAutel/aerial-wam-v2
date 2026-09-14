#!/usr/bin/env python3
"""Grab frames from RealCamera and run one YOLO detection (Orin bench)."""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("camera_yolo_probe")


def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="RealCamera + YOLO one-shot probe")
    p.add_argument("--camera", default="0")
    p.add_argument("--capture-w", type=int, default=1280)
    p.add_argument("--capture-h", type=int, default=720)
    p.add_argument("--capture-fps", type=int, default=30)
    p.add_argument("--wam-encode-size", type=int, default=224)
    p.add_argument("--yolo-model", default="yolov8n.pt")
    p.add_argument("--yolo-conf", type=float, default=0.25)
    p.add_argument("--yolo-imgsz", type=int, default=640)
    p.add_argument("--target-class", default="car")
    p.add_argument("--device", default="cpu")
    p.add_argument("--frames", type=int, default=5, help="Frames to grab for timing")
    p.add_argument("--out", default="~/camera_yolo_probe.jpg")
    return p.parse_args()


def main() -> int:
    args = _parse()
    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    vgoal_repo = Path("~/Projects/aerial-vgoal-wam").expanduser().resolve()
    if not vgoal_repo.is_dir():
        raise SystemExit(f"vgoal repo not found: {vgoal_repo}")
    if str(vgoal_repo) not in sys.path:
        sys.path.insert(0, str(vgoal_repo))

    from experiments.aerial.deploy.real_camera import RealCamera, RealCameraConfig
    from experiments.aerial.scripts.wam_vgoal_eval import _build_detector

    cam = RealCamera(
        RealCameraConfig(
            device=str(args.camera),
            width=int(args.capture_w),
            height=int(args.capture_h),
            fps=int(args.capture_fps),
        )
    )
    cam.open()

    t0 = time.perf_counter()
    bgr, wam_rgb = cam.read()
    grab_ms = (time.perf_counter() - t0) * 1000.0
    logger.info("first frame shape=%s wam=%s grab=%.1fms", bgr.shape, wam_rgb.shape, grab_ms)

    n = max(1, int(args.frames))
    t1 = time.perf_counter()
    for _ in range(n - 1):
        cam.read()
    elapsed = time.perf_counter() - t1
    if n > 1:
        logger.info("%d-frame grab avg=%.1fms (%.1f fps)", n, elapsed / n * 1000.0, n / elapsed)

    detector = _build_detector(
        argparse.Namespace(
            detector="yolo",
            target_class=args.target_class,
            visual_prompt=args.target_class,
            yolo_model=args.yolo_model,
            yolo_conf=args.yolo_conf,
            yolo_imgsz=args.yolo_imgsz,
            yolo_device=str(args.device),
            camera_fov_deg=80.0,
            capture_w=args.capture_w,
            capture_h=args.capture_h,
        ),
        vgoal_repo,
    )

    import cv2  # type: ignore

    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    t2 = time.perf_counter()
    detect_all = getattr(detector, "detect_all", None)
    if callable(detect_all):
        dets = list(detect_all(rgb) or [])
    else:
        det = detector.detect(rgb)
        dets = list(det) if isinstance(det, (list, tuple)) else ([det] if det is not None else [])
    yolo_ms = (time.perf_counter() - t2) * 1000.0
    logger.info("YOLO %d detections in %.1fms", len(dets), yolo_ms)
    for i, det in enumerate(dets[:5]):
        logger.info(
            "  det[%d] class=%s conf=%.3f bbox=%s",
            i,
            getattr(det, "class_name", "?"),
            float(getattr(det, "confidence", 0.0)),
            getattr(det, "bbox", None),
        )

    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    vis = bgr.copy()
    for det in dets:
        box = getattr(det, "bbox", None)
        if box is None:
            continue
        x1, y1, x2, y2 = [int(v) for v in box]
        cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 2)
        label = f"{getattr(det, 'class_name', 'obj')}:{getattr(det, 'confidence', 0):.2f}"
        cv2.putText(vis, label, (x1, max(0, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    cv2.imwrite(str(out), vis)
    logger.info("saved %s", out)

    cam.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
