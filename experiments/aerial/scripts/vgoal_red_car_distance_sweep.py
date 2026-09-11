#!/usr/bin/env python3
"""Ring sweep around a known red-car world position for open-vocab perception.

Places the drone on horizontal rings at configurable standoffs / bearings / heights,
scores YOLO-World ``red car`` detections vs projected car center, and writes:
  - full pose report with per-distance-bin recall
  - Tier-A flight annotation (aligned hits in 10–25 m band)
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import yaml

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("vgoal_red_car_distance_sweep")

# Route-0 vision lock @ step 129 (xy) + outdoor ground z (~0.77 m).
DEFAULT_CAR_WORLD = (-1251.940, 62.520, 0.770)


def _capture_wh(capture_w: Optional[int], capture_h: Optional[int]) -> Tuple[int, int]:
    if capture_w is not None and capture_h is not None:
        return int(capture_w), int(capture_h)
    try:
        from experiments.aerial.rl.capture_config import aerial_capture_wh

        return aerial_capture_wh()
    except ImportError:
        w = int(os.environ.get("AERIAL_CAPTURE_W", os.environ.get("INDOOR_CAPTURE_W", "1920")))
        h = int(os.environ.get("AERIAL_CAPTURE_H", os.environ.get("INDOOR_CAPTURE_H", "1080")))
        return w, h


def _yolo_defaults(model: Optional[str], imgsz: Optional[int]) -> Tuple[str, int]:
    try:
        from experiments.aerial.rl.capture_config import aerial_yolo_imgsz, aerial_yolo_model

        return (
            str(model or aerial_yolo_model()),
            int(imgsz if imgsz is not None else aerial_yolo_imgsz()),
        )
    except ImportError:
        return (
            str(model or os.environ.get("AERIAL_YOLO_MODEL", "yolov8m-worldv2.pt")),
            int(imgsz if imgsz is not None else os.environ.get("AERIAL_YOLO_IMGSZ", "640")),
        )


def _parse_floats(csv: str) -> List[float]:
    return [float(x) for x in str(csv).split(",") if x.strip()]


def _parse_vec3(text: str) -> np.ndarray:
    parts = [float(x) for x in str(text).split(",") if x.strip()]
    if len(parts) != 3:
        raise ValueError(f"expected x,y,z got: {text}")
    return np.array(parts, dtype=np.float64)


def ring_poses(
    car_world: np.ndarray,
    *,
    standoffs_m: Sequence[float],
    bearings_deg: Sequence[float],
    heights_m: Sequence[float],
    yaw_offsets_deg: Sequence[float],
    yaw_mode: str = "face_car",
    reference_yaw_rad: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Generate hover poses on horizontal rings around ``car_world``.

    ``yaw_mode=face_car``: drone yaws toward car center (level camera).
    ``yaw_mode=reference``: keep ``reference_yaw_rad`` (+ offsets) — matches a
    known-good spawn heading (e.g. route0 red-car probe at -90°).
    """
    car = np.asarray(car_world, dtype=np.float64).reshape(3)
    out: List[Dict[str, Any]] = []
    for standoff in standoffs_m:
        for bearing_deg in bearings_deg:
            br = math.radians(float(bearing_deg))
            dx = float(standoff) * math.cos(br)
            dy = float(standoff) * math.sin(br)
            for z in heights_m:
                pos_xy = car[:2] + np.array([dx, dy], dtype=np.float64)
                face_yaw = math.atan2(float(car[1] - pos_xy[1]), float(car[0] - pos_xy[0]))
                for yaw_off_deg in yaw_offsets_deg:
                    if str(yaw_mode).lower() in ("reference", "spawn", "fixed"):
                        if reference_yaw_rad is None:
                            raise ValueError("reference_yaw_rad required for yaw_mode=reference")
                        yaw = float(reference_yaw_rad + math.radians(float(yaw_off_deg)))
                    else:
                        yaw = float(face_yaw + math.radians(float(yaw_off_deg)))
                    pos = np.array([pos_xy[0], pos_xy[1], float(z)], dtype=np.float64)
                    horiz = float(np.linalg.norm(pos[:2] - car[:2]))
                    dist3 = float(np.linalg.norm(pos - car))
                    out.append(
                        {
                            "standoff_m": round(float(standoff), 3),
                            "bearing_deg": round(float(bearing_deg), 3),
                            "height_z": round(float(z), 3),
                            "yaw_off_deg": round(float(yaw_off_deg), 3),
                            "yaw_mode": str(yaw_mode),
                            "pos": [round(float(x), 3) for x in pos],
                            "yaw_rad": yaw,
                            "face_yaw_rad": face_yaw,
                            "horiz_dist_m": round(horiz, 3),
                            "dist_3d_m": round(dist3, 3),
                        }
                    )
    return out


