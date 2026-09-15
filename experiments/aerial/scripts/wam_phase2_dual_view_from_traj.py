#!/usr/bin/env python3
"""Render Phase-2 closed-loop trajectory as dual-view dashboard videos.

Replays flown poses in AirSim for photorealistic FPV, composites with a 3D
trajectory panel (same style as ``v4_record_route04_videos.py``).

Inputs:
  - ``long_route*_traj.json`` from ``wam_phase2_record_route.py``
  - or per-step JSONL from ``wam_phase2_long_eval.py --traj-out``

Outputs (under ``--out-dir``):
  - ``*_first_person_ego.mp4``
  - ``*_full_flight_path.mp4``
  - ``*_dual_view_dashboard.mp4``
  - ``*_trajectory_summary.json``
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

try:
    import airsim
except ImportError:
    airsim = None

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("phase2_dual_view")

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from v4_record_route04_videos import (  # noqa: E402
    Trajectory3DRenderer,
    _compose_dual_view,
    _draw_hud_overlay,
    _goal_dist,
    _write_video_ffmpeg,
)


def _write_video_cv2(frames: List[np.ndarray], out_path: Path, fps: float) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    h, w = frames[0].shape[:2]
    ww, hh = w - (w % 2), h - (h % 2)
    writer = cv2.VideoWriter(
        str(out_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        float(fps),
        (ww, hh),
    )
    if not writer.isOpened():
        raise RuntimeError(f"cv2.VideoWriter failed for {out_path}")
    for fr in frames:
        writer.write(np.ascontiguousarray(fr[:hh, :ww, :3], dtype=np.uint8))
    writer.release()
    logger.info("Wrote %d frames → %s (cv2/mp4v)", len(frames), out_path)


def _encode_video(frames: List[np.ndarray], out_path: Path, fps: float) -> None:
    if shutil.which("ffmpeg"):
        _write_video_ffmpeg(frames, out_path, fps=fps)
    else:
        logger.warning("ffmpeg not found; using OpenCV mp4v encoder")
        _write_video_cv2(frames, out_path, fps=fps)


def _yaws_from_path(pos: np.ndarray) -> np.ndarray:
    pos = np.asarray(pos, dtype=np.float64).reshape(-1, 3)
    yaws = np.zeros(len(pos), dtype=np.float64)
    for i in range(len(pos)):
        if i + 1 < len(pos):
            d = pos[i + 1] - pos[i]
        elif i > 0:
            d = pos[i] - pos[i - 1]
        else:
            d = np.array([1.0, 0.0, 0.0], dtype=np.float64)
        n = float(np.linalg.norm(d[:2]))
        yaws[i] = math.atan2(d[1], d[0]) if n > 1e-4 else 0.0
    return yaws


def _load_traj(
    traj_json: Optional[Path],
    traj_jsonl: Optional[Path],
) -> Tuple[np.ndarray, np.ndarray, int, Dict[str, Any]]:
    meta: Dict[str, Any] = {}
    if traj_json is not None:
        data = json.loads(traj_json.read_text(encoding="utf-8"))
        ref = np.asarray(data["ref_polyline"], dtype=np.float64).reshape(-1, 3)
        flown = np.asarray(data["flown"], dtype=np.float64).reshape(-1, 3)
        route_idx = int(data.get("route_idx", 0))
        meta.update(data)
        return ref, flown, route_idx, meta

    if traj_jsonl is None:
        raise ValueError("need --traj-json or --traj-jsonl")

    rows: List[Dict[str, Any]] = []
    for line in traj_jsonl.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    if not rows:
        raise ValueError(f"empty traj jsonl: {traj_jsonl}")

    flown = np.asarray([r["pos"] for r in rows], dtype=np.float64).reshape(-1, 3)
    yaws_deg = [r.get("yaw_deg") for r in rows]
    meta["intervened_steps"] = {int(r["step"]) for r in rows if r.get("intervened")}
    meta["yaws_deg"] = yaws_deg
    route_idx = 0
    ref = flown.copy()
    return ref, flown, route_idx, meta


def _route_from_annotation(data: Any, route_idx: int) -> Dict[str, Any]:
    if isinstance(data, dict):
        for key in ("routes", "episodes"):
            items = data.get(key)
            if isinstance(items, list):
                for item in items:
                    if int(item.get("route_idx", -1)) == int(route_idx):
                        return item
                if 0 <= int(route_idx) < len(items):
                    return items[int(route_idx)]
    raise KeyError(f"route_idx {route_idx} not found in annotation")


def _subsample_indices(n: int, target_fps: float, source_hz: float) -> List[int]:
    if n <= 1:
        return [0]
    stride = max(1, int(round(source_hz / max(target_fps, 0.1))))
    idx = list(range(0, n, stride))
    if idx[-1] != n - 1:
        idx.append(n - 1)
    return idx


def main() -> int:
    p = argparse.ArgumentParser(description="Phase-2 dual-view video from flown trajectory")
    p.add_argument("--traj-json", type=Path, default=None)
    p.add_argument("--traj-jsonl", type=Path, default=None)
    p.add_argument("--route-label", default=None, help="HUD title, e.g. PHASE-2 ROUTE 08")
    p.add_argument("--map-title", default=None, help="3D panel header")
    p.add_argument("--plan-mode", choices=("toward_g", "polyline"), default="toward_g")
    p.add_argument("--ref-polyline-json", type=Path, default=None, help="Override ref path")
    p.add_argument(
        "--route-idx",
        type=int,
        default=None,
        help="0-based route index when loading ref from annotation (jsonl default 0)",
    )
    p.add_argument("--out-dir", default="artifacts/videos/wam_phase2_route08_dual")
    p.add_argument("--out-prefix", default=None, help="Output filename prefix")
    p.add_argument("--fps", type=float, default=5.0)
    p.add_argument("--source-hz", type=float, default=5.0, help="Closed-loop control rate")
    p.add_argument("--airsim-host", default="127.0.0.1")
    p.add_argument("--ego-width", type=int, default=640)
    p.add_argument("--ego-height", type=int, default=480)
    p.add_argument("--pad-seconds", type=float, default=2.0)
    p.add_argument("--skip-airsim", action="store_true", help="Synthetic FPV placeholder")
    args = p.parse_args()

    if args.traj_json is None and args.traj_jsonl is None:
        p.error("one of --traj-json or --traj-jsonl is required")

    root = Path(__file__).resolve().parents[3]
    out_dir = (root / args.out_dir).resolve() if not Path(args.out_dir).is_absolute() else Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    traj_json = None
    if args.traj_json is not None:
        traj_json = (
            (root / args.traj_json).resolve()
            if not args.traj_json.is_absolute()
            else args.traj_json
        )
    traj_jsonl = None
    if args.traj_jsonl is not None:
        traj_jsonl = (
            (root / args.traj_jsonl).resolve()
            if not args.traj_jsonl.is_absolute()
            else args.traj_jsonl
        )

    ref, flown, route_idx, meta = _load_traj(traj_json, traj_jsonl)
    if args.route_idx is not None:
        route_idx = int(args.route_idx)
    if args.ref_polyline_json is not None:
        ref_path = (
            (root / args.ref_polyline_json).resolve()
            if not args.ref_polyline_json.is_absolute()
            else args.ref_polyline_json
        )
        ref_data = json.loads(ref_path.read_text(encoding="utf-8"))
        if isinstance(ref_data, dict) and "ref_polyline" in ref_data:
            ref = np.asarray(ref_data["ref_polyline"], dtype=np.float64)
        elif isinstance(ref_data, list):
            ref = np.asarray(ref_data, dtype=np.float64)
        else:
            r0 = _route_from_annotation(ref_data, route_idx)
            ref = np.asarray(r0.get("pos", r0.get("positions")), dtype=np.float64)

    start_pos = ref[0].copy()
    goal_pos = ref[-1].copy()
    d0_m = _goal_dist(start_pos, goal_pos)
    d_end = _goal_dist(flown[-1], goal_pos)
    arrived = bool(d_end <= 3.0)

    yaws = _yaws_from_path(flown)
    if meta.get("yaws_deg"):
        for i, yd in enumerate(meta["yaws_deg"]):
            if yd is not None and i < len(yaws):
                # AirSim often reports yaw≈0 for long straight segments; overwriting
                # path tangent yaw makes FPV replay look like violent shaking.
                if abs(float(yd)) > 0.5:
                    yaws[i] = math.radians(float(yd))

    route_label = args.route_label or f"PHASE-2 ROUTE {route_idx + 1:02d}"
    map_title = args.map_title or f"{route_label} : 3D TRAJECTORY"
    prefix = args.out_prefix or f"phase2_route{route_idx + 1:02d}"
    ref_plan_label = (
        "ACTIVE PLAN (polyline carrot)" if args.plan_mode == "polyline"
        else "CORRIDOR REF (inactive under toward_g)"
    )

    frame_idx = _subsample_indices(len(flown), float(args.fps), float(args.source_hz))
    logger.info(
        "flown=%d frames=%d d0=%.1fm d_end=%.2fm arrived=%s",
        len(flown),
        len(frame_idx),
        d0_m,
        d_end,
        arrived,
    )

    client = None
    if not args.skip_airsim and airsim is not None:
        try:
            client = airsim.MultirotorClient(ip=args.airsim_host)
            client.confirmConnection()
            client.enableApiControl(True)
            logger.info("AirSim connected at %s", args.airsim_host)
        except Exception as exc:
            logger.warning("AirSim unavailable (%s); using placeholder FPV", exc)
            client = None

    raw_ego: List[np.ndarray] = []
    for fi, i in enumerate(frame_idx):
        pos = flown[i]
        yaw = float(yaws[i])
        if client is not None:
            q = airsim.to_quaternion(0.0, 0.0, yaw)
            p_ned = airsim.Vector3r(float(pos[0]), float(pos[1]), float(-pos[2]))
            client.simSetVehiclePose(airsim.Pose(p_ned, q), ignore_collision=True)
            time.sleep(0.02)
            rq = [airsim.ImageRequest("front_center", airsim.ImageType.Scene, False, False)]
            rs = client.simGetImages(rq)
            if rs and rs[0].width > 0:
                raw = np.frombuffer(rs[0].image_data_uint8, dtype=np.uint8).reshape(
                    rs[0].height, rs[0].width, 3
                )
                raw_bgr = cv2.resize(raw, (int(args.ego_width), int(args.ego_height)))
            else:
                raw_bgr = np.full((int(args.ego_height), int(args.ego_width), 3), (30, 40, 55), np.uint8)
        else:
            raw_bgr = np.full((int(args.ego_height), int(args.ego_width), 3), (30, 40, 55), np.uint8)
        raw_ego.append(raw_bgr)
        if fi % 50 == 0:
            logger.info("AirSim capture %d/%d step=%d", fi + 1, len(frame_idx), i)

    if client is not None:
        try:
            client.enableApiControl(False)
        except Exception:
            pass

    renderer = Trajectory3DRenderer(start_pos, goal_pos, ref, out_size=(960, 720))
    intervened = meta.get("intervened_steps", set())

    ego_frames: List[np.ndarray] = []
    map_frames: List[np.ndarray] = []
    dual_frames: List[np.ndarray] = []

    for fi, i in enumerate(frame_idx):
        pos = flown[i]
        yaw = float(yaws[i])
        curr_dist = _goal_dist(pos, goal_pos)
        curr_prog = (d0_m - curr_dist) / max(d0_m, 1e-3)
        is_arr = curr_dist <= 3.0
        is_interv = int(i) in intervened

        act = None
        if fi > 0:
            prev_i = frame_idx[fi - 1]
            dp = flown[i] - flown[prev_i]
            cy, sy = math.cos(yaw), math.sin(yaw)
            act = np.array([dp[0] * cy + dp[1] * sy, -dp[0] * sy + dp[1] * cy, dp[2], yaws[i] - yaws[prev_i]])

        ego_hud = _draw_hud_overlay(
            bgr=raw_ego[fi],
            step=i + 1,
            total_steps=len(flown),
            dist_m=curr_dist,
            d0_m=d0_m,
            progress_ratio=curr_prog,
            pos=pos,
            yaw_rad=yaw,
            action=act,
            arrived=is_arr,
            shield_interv=is_interv,
            route_title=route_label,
        )
        ego_frames.append(ego_hud)

        sub_traj = flown[: i + 1]
        map_3d = renderer.render_frame(
            flown_so_far=sub_traj,
            full_traj=flown,
            step=i + 1,
            total_steps=len(flown),
            dist_m=curr_dist,
            d0_m=d0_m,
            prog_ratio=curr_prog,
            map_title=map_title,
            start_label=f"START ({d0_m:.1f}m)",
        )
        cv2.putText(
            map_3d, ref_plan_label, (18, 64),
            cv2.FONT_HERSHEY_SIMPLEX, 0.38,
            (120, 220, 180) if args.plan_mode == "polyline" else (120, 140, 160),
            1, cv2.LINE_AA,
        )
        map_frames.append(map_3d)
        dual_frames.append(_compose_dual_view(ego_hud, map_3d, out_size=(1920, 720)))

    pad = int(float(args.pad_seconds) * float(args.fps))
    for _ in range(pad):
        ego_frames.append(ego_frames[-1])
        map_frames.append(map_frames[-1])
        dual_frames.append(dual_frames[-1])

    ego_mp4 = out_dir / f"{prefix}_first_person_ego.mp4"
    path_mp4 = out_dir / f"{prefix}_full_flight_path.mp4"
    dual_mp4 = out_dir / f"{prefix}_dual_view_dashboard.mp4"
    summary_json = out_dir / f"{prefix}_trajectory_summary.json"

    logger.info("Encoding videos...")
    _encode_video(ego_frames, ego_mp4, fps=float(args.fps))
    _encode_video(map_frames, path_mp4, fps=float(args.fps))
    _encode_video(dual_frames, dual_mp4, fps=float(args.fps))

    summary = {
        "route_label": route_label,
        "route_idx": int(route_idx),
        "protocol": "phase2_toward_g_closed_loop_replay",
        "start_pos": [float(x) for x in start_pos],
        "goal_pos": [float(x) for x in goal_pos],
        "initial_distance_m": float(d0_m),
        "final_distance_m": float(d_end),
        "n_flown_steps": int(len(flown)),
        "n_video_frames": int(len(frame_idx)),
        "progress_ratio": float((d0_m - d_end) / max(d0_m, 1e-3)),
        "arrived": bool(arrived),
        "fps": float(args.fps),
        "duration_seconds": float(len(ego_frames) / float(args.fps)),
        "videos": {
            "first_person_ego": str(ego_mp4),
            "full_flight_path": str(path_mp4),
            "dual_view_dashboard": str(dual_mp4),
        },
        "traj_source": str(traj_json or traj_jsonl),
    }
    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info("Done → %s", dual_mp4)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
