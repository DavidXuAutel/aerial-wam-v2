#!/usr/bin/env python3
"""Visual Goal Phase-2 evaluator.

Replaces the geometric toward_g subgoal with a camera-based visual detector
+ spatial tracker from aerial-vgoal-wam.

Stack:
  GroundTruthVisualTargetDetector (AirSim GT) | YOLO Detector (real deploy)
    → TargetTracker (dead-reckoning, occlusion handling)
    → goal_rel [d_fwd, d_left, d_up, dist] in body frame
    → LatentActorDeployPolicy (Phase-2 AC ckpt)
    → optional ImaginationPlanner
    → ThreeZoneSpeedShield (tti_coeff=2.5 baseline)
    → env.step

Fallback: when tracker is SEARCHING (no detection memory), falls back to
toward_g geometry until the target comes into camera FOV.

Ckpt defaults match Phase-2 close config (E2 ckpt + tti=2.5).
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import yaml


logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("wam_vgoal_eval")


# ---------------------------------------------------------------------------
# Re-use metric helpers from Phase-2 eval (safe to import as module)
# ---------------------------------------------------------------------------
def _goal_dist(pos: np.ndarray, goal: np.ndarray) -> float:
    return float(np.linalg.norm(
        np.asarray(goal, dtype=np.float64).reshape(3)
        - np.asarray(pos, dtype=np.float64).reshape(3)
    ))


def _goal_closure(d_start_m: float, d_min_m: float) -> float:
    d0 = float(max(1e-3, d_start_m))
    return float(np.clip(1.0 - float(d_min_m) / d0, 0.0, 1.0))


def _segment_min_dist(p0: np.ndarray, p1: np.ndarray, goal: np.ndarray) -> float:
    p0_arr = np.asarray(p0, dtype=np.float64).reshape(3)
    p1_arr = np.asarray(p1, dtype=np.float64).reshape(3)
    g = np.asarray(goal, dtype=np.float64).reshape(3)
    v = p1_arr - p0_arr
    v_sq = float(np.sum(v**2))
    if v_sq < 1e-8:
        return float(np.linalg.norm(p0_arr - g))
    t = float(np.clip(np.dot(g - p0_arr, v) / v_sq, 0.0, 1.0))
    return float(np.linalg.norm(p0_arr + t * v - g))


# Same PASS gates as Phase-2 mainline.
PASS_THRESHOLDS: Dict[str, float] = {
    "arrival_rate_min": 0.80,
    "severe_collision_rate_max": 0.10,
}


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


# ---------------------------------------------------------------------------
# vgoal GroundTruth simulator (mirrors eval_visual_goal_airsim.py)
# ---------------------------------------------------------------------------

class _GroundTruthDetector:
    """Projects 3D goal into 2D camera and returns a DetectionResult with direct_depth."""

    def __init__(self, fov_deg: float = 80.0, img_w: int = 224, img_h: int = 224) -> None:
        from vgoal.geometry import CameraIntrinsics
        self.intrinsics = CameraIntrinsics.from_fov(fov_deg, width=img_w, height=img_h)
        self._goal_world: Optional[np.ndarray] = None
        self._pos: Optional[np.ndarray] = None
        self._yaw: float = 0.0

    def set_goal(self, goal_world: np.ndarray) -> None:
        self._goal_world = np.asarray(goal_world, dtype=np.float64).reshape(3)

    def set_pose(self, pos: np.ndarray, yaw: float) -> None:
        self._pos = np.asarray(pos, dtype=np.float64).reshape(3)
        self._yaw = float(yaw)

    def detect(self, rgb: Optional[np.ndarray] = None):  # -> Optional[DetectionResult]
        """Simulate detection by projecting 3D goal into body-frame camera."""
        if self._goal_world is None or self._pos is None:
            return None
        from vgoal.geometry import project_3d_to_pixel
        from vgoal.detector import DetectionResult
        d_world = self._goal_world - self._pos
        c, s = math.cos(self._yaw), math.sin(self._yaw)
        d_fwd = float(c * d_world[0] + s * d_world[1])
        d_left = float(-s * d_world[0] + c * d_world[1])
        d_up = float(d_world[2])
        if d_fwd <= 0.5:
            return None  # goal is behind the drone
        intr = self.intrinsics
        # x_cam = -d_left (body-left = camera-right → negative x_cam)
        # y_cam = -d_up  (body-up = camera-up → depends on convention; WAM uses -y_cam=d_up)
        x_cam = -d_left
        y_cam = -d_up
        u = float(intr.cx + intr.fx * x_cam / d_fwd)
        v = float(intr.cy + intr.fy * y_cam / d_fwd)
        w, h = intr.width, intr.height
        if not (0 <= u < w and 0 <= v < h):
            return None  # out of FOV
        half_box = max(6.0, 20.0 * (10.0 / max(1.0, d_fwd)))
        bbox = np.array([
            max(0.0, u - half_box), max(0.0, v - half_box),
            min(float(w - 1), u + half_box), min(float(h - 1), v + half_box),
        ], dtype=np.float32)
        res = DetectionResult(bbox=bbox, confidence=0.95, class_id=0, class_name="goal")
        setattr(res, "direct_depth", float(d_fwd))
        # Store lateral offsets so goal_rel can be constructed without a depth map
        setattr(res, "_d_left", d_left)
        setattr(res, "_d_up", d_up)
        return res


def _det_to_goal_rel(det: Any, intrinsics: Any) -> Optional[np.ndarray]:
    """Convert DetectionResult → body-frame goal_rel [d_fwd, d_left, d_up, dist]."""
    d_fwd = float(getattr(det, "direct_depth", 0.0) or 0.0)
    if d_fwd <= 0.0:
        return None
    # Prefer stored lateral offsets (GroundTruthDetector) for accuracy
    d_left_stored = getattr(det, "_d_left", None)
    d_up_stored = getattr(det, "_d_up", None)
    if d_left_stored is not None and d_up_stored is not None:
        d_left = float(d_left_stored)
        d_up = float(d_up_stored)
    else:
        u_c = float((det.bbox[0] + det.bbox[2]) * 0.5)
        v_c = float((det.bbox[1] + det.bbox[3]) * 0.5)
        x_cam = (u_c - intrinsics.cx) * d_fwd / intrinsics.fx
        y_cam = (v_c - intrinsics.cy) * d_fwd / intrinsics.fy
        d_left = float(-x_cam)
        d_up = float(-y_cam)
    dist = float(np.sqrt(d_fwd**2 + d_left**2 + d_up**2))
    return np.array([d_fwd, d_left, d_up, dist], dtype=np.float64)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:  # noqa: C901
    parser = argparse.ArgumentParser(description="Visual Goal Phase-2 eval (vgoal integration)")
    parser.add_argument("--config", default="configs/aerial_rl.yaml")
    parser.add_argument(
        "--wm-ckpt",
        default="experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt",
        help="WM checkpoint (Phase-2 baseline)",
    )
    parser.add_argument(
        "--actor-ckpt",
        default=(
            "experiments/aerial/rl/artifacts/"
            "v4_ac_ckpt_phase2_toward_g_20260905_112006/v4_ac_latest.pt"
        ),
        help="Phase-2 E2 actor ckpt (tti=2.5 baseline)",
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
    parser.add_argument("--routes", type=str, default=None,
                        help="Comma-separated 0-based route indices")
    parser.add_argument("--step-hz", type=float, default=5.0)
    parser.add_argument("--max-steps", type=int, default=1000)
    parser.add_argument("--cruise-speed", type=float, default=10.0)
    parser.add_argument("--tti-coeff", type=float, default=2.5,
                        help="ThreeZoneShield tti_coeff (2.5 = Phase-2 close config)")
    parser.add_argument("--success-dist", type=float, default=3.0)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--planner", action="store_true")
    parser.add_argument("--planner-horizon", type=int, default=5)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--out", default="artifacts/wam_vgoal_eval_result.json")
    parser.add_argument("--spawn-tol-m", type=float, default=12.0)
    parser.add_argument(
        "--traj-out",
        default=None,
        help="Directory for per-route JSONL trajectory files",
    )
    # vgoal-specific
    parser.add_argument(
        "--vgoal-repo",
        default=os.path.expanduser("~/Projects/aerial-vgoal-wam"),
        help="Path to aerial-vgoal-wam repo (for vgoal.* imports)",
    )
    parser.add_argument(
        "--camera-fov-deg",
        type=float,
        default=80.0,
        help="Horizontal camera FOV for projection / back-projection",
    )
    parser.add_argument(
        "--img-w",
        type=int,
        default=224,
        help="Detection image width in pixels (for pinhole projection)",
    )
    parser.add_argument(
        "--img-h",
        type=int,
        default=224,
        help="Detection image height in pixels",
    )
    parser.add_argument(
        "--tracker-max-occlusion-s",
        type=float,
        default=2.0,
        help="Tracker max occlusion seconds before resetting to SEARCHING",
    )
    parser.add_argument(
        "--tracker-ema-alpha",
        type=float,
        default=0.7,
        help="Tracker EMA smoothing for new measurements (1.0 = no smoothing)",
    )
    parser.add_argument(
        "--fallback-toward-g",
        action="store_true",
        default=True,
        help="Fall back to toward_g when tracker is SEARCHING (default ON)",
    )
    parser.add_argument(
        "--no-fallback-toward-g",
        dest="fallback_toward_g",
        action="store_false",
        help="Disable toward_g fallback (hover/search only when SEARCHING)",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    # Wire vgoal repo into sys.path so `from vgoal.xxx import ...` resolves
    vgoal_repo = Path(args.vgoal_repo).expanduser().resolve()
    if not vgoal_repo.is_dir():
        raise SystemExit(f"--vgoal-repo not found: {vgoal_repo}")
    if str(vgoal_repo) not in sys.path:
        sys.path.insert(0, str(vgoal_repo))

    from vgoal.geometry import CameraIntrinsics
    from vgoal.tracker import TargetTracker, TargetState, TrackerConfig

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
    logger.info("device=%s mock=%s", device, args.mock)

    anno_path = (
        (root / args.annotation).resolve()
        if not Path(args.annotation).is_absolute()
        else Path(args.annotation)
    )
    with open(anno_path, "r", encoding="utf-8") as f:
        anno_data = json.load(f)
    routes = anno_data.get("routes", anno_data) if isinstance(anno_data, dict) else anno_data
    route_idxs = _select_route_indices(len(routes), args.episodes, args.routes)
    n_routes = len(route_idxs)

    env_cfg = dict(cfg.get("env") or {})
    env_cfg["backend"] = "mock" if args.mock else "airsim"
    env_cfg["step_hz"] = float(args.step_hz)
    env_cfg["grab_depth"] = True
    env = _build_env(env_cfg)

    wm_cfg = cfg.get("world_model") or {}
    wm_path = (
        (root / args.wm_ckpt).resolve()
        if not Path(args.wm_ckpt).is_absolute()
        else Path(args.wm_ckpt)
    )
    dynamics, _ = load_torch_dynamics(
        wm_cfg, str(wm_path), device=device_str, success_dist_m=float(args.success_dist)
    )

    actor_path = (
        (root / args.actor_ckpt).resolve()
        if not Path(args.actor_ckpt).is_absolute()
        else Path(args.actor_ckpt)
    )
    if not args.mock and actor_path.exists():
        actor_ac = LatentActorCritic.load_from_checkpoint(actor_path, device=device_str)
        actor_ac.config.goal_feat_mode = "meter"
        logger.info("Loaded actor-critic from %s", actor_path)
    else:
        actor_ac = LatentActorCritic.from_config(
            {"latent_dim": dynamics.latent_dim, "device": device_str}
        )

    depth_path = (
        (root / args.depth_ckpt).resolve()
        if not Path(args.depth_ckpt).is_absolute()
        else Path(args.depth_ckpt)
    )
    depth_pred = (
        DepthMinPredictor.from_checkpoint(depth_path, device=device_str)
        if (not args.mock and depth_path.is_file())
        else None
    )
    if depth_pred is None and not args.mock:
        raise SystemExit(
            f"depth checkpoint not found: {depth_path} — pass --depth-ckpt or --mock"
        )

    tau_path = (
        (root / args.tau_ckpt).resolve()
        if not Path(args.tau_ckpt).is_absolute()
        else Path(args.tau_ckpt)
    )
    tau_pred = make_tau_predictor(
        kind="foe_calibrated",
        ckpt=tau_path if (not args.mock and tau_path.is_file()) else None,
        device=device_str,
    )

    phys_limits = body_delta_limits(1.0 / float(args.step_hz))
    vx_max_step = float(min(float(args.cruise_speed) / float(args.step_hz), float(phys_limits[0])))
    action_limits = np.array(
        [vx_max_step, float(phys_limits[1]), float(phys_limits[2]), float(phys_limits[3])],
        dtype=np.float64,
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

    # toward_g fallback intent (used when tracker is SEARCHING)
    fallback_intent = TowardGoalIntent(r_m=100.0, mode="toward_g", cruise_speed=float(args.cruise_speed))

    # vgoal detector + tracker setup
    intrinsics = CameraIntrinsics.from_fov(
        args.camera_fov_deg, width=args.img_w, height=args.img_h
    )
    tracker_cfg = TrackerConfig(
        success_dist_m=float(args.success_dist),
        max_occlusion_s=float(args.tracker_max_occlusion_s),
        ema_alpha=float(args.tracker_ema_alpha),
        min_confidence=0.5,
    )
    # GroundTruth detector uses AirSim GT goal position (swap for YOLO in real deploy)
    detector = _GroundTruthDetector(
        fov_deg=float(args.camera_fov_deg),
        img_w=int(args.img_w),
        img_h=int(args.img_h),
    )

    logger.info(
        "vgoal eval: %d routes | cs=%.1f tti=%.1f | fov=%.0f img=%dx%d "
        "tracker_occ=%.1fs ema=%.2f fallback_toward_g=%s",
        n_routes, args.cruise_speed, args.tti_coeff,
        args.camera_fov_deg, args.img_w, args.img_h,
        args.tracker_max_occlusion_s, args.tracker_ema_alpha,
        args.fallback_toward_g,
    )

    results: List[Dict[str, Any]] = []

    for slot, ep_idx in enumerate(route_idxs):
        r_info = routes[ep_idx]
        pts = np.array(r_info.get("pos", r_info.get("positions")), dtype=np.float64)
        goal_pos = pts[-1].copy()
        start_pos = pts[0].copy()
        yaws = np.array(r_info.get("yaw", [0.0] * len(pts)), dtype=np.float64)
        start_yaw = float(yaws[0]) if len(yaws) else 0.0
        ref_len = float(np.sum(np.linalg.norm(pts[1:] - pts[:-1], axis=1)))

        # Per-episode resets
        policy.reset()
        shield.reset()
        tau_pred.reset()
        fallback_intent.reset()
        if depth_pred is not None:
            depth_pred.reset()
        if planner is not None:
            planner.reset()
        tracker = TargetTracker(tracker_cfg)        # fresh tracker per episode
        detector.set_goal(goal_pos)                  # tell GT detector where goal is

        ep_dict = {
            "pos": pts.tolist(),
            "yaw": yaws.tolist() if len(yaws) == len(pts) else [start_yaw] * len(pts),
            "gpt_instruction": r_info.get("gpt_instruction", ""),
        }
        obs = env.reset(ep_dict)

        p_curr = np.array(obs.position, dtype=np.float64)
        curr_yaw = float(obs.yaw) if hasattr(obs, "yaw") else 0.0
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

        d0 = _goal_dist(p_curr, goal_pos)
        min_d = d0
        d_final = d0
        traj = [p_curr.copy()]
        traj_writer = None
        if args.traj_out:
            _tp = Path(args.traj_out).with_suffix("") / f"route{ep_idx:02d}.jsonl"
            _tp.parent.mkdir(parents=True, exist_ok=True)
            traj_writer = _tp.open("w")

        arrived = False
        collided = False
        severe_coll = False
        fail_tag: Optional[str] = None
        interventions = 0
        intervened_steps: set = set()
        s_prog = 0.0
        p_prev_tracker = p_curr.copy()  # for ego-motion dead-reckoning
        prev_yaw_tracker = curr_yaw
        detections_hit = 0
        steps_searching = 0

        for step in range(args.max_steps):
            # --- Depth prediction ---
            d_fwd = None
            obs.info.pop("depth_min_pred", None)
            obs.info.pop("depth_cones_pred", None)
            obs.info.pop("tau_pred", None)
            if depth_pred is not None and obs.rgb is not None:
                pred_both = getattr(depth_pred, "predict_min_and_cones", None)
                if callable(pred_both):
                    d_min, cones = pred_both(obs)
                    if d_min is not None:
                        obs.info["depth_min_pred"] = float(d_min)
                        d_fwd = float(d_min)
                    if isinstance(cones, dict):
                        obs.info["depth_cones_pred"] = {
                            k: (float(v) if v is not None else None)
                            for k, v in cones.items()
                        }
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

            # --- Visual detection ---
            detector.set_pose(p_curr, curr_yaw)
            det = detector.detect(obs.rgb if obs.rgb is not None else None)
            measured_gr: Optional[np.ndarray] = None
            det_conf = 0.0
            if det is not None:
                measured_gr = _det_to_goal_rel(det, intrinsics)
                det_conf = float(det.confidence)
                if measured_gr is not None:
                    detections_hit += 1

            # --- Ego-motion for tracker dead-reckoning ---
            d_world = p_curr - p_prev_tracker
            dyaw_dr = float(curr_yaw - prev_yaw_tracker)
            dyaw_dr = float((dyaw_dr + math.pi) % (2.0 * math.pi) - math.pi)
            c_yaw, s_yaw = math.cos(prev_yaw_tracker), math.sin(prev_yaw_tracker)
            ego_delta = np.array([
                c_yaw * d_world[0] + s_yaw * d_world[1],
                -s_yaw * d_world[0] + c_yaw * d_world[1],
                d_world[2],
            ], dtype=np.float64)
            p_prev_tracker = p_curr.copy()
            prev_yaw_tracker = curr_yaw

            dt_step = 1.0 / float(args.step_hz)
            tracker_state = tracker.update(
                measured_gr,
                dt=dt_step,
                ego_delta_body=ego_delta,
                ego_delta_yaw=dyaw_dr,
                confidence=det_conf,
            )

            # --- Build goal_rel for policy ---
            cur_goal_rel = tracker.goal_rel  # 4D [d_fwd, d_left, d_up, dist] or None
            using_fallback = False

            if cur_goal_rel is not None and tracker_state != TargetState.SEARCHING:
                # Tracker has a valid 3D estimate — use it directly
                g_rel_body = np.asarray(cur_goal_rel, dtype=np.float64)
                c, ss = math.cos(curr_yaw), math.sin(curr_yaw)
                target_world = p_curr + np.array([
                    c * g_rel_body[0] - ss * g_rel_body[1],
                    ss * g_rel_body[0] + c * g_rel_body[1],
                    g_rel_body[2],
                ], dtype=np.float64)
                rem_dist = float(g_rel_body[3]) if g_rel_body[3] > 0 else float(np.linalg.norm(g_rel_body[:3]))
                safe_v = float(args.cruise_speed)
                s_info: Dict[str, Any] = {"target_world": target_world.tolist(), "rem_dist": rem_dist}
            elif args.fallback_toward_g:
                # No detection memory — geometric toward_g fallback
                g_rel_body, s_info = fallback_intent.compute(
                    curr_pos=p_curr, curr_yaw=curr_yaw, goal=goal_pos, d_fwd_hat=d_fwd
                )
                target_world = np.array(s_info["target_world"], dtype=np.float64)
                rem_dist = float(s_info["rem_dist"])
                safe_v = float(s_info.get("safe_speed_limit", args.cruise_speed))
                using_fallback = True
                steps_searching += 1
            else:
                # Slow forward drift when searching without fallback
                g_rel_body = np.array([1.0, 0.0, 0.0, 1.0], dtype=np.float64)
                target_world = p_curr + np.array([1.0, 0.0, 0.0])
                rem_dist = float(_goal_dist(p_curr, goal_pos))
                safe_v = 1.0
                s_info = {"target_world": target_world.tolist(), "rem_dist": rem_dist}
                steps_searching += 1

            # --- Action limits and distance bookkeeping ---
            phys = body_delta_limits(1.0 / float(args.step_hz))
            vx_step_limit = float(min(safe_v / float(args.step_hz), float(phys[0])))
            cur_limits = np.array(
                [vx_step_limit, float(phys[1]), float(phys[2]), float(phys[3])],
                dtype=np.float64,
            )
            if planner is not None:
                planner.action_limits = cur_limits

            d_to_goal = _goal_dist(p_curr, goal_pos)
            d_final = float(d_to_goal)
            if d_to_goal < min_d:
                min_d = d_to_goal
            s_prog = float(max(0.0, d0 - d_to_goal))

            if d_to_goal <= float(args.success_dist):
                arrived = True
                break

            # --- Policy step ---
            obs.info["goal"] = target_world.tolist()
            obs.info["goal_rel"] = g_rel_body.tolist()
            if planner is not None:
                planner.set_goal(target_world)

            action = policy.act(obs)
            if planner is not None:
                action = planner.plan(obs, action, latent=policy._latent)
            action = clip_body_delta(action, cur_limits)

            # WM rollout for shield
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
                act_safe, overridden = shield.apply_action(
                    action, obs, wm_out=wm_out, limits=cur_limits
                )
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

            _step_jump = float(np.linalg.norm(p_curr - p_prev))
            if _step_jump > 20.0:
                logger.error(
                    "Route %02d F-tele teleportation step=%d jump=%.1fm — invalidated",
                    ep_idx + 1, step, _step_jump,
                )
                fail_tag = "F-tele"
                break

            traj.append(p_curr.copy())

            if traj_writer is not None:
                traj_writer.write(json.dumps({
                    "step": step,
                    "pos": p_curr.tolist(),
                    "yaw_deg": round(float(np.degrees(curr_yaw)), 2),
                    "d_to_g": round(float(np.linalg.norm(goal_pos - p_curr)), 2),
                    "d_fwd": round(float(d_fwd), 3) if d_fwd is not None else None,
                    "tracker_state": str(tracker_state.value),
                    "det_hit": measured_gr is not None,
                    "using_fallback": using_fallback,
                    "goal_rel": [round(float(x), 3) for x in g_rel_body],
                    "intervened": bool(step in intervened_steps),
                }) + "\n")

            seg_d = _segment_min_dist(p_prev, p_curr, goal_pos)
            if seg_d <= float(args.success_dist):
                arrived = True
                min_d = min(min_d, seg_d)
                d_final = float(seg_d)
                break

            if done:
                collided = bool(
                    getattr(obs, "collided", False) or step_info.get("collided", False)
                )
                if step_info.get("severe_collision", False) or collided:
                    severe_coll = True
                break

        if traj_writer is not None:
            traj_writer.close()

        actual_len = (
            float(np.sum(np.linalg.norm(np.diff(np.array(traj), axis=0), axis=1)))
            if len(traj) > 1 else 0.0
        )
        prog_ratio = float(np.clip(s_prog / max(1e-3, ref_len), 0.0, 1.0))
        ep_spl = (ref_len / max(ref_len, actual_len)) if arrived else 0.0
        goal_closure = _goal_closure(d0, min_d)

        ep_result = {
            "route_idx": ep_idx,
            "base_route_idx": r_info.get("base_route_idx"),
            "nominal_length_m": round(ref_len, 2),
            "actual_length_m": round(actual_len, 2),
            "steps": len(traj),
            "d_start_m": round(d0, 2),
            "d_min_m": round(min_d, 2),
            "d_final_m": round(float(d_final), 2),
            "goal_closure": round(goal_closure, 4),
            "arrived": arrived,
            "collided": collided,
            "severe_collision": severe_coll,
            "progress_ratio": round(prog_ratio, 4),
            "spl": round(ep_spl, 4),
            "intervention_rate": round(interventions / max(1, len(traj)), 4),
            "subgoal_source": "visual",
            "detections_hit": detections_hit,
            "steps_searching": steps_searching,
            "detection_frac": round(detections_hit / max(1, len(traj)), 4),
            "fail_tag": fail_tag,
        }
        results.append(ep_result)

        scored_so_far = [r for r in results if not r.get("spawn_fail")]
        sr_now = float(np.mean([r["arrived"] for r in scored_so_far])) if scored_so_far else 0.0
        logger.info(
            "Route %02d/%02d | arrived=%s d_final=%.1fm det_frac=%.0f%% search_steps=%d "
            "IR=%.0f%% | SR_now=%.1f%%",
            slot + 1, n_routes,
            arrived, float(d_final),
            ep_result["detection_frac"] * 100,
            steps_searching,
            ep_result["intervention_rate"] * 100,
            sr_now * 100,
        )

    # --- Aggregate ---
    scored = [r for r in results if not r.get("spawn_fail")]
    spawn_fails = [r for r in results if r.get("spawn_fail")]

    def _mean(key: str) -> float:
        return float(np.mean([r[key] for r in scored])) if scored else 0.0

    sr = _mean("arrived")
    scr = _mean("severe_collision")
    metrics = {
        "arrival_rate": round(sr, 4),
        "spl": round(_mean("spl"), 4),
        "severe_collision_rate": round(scr, 4),
        "mean_goal_closure": round(_mean("goal_closure"), 4),
        "mean_progress_ratio": round(_mean("progress_ratio"), 4),
        "mean_intervention_rate": round(_mean("intervention_rate"), 4),
        "mean_detection_frac": round(_mean("detection_frac"), 4),
        "mean_steps_searching": round(_mean("steps_searching"), 1),
    }
    verdict = (
        "PASS"
        if sr >= PASS_THRESHOLDS["arrival_rate_min"] and scr <= PASS_THRESHOLDS["severe_collision_rate_max"]
        else "FAIL"
    )

    summary = {
        "verdict": verdict,
        "n_scored": len(scored),
        "n_spawn_fail": len(spawn_fails),
        "metrics": metrics,
        "config": {
            "actor_ckpt": str(args.actor_ckpt),
            "wm_ckpt": str(args.wm_ckpt),
            "cruise_speed": args.cruise_speed,
            "tti_coeff": args.tti_coeff,
            "camera_fov_deg": args.camera_fov_deg,
            "tracker_max_occlusion_s": args.tracker_max_occlusion_s,
            "fallback_toward_g": args.fallback_toward_g,
        },
        "episodes": results,
    }

    out_path = (
        (root / args.out).resolve()
        if not Path(args.out).is_absolute()
        else Path(args.out)
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    logger.info("Written: %s", out_path)

    logger.info(
        "FINAL | Verdict=%s SR=%.1f%% SCR=%.1f%% closure=%.2f "
        "det_frac=%.0f%% IR=%.0f%%",
        verdict,
        metrics["arrival_rate"] * 100,
        metrics["severe_collision_rate"] * 100,
        metrics["mean_goal_closure"],
        metrics["mean_detection_frac"] * 100,
        metrics["mean_intervention_rate"] * 100,
    )
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