def _auto_yaw_at_pos(
    env: Any,
    detector: Any,
    pos: np.ndarray,
    base_yaw: float,
    *,
    sweep_deg: float = 60.0,
    step_deg: float = 5.0,
    min_conf: float = 0.05,
) -> Tuple[float, float, int]:
    """Return (best_yaw_rad, best_conf, n_dets) via coarse yaw sweep at fixed pos."""
    best_yaw = float(base_yaw)
    best_conf = 0.0
    best_n = 0
    half = float(sweep_deg)
    step = max(float(step_deg), 1.0)
    n_steps = int(math.ceil((2.0 * half) / step))
    for i in range(n_steps + 1):
        off_deg = -half + i * step
        yaw = float(base_yaw + math.radians(off_deg))
        obs = env.reset({"pos": [pos.tolist(), pos.tolist()], "yaw": [yaw, yaw]})
        rgb = getattr(obs, "rgb_yolo", None)
        if rgb is None:
            rgb = getattr(obs, "rgb", None)
        if rgb is None:
            continue
        rgb_arr = np.asarray(rgb, dtype=np.uint8)
        dets = list(getattr(detector, "detect_all", lambda _: [])(rgb_arr) or [])
        if not dets:
            continue
        top = max(dets, key=lambda d: float(getattr(d, "confidence", 0.0) or 0.0))
        conf = float(getattr(top, "confidence", 0.0) or 0.0)
        if conf >= best_conf:
            best_conf = conf
            best_yaw = yaw
            best_n = len(dets)
    if best_conf < float(min_conf):
        return float(base_yaw), best_conf, best_n
    return best_yaw, best_conf, best_n


def _load_asset_hit(path: Path, rank: int) -> Dict[str, Any]:
    """Load the Nth-best hit from ``vgoal_red_car_asset`` report (0 = top conf)."""
    data = json.loads(path.expanduser().read_text(encoding="utf-8"))
    hits = [h for h in data.get("hits", []) if h.get("hit")]
    if not hits:
        raise ValueError(f"no hits in asset report: {path}")
    hits.sort(key=lambda h: (-float(h.get("confidence", 0.0) or 0.0), str(h.get("source_route_id", ""))))
    if not 0 <= int(rank) < len(hits):
        raise IndexError(f"anchor hit rank {rank} out of range ({len(hits)} hits)")
    hit = hits[int(rank)]
    pos = np.array(hit["pos"], dtype=np.float64).reshape(3)
    yaw = float(hit["yaw_rad"])
    return {
        "pos": pos,
        "yaw_rad": yaw,
        "confidence": float(hit.get("confidence", 0.0) or 0.0),
        "yaw_off_deg": float(hit.get("yaw_off_deg", 0.0) or 0.0),
        "source": (
            f"{hit.get('source_route_id')} wp{hit.get('waypoint_idx')} "
            f"yaw_off={hit.get('yaw_off_deg')} conf={hit.get('confidence')}"
        ),
        "hit": hit,
    }


def anchor_perturb_poses(
    anchor_pos: np.ndarray,
    anchor_yaw: float,
    *,
    fwd_jitter_m: Sequence[float],
    lat_jitter_m: Sequence[float],
    z_jitter_m: Sequence[float],
    yaw_jitter_deg: Sequence[float],
) -> List[Dict[str, Any]]:
    """Micro-perturb a known-good asset hit in body frame (+fwd, +left, +up)."""
    base = np.asarray(anchor_pos, dtype=np.float64).reshape(3)
    c0, s0 = math.cos(float(anchor_yaw)), math.sin(float(anchor_yaw))
    out: List[Dict[str, Any]] = []
    for df in fwd_jitter_m:
        for dl in lat_jitter_m:
            for dz in z_jitter_m:
                for yaw_off_deg in yaw_jitter_deg:
                    offset = np.array(
                        [
                            float(c0 * df - s0 * dl),
                            float(s0 * df + c0 * dl),
                            float(dz),
                        ],
                        dtype=np.float64,
                    )
                    pos = base + offset
                    yaw = float(anchor_yaw + math.radians(float(yaw_off_deg)))
                    jitter_norm = float(math.sqrt(df * df + dl * dl + dz * dz))
                    out.append(
                        {
                            "sweep_mode": "anchor",
                            "anchor_fwd_m": round(float(df), 3),
                            "anchor_lat_m": round(float(dl), 3),
                            "anchor_dz_m": round(float(dz), 3),
                            "anchor_jitter_m": round(jitter_norm, 3),
                            "yaw_off_deg": round(float(yaw_off_deg), 3),
                            "standoff_m": round(jitter_norm, 3),
                            "bearing_deg": 0.0,
                            "height_z": round(float(pos[2]), 3),
                            "yaw_mode": "anchor",
                            "pos": [round(float(x), 3) for x in pos],
                            "yaw_rad": yaw,
                            "horiz_dist_m": round(float(np.linalg.norm(pos[:2] - base[:2])), 3),
                            "dist_3d_m": round(float(np.linalg.norm(pos - base)), 3),
                        }
                    )
    return out


