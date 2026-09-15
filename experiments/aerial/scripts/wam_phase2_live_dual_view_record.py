#!/usr/bin/env python3
"""Record Phase-2 closed-loop flight as live dual-view video (no pose replay).

Captures real RGB + yaw during ``wam_phase2_long_eval`` stack flight, and
renders a 3D map with the **active intent subgoal** (toward_g) — not the
inactive A* polyline corridor.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import yaml

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("phase2_live_dual")

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


def _encode_video(frames: List[np.ndarray], out_path: Path, fps: float) -> None:
    if shutil.which("ffmpeg"):
        bgr_frames = [cv2.cvtColor(f, cv2.COLOR_RGB2BGR) if f.shape[2] == 3 else f for f in frames]
        _write_video_ffmpeg(bgr_frames, out_path, fps=fps)
    else:
        raise RuntimeError("ffmpeg required for live dual-view encode")


def _overlay_intent_on_map(
    map_bgr: np.ndarray,
    renderer: Trajectory3DRenderer,
    drone_pos: np.ndarray,
    intent_pos: Optional[np.ndarray],
    goal_pos: np.ndarray,
    step: int,
    total_steps: int,
) -> np.ndarray:
    frame = map_bgr.copy()
    u_norm = step / max(total_steps - 1, 1)
    elev = 32.0 + 6.0 * math.sin(u_norm * math.pi)
    azim = -125.0 + 32.0 * u_norm

    # Direct start→goal bearing (toward_g macro plan)
    bear_pts = np.vstack([renderer.start_pos, goal_pos])
    bear_uv = renderer.project_3d_to_2d(bear_pts, elev, azim).astype(np.int32)
    for i in range(0, max(len(bear_uv) - 1, 1)):
        cv2.line(frame, tuple(bear_uv[0]), tuple(bear_uv[1]), (180, 80, 220), 1, cv2.LINE_AA)

    if intent_pos is not None:
        ip = np.asarray(intent_pos, dtype=np.float64).reshape(3)
        dr_uv = renderer.project_3d_to_2d(drone_pos.reshape(1, 3), elev, azim).astype(np.int32)[0]
        in_uv = renderer.project_3d_to_2d(ip.reshape(1, 3), elev, azim).astype(np.int32)[0]
        cv2.arrowedLine(frame, tuple(dr_uv), tuple(in_uv), (0, 200, 255), 2, tipLength=0.12, line_type=cv2.LINE_AA)
        cv2.circle(frame, tuple(in_uv), 7, (0, 180, 255), -1, cv2.LINE_AA)
        cv2.putText(
            frame, "INTENT (toward_g)", (in_uv[0] + 10, in_uv[1] - 6),
            cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 220, 255), 1, cv2.LINE_AA,
        )

    cv2.putText(
        frame, "CORRIDOR REF (inactive under toward_g)", (18, 64),
        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (120, 140, 160), 1, cv2.LINE_AA,
    )
    return frame


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--route-idx", type=int, default=6, help="0-based route (6=Route 07, best L_act/L_nom)")
    p.add_argument("--config", default="configs/aerial_rl.yaml")
    p.add_argument("--wm-ckpt", default="experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt")
    p.add_argument(
        "--actor-ckpt",
        default="experiments/aerial/rl/artifacts/v4_ac_ckpt_phase2_toward_g_20260905_112006/v4_ac_latest.pt",
    )
    p.add_argument("--depth-ckpt", default="experiments/aerial/rl/artifacts/depth_ckpt_p45mid_s8j_20260825/depth_best_holdout_da3_ft_head.pt")
    p.add_argument("--tau-ckpt", default="experiments/aerial/rl/artifacts/tau_ckpt_foe_r60_20260815/tau_foe_calibrator.pt")
    p.add_argument("--annotation", default="artifacts/seen_airsim16_long_routes.json")
    p.add_argument("--cruise-speed", type=float, default=10.0)
    p.add_argument("--max-steps", type=int, default=2000)
    p.add_argument("--step-hz", type=float, default=5.0)
    p.add_argument("--success-dist", type=float, default=3.0)
    p.add_argument("--planner-horizon", type=int, default=5)
    p.add_argument("--tti-coeff", type=float, default=2.5)
    p.add_argument("--goal-feat-mode", choices=("meter", "g_norm"), default="meter")
    p.add_argument("--fps", type=float, default=5.0)
    p.add_argument("--frame-stride", type=int, default=1)
    p.add_argument("--ego-width", type=int, default=448, help="must be multiple of 14 for DA3 depth head")
    p.add_argument("--ego-height", type=int, default=448)
    p.add_argument("--out-dir", default="artifacts/videos/wam_phase2_route07_live")
    p.add_argument("--out-prefix", default=None)
    args = p.parse_args()

    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    import torch
    from experiments.aerial.rl.actor_critic import LatentActorCritic, LatentActorDeployPolicy
    from experiments.aerial.rl.depth_predictor import DepthMinPredictor
    from experiments.aerial.rl.env.action import body_delta_limits, clip_body_delta
    from experiments.aerial.rl.goal_features import body_vel_from_obs
    from experiments.aerial.rl.planner import ImaginationPlanner
    from experiments.aerial.rl.reward import RewardConfig
    from experiments.aerial.rl.scene_intent import TowardGoalIntent
    from experiments.aerial.rl.tau_predictor import make_tau_predictor
    from experiments.aerial.rl.train_rl import _build_env, _build_safety, load_torch_dynamics

    cfg = yaml.safe_load((root / args.config).read_text())
    device_str = "cuda" if torch.cuda.is_available() else "cpu"

    with open(root / args.annotation, encoding="utf-8") as f:
        anno = json.load(f)
    routes = anno.get("routes", anno)
    r_info = routes[int(args.route_idx)]
    pts = np.array(r_info.get("pos", r_info.get("positions")), dtype=np.float64)
    goal_pos = pts[-1].copy()
    start_pos = pts[0].copy()
    ref_len = float(np.sum(np.linalg.norm(pts[1:] - pts[:-1], axis=1)))

    env_cfg = dict(cfg.get("env") or {})
    env_cfg["backend"] = "airsim"
    env_cfg["step_hz"] = float(args.step_hz)
    env_cfg["grab_depth"] = True
    env_cfg["width"] = int(args.ego_width)
    env_cfg["height"] = int(args.ego_height)
    env = _build_env(env_cfg)

    dynamics, _ = load_torch_dynamics(cfg.get("world_model") or {}, str(root / args.wm_ckpt), device=device_str, success_dist_m=float(args.success_dist))
    actor_ac = LatentActorCritic.load_from_checkpoint(str(root / args.actor_ckpt), device=device_str)
    actor_ac.config.goal_feat_mode = str(args.goal_feat_mode)

    phys = body_delta_limits(1.0 / float(args.step_hz))
    action_limits = np.array([
        min(float(args.cruise_speed) / float(args.step_hz), float(phys[0])),
        float(phys[1]), float(phys[2]), float(phys[3]),
    ], dtype=np.float64)
    reward_cfg = RewardConfig(**(cfg.get("reward") or {}))
    reward_cfg.success_dist_m = float(args.success_dist)
    planner = ImaginationPlanner(dynamics=dynamics, horizon=int(args.planner_horizon), reward_cfg=reward_cfg, action_limits=action_limits)
    policy = LatentActorDeployPolicy(dynamics, actor_ac, deterministic=True, stream_latent=True)

    depth_pred = DepthMinPredictor.from_checkpoint(str(root / args.depth_ckpt), device=device_str)
    tau_path = (root / args.tau_ckpt).resolve()
    tau_pred = make_tau_predictor(
        kind="foe_calibrated",
        ckpt=tau_path if tau_path.is_file() else None,
        device=device_str,
    )

    safety_cfg = dict(cfg.get("safety") or {})
    if str(safety_cfg.get("kind", "null")) in ("null", "none", "None"):
        safety_cfg["kind"] = "three_zone"
    safety_cfg.setdefault("three_zone", {})["v_cruise"] = float(args.cruise_speed)
    if args.tti_coeff is not None:
        safety_cfg["three_zone"]["tti_coeff"] = float(args.tti_coeff)
    shield = _build_safety(safety_cfg)

    intent = TowardGoalIntent(r_m=100.0, mode="toward_g", cruise_speed=float(args.cruise_speed))
    intent.reset()
    shield.reset()
    depth_pred.reset()
    tau_pred.reset()
    policy.reset()
    planner.reset()

    yaws_arr = np.array(r_info.get("yaw", [0.0] * len(pts)), dtype=np.float64)
    ep_dict = {
        "pos": pts.tolist(),
        "yaw": yaws_arr.tolist() if len(yaws_arr) == len(pts) else [float(yaws_arr[0])] * len(pts),
        "gpt_instruction": r_info.get("gpt_instruction", ""),
    }
    obs = env.reset(ep_dict)
    p_curr = np.array(obs.position, dtype=np.float64)
    curr_yaw = float(obs.yaw)
    d0 = _goal_dist(p_curr, goal_pos)

    renderer = Trajectory3DRenderer(start_pos, goal_pos, pts, out_size=(960, 720))
    route_label = f"PHASE-2 ROUTE {args.route_idx + 1:02d}"
    prefix = args.out_prefix or f"phase2_route{args.route_idx + 1:02d}_live"

    ego_frames: List[np.ndarray] = []
    map_frames: List[np.ndarray] = []
    dual_frames: List[np.ndarray] = []
    traj: List[np.ndarray] = [p_curr.copy()]
    interventions = 0
    arrived = False
    intent_target: Optional[np.ndarray] = None
    last_action: Optional[np.ndarray] = None

    logger.info("Live record route %02d d0=%.1fm toward_g", args.route_idx + 1, d0)

    for step in range(int(args.max_steps)):
        d_fwd = None
        obs.info.pop("depth_min_pred", None)
        obs.info.pop("depth_cones_pred", None)
        obs.info.pop("tau_pred", None)
        if obs.rgb is not None:
            pred_both = getattr(depth_pred, "predict_min_and_cones", None)
            if callable(pred_both):
                d_min, cones = pred_both(obs)
                if d_min is not None:
                    obs.info["depth_min_pred"] = float(d_min)
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

        g_rel_body, s_info = intent.compute(
            curr_pos=p_curr, curr_yaw=curr_yaw, goal=goal_pos, d_fwd_hat=d_fwd,
        )
        intent_target = np.array(s_info["target_world"], dtype=np.float64)
        safe_v = float(s_info.get("safe_speed_limit", args.cruise_speed))
        phys = body_delta_limits(1.0 / float(args.step_hz))
        cur_limits = np.array([
            float(min(safe_v / float(args.step_hz), float(phys[0]))),
            float(phys[1]), float(phys[2]), float(phys[3]),
        ], dtype=np.float64)
        planner.action_limits = cur_limits

        d_to_goal = _goal_dist(p_curr, goal_pos)
        if d_to_goal <= float(args.success_dist):
            arrived = True
            if step % max(1, int(args.frame_stride)) == 0:
                pass  # capture final frame below
            else:
                break

        obs.info["goal"] = intent_target.tolist()
        obs.info["goal_rel"] = g_rel_body.tolist()
        planner.set_goal(intent_target)
        action = policy.act(obs)
        action = planner.plan(obs, action, latent=policy._latent)
        action = clip_body_delta(action, cur_limits)
        last_action = action.copy()

        wm_out = None
        if policy._latent is not None:
            try:
                wm_out = dynamics.step(policy._latent, action, goal_rel=g_rel_body, body_vel=body_vel_from_obs(obs))
            except Exception:
                wm_out = None

        overridden = False
        if shield is not None:
            action, overridden = shield.apply_action(action, obs, wm_out=wm_out, limits=cur_limits)
            if overridden:
                interventions += 1

        stride = max(1, int(args.frame_stride))
        if step % stride == 0 and obs.rgb is not None:
            rgb = np.asarray(obs.rgb)
            bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            if bgr.shape[1] != args.ego_width or bgr.shape[0] != args.ego_height:
                bgr = cv2.resize(bgr, (int(args.ego_width), int(args.ego_height)))
            prog = (d0 - d_to_goal) / max(d0, 1e-3)
            ego_hud = _draw_hud_overlay(
                bgr=bgr, step=step + 1, total_steps=int(args.max_steps),
                dist_m=d_to_goal, d0_m=d0, progress_ratio=prog,
                pos=p_curr, yaw_rad=curr_yaw, action=last_action,
                arrived=(d_to_goal <= float(args.success_dist)),
                shield_interv=overridden, route_title=route_label,
            )
            full_traj = np.asarray(traj, dtype=np.float64)
            map_3d = renderer.render_frame(
                flown_so_far=full_traj, full_traj=full_traj,
                step=step + 1, total_steps=int(args.max_steps),
                dist_m=d_to_goal, d0_m=d0, prog_ratio=prog,
            )
            map_3d = _overlay_intent_on_map(
                map_3d, renderer, p_curr, intent_target, goal_pos, step + 1, int(args.max_steps),
            )
            ego_frames.append(cv2.cvtColor(ego_hud, cv2.COLOR_BGR2RGB))
            map_frames.append(map_3d)
            dual_frames.append(_compose_dual_view(ego_hud, map_3d, out_size=(1920, 720)))

        if arrived:
            break

        step_out = env.step(action)
        obs = step_out[0] if len(step_out) == 4 else step_out[0]
        p_curr = np.array(obs.position, dtype=np.float64)
        curr_yaw = float(obs.yaw)
        traj.append(p_curr.copy())

        if step % 100 == 0:
            logger.info("step=%d d_goal=%.1f frames=%d IR=%.2f", step, d_to_goal, len(ego_frames), interventions / max(1, step + 1))

    out_dir = (root / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    flown = np.asarray(traj, dtype=np.float64)
    d_final = _goal_dist(flown[-1], goal_pos)
    path_len = float(np.sum(np.linalg.norm(np.diff(flown, axis=0), axis=1))) if len(flown) > 1 else 0.0

    (out_dir / f"{prefix}_traj.json").write_text(json.dumps({
        "route_idx": int(args.route_idx),
        "ref_polyline": pts.tolist(),
        "flown": flown.tolist(),
        "subgoal_source": "toward_g",
        "path_len_m": path_len,
        "ref_len_m": ref_len,
        "path_efficiency": path_len / max(ref_len, 1e-3),
        "arrived": bool(arrived),
        "d_final_m": d_final,
    }, indent=2), encoding="utf-8")

    if not dual_frames:
        raise RuntimeError("no frames captured")

    pad = int(args.fps * 2.0)
    for _ in range(pad):
        ego_frames.append(ego_frames[-1])
        map_frames.append(map_frames[-1])
        dual_frames.append(dual_frames[-1])

    dual_mp4 = out_dir / f"{prefix}_dual_view_dashboard.mp4"
    ego_mp4 = out_dir / f"{prefix}_first_person_ego.mp4"
    path_mp4 = out_dir / f"{prefix}_full_flight_path.mp4"
    _encode_video(ego_frames, ego_mp4, float(args.fps))
    _encode_video(map_frames, path_mp4, float(args.fps))
    _encode_video(dual_frames, dual_mp4, float(args.fps))

    summary = {
        "route_idx": int(args.route_idx),
        "route_label": route_label,
        "arrived": bool(arrived),
        "d_final_m": round(d_final, 2),
        "path_len_m": round(path_len, 1),
        "ref_len_m": round(ref_len, 1),
        "path_efficiency": round(path_len / max(ref_len, 1e-3), 2),
        "frames": len(ego_frames),
        "videos": {"dual_view": str(dual_mp4), "ego": str(ego_mp4), "path": str(path_mp4)},
    }
    (out_dir / f"{prefix}_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info("SUMMARY %s", json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
