#!/usr/bin/env python3
"""Spawn-only YOLO visibility probe for outdoor visual-goal eval.

Teleports to each annotation pose, grabs one fan-out RGB frame, runs YOLO.
Use this to calibrate ``artifacts/airsim16_car_spawn_probe.json`` before
``wam_vgoal_eval.py`` — no π / planner / WM required.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import yaml

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("vgoal_yolo_spawn_probe")


def _select_route_indices(n_available: int, episodes: int, routes_arg: Optional[str]) -> List[int]:
    if not routes_arg:
        return list(range(min(int(episodes), int(n_available))))
    idxs = [int(t) for t in str(routes_arg).split(",") if t.strip()]
    bad = [i for i in idxs if not 0 <= i < n_available]
    if bad:
        raise SystemExit(f"--routes {bad} out of range (annotation has {n_available})")
    return idxs


def _yaw_offsets(sweep_deg: float, step_deg: float) -> List[float]:
    if sweep_deg <= 0.0 or step_deg <= 0.0:
        return [0.0]
    half = float(sweep_deg)
    step = max(float(step_deg), 1.0)
    n = int(math.ceil((2.0 * half) / step))
    return [(-half + i * step) * math.pi / 180.0 for i in range(n + 1)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Spawn-only YOLO car visibility probe")
    parser.add_argument("--config", default="configs/aerial_rl.yaml")
    parser.add_argument(
        "--annotation",
        default="experiments/aerial/phase2-vgoal/airsim16_car_spawn_probe.json",
    )
    parser.add_argument("--routes", default=None)
    parser.add_argument("--episodes", type=int, default=8)
    parser.add_argument("--vgoal-repo", default="~/Projects/aerial-vgoal-wam")
    parser.add_argument("--detector", default="yolo", choices=["yolo", "open_vocab", "semantic"])
    parser.add_argument("--target-class", default="car")
    parser.add_argument("--visual-prompt", default=None)
    parser.add_argument("--yolo-model", default="yolov8n.pt")
    parser.add_argument("--yolo-conf", type=float, default=0.15)
    parser.add_argument("--yolo-imgsz", type=int, default=640)
    parser.add_argument("--yolo-device", default="cuda")
    parser.add_argument("--capture-w", type=int, default=640)
    parser.add_argument("--capture-h", type=int, default=480)
    parser.add_argument("--fanout-rgb", action="store_true", default=True)
    parser.add_argument("--wam-encode-size", type=int, default=224)
    parser.add_argument("--step-hz", type=float, default=5.0)
    parser.add_argument("--spawn-tol-m", type=float, default=12.0)
    parser.add_argument("--yaw-sweep-deg", type=float, default=0.0, help="±deg yaw sweep at each spawn (0=off)")
    parser.add_argument("--yaw-step-deg", type=float, default=15.0)
    parser.add_argument("--snapshot-dir", default="artifacts/yolo_spawn_snapshots")
    parser.add_argument("--out", default="artifacts/yolo_spawn_probe.json")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    vgoal_repo = Path(args.vgoal_repo).expanduser().resolve()
    if not vgoal_repo.is_dir():
        raise SystemExit(f"--vgoal-repo not found: {vgoal_repo}")
    if str(vgoal_repo) not in sys.path:
        sys.path.insert(0, str(vgoal_repo))

    from experiments.aerial.scripts.wam_vgoal_eval import _build_detector
    from experiments.aerial.rl.train_rl import _build_env

    cfg_file = (root / args.config).resolve()
    cfg = yaml.safe_load(cfg_file.read_text()) if cfg_file.is_file() else {}

    anno_path = (root / args.annotation).resolve() if not Path(args.annotation).is_absolute() else Path(args.annotation)
    with open(anno_path, "r", encoding="utf-8") as f:
        anno_data = json.load(f)
    routes = anno_data.get("routes", anno_data) if isinstance(anno_data, dict) else anno_data
    route_idxs = _select_route_indices(len(routes), args.episodes, args.routes)

    env_cfg = dict(cfg.get("env") or {})
    env_cfg["backend"] = "airsim"
    env_cfg["step_hz"] = float(args.step_hz)
    env_cfg["grab_depth"] = False
    env_cfg["health_check"] = False
    env_cfg["fanout_rgb"] = bool(args.fanout_rgb)
    env_cfg["width"] = int(args.capture_w)
    env_cfg["height"] = int(args.capture_h)
    env_cfg["wam_encode_size"] = int(args.wam_encode_size)
    env = _build_env(env_cfg)
    detector = _build_detector(args, vgoal_repo)

    snap_dir = (root / args.snapshot_dir).resolve()
    snap_dir.mkdir(parents=True, exist_ok=True)
    yaw_offsets = _yaw_offsets(float(args.yaw_sweep_deg), float(args.yaw_step_deg))

    results: List[Dict[str, Any]] = []
    try:
        import cv2  # noqa: F401
    except ImportError:
        cv2 = None

    for ep_idx in route_idxs:
        r_info = routes[ep_idx]
        pts = np.array(r_info.get("pos", r_info.get("positions")), dtype=np.float64)
        start_pos = pts[0].copy()
        yaws = np.array(r_info.get("yaw", [0.0] * len(pts)), dtype=np.float64)
        base_yaw = float(yaws[0]) if len(yaws) else 0.0

        for off_i, yaw_off in enumerate(yaw_offsets):
            spawn_yaw = base_yaw + float(yaw_off)
            ep_dict = {
                "pos": [start_pos.tolist(), start_pos.tolist()],
                "yaw": [spawn_yaw, spawn_yaw],
                "gpt_instruction": r_info.get("gpt_instruction", ""),
            }
            try:
                obs = env.reset(ep_dict)
            except Exception as exc:
                logger.warning("route %d yaw_off=%.1f° reset failed: %s", ep_idx, math.degrees(yaw_off), exc)
                results.append({
                    "route_idx": ep_idx,
                    "route_id": r_info.get("route_id"),
                    "source": r_info.get("source"),
                    "start_pos": start_pos.tolist(),
                    "yaw_rad": spawn_yaw,
                    "yaw_off_deg": math.degrees(yaw_off),
                    "spawn_err_m": None,
                    "hit": False,
                    "n_detections": 0,
                    "confidence": 0.0,
                    "snapshot": None,
                    "reset_error": str(exc),
                })
                continue
            p_curr = np.array(obs.position, dtype=np.float64)
            spawn_err = float(np.linalg.norm(p_curr - start_pos))
            if spawn_err > float(args.spawn_tol_m):
                logger.warning("route %d yaw_off=%.1f° spawn_err=%.1fm", ep_idx, math.degrees(yaw_off), spawn_err)

            rgb = getattr(obs, "rgb_yolo", None)
            if rgb is None:
                rgb = getattr(obs, "rgb", None)
            rgb_arr = np.asarray(rgb, dtype=np.uint8) if rgb is not None else None

            det = None
            n_det = 0
            if rgb_arr is not None:
                detect_all = getattr(detector, "detect_all", None)
                if callable(detect_all):
                    dets = detect_all(rgb_arr) or []
                    n_det = len(dets)
                    det = dets[0] if dets else None
                else:
                    det = detector.detect(rgb_arr)
                    n_det = 1 if det is not None else 0

            snap_path = None
            if rgb_arr is not None and cv2 is not None:
                snap_path = snap_dir / f"route{ep_idx:02d}_yaw{off_i:02d}.jpg"
                bgr = rgb_arr[:, :, ::-1].copy()
                if det is not None and hasattr(det, "bbox"):
                    u0, v0, u1, v1 = [int(x) for x in det.bbox]
                    cv2.rectangle(bgr, (u0, v0), (u1, v1), (0, 255, 0), 2)
                cv2.imwrite(str(snap_path), bgr)

            hit = det is not None
            conf = float(getattr(det, "confidence", 0.0) or 0.0) if det is not None else 0.0
            logger.info(
                "route %d (%s) yaw_off=%+.0f° hit=%s n=%d conf=%.2f spawn_err=%.1fm snap=%s",
                ep_idx, r_info.get("route_id", "?"), math.degrees(yaw_off),
                hit, n_det, conf, spawn_err, snap_path,
            )
            results.append({
                "route_idx": ep_idx,
                "route_id": r_info.get("route_id"),
                "source": r_info.get("source"),
                "start_pos": start_pos.tolist(),
                "yaw_rad": spawn_yaw,
                "yaw_off_deg": math.degrees(yaw_off),
                "spawn_err_m": spawn_err,
                "hit": hit,
                "n_detections": n_det,
                "confidence": conf,
                "snapshot": str(snap_path) if snap_path else None,
            })

    n_hit = sum(1 for r in results if r["hit"])
    summary = {
        "annotation": str(anno_path),
        "n_poses": len(results),
        "n_hit": n_hit,
        "hit_rate": float(n_hit / max(1, len(results))),
        "detector": args.detector,
        "target_class": args.target_class,
        "yaw_sweep_deg": args.yaw_sweep_deg,
        "results": results,
    }
    out_path = (root / args.out).resolve() if not Path(args.out).is_absolute() else Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info("Written %s | hit_rate=%.0f%% (%d/%d)", out_path, 100.0 * summary["hit_rate"], n_hit, len(results))
    return 0 if n_hit > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