def _reference_from_annotation(path: Path, route_idx: int) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    routes = data.get("routes", data)
    route = routes[int(route_idx)]
    pos = np.array(route["pos"][0], dtype=np.float64)
    yaw = float(route["yaw"][0])
    return {"pos": pos, "yaw_rad": yaw, "route": route}


def _project_car(
    car_world: np.ndarray,
    pos: np.ndarray,
    yaw: float,
    intrinsics: Any,
    car_width_m: float,
) -> Dict[str, Any]:
    from vgoal.geometry import project_3d_to_pixel

    c, s = math.cos(float(yaw)), math.sin(float(yaw))
    d_world = np.asarray(car_world, dtype=np.float64).reshape(3) - np.asarray(pos, dtype=np.float64).reshape(3)
    d_fwd = float(c * d_world[0] + s * d_world[1])
    d_left = float(-s * d_world[0] + c * d_world[1])
    d_up = float(d_world[2])
    dist3 = float(np.linalg.norm(d_world))
    horiz = float(np.linalg.norm(d_world[:2]))
    rec: Dict[str, Any] = {
        "cart_in_fov": False,
        "exp_bbox_w_px": 0.0,
        "cart_u": None,
        "cart_v": None,
        "d_fwd_m": round(d_fwd, 3),
        "horiz_dist_m": round(horiz, 3),
        "dist_3d_m": round(dist3, 3),
    }
    if d_fwd <= 0.5:
        return rec
    cu, cv, _z = project_3d_to_pixel([d_fwd, d_left, d_up], intrinsics)
    in_fov = 0 <= cu < intrinsics.width and 0 <= cv < intrinsics.height
    rec["cart_in_fov"] = bool(in_fov)
    if in_fov:
        rec["cart_u"] = round(float(cu), 2)
        rec["cart_v"] = round(float(cv), 2)
        rec["exp_bbox_w_px"] = round(float(intrinsics.fx) * float(car_width_m) / max(d_fwd, 1.0), 2)
    return rec


def _pix_offset(det: Any, cart_u: float, cart_v: float) -> float:
    bb = [float(x) for x in det.bbox]
    cu = 0.5 * (bb[0] + bb[2])
    cv = 0.5 * (bb[1] + bb[3])
    return float(math.hypot(cu - cart_u, cv - cart_v))


def _pick_det(
    dets: List[Any],
    *,
    cart_in_fov: bool,
    cart_u: Optional[float],
    cart_v: Optional[float],
) -> Tuple[Optional[Any], Optional[float], str]:
    if not dets:
        return None, None, "none"
    if cart_in_fov and cart_u is not None and cart_v is not None:
        best = None
        best_pix = float("inf")
        for det in dets:
            pix = _pix_offset(det, cart_u, cart_v)
            if pix < best_pix:
                best_pix = pix
                best = det
        return best, best_pix, "pix"
    best = max(dets, key=lambda d: float(getattr(d, "confidence", 0.0) or 0.0))
    return best, None, "conf"


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, np.ndarray):
        return [round(float(x), 6) for x in obj.reshape(-1)]
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        return round(float(obj), 6)
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    return obj


