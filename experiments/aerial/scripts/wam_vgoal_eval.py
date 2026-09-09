#!/usr/bin/env python3
"""Phase-2 monocular visual goal eval (M1+M2).

Product stack (no GT world-goal control by default):
  YOLO / open-vocab detector
    → monocular D̂ back-projection (``bbox_to_goal_rel``)
    → TargetTracker (TRACKING / OCCLUDED / SEARCHING)
    → goal_rel → LatentActorDeployPolicy + ImaginationPlanner
    → ThreeZoneSpeedShield → env.step

SEARCHING: slow forward + yaw scan with optional z-hold (spawn z clipped 20–40 m).
TRACKING/APPROACH: visual ``G`` → ``TowardGoalIntent`` clip → π/planner (Phase-2
toward_g shell). ``--fallback-toward-g`` is opt-in ablation only.

Ckpt defaults match Phase-2 close (E2 toward_g · tti=2.5 · long routes).
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import yaml

from experiments.aerial.scripts.wam_phase2_long_eval import (
    PASS_THRESHOLDS,
    _goal_closure,
    _goal_dist,
    _segment_min_dist,
    aggregate_metrics,
)


logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("wam_vgoal_eval")


def _select_route_indices(n_available: int, episodes: int, routes_arg: Optional[str]) -> List[int]:
    if not routes_arg:
        return list(range(min(int(episodes), int(n_available))))
    idxs = [int(t) for t in str(routes_arg).split(",") if t.strip()]
    bad = [i for i in idxs if not 0 <= i < n_available]
    if bad:
        raise SystemExit(f"--routes {bad} out of range (annotation has {n_available})")
    if len(set(idxs)) != len(idxs):
        raise SystemExit(f"--routes has duplicates: {idxs}")
    return idxs


def _resolve_search_fwd_step(
    search_fwd_speed: Optional[float],
    *,
    search_at_cruise: bool,
    vx_max_step: float,
    slow_default: float = 0.2,
) -> float:
    if search_fwd_speed is not None:
        return float(search_fwd_speed)
    if search_at_cruise:
        return float(vx_max_step)
    return float(slow_default)


def _episode_search_z_hold(
    start_z: float,
    *,
    mode: str,
    hold_m: Optional[float],
    z_min: float,
    z_max: float,
) -> Optional[float]:
    if str(mode).lower() == "off":
        return None
    if hold_m is not None:
        return float(hold_m)
    # auto: hold spawn altitude, clipped to outdoor search band
    return float(np.clip(float(start_z), float(z_min), float(z_max)))


def _body_to_world(pos: np.ndarray, yaw: float, g_rel: np.ndarray) -> np.ndarray:
    c, s = math.cos(yaw), math.sin(yaw)
    g = np.asarray(g_rel, dtype=np.float64).reshape(-1)
    return pos + np.array([
        c * g[0] - s * g[1],
        s * g[0] + c * g[1],
        g[2] if g.size > 2 else 0.0,
    ], dtype=np.float64)


@dataclass
class VisionStepResult:
    goal_rel: Optional[np.ndarray]
    target_world: Optional[np.ndarray]
    tracker_state: str
    det_hit: bool
    using_vision: bool
    using_fallback: bool
    search_action: Optional[np.ndarray]
    perception: Optional[Dict[str, Any]] = None


def _nearest_scene_object_goal(
    env: Any,
    pos: np.ndarray,
    *,
    pattern: str = "Cart.*",
    max_dist_m: float = 250.0,
) -> Optional[np.ndarray]:
    """Resolve a static scene object pose from AirSim (GT smoke / car probe)."""
    connect = getattr(env, "_connect", None)
    if not callable(connect):
        return None
    try:
        client = connect()
        names = client.simListSceneObjects(str(pattern))
    except Exception as exc:
        logger.warning("gt scene goal lookup failed: %s", exc)
        return None
    if not names:
        return None
    best_goal: Optional[np.ndarray] = None
    best_dist = float(max_dist_m)
    pos_xy = np.asarray(pos[:2], dtype=np.float64)
    for name in names:
        try:
            pose = client.simGetObjectPose(name)
        except Exception:
            continue
        goal = np.array([pose.position.x_val, pose.position.y_val, pose.position.z_val], dtype=np.float64)
        horiz = float(np.linalg.norm(goal[:2] - pos_xy))
        if horiz < best_dist:
            best_dist = horiz
            best_goal = goal
    return best_goal


def _raw_perception_record(
    det: Any,
    depth_map: Optional[np.ndarray],
    intrinsics: Any,
    src_shape: Tuple[int, int],
    measured_gr: Optional[np.ndarray],
    *,
    object_width_m: float,
    det_conf: float,
) -> Dict[str, Any]:
    from vgoal.geometry import bbox_forward_depth_prior, extract_target_depth, fuse_target_depth

    rec: Dict[str, Any] = {
        "det_raw": det is not None,
        "conf": round(float(det_conf), 4) if det_conf else None,
        "measured_dist_m": round(float(measured_gr[3]), 3) if measured_gr is not None else None,
        "measured_fwd_m": round(float(measured_gr[0]), 3) if measured_gr is not None else None,
        "d_patch_m": None,
        "d_bbox_prior_m": None,
        "d_fused_m": None,
        "bbox_w_px": None,
        "gt_direct_depth_m": None,
    }
    if det is None:
        return rec
    bb = [float(x) for x in det.bbox]
    rec["bbox_w_px"] = round(bb[2] - bb[0], 1)
    d_direct = float(getattr(det, "direct_depth", 0.0) or 0.0)
    if d_direct > 0.0:
        rec["gt_direct_depth_m"] = round(d_direct, 3)
    if depth_map is not None:
        dp = extract_target_depth(depth_map, bb, src_shape=src_shape)
        db = bbox_forward_depth_prior(bb, intrinsics, src_shape=src_shape, object_width_m=object_width_m)
        df = fuse_target_depth(dp, db, bb[2] - bb[0])
        if np.isfinite(dp):
            rec["d_patch_m"] = round(float(dp), 3)
        if np.isfinite(db):
            rec["d_bbox_prior_m"] = round(float(db), 3)
        if np.isfinite(df):
            rec["d_fused_m"] = round(float(df), 3)
    return rec


def _build_detector(args: argparse.Namespace, vgoal_repo: Path) -> Any:
    from vgoal.detector import MockDetector, OpenVocabPromptDetector, YOLOTargetDetector

    kind = str(args.detector).lower()
    if kind == "mock":
        return MockDetector(confidence=0.0, class_name=str(args.target_class or "target"))
    if kind == "gt":
        logger.warning("--detector gt is DEBUG ONLY — not valid for product eval")
        return _GroundTruthDetector(
            fov_deg=float(args.camera_fov_deg),
            img_w=int(args.capture_w),
            img_h=int(args.capture_h),
        )
    if kind in ("open_vocab", "semantic"):
        prompt = str(args.visual_prompt or args.target_class or "car")
        return OpenVocabPromptDetector(
            visual_prompt=prompt,
            model_path=str(args.yolo_model),
            conf_threshold=float(args.yolo_conf),
            imgsz=int(args.yolo_imgsz),
            device=str(args.yolo_device),
        )
    classes = [str(args.target_class)] if args.target_class else None
    return YOLOTargetDetector(
        model_path=str(args.yolo_model),
        target_classes=classes,
        conf_threshold=float(args.yolo_conf),
        imgsz=int(args.yolo_imgsz),
        device=str(args.yolo_device),
    )


class _GroundTruthDetector:
    """DEBUG: project annotation goal into image (not product path)."""

    def __init__(self, fov_deg: float = 80.0, img_w: int = 224, img_h: int = 224) -> None:
        from vgoal.geometry import CameraIntrinsics
        from vgoal.detector import DetectionResult

        self.intrinsics = CameraIntrinsics.from_fov(fov_deg, width=img_w, height=img_h)
        self._DetectionResult = DetectionResult
        self._goal_world: Optional[np.ndarray] = None
        self._pos: Optional[np.ndarray] = None
        self._yaw: float = 0.0

    def set_goal(self, goal_world: np.ndarray) -> None:
        self._goal_world = np.asarray(goal_world, dtype=np.float64).reshape(3)

    def set_pose(self, pos: np.ndarray, yaw: float) -> None:
        self._pos = np.asarray(pos, dtype=np.float64).reshape(3)
        self._yaw = float(yaw)

    def detect(self, rgb: Optional[np.ndarray] = None):
        if self._goal_world is None or self._pos is None:
            return None
        from vgoal.geometry import project_3d_to_pixel

        d_world = self._goal_world - self._pos
        c, s = math.cos(self._yaw), math.sin(self._yaw)
        d_fwd = float(c * d_world[0] + s * d_world[1])
        d_left = float(-s * d_world[0] + c * d_world[1])
        d_up = float(d_world[2])
        if d_fwd <= 0.5:
            return None
        u, v, _z = project_3d_to_pixel([d_fwd, d_left, d_up], self.intrinsics)
        if math.isnan(u) or math.isnan(v):
            return None
        w, h = self.intrinsics.width, self.intrinsics.height
        if not (0 <= u < w and 0 <= v < h):
            return None
        half_box = max(6.0, 20.0 * (10.0 / max(1.0, d_fwd)))
        bbox = np.array([
            max(0.0, u - half_box), max(0.0, v - half_box),
            min(float(w - 1), u + half_box), min(float(h - 1), v + half_box),
        ], dtype=np.float32)
        res = self._DetectionResult(bbox=bbox, confidence=0.95, class_id=0, class_name="goal")
        setattr(res, "direct_depth", float(d_fwd))
        setattr(res, "_d_left", d_left)
        setattr(res, "_d_up", d_up)
        return res


def _det_to_goal_rel(
    det: Any,
    intrinsics: Any,
    depth_map: Optional[np.ndarray],
    src_shape: Tuple[int, int],
    *,
    object_width_m: float = 2.0,
    fuse_bbox_depth: bool = True,
) -> Optional[np.ndarray]:
    from vgoal.geometry import bbox_to_goal_rel

    d_fwd = float(getattr(det, "direct_depth", 0.0) or 0.0)
    if d_fwd > 0.0:
        d_left_stored = getattr(det, "_d_left", None)
        d_up_stored = getattr(det, "_d_up", None)
        if d_left_stored is not None and d_up_stored is not None:
            d_left = float(d_left_stored)
            d_up = float(d_up_stored)
            dist = float(np.sqrt(d_fwd**2 + d_left**2 + d_up**2))
            return np.array([d_fwd, d_left, d_up, dist], dtype=np.float64)
    if depth_map is None:
        return None
    gr = bbox_to_goal_rel(
        det.bbox,
        depth_map,
        intrinsics,
        src_shape=src_shape,
        object_width_m=object_width_m,
        fuse_bbox_depth=fuse_bbox_depth,
    )
    if gr is None:
        return None
    return np.asarray(gr, dtype=np.float64)


def _vision_step(
    *,
    obs: Any,
    detector: Any,
    tracker: Any,
    depth_pred: Any,
    intrinsics: Any,
    pos: np.ndarray,
    yaw: float,
    prev_pos: np.ndarray,
    prev_yaw: float,
    dt: float,
    search_fwd_step: float,
    search_yaw_rate: float,
    fallback_intent: Any,
    annot_goal: np.ndarray,
    allow_fallback: bool,
    prefer_nearest: bool,
    camera_fov_deg: float,
    object_width_m: float = 2.0,
    fuse_bbox_depth: bool = True,
) -> VisionStepResult:
    from vgoal.geometry import CameraIntrinsics
    from vgoal.tracker import TargetState

    rgb = getattr(obs, "rgb", None)
    rgb_det = getattr(obs, "rgb_yolo", None)
    rgb_det_arr = np.asarray(rgb_det if rgb_det is not None else rgb, dtype=np.uint8)
    det_h, det_w = rgb_det_arr.shape[:2]
    if det_w != intrinsics.width or det_h != intrinsics.height:
        intrinsics = CameraIntrinsics.from_fov(float(camera_fov_deg), width=det_w, height=det_h)

    depth_map = depth_pred.predict_depth(obs) if depth_pred is not None else None

    if hasattr(detector, "set_pose"):
        detector.set_pose(pos, yaw)
    det = None
    measured_gr: Optional[np.ndarray] = None
    det_conf = 0.0

    detect_all = getattr(detector, "detect_all", None)
    if prefer_nearest and callable(detect_all) and depth_map is not None:
        best_gr = None
        best_conf = 0.0
        best_det = None
        for cand in detect_all(rgb_det_arr) or []:
            gr = _det_to_goal_rel(
                cand,
                intrinsics,
                depth_map,
                (det_w, det_h),
                object_width_m=object_width_m,
                fuse_bbox_depth=fuse_bbox_depth,
            )
            if gr is None:
                continue
            if best_gr is None or float(gr[3]) < float(best_gr[3]):
                best_gr = gr
                best_conf = float(cand.confidence)
                best_det = cand
        if best_gr is not None:
            det = best_det
            measured_gr = best_gr
            det_conf = best_conf
    else:
        det = detector.detect(rgb_det_arr)
        if det is not None:
            measured_gr = _det_to_goal_rel(
                det,
                intrinsics,
                depth_map,
                (det_w, det_h),
                object_width_m=object_width_m,
                fuse_bbox_depth=fuse_bbox_depth,
            )
            if measured_gr is not None:
                det_conf = float(det.confidence)

    perception_rec = _raw_perception_record(
        det,
        depth_map,
        intrinsics,
        (det_w, det_h),
        measured_gr,
        object_width_m=object_width_m,
        det_conf=det_conf,
    )

    d_world = pos - prev_pos
    dyaw = float(yaw - prev_yaw)
    dyaw = float((dyaw + math.pi) % (2.0 * math.pi) - math.pi)
    c_yaw, s_yaw = math.cos(prev_yaw), math.sin(prev_yaw)
    ego_delta = np.array([
        c_yaw * d_world[0] + s_yaw * d_world[1],
        -s_yaw * d_world[0] + c_yaw * d_world[1],
        d_world[2],
    ], dtype=np.float64)

    tracker_state = tracker.update(
        measured_gr,
        dt=dt,
        ego_delta_body=ego_delta,
        ego_delta_yaw=dyaw,
        confidence=det_conf,
    )
    cur_goal_rel = tracker.goal_rel
    det_hit = measured_gr is not None

    if cur_goal_rel is not None and tracker_state != TargetState.SEARCHING:
        g_rel = np.asarray(cur_goal_rel, dtype=np.float64)
        target_world = _body_to_world(pos, yaw, g_rel)
        return VisionStepResult(
            goal_rel=g_rel,
            target_world=target_world,
            tracker_state=str(tracker_state.value),
            det_hit=det_hit,
            using_vision=True,
            using_fallback=False,
            search_action=None,
            perception=perception_rec,
        )

    if allow_fallback and fallback_intent is not None:
        d_fwd_hat = obs.info.get("depth_min_pred")
        g_rel_body, s_info = fallback_intent.compute(
            curr_pos=pos, curr_yaw=yaw, goal=annot_goal, d_fwd_hat=d_fwd_hat
        )
        target_world = np.array(s_info["target_world"], dtype=np.float64)
        return VisionStepResult(
            goal_rel=np.asarray(g_rel_body, dtype=np.float64),
            target_world=target_world,
            tracker_state=str(TargetState.SEARCHING.value),
            det_hit=det_hit,
            using_vision=False,
            using_fallback=True,
            search_action=None,
            perception=perception_rec,
        )

    search_action = np.array([search_fwd_step, 0.0, 0.0, search_yaw_rate], dtype=np.float64)
    return VisionStepResult(
        goal_rel=None,
        target_world=None,
        tracker_state=str(TargetState.SEARCHING.value),
        det_hit=det_hit,
        using_vision=False,
        using_fallback=False,
        search_action=search_action,
        perception=perception_rec,
    )


def main() -> int:  # noqa: C901
    parser = argparse.ArgumentParser(description="Phase-2 monocular visual goal eval")
    parser.add_argument("--config", default="configs/aerial_rl.yaml")
    parser.add_argument(
        "--wm-ckpt",
        default="experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt",
    )
    parser.add_argument(
        "--actor-ckpt",
        default=(
            "experiments/aerial/rl/artifacts/"
            "v4_ac_ckpt_phase2_toward_g_20260905_112006/v4_ac_latest.pt"
        ),
    )
    parser.add_argument(
        "--depth-ckpt",
        default="experiments/aerial/rl/artifacts/depth_ckpt_p45mid_s8j_20260825/depth_best_holdout_da3_ft_head.pt",
    )
    parser.add_argument(
        "--tau-ckpt",
        default="experiments/aerial/rl/artifacts/tau_ckpt_foe_r60_20260815/tau_foe_calibrator.pt",
    )
    parser.add_argument("--annotation", default="artifacts/seen_airsim16_long_routes.json")
    parser.add_argument("--episodes", type=int, default=16)
    parser.add_argument("--routes", type=str, default=None)
    parser.add_argument("--step-hz", type=float, default=5.0)
    parser.add_argument("--max-steps", type=int, default=2000)
    parser.add_argument("--cruise-speed", type=float, default=10.0)
    parser.add_argument("--tti-coeff", type=float, default=2.5)
    parser.add_argument("--success-dist", type=float, default=3.0)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--planner", action="store_true")
    parser.add_argument("--planner-horizon", type=int, default=5)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--out", default="artifacts/wam_vgoal_eval_result.json")
    parser.add_argument("--spawn-tol-m", type=float, default=12.0)
    parser.add_argument("--traj-out", default=None)
    parser.add_argument(
        "--perception-log",
        default=None,
        help="Per-step raw perception JSONL dir/prefix (route{idx}_perception.jsonl)",
    )
    parser.add_argument(
        "--gt-nearest-scene-object",
        action="store_true",
        help="DEBUG/GT: use nearest AirSim scene object as goal (--detector gt)",
    )
    parser.add_argument("--gt-scene-pattern", default="Cart.*")
    parser.add_argument("--gt-scene-max-dist-m", type=float, default=250.0)
    parser.add_argument("--vgoal-repo", default=os.path.expanduser("~/Projects/aerial-vgoal-wam"))
    parser.add_argument("--camera-fov-deg", type=float, default=80.0)
    parser.add_argument(
        "--capture-w",
        type=int,
        default=int(os.environ.get("AERIAL_CAPTURE_W", os.environ.get("INDOOR_CAPTURE_W", "640"))),
        help="AirSim CaptureSettings width (native grab before fan-out)",
    )
    parser.add_argument(
        "--capture-h",
        type=int,
        default=int(os.environ.get("AERIAL_CAPTURE_H", os.environ.get("INDOOR_CAPTURE_H", "480"))),
        help="AirSim CaptureSettings height",
    )
    parser.add_argument("--wam-encode-size", type=int, default=224)
    parser.add_argument(
        "--fanout-rgb",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Single grab → rgb_vio(native) + rgb_yolo(native) + rgb(224 WAM)",
    )
    parser.add_argument("--tracker-max-occlusion-s", type=float, default=2.0)
    parser.add_argument("--tracker-ema-alpha", type=float, default=0.7)
    parser.add_argument("--tracker-near-dist-m", type=float, default=35.0)
    parser.add_argument("--tracker-near-ema-alpha", type=float, default=0.92)
    parser.add_argument("--tracker-inflate-reject-m", type=float, default=4.0)
    parser.add_argument("--tracker-inflate-alpha", type=float, default=0.15)
    parser.add_argument(
        "--car-width-m",
        type=float,
        default=2.0,
        help="Assumed car width for bbox→depth prior (pinhole Z ≈ fx·W/w_px)",
    )
    parser.add_argument(
        "--bbox-depth-fuse",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Fuse D̂ patch depth with bbox-width prior (default ON)",
    )
    parser.add_argument(
        "--detector",
        choices=("yolo", "open_vocab", "semantic", "mock", "gt"),
        default="yolo",
        help="Perception frontend (default: yolo pure vision)",
    )
    parser.add_argument("--target-class", default="car", help="YOLO COCO class filter")
    parser.add_argument("--visual-prompt", default=None, help="Open-vocab prompt (open_vocab detector)")
    parser.add_argument("--yolo-model", default="yolov8n.pt")
    parser.add_argument("--yolo-conf", type=float, default=0.25)
    parser.add_argument("--yolo-imgsz", type=int, default=640)
    parser.add_argument("--yolo-device", default="cuda")
    parser.add_argument("--prefer-nearest-target", action="store_true", default=True)
    parser.add_argument(
        "--search-fwd-speed",
        type=float,
        default=None,
        help="SEARCHING forward m/step; default 0.2 (slow scan) unless --search-at-cruise",
    )
    parser.add_argument(
        "--search-at-cruise",
        action="store_true",
        help="SEARCHING uses cruise_speed/step_hz forward (default: slow 0.2 m/step)",
    )
    parser.add_argument("--search-yaw-rate", type=float, default=0.314)
    parser.add_argument(
        "--search-z-hold-mode",
        choices=("auto", "off"),
        default="auto",
        help="SEARCHING altitude hold: auto clips spawn z to [--search-z-min, --search-z-max]",
    )
    parser.add_argument("--search-z-hold-m", type=float, default=None, help="Fixed SEARCHING z (m); overrides auto")
    parser.add_argument("--search-z-min", type=float, default=20.0)
    parser.add_argument("--search-z-max", type=float, default=40.0)
    parser.add_argument(
        "--search-z-gain",
        type=float,
        default=1.0,
        help="SEARCHING z-hold P gain: dz_step ~= gain * (z_hold - z) clipped per step",
    )
    parser.add_argument(
        "--toward-g-r-m",
        type=float,
        default=25.0,
        help="Visual G TowardGoalIntent clip radius (m)",
    )
    parser.add_argument(
        "--visual-toward-g",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="TRACKING: clip visual target through TowardGoalIntent before π (default ON)",
    )
    parser.add_argument(
        "--tracker-min-confidence",
        type=float,
        default=None,
        help="TargetTracker lock threshold; default aligns with --yolo-conf (cap 0.5)",
    )
    parser.add_argument(
        "--fallback-toward-g",
        action="store_true",
        help="Ablation: geometric toward_g when SEARCHING (default OFF)",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    vgoal_repo = Path(args.vgoal_repo).expanduser().resolve()
    if not vgoal_repo.is_dir():
        raise SystemExit(f"--vgoal-repo not found: {vgoal_repo}")
    if str(vgoal_repo) not in sys.path:
        sys.path.insert(0, str(vgoal_repo))

    from vgoal.geometry import CameraIntrinsics
    from vgoal.tracker import TargetTracker, TrackerConfig

    import torch
    from experiments.aerial.rl.actor_critic import LatentActorCritic, LatentActorDeployPolicy
    from experiments.aerial.rl.env.action import body_delta_limits, clip_body_delta
    from experiments.aerial.rl.goal_features import body_vel_from_obs
    from experiments.aerial.rl.planner import ImaginationPlanner
    from experiments.aerial.rl.reward import RewardConfig
    from experiments.aerial.rl.depth_predictor import DepthMinPredictor
    from experiments.aerial.rl.tau_predictor import make_tau_predictor
    from experiments.aerial.rl.scene_intent import TowardGoalIntent
    from experiments.aerial.rl.train_rl import _build_env, _build_safety, load_torch_dynamics

    cfg_file = (root / args.config).resolve()
    cfg = yaml.safe_load(cfg_file.read_text()) if cfg_file.is_file() else {}

    device_str = "cpu" if (args.mock or not torch.cuda.is_available()) else args.device
    device = torch.device(device_str)
    logger.info("device=%s mock=%s detector=%s fallback=%s", device, args.mock, args.detector, args.fallback_toward_g)

    anno_path = (root / args.annotation).resolve() if not Path(args.annotation).is_absolute() else Path(args.annotation)
    with open(anno_path, "r", encoding="utf-8") as f:
        anno_data = json.load(f)
    routes = anno_data.get("routes", anno_data) if isinstance(anno_data, dict) else anno_data
    route_idxs = _select_route_indices(len(routes), args.episodes, args.routes)
    n_routes = len(route_idxs)

    env_cfg = dict(cfg.get("env") or {})
    env_cfg["backend"] = "mock" if args.mock else "airsim"
    env_cfg["step_hz"] = float(args.step_hz)
    env_cfg["grab_depth"] = True
    use_fanout = bool(args.fanout_rgb) and str(args.detector).lower() != "mock"
    env_cfg["fanout_rgb"] = use_fanout
    env_cfg["width"] = int(args.capture_w)
    env_cfg["height"] = int(args.capture_h)
    env_cfg["wam_encode_size"] = int(args.wam_encode_size)
    env = _build_env(env_cfg)

    wm_cfg = cfg.get("world_model") or {}
    wm_path = (root / args.wm_ckpt).resolve() if not Path(args.wm_ckpt).is_absolute() else Path(args.wm_ckpt)
    dynamics, _ = load_torch_dynamics(wm_cfg, str(wm_path), device=device_str, success_dist_m=float(args.success_dist))

    actor_path = (root / args.actor_ckpt).resolve() if not Path(args.actor_ckpt).is_absolute() else Path(args.actor_ckpt)
    if not args.mock and actor_path.exists():
        actor_ac = LatentActorCritic.load_from_checkpoint(actor_path, device=device_str)
        actor_ac.config.goal_feat_mode = "meter"
        logger.info("Loaded actor-critic from %s", actor_path)
    else:
        actor_ac = LatentActorCritic.from_config({"latent_dim": dynamics.latent_dim, "device": device_str})

    depth_path = (root / args.depth_ckpt).resolve() if not Path(args.depth_ckpt).is_absolute() else Path(args.depth_ckpt)
    depth_pred = (
        DepthMinPredictor.from_checkpoint(depth_path, device=device_str)
        if (not args.mock and depth_path.is_file() and str(args.detector).lower() not in ("gt", "mock"))
        else None
    )
    if depth_pred is None and not args.mock and args.detector not in ("gt", "mock"):
        raise SystemExit(f"depth checkpoint required for YOLO back-projection: {depth_path}")

    tau_path = (root / args.tau_ckpt).resolve() if not Path(args.tau_ckpt).is_absolute() else Path(args.tau_ckpt)
    tau_pred = make_tau_predictor(
        kind="foe_calibrated",
        ckpt=tau_path if (not args.mock and tau_path.is_file()) else None,
        device=device_str,
    )

    dt_step = 1.0 / float(args.step_hz)
    phys_limits = body_delta_limits(dt_step)
    vx_max_step = float(min(float(args.cruise_speed) / float(args.step_hz), float(phys_limits[0])))
    action_limits = np.array(
        [vx_max_step, float(phys_limits[1]), float(phys_limits[2]), float(phys_limits[3])],
        dtype=np.float64,
    )
    search_fwd_step = _resolve_search_fwd_step(
        args.search_fwd_speed,
        search_at_cruise=bool(args.search_at_cruise),
        vx_max_step=vx_max_step,
    )
    search_fwd_label = (
        "override"
        if args.search_fwd_speed is not None
        else ("cruise" if args.search_at_cruise else "slow")
    )
    tracker_min_conf = (
        float(args.tracker_min_confidence)
        if args.tracker_min_confidence is not None
        else float(max(0.15, min(0.5, float(args.yolo_conf))))
    )

    reward_cfg = RewardConfig(**(cfg.get("reward") or {}))
    reward_cfg.success_dist_m = float(args.success_dist)

    planner = None
    if args.planner:
        planner = ImaginationPlanner(
            dynamics=dynamics,
            horizon=int(args.planner_horizon),
            reward_cfg=reward_cfg,
            action_limits=action_limits,
        )

    policy = LatentActorDeployPolicy(dynamics, actor_ac, deterministic=True, stream_latent=True)

    safety_cfg = dict(cfg.get("safety") or {})
    if str(safety_cfg.get("kind", "null")) in ("null", "none", "None"):
        safety_cfg["kind"] = "three_zone"
    safety_cfg["v_cruise_m_s"] = float(args.cruise_speed)
    safety_cfg["tti_coeff"] = float(args.tti_coeff)
    safety_cfg.pop("schedule_margin_l1_m", None)
    safety_cfg.pop("schedule_margin_l2_m", None)
    safety_cfg.pop("disc_lag_steps", None)
    shield = _build_safety(safety_cfg)
    if hasattr(shield, "zone"):
        logger.info(
            "three_zone v_cruise=%.1f engage_outer=%.1fm tti_coeff=%.1f",
            float(shield.zone.v_cruise_m_s),
            float(shield.zone.engage_outer_m),
            float(shield.tti_coeff),
        )

    fallback_intent = (
        TowardGoalIntent(r_m=100.0, mode="toward_g", cruise_speed=float(args.cruise_speed))
        if args.fallback_toward_g
        else None
    )
    visual_intent = (
        TowardGoalIntent(
            r_m=float(args.toward_g_r_m),
            mode="toward_g",
            cruise_speed=float(args.cruise_speed),
        )
        if args.visual_toward_g
        else None
    )

    det_w = int(args.capture_w)
    det_h = int(args.capture_h)
    intrinsics = CameraIntrinsics.from_fov(args.camera_fov_deg, width=det_w, height=det_h)
    tracker_cfg = TrackerConfig(
        success_dist_m=float(args.success_dist),
        max_occlusion_s=float(args.tracker_max_occlusion_s),
        ema_alpha=float(args.tracker_ema_alpha),
        min_confidence=tracker_min_conf,
        near_dist_m=float(args.tracker_near_dist_m),
        near_ema_alpha=float(args.tracker_near_ema_alpha),
        inflate_reject_m=float(args.tracker_inflate_reject_m),
        inflate_alpha=float(args.tracker_inflate_alpha),
    )
    detector = _build_detector(args, vgoal_repo)

    visual_prompt = str(args.visual_prompt or args.target_class or "car")
    logger.info(
        "phase2_vgoal: %d routes | cs=%.1f tti=%.1f | det=%s prompt=%s "
        "fanout=%s capture=%dx%d wam=%d search_fwd=%.3f(%s) yaw=%.2f "
        "z_hold=%s visual_toward_g=%s tracker_conf=%.2f yolo_conf=%.2f "
        "bbox_fuse=%s car_w=%.1fm near_ema=%.2f",
        n_routes, args.cruise_speed, args.tti_coeff, args.detector, visual_prompt,
        use_fanout, int(args.capture_w), int(args.capture_h), int(args.wam_encode_size),
        search_fwd_step, search_fwd_label, args.search_yaw_rate,
        args.search_z_hold_mode, bool(args.visual_toward_g), tracker_min_conf, args.yolo_conf,
        bool(args.bbox_depth_fuse), float(args.car_width_m), float(args.tracker_near_ema_alpha),
    )

    results: List[Dict[str, Any]] = []

    for slot, ep_idx in enumerate(route_idxs):
        r_info = routes[ep_idx]
        pts = np.array(r_info.get("pos", r_info.get("positions")), dtype=np.float64)
        goal_world = pts[-1].copy()
        if r_info.get("goal_pos"):
            goal_world = np.asarray(r_info["goal_pos"], dtype=np.float64).reshape(3)
        annot_goal = goal_world.copy()
        start_pos = pts[0].copy()
        yaws = np.array(r_info.get("yaw", [0.0] * len(pts)), dtype=np.float64)
        start_yaw = float(yaws[0]) if len(yaws) else 0.0
        ref_len = float(np.sum(np.linalg.norm(pts[1:] - pts[:-1], axis=1)))

        policy.reset()
        shield.reset()
        tau_pred.reset()
        if depth_pred is not None:
            depth_pred.reset()
        if planner is not None:
            planner.reset()
        if fallback_intent is not None:
            fallback_intent.reset()
        if visual_intent is not None:
            visual_intent.reset()
        ep_z_hold = _episode_search_z_hold(
            float(start_pos[2]),
            mode=str(args.search_z_hold_mode),
            hold_m=args.search_z_hold_m,
            z_min=float(args.search_z_min),
            z_max=float(args.search_z_max),
        )
        tracker = TargetTracker(tracker_cfg)

        ep_dict = {
            "pos": pts.tolist(),
            "yaw": yaws.tolist() if len(yaws) == len(pts) else [start_yaw] * len(pts),
            "gpt_instruction": r_info.get("gpt_instruction", visual_prompt),
        }
        obs = env.reset(ep_dict)

        p_curr = np.array(obs.position, dtype=np.float64)
        curr_yaw = float(obs.yaw) if hasattr(obs, "yaw") else 0.0
        if bool(args.gt_nearest_scene_object) and str(args.detector).lower() == "gt":
            resolved = _nearest_scene_object_goal(
                env,
                p_curr,
                pattern=str(args.gt_scene_pattern),
                max_dist_m=float(args.gt_scene_max_dist_m),
            )
            if resolved is not None:
                annot_goal = np.asarray(resolved, dtype=np.float64)
                goal_world = annot_goal.copy()
                logger.info(
                    "Route %02d GT goal from scene %s dist=%.1fm pos=%s",
                    ep_idx + 1,
                    args.gt_scene_pattern,
                    float(np.linalg.norm(annot_goal[:2] - p_curr[:2])),
                    [round(float(x), 2) for x in annot_goal],
                )
            else:
                logger.warning("Route %02d GT scene goal lookup failed — using annotation goal", ep_idx + 1)
        if hasattr(detector, "set_goal"):
            detector.set_goal(annot_goal)
        spawn_err = float(np.linalg.norm(p_curr - start_pos))

        if spawn_err > float(args.spawn_tol_m) and not args.mock:
            bump = start_pos.copy()
            bump[2] = float(bump[2]) + 2.0
            logger.warning("Route %02d spawn_err=%.1fm — retry z+=2", ep_idx + 1, spawn_err)
            ep_retry = dict(ep_dict)
            pts_retry = np.asarray(ep_retry["pos"], dtype=np.float64).copy()
            pts_retry[0] = bump
            ep_retry["pos"] = pts_retry.tolist()
            obs = env.reset(ep_retry)
            p_curr = np.array(obs.position, dtype=np.float64)
            curr_yaw = float(obs.yaw) if hasattr(obs, "yaw") else curr_yaw
            spawn_err = float(np.linalg.norm(p_curr - bump))

        if spawn_err > float(args.spawn_tol_m):
            logger.error("Route %02d spawn_fail err=%.1fm — skip", ep_idx + 1, spawn_err)
            results.append({
                "route_idx": ep_idx,
                "base_route_idx": r_info.get("base_route_idx", ep_idx),
                "L_ref": ref_len, "L_act": 0.0, "d0": float("nan"), "min_d": float("nan"),
                "arrived": False, "collided": False, "severe_collision": False,
                "progress_ratio": 0.0, "spl": 0.0, "intervention_rate": 0.0,
                "spawn_fail": True, "spawn_err_m": spawn_err, "fail_tag": "F1",
            })
            continue

        d0_annot = _goal_dist(p_curr, annot_goal)
        min_d_annot = d0_annot
        min_d_vision = float("inf")
        min_d_measured = float("inf")
        d_final_vision = float("inf")
        had_vision_lock = False
        traj = [p_curr.copy()]
        traj_writer = None
        perception_writer = None
        if args.traj_out:
            _tp = Path(args.traj_out).with_suffix("") / f"route{ep_idx:02d}.jsonl"
            _tp.parent.mkdir(parents=True, exist_ok=True)
            traj_writer = _tp.open("w")
        if args.perception_log:
            _pp = Path(args.perception_log).with_suffix("") / f"route{ep_idx:02d}_perception.jsonl"
            _pp.parent.mkdir(parents=True, exist_ok=True)
            perception_writer = _pp.open("w")

        arrived = False
        collided = False
        severe_coll = False
        fail_tag: Optional[str] = None
        interventions = 0
        intervened_steps: set = set()
        s_prog = 0.0
        p_prev_tracker = p_curr.copy()
        prev_yaw_tracker = curr_yaw
        detections_hit = 0
        steps_searching = 0
        steps_vision = 0
        steps_fallback = 0
        vision_target_last: Optional[np.ndarray] = None

        from vgoal.tracker import TargetState as TS

        for step in range(args.max_steps):
            obs.info.pop("depth_min_pred", None)
            obs.info.pop("depth_cones_pred", None)
            obs.info.pop("tau_pred", None)
            d_fwd = None
            if depth_pred is not None and obs.rgb is not None:
                pred_both = getattr(depth_pred, "predict_min_and_cones", None)
                if callable(pred_both):
                    d_min, cones = pred_both(obs)
                    if d_min is not None:
                        obs.info["depth_min_pred"] = float(d_min)
                        d_fwd = float(d_min)
                    if isinstance(cones, dict):
                        obs.info["depth_cones_pred"] = {k: (float(v) if v is not None else None) for k, v in cones.items()}
                        cf = cones.get("forward")
                        if cf is not None and np.isfinite(float(cf)):
                            d_fwd = float(cf)
                else:
                    d_fwd = depth_pred.predict_min(obs)
                    if d_fwd is not None:
                        obs.info["depth_min_pred"] = float(d_fwd)
            tau_v = tau_pred.predict_tau(obs)
            if tau_v is not None:
                obs.info["tau_pred"] = float(tau_v)

            vstep = _vision_step(
                obs=obs,
                detector=detector,
                tracker=tracker,
                depth_pred=depth_pred,
                intrinsics=intrinsics,
                pos=p_curr,
                yaw=curr_yaw,
                prev_pos=p_prev_tracker,
                prev_yaw=prev_yaw_tracker,
                dt=dt_step,
                search_fwd_step=search_fwd_step,
                search_yaw_rate=float(args.search_yaw_rate),
                fallback_intent=fallback_intent,
                annot_goal=annot_goal,
                allow_fallback=bool(args.fallback_toward_g),
                prefer_nearest=bool(args.prefer_nearest_target),
                camera_fov_deg=float(args.camera_fov_deg),
                object_width_m=float(args.car_width_m),
                fuse_bbox_depth=bool(args.bbox_depth_fuse),
            )
            p_prev_tracker = p_curr.copy()
            prev_yaw_tracker = curr_yaw

            if vstep.perception and vstep.perception.get("measured_dist_m") is not None:
                min_d_measured = min(min_d_measured, float(vstep.perception["measured_dist_m"]))

            if vstep.det_hit:
                detections_hit += 1
            if vstep.using_fallback:
                steps_fallback += 1
            elif vstep.search_action is not None:
                steps_searching += 1
            elif vstep.using_vision:
                steps_vision += 1

            if vstep.target_world is not None:
                vision_target_last = vstep.target_world.copy()
                had_vision_lock = True
                d_vis = _goal_dist(p_curr, vstep.target_world)
                min_d_vision = min(min_d_vision, d_vis)
                d_final_vision = d_vis
                if d_vis <= float(args.success_dist) or vstep.tracker_state == TS.ARRIVED.value:
                    arrived = True

            d_annot = _goal_dist(p_curr, annot_goal)
            min_d_annot = min(min_d_annot, d_annot)
            s_prog = float(max(0.0, d0_annot - d_annot))

            if arrived:
                break

            phys = body_delta_limits(dt_step)
            if vstep.search_action is not None:
                search_action = np.asarray(vstep.search_action, dtype=np.float64).copy()
                if ep_z_hold is not None:
                    z_err = float(ep_z_hold) - float(p_curr[2])
                    search_action[2] = float(
                        np.clip(z_err * float(args.search_z_gain), -float(phys[2]), float(phys[2]))
                    )
                vx_step_limit = float(min(float(args.cruise_speed) / float(args.step_hz), float(phys[0])))
                search_limits = np.array(
                    [vx_step_limit, float(phys[1]), float(phys[2]), float(phys[3])],
                    dtype=np.float64,
                )
                action = clip_body_delta(search_action, search_limits)
                g_rel_body = np.array([1.0, 0.0, 0.0, 1.0], dtype=np.float64)
                target_world = p_curr + np.array([1.0, 0.0, 0.0])
                wm_out = None
            else:
                assert vstep.goal_rel is not None and vstep.target_world is not None
                g_vis = np.asarray(vstep.target_world, dtype=np.float64)
                if vstep.using_vision and visual_intent is not None:
                    g_rel_body, s_info = visual_intent.compute(
                        curr_pos=p_curr,
                        curr_yaw=curr_yaw,
                        goal=g_vis,
                        d_fwd_hat=obs.info.get("depth_min_pred"),
                    )
                    target_world = np.array(s_info["target_world"], dtype=np.float64)
                    safe_v = float(s_info.get("safe_speed_limit", args.cruise_speed))
                else:
                    g_rel_body = np.asarray(vstep.goal_rel, dtype=np.float64)
                    target_world = g_vis
                    safe_v = float(args.cruise_speed)
                vx_step_limit = float(min(safe_v / float(args.step_hz), float(phys[0])))
                cur_limits = np.array([vx_step_limit, float(phys[1]), float(phys[2]), float(phys[3])], dtype=np.float64)
                if planner is not None:
                    planner.action_limits = cur_limits
                obs.info["goal"] = target_world.tolist()
                obs.info["goal_rel"] = g_rel_body.tolist()
                if planner is not None:
                    planner.set_goal(target_world)
                action = policy.act(obs)
                if planner is not None:
                    action = planner.plan(obs, action, latent=policy._latent)
                action = clip_body_delta(action, cur_limits)
                wm_out = None
                if policy._latent is not None and hasattr(dynamics, "step"):
                    try:
                        wm_out = dynamics.step(
                            policy._latent, action, goal_rel=g_rel_body,
                            body_vel=body_vel_from_obs(obs),
                        )
                    except Exception:
                        wm_out = None

            if shield is not None:
                act_safe, overridden = shield.apply_action(action, obs, wm_out=wm_out, limits=action_limits)
                if overridden:
                    interventions += 1
                    intervened_steps.add(step)
                action = act_safe

            step_out = env.step(action)
            if len(step_out) == 4:
                obs, _rew, done, step_info = step_out
            else:
                obs, step_info = step_out
                done = bool(getattr(obs, "collided", False))

            p_prev = p_curr.copy()
            p_curr = np.array(obs.position, dtype=np.float64)
            curr_yaw = float(obs.yaw) if hasattr(obs, "yaw") else curr_yaw

            if float(np.linalg.norm(p_curr - p_prev)) > 20.0:
                logger.error("Route %02d F-tele step=%d — invalidated", ep_idx + 1, step)
                fail_tag = "F-tele"
                break

            traj.append(p_curr.copy())

            if traj_writer is not None:
                traj_writer.write(json.dumps({
                    "step": step,
                    "pos": p_curr.tolist(),
                    "tracker_state": vstep.tracker_state,
                    "det_hit": vstep.det_hit,
                    "using_vision": vstep.using_vision,
                    "using_fallback": vstep.using_fallback,
                    "goal_rel": None if vstep.goal_rel is None else [round(float(x), 3) for x in vstep.goal_rel],
                }) + "\n")

            if perception_writer is not None and vstep.perception is not None:
                perc_row = dict(vstep.perception)
                perc_row.update({
                    "step": step,
                    "tracker_state": vstep.tracker_state,
                    "det_hit": vstep.det_hit,
                    "goal_rel_dist": (
                        round(float(vstep.goal_rel[3]), 3) if vstep.goal_rel is not None else None
                    ),
                })
                perception_writer.write(json.dumps(perc_row) + "\n")

            if vision_target_last is not None:
                seg_d = _segment_min_dist(p_prev, p_curr, vision_target_last)
                if seg_d <= float(args.success_dist):
                    arrived = True
                    min_d_vision = min(min_d_vision, seg_d)
                    d_final_vision = float(seg_d)
                    break

            if done:
                collided = bool(getattr(obs, "collided", False) or step_info.get("collided", False))
                if step_info.get("severe_collision", False) or collided:
                    severe_coll = True
                break

        if traj_writer is not None:
            traj_writer.close()
        if perception_writer is not None:
            perception_writer.close()

        actual_len = float(np.sum(np.linalg.norm(np.diff(np.array(traj), axis=0), axis=1))) if len(traj) > 1 else 0.0
        prog_ratio = float(np.clip(s_prog / max(1e-3, ref_len), 0.0, 1.0))
        ep_spl = (ref_len / max(ref_len, actual_len)) if arrived else 0.0
        goal_closure = _goal_closure(d0_annot, min_d_annot)
        n_steps = max(1, len(traj))

        ep_result = {
            "route_idx": ep_idx,
            "base_route_idx": r_info.get("base_route_idx"),
            "nominal_length_m": round(ref_len, 2),
            "actual_length_m": round(actual_len, 2),
            "steps": len(traj),
            "d_start_m": round(d0_annot, 2),
            "d_min_m": round(min_d_annot, 2),
            "d_final_m": round(float(min_d_vision if had_vision_lock else d_annot), 2),
            "d_min_vision_m": round(float(min_d_vision), 2) if had_vision_lock else None,
            "d_min_measured_m": round(float(min_d_measured), 2) if np.isfinite(min_d_measured) else None,
            "d_final_vision_m": round(float(d_final_vision), 2) if had_vision_lock else None,
            "gt_goal_world": [round(float(x), 2) for x in annot_goal] if args.gt_nearest_scene_object else None,
            "goal_closure": round(goal_closure, 4),
            "arrived": arrived,
            "arrived_vision": bool(arrived and had_vision_lock and steps_fallback == 0),
            "collided": collided,
            "severe_collision": severe_coll,
            "progress_ratio": round(prog_ratio, 4),
            "spl": round(ep_spl, 4),
            "intervention_rate": round(interventions / n_steps, 4),
            "subgoal_source": "visual",
            "goal_from": "vision" if had_vision_lock and steps_fallback == 0 else ("mixed" if steps_fallback else "search_only"),
            "detections_hit": detections_hit,
            "steps_searching": steps_searching,
            "steps_vision": steps_vision,
            "steps_fallback": steps_fallback,
            "detection_frac": round(detections_hit / n_steps, 4),
            "vision_frac": round(steps_vision / n_steps, 4),
            "fail_tag": fail_tag,
        }
        results.append(ep_result)

        scored_so_far = [r for r in results if not r.get("spawn_fail")]
        sr_now = float(np.mean([r["arrived"] for r in scored_so_far])) if scored_so_far else 0.0
        logger.info(
            "Route %02d/%02d | arrived=%s vision=%s det=%.0f%% vis=%.0f%% fb=%d IR=%.0f%% | SR=%.1f%%",
            slot + 1, n_routes, arrived, ep_result["goal_from"],
            ep_result["detection_frac"] * 100, ep_result["vision_frac"] * 100,
            steps_fallback, ep_result["intervention_rate"] * 100, sr_now * 100,
        )

    scored, spawn_fails, metrics, verdict = aggregate_metrics(results)
    metrics["mean_detection_frac"] = round(
        float(np.mean([r["detection_frac"] for r in scored])), 4
    ) if scored else 0.0
    metrics["mean_vision_frac"] = round(
        float(np.mean([r["vision_frac"] for r in scored])), 4
    ) if scored else 0.0

    summary = {
        "verdict": verdict,
        "n_scored": len(scored),
        "n_spawn_fail": len(spawn_fails),
        "metrics": metrics,
        "protocol_version": "phase2_vgoal_m2",
        "method": "monocular_visual",
        "goal_from": "vision",
        "config": {
            "actor_ckpt": str(args.actor_ckpt),
            "wm_ckpt": str(args.wm_ckpt),
            "cruise_speed": args.cruise_speed,
            "tti_coeff": args.tti_coeff,
            "detector": args.detector,
            "target_class": args.target_class,
            "visual_prompt": visual_prompt,
            "yolo_model": args.yolo_model,
            "fallback_toward_g": bool(args.fallback_toward_g),
            "search_fwd_speed": search_fwd_step,
            "search_fwd_mode": search_fwd_label,
            "search_yaw_rate": args.search_yaw_rate,
            "search_z_hold_mode": args.search_z_hold_mode,
            "search_z_min": float(args.search_z_min),
            "search_z_max": float(args.search_z_max),
            "search_z_gain": float(args.search_z_gain),
            "visual_toward_g": bool(args.visual_toward_g),
            "toward_g_r_m": float(args.toward_g_r_m),
            "tracker_min_confidence": tracker_min_conf,
            "tracker_near_dist_m": float(args.tracker_near_dist_m),
            "tracker_near_ema_alpha": float(args.tracker_near_ema_alpha),
            "tracker_inflate_reject_m": float(args.tracker_inflate_reject_m),
            "tracker_inflate_alpha": float(args.tracker_inflate_alpha),
            "car_width_m": float(args.car_width_m),
            "bbox_depth_fuse": bool(args.bbox_depth_fuse),
            "perception_log": bool(args.perception_log),
            "gt_nearest_scene_object": bool(args.gt_nearest_scene_object),
            "gt_scene_pattern": str(args.gt_scene_pattern),
            "yolo_conf": float(args.yolo_conf),
            "fanout_rgb": use_fanout,
            "capture_w": int(args.capture_w),
            "capture_h": int(args.capture_h),
            "wam_encode_size": int(args.wam_encode_size),
        },
        "episodes": results,
    }

    out_path = (root / args.out).resolve() if not Path(args.out).is_absolute() else Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    logger.info("Written: %s", out_path)
    logger.info(
        "FINAL | Verdict=%s SR=%.1f%% SCR=%.1f%% det=%.0f%% vision=%.0f%%",
        verdict,
        metrics["arrival_rate"] * 100,
        metrics["severe_collision_rate"] * 100,
        metrics.get("mean_detection_frac", 0) * 100,
        metrics.get("mean_vision_frac", 0) * 100,
    )
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