def _summarize_anchor(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(rows)
    raw = [r for r in rows if r.get("hit_raw")]
    aligned = [r for r in rows if r.get("hit_aligned")]
    best = max(rows, key=lambda r: float(r.get("yolo_conf") or 0.0)) if rows else None
    return {
        "n": n,
        "hit_raw": len(raw),
        "hit_aligned": len(aligned),
        "recall_raw": round(len(raw) / n, 4) if n else 0.0,
        "recall_aligned": round(len(aligned) / n, 4) if n else 0.0,
        "best_conf": float(best.get("yolo_conf") or 0.0) if best else 0.0,
        "best_pose": _json_safe(best) if best else None,
    }


def _summarize_by_standoff(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    bins: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        key = f"{float(row['standoff_m']):.0f}"
        bins.setdefault(key, []).append(row)
    out: Dict[str, Dict[str, Any]] = {}
    for key, group in sorted(bins.items(), key=lambda kv: float(kv[0])):
        n = len(group)
        out[key] = {
            "n": n,
            "hit_raw": sum(1 for r in group if r.get("hit_raw")),
            "hit_aligned": sum(1 for r in group if r.get("hit_aligned")),
            "hit_strong": sum(1 for r in group if r.get("hit_strong")),
            "recall_raw": round(sum(1 for r in group if r.get("hit_raw")) / n, 4),
            "recall_aligned": round(sum(1 for r in group if r.get("hit_aligned")) / n, 4),
            "recall_strong": round(sum(1 for r in group if r.get("hit_strong")) / n, 4),
            "median_conf": round(
                float(np.median([r["yolo_conf"] for r in group if r.get("yolo_conf") is not None] or [0.0])),
                4,
            ),
            "median_pix_offset_px": round(
                float(
                    np.median(
                        [r["pix_offset_px"] for r in group if r.get("pix_offset_px") is not None] or [float("nan")]
                    )
                ),
                2,
            )
            if any(r.get("pix_offset_px") is not None for r in group)
            else None,
        }
    return out


def _car_world_from_traj(traj_path: Path, step: int) -> np.ndarray:
    """Recover locked vision target xyz from a traj JSONL row (yaw=0 if missing)."""
    rows = [
        json.loads(line)
        for line in traj_path.expanduser().read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    row = next((r for r in rows if int(r.get("step", -1)) == int(step)), None)
    if row is None:
        raise ValueError(f"step {step} not found in {traj_path}")
    gr = row.get("goal_rel")
    if not gr or len(gr) < 3:
        raise ValueError(f"step {step} has no goal_rel in {traj_path}")
    pos = np.asarray(row["pos"], dtype=np.float64).reshape(3)
    yaw = float(row.get("yaw") or 0.0)
    g = np.asarray(gr[:3], dtype=np.float64)
    c, s = math.cos(yaw), math.sin(yaw)
    return pos + np.array([c * g[0] - s * g[1], s * g[0] + c * g[1], g[2]], dtype=np.float64)


def _resolve_car_world(
    env: Any,
    car_world_arg: Optional[str],
    car_world_file: Optional[str],
    car_ground_z: Optional[float],
    traj_path: Optional[str],
    traj_step: int,
) -> np.ndarray:
    if traj_path:
        car = _car_world_from_traj(Path(traj_path), int(traj_step))
        if car_ground_z is not None:
            car[2] = float(car_ground_z)
        return car
    if car_world_file:
        data = json.loads(Path(car_world_file).expanduser().read_text(encoding="utf-8"))
        if "car_world" in data:
            car = np.array(data["car_world"], dtype=np.float64)
            if car_ground_z is not None:
                car[2] = float(car_ground_z)
            return car
    if car_world_arg:
        car = _parse_vec3(car_world_arg)
        if car_ground_z is not None:
            car[2] = float(car_ground_z)
        return car
    car = np.array(DEFAULT_CAR_WORLD, dtype=np.float64)
    if car_ground_z is not None:
        car[2] = float(car_ground_z)
    return car


def main() -> int:
    parser = argparse.ArgumentParser(description="Red-car distance ring sweep (static hover)")
    parser.add_argument("--config", default="configs/aerial_rl.yaml")
    parser.add_argument("--vgoal-repo", default="~/aerial-vgoal-wam")
    parser.add_argument(
        "--car-world",
        default=None,
        help=f"Target xyz (default {','.join(str(x) for x in DEFAULT_CAR_WORLD)})",
    )
    parser.add_argument("--car-world-file", default=None, help="JSON with car_world [x,y,z]")
    parser.add_argument(
        "--car-ground-z",
        type=float,
        default=None,
        help="Override car z for projection (default: keep car_world z)",
    )
    parser.add_argument(
        "--from-traj",
        default=None,
        help="Traj JSONL; use goal_rel at --traj-step for car xy (optional --car-ground-z)",
    )
    parser.add_argument("--traj-step", type=int, default=129)
    parser.add_argument(
        "--sweep-mode",
        choices=("ring", "anchor"),
        default="ring",
        help="ring=car-centered rings; anchor=micro-perturb around asset hit",
    )
    parser.add_argument(
        "--anchor-asset-report",
        default="artifacts/red_car_asset_report_1080m.json",
        help="Asset report from vgoal_red_car_asset.py (anchor mode)",
    )
    parser.add_argument("--anchor-hit-rank", type=int, default=0, help="0=best conf hit")
    parser.add_argument("--anchor-fwd-jitter-m", default="-3,-2,-1,0,1,2,3")
    parser.add_argument("--anchor-lat-jitter-m", default="-2,-1,0,1,2")
    parser.add_argument("--anchor-z-jitter-m", default="-1,0,1")
    parser.add_argument("--anchor-yaw-jitter-deg", default="-15,-10,-5,0,5,10,15")
    parser.add_argument(
        "--anchor-yaw-deg",
        type=float,
        default=None,
        help="Override anchor yaw (degrees); default uses asset hit yaw_rad",
    )
    parser.add_argument(
        "--anchor-auto-yaw",
        action="store_true",
        help="Coarse yaw sweep at anchor pos before micro perturb (scene drift)",
    )
    parser.add_argument("--anchor-auto-yaw-sweep-deg", type=float, default=60.0)
    parser.add_argument("--anchor-auto-yaw-step-deg", type=float, default=5.0)
    parser.add_argument("--standoffs-m", default="10,15,20,25,30,40,50")
    parser.add_argument("--tier-c-standoffs-m", default="80,100,120", help="Extra far ring (pressure test)")
    parser.add_argument("--include-tier-c", action="store_true")
    parser.add_argument("--bearings-deg", default="0,30,60,90,120,150,180,210,240,270,300,330")
    parser.add_argument("--heights-m", default="18,20,22")
    parser.add_argument("--yaw-offsets-deg", default="0", help="Extra yaw offsets per pose (comma sep)")
    parser.add_argument(
        "--yaw-mode",
        choices=("face_car", "reference"),
        default="reference",
        help="face_car=yaw toward car; reference=keep probe heading (recommended for red-car poster)",
    )
    parser.add_argument(
        "--reference-annotation",
        default="experiments/aerial/phase2-vgoal/airsim16_red_car_spawn_probe_1080m.json",
        help="Known-good spawn annotation (route yaw copied when yaw_mode=reference)",
    )
    parser.add_argument("--reference-route-idx", type=int, default=0)
    parser.add_argument(
        "--fixed-bearing-deg",
        type=float,
        default=None,
        help="If set, only sweep this bearing (degrees, car→drone)",
    )
    parser.add_argument("--visual-prompt", default="red car")
    parser.add_argument("--yolo-model", default=None)
    parser.add_argument("--yolo-conf", type=float, default=0.12)
    parser.add_argument("--yolo-imgsz", type=int, default=None)
    parser.add_argument("--yolo-device", default="cuda")
    parser.add_argument("--capture-w", type=int, default=None)
    parser.add_argument("--capture-h", type=int, default=None)
    parser.add_argument("--camera-fov-deg", type=float, default=80.0)
    parser.add_argument("--car-width-m", type=float, default=2.0)
    parser.add_argument("--min-conf", type=float, default=0.12)
    parser.add_argument("--min-yolo-bbox-px", type=float, default=24.0)
    parser.add_argument("--max-pix-offset-px", type=float, default=60.0)
    parser.add_argument("--min-exp-bbox-px", type=float, default=40.0)
    parser.add_argument("--tier-a-max-standoff-m", type=float, default=25.0)
    parser.add_argument("--tier-a-min-standoff-m", type=float, default=10.0)
    parser.add_argument("--snapshot-dir", default="artifacts/red_car_distance_sweep_snapshots")
    parser.add_argument("--save-snapshots", choices=("hits", "all", "none"), default="hits")
    parser.add_argument("--out-report", default="artifacts/red_car_distance_sweep_report.json")
    parser.add_argument(
        "--out-annotation",
        default="experiments/aerial/phase2-vgoal/airsim16_red_car_distance_tier_a.json",
    )
    parser.add_argument("--max-annotation-routes", type=int, default=20)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    vgoal_repo = Path(args.vgoal_repo).expanduser().resolve()
    if not vgoal_repo.is_dir():
        raise SystemExit(f"--vgoal-repo not found: {vgoal_repo}")
    if str(vgoal_repo) not in sys.path:
        sys.path.insert(0, str(vgoal_repo))

    from experiments.aerial.rl.train_rl import _build_env
    from experiments.aerial.scripts.wam_vgoal_eval import _build_detector
    from vgoal.geometry import CameraIntrinsics

    cap_w, cap_h = _capture_wh(args.capture_w, args.capture_h)
    yolo_model, yolo_imgsz = _yolo_defaults(args.yolo_model, args.yolo_imgsz)

    standoffs = _parse_floats(args.standoffs_m)
    if args.include_tier_c:
        standoffs = standoffs + [s for s in _parse_floats(args.tier_c_standoffs_m) if s not in standoffs]
    bearings = _parse_floats(args.bearings_deg)
    heights = _parse_floats(args.heights_m)
    yaw_offs = _parse_floats(args.yaw_offsets_deg)

    cfg_file = (root / args.config).resolve()
    cfg = yaml.safe_load(cfg_file.read_text(encoding="utf-8")) if cfg_file.is_file() else {}
    env_cfg = dict(cfg.get("env") or {})
    env_cfg.update(
        backend="airsim",
        step_hz=5.0,
        grab_depth=False,
        health_check=False,
        fanout_rgb=True,
        width=cap_w,
        height=cap_h,
        wam_encode_size=224,
    )
    env = _build_env(env_cfg)

    car_world = _resolve_car_world(
        env,
        args.car_world,
        args.car_world_file,
        args.car_ground_z,
        args.from_traj,
        int(args.traj_step),
    )
    logger.info("Red car world position: [%.3f, %.3f, %.3f]", car_world[0], car_world[1], car_world[2])

    anchor_meta: Optional[Dict[str, Any]] = None
    if str(args.sweep_mode).lower() == "anchor":
        asset_path = (root / args.anchor_asset_report).resolve()
        if not asset_path.is_file():
            raise SystemExit(f"--anchor-asset-report not found: {asset_path}")
        anchor_meta = _load_asset_hit(asset_path, int(args.anchor_hit_rank))
        anchor_yaw = (
            math.radians(float(args.anchor_yaw_deg))
            if args.anchor_yaw_deg is not None
            else float(anchor_meta["yaw_rad"])
        )
        logger.info(
            "Anchor hit rank %d: %s | pos=%s yaw=%.1f°",
            int(args.anchor_hit_rank),
            anchor_meta["source"],
            [round(float(x), 2) for x in anchor_meta["pos"]],
            math.degrees(anchor_yaw),
        )
    else:
        reference_yaw_rad: Optional[float] = None
        ref_anno_path = (root / args.reference_annotation).resolve() if args.reference_annotation else None
        if str(args.yaw_mode).lower() == "reference":
            if not ref_anno_path or not ref_anno_path.is_file():
                raise SystemExit(f"--reference-annotation not found: {ref_anno_path}")
            ref = _reference_from_annotation(ref_anno_path, int(args.reference_route_idx))
            reference_yaw_rad = float(ref["yaw_rad"])
            logger.info(
                "Reference route %d yaw=%.1f° pos=%s",
                int(args.reference_route_idx),
                math.degrees(reference_yaw_rad),
                [round(float(x), 2) for x in ref["pos"]],
            )
            if args.fixed_bearing_deg is None:
                br = math.degrees(
                    math.atan2(float(ref["pos"][1] - car_world[1]), float(ref["pos"][0] - car_world[0]))
                )
                bearings = [br]
                logger.info("Auto fixed bearing from reference spawn: %.1f°", br)

        if args.fixed_bearing_deg is not None:
            bearings = [float(args.fixed_bearing_deg)]

        candidates = ring_poses(
            car_world,
            standoffs_m=standoffs,
            bearings_deg=bearings,
            heights_m=heights,
            yaw_offsets_deg=yaw_offs,
            yaw_mode=str(args.yaw_mode),
            reference_yaw_rad=reference_yaw_rad,
        )
        logger.info(
            "Ring sweep %d poses | standoffs=%s bearings=%d heights=%s",
            len(candidates),
            standoffs,
            len(bearings),
            heights,
        )

    det_ns = argparse.Namespace(
        detector="open_vocab",
        target_class="car",
        visual_prompt=str(args.visual_prompt),
        yolo_model=yolo_model,
        yolo_conf=float(args.yolo_conf),
        yolo_imgsz=yolo_imgsz,
        yolo_device=str(args.yolo_device),
        vgoal_repo=str(vgoal_repo),
        capture_w=cap_w,
        capture_h=cap_h,
        camera_fov_deg=float(args.camera_fov_deg),
    )
    detector = _build_detector(det_ns, vgoal_repo)
    intr = CameraIntrinsics.from_fov(float(args.camera_fov_deg), cap_w, cap_h)

    try:
        import cv2
    except ImportError:
        cv2 = None

    if str(args.sweep_mode).lower() == "anchor" and anchor_meta is not None:
        if args.anchor_auto_yaw:
            auto_yaw, auto_conf, auto_n = _auto_yaw_at_pos(
                env,
                detector,
                anchor_meta["pos"],
                anchor_yaw,
                sweep_deg=float(args.anchor_auto_yaw_sweep_deg),
                step_deg=float(args.anchor_auto_yaw_step_deg),
                min_conf=float(args.min_conf),
            )
            logger.info(
                "Anchor auto-yaw: %.1f° -> %.1f° conf=%.3f n=%d",
                math.degrees(anchor_yaw),
                math.degrees(auto_yaw),
                auto_conf,
                auto_n,
            )
            anchor_meta["auto_yaw_rad"] = auto_yaw
            anchor_meta["auto_yaw_conf"] = auto_conf
            anchor_yaw = auto_yaw
        candidates = anchor_perturb_poses(
            anchor_meta["pos"],
            float(anchor_yaw),
            fwd_jitter_m=_parse_floats(args.anchor_fwd_jitter_m),
            lat_jitter_m=_parse_floats(args.anchor_lat_jitter_m),
            z_jitter_m=_parse_floats(args.anchor_z_jitter_m),
            yaw_jitter_deg=_parse_floats(args.anchor_yaw_jitter_deg),
        )
        logger.info("Anchor sweep %d poses", len(candidates))

    snap_dir = (root / args.snapshot_dir).resolve()
    if args.save_snapshots != "none":
        snap_dir.mkdir(parents=True, exist_ok=True)

    scored: List[Dict[str, Any]] = []
    for pi, cand in enumerate(candidates):
        pos = np.array(cand["pos"], dtype=np.float64)
        yaw = float(cand["yaw_rad"])
        proj = _project_car(car_world, pos, yaw, intr, float(args.car_width_m))

        obs = env.reset({"pos": [pos.tolist(), pos.tolist()], "yaw": [yaw, yaw]})
        rgb = getattr(obs, "rgb_yolo", None)
        if rgb is None:
            rgb = getattr(obs, "rgb", None)
        rgb_arr = np.asarray(rgb, dtype=np.uint8) if rgb is not None else None

        dets: List[Any] = []
        if rgb_arr is not None:
            dets = list(getattr(detector, "detect_all", lambda _: [])(rgb_arr) or [])

        pick, pix, pick_mode = _pick_det(
            dets,
            cart_in_fov=bool(proj["cart_in_fov"]),
            cart_u=proj.get("cart_u"),
            cart_v=proj.get("cart_v"),
        )
        conf = float(getattr(pick, "confidence", 0.0) or 0.0) if pick is not None else 0.0
        yolo_w = 0.0
        if pick is not None and hasattr(pick, "bbox"):
            bb = [float(x) for x in pick.bbox]
            yolo_w = bb[2] - bb[0]

        hit_raw = pick is not None and conf >= float(args.min_conf)
        hit_aligned = (
            hit_raw
            and bool(proj["cart_in_fov"])
            and float(proj["exp_bbox_w_px"]) >= float(args.min_exp_bbox_px)
            and yolo_w >= float(args.min_yolo_bbox_px)
            and pix is not None
            and float(pix) <= float(args.max_pix_offset_px)
        )
        hit_strong = hit_aligned and conf >= 0.20

        snap_path = None
        save_this = (
            args.save_snapshots == "all"
            or (args.save_snapshots == "hits" and (hit_aligned or hit_raw))
        )
        if save_this and rgb_arr is not None and cv2 is not None:
            snap_path = snap_dir / (
                f"pose_{pi:04d}_d{int(cand['standoff_m'])}_b{int(cand['bearing_deg'])}"
                f"_z{int(cand['height_z'])}_{'aln' if hit_aligned else 'raw' if hit_raw else 'miss'}.jpg"
            )
            bgr = rgb_arr[:, :, ::-1].copy()
            if proj.get("cart_u") is not None:
                cv2.circle(bgr, (int(proj["cart_u"]), int(proj["cart_v"])), 8, (0, 0, 255), 2)
            for det in dets:
                u0, v0, u1, v1 = [int(x) for x in det.bbox]
                color = (0, 255, 0) if det is pick else (255, 128, 0)
                cv2.rectangle(bgr, (u0, v0), (u1, v1), color, 2)
            cv2.imwrite(str(snap_path), bgr)

        row = {
            **cand,
            **proj,
            "n_detections": len(dets),
            "yolo_conf": round(conf, 4) if pick is not None else None,
            "yolo_bbox_w_px": round(yolo_w, 2) if pick is not None else None,
            "pix_offset_px": round(float(pix), 2) if pix is not None else None,
            "pick_mode": pick_mode,
            "hit_raw": hit_raw,
            "hit_aligned": hit_aligned,
            "hit_strong": hit_strong,
            "snapshot": str(snap_path) if snap_path else None,
        }
        scored.append(row)
        if (pi + 1) % 12 == 0 or hit_aligned or hit_raw:
            if str(args.sweep_mode).lower() == "anchor":
                logger.info(
                    "pose %d/%d fwd=%+.0f lat=%+.0f dz=%+.0f yaw_off=%+.0f° raw=%s conf=%.2f pix=%s",
                    pi + 1,
                    len(candidates),
                    cand.get("anchor_fwd_m", 0.0),
                    cand.get("anchor_lat_m", 0.0),
                    cand.get("anchor_dz_m", 0.0),
                    cand.get("yaw_off_deg", 0.0),
                    hit_raw,
                    conf,
                    f"{pix:.0f}" if pix is not None else "-",
                )
            else:
                logger.info(
                    "pose %d/%d standoff=%.0fm bearing=%.0f° z=%.0f raw=%s aligned=%s conf=%.2f pix=%s",
                    pi + 1,
                    len(candidates),
                    cand["standoff_m"],
                    cand["bearing_deg"],
                    cand["height_z"],
                    hit_raw,
                    hit_aligned,
                    conf,
                    f"{pix:.0f}" if pix is not None else "-",
                )

    by_standoff = _summarize_by_standoff(scored) if str(args.sweep_mode).lower() != "anchor" else {}
    anchor_summary = _summarize_anchor(scored) if str(args.sweep_mode).lower() == "anchor" else None
    tier_a_pool = [
        r
        for r in scored
        if r.get("hit_aligned")
        and float(args.tier_a_min_standoff_m) <= float(r["standoff_m"]) <= float(args.tier_a_max_standoff_m)
    ]
    tier_a_pool.sort(key=lambda r: (-float(r["yolo_conf"]), float(r["pix_offset_px"] or 9999)))

    # diversify annotation: best aligned per (standoff, bearing) bucket
    anno_seen: set = set()
    anno_rows: List[Dict[str, Any]] = []
    for row in tier_a_pool:
        key = (float(row["standoff_m"]), float(row["bearing_deg"]))
        if key in anno_seen:
            continue
        anno_seen.add(key)
        anno_rows.append(row)
        if len(anno_rows) >= int(args.max_annotation_routes):
            break

    out_routes: List[Dict[str, Any]] = []
    for out_i, row in enumerate(anno_rows):
        rid = (
            f"red_car_ring_d{int(row['standoff_m'])}_b{int(row['bearing_deg'])}"
            f"_z{int(row['height_z'])}"
        )
        out_routes.append(
            {
                "route_id": rid,
                "route_idx": out_i,
                "source": (
                    f"distance_sweep standoff={row['standoff_m']:.0f}m bearing={row['bearing_deg']:.0f}° "
                    f"z={row['height_z']:.0f}m; conf={row['yolo_conf']} pix={row['pix_offset_px']}"
                ),
                "pos": [row["pos"], row["pos"]],
                "yaw": [row["yaw_rad"], row["yaw_rad"]],
                "gpt_instruction": f"Find and approach the {args.visual_prompt}",
                "visual_prompt": str(args.visual_prompt),
                "detector": "open_vocab",
                "probe_conf": row["yolo_conf"],
                "standoff_m": row["standoff_m"],
                "bearing_deg": row["bearing_deg"],
                "height_z": row["height_z"],
                "snapshot": row.get("snapshot"),
            }
        )

    annotation = {
        "version": "airsim16_red_car_distance_tier_a_v1",
        "description": (
            f"Tier-A ring sweep aligned hits ({args.tier_a_min_standoff_m:.0f}-"
            f"{args.tier_a_max_standoff_m:.0f}m, pix<={args.max_pix_offset_px}px). "
            f"Generated by vgoal_red_car_distance_sweep.py."
        ),
        "car_world": [round(float(x), 3) for x in car_world],
        "visual_prompt": str(args.visual_prompt),
        "detector": "open_vocab",
        "yolo_model": yolo_model,
        "capture": {"w": cap_w, "h": cap_h, "fov_deg": float(args.camera_fov_deg)},
        "n_routes": len(out_routes),
        "routes": out_routes,
    }
    anno_path = (root / args.out_annotation).resolve()
    anno_path.parent.mkdir(parents=True, exist_ok=True)
    anno_path.write_text(json.dumps(annotation, indent=2), encoding="utf-8")

    report = {
        "sweep_mode": str(args.sweep_mode),
        "car_world": [round(float(x), 3) for x in car_world],
        "visual_prompt": str(args.visual_prompt),
        "yolo_model": yolo_model,
        "yolo_conf": float(args.yolo_conf),
        "yolo_imgsz": yolo_imgsz,
        "capture": {"w": cap_w, "h": cap_h},
        "n_poses": len(scored),
        "thresholds": {
            "min_conf": float(args.min_conf),
            "min_exp_bbox_px": float(args.min_exp_bbox_px),
            "min_yolo_bbox_px": float(args.min_yolo_bbox_px),
            "max_pix_offset_px": float(args.max_pix_offset_px),
        },
        "anchor": _json_safe(anchor_meta),
        "summary_anchor": anchor_summary,
        "summary_by_standoff_m": by_standoff,
        "tier_a": {
            "min_standoff_m": float(args.tier_a_min_standoff_m),
            "max_standoff_m": float(args.tier_a_max_standoff_m),
            "n_aligned": len(tier_a_pool),
            "n_annotation_routes": len(out_routes),
        },
        "poses": scored,
        "annotation": str(anno_path),
    }
    report_path = (root / args.out_report).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    logger.info("Report: %s", report_path)
    logger.info("Annotation (%d routes): %s", len(out_routes), anno_path)
    if anchor_summary:
        logger.info(
            "anchor: recall_raw=%.0f%% recall_aligned=%.0f%% best_conf=%.3f (n=%d)",
            100.0 * anchor_summary["recall_raw"],
            100.0 * anchor_summary["recall_aligned"],
            anchor_summary["best_conf"],
            anchor_summary["n"],
        )
    for key, summ in by_standoff.items():
        logger.info(
            "standoff %sm: recall_raw=%.0f%% recall_aligned=%.0f%% (n=%d)",
            key,
            100.0 * summ["recall_raw"],
            100.0 * summ["recall_aligned"],
            summ["n"],
        )
    return 0 if scored else 1


if __name__ == "__main__":
    raise SystemExit(main())
