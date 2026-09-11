#!/usr/bin/env python3
"""Phase-2 + vgoal real-aircraft deploy (Pixhawk 6C + Orin camera).

Loads the same π / WM / depth / shield stack as ``wam_vgoal_eval``, but drives
a ``PixhawkDroneEnv`` instead of AirSim. Default is **bench-safe**: mock
camera, no OFFBOARD, no ARM — only loads models and prints one observation.

Stages:
  (default)       connect MAVLink + load stack + one observe()
  --offboard      enter PX4 OFFBOARD (disarmed)
  --arm           arm motors (requires --i-know-props-are-on)
  --run           closed-loop steps (requires --offboard; --arm for flight)

Example (bench, props off):

  python -m experiments.aerial.scripts.wam_vgoal_deploy \\
    --mavlink-port /dev/ttyACM0 --mock-camera

Outdoor flight (props on, RC ready):

  sudo python -m experiments.aerial.scripts.wam_vgoal_deploy \\
    --mavlink-port /dev/ttyACM0 --camera 0 \\
    --vgoal-repo ~/Projects/aerial-vgoal-wam \\
    --goal-x 10 --goal-y 0 --goal-z 5 \\
    --offboard --arm --run --max-steps 300 --i-know-props-are-on
"""
from __future__ import annotations

import argparse
import logging
import math
import sys
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np
import yaml

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("wam_vgoal_deploy")


def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Phase-2 vgoal Pixhawk deploy")
    p.add_argument("--config", default="configs/aerial_rl.yaml")
    p.add_argument("--vgoal-repo", default="~/Projects/aerial-vgoal-wam")
    p.add_argument("--mavlink-port", default="/dev/ttyACM0")
    p.add_argument("--step-hz", type=float, default=5.0)
    p.add_argument("--max-steps", type=int, default=100)
    p.add_argument("--camera", default="0", help="V4L2 device index or path")
    p.add_argument("--mock-camera", action="store_true")
    p.add_argument("--capture-w", type=int, default=1280)
    p.add_argument("--capture-h", type=int, default=720)
    p.add_argument("--capture-fps", type=int, default=30)
    p.add_argument("--wam-encode-size", type=int, default=224)
    p.add_argument("--camera-fov-deg", type=float, default=80.0)
    p.add_argument("--cruise-speed", type=float, default=10.0)
    p.add_argument("--tti-coeff", type=float, default=2.5)
    p.add_argument("--success-dist", type=float, default=3.0)
    p.add_argument("--yolo-model", default="yolov8n.pt")
    p.add_argument("--yolo-conf", type=float, default=0.25)
    p.add_argument("--target-class", default="car")
    p.add_argument("--visual-prompt", default=None)
    p.add_argument("--goal-x", type=float, default=None)
    p.add_argument("--goal-y", type=float, default=None)
    p.add_argument("--goal-z", type=float, default=None)
    p.add_argument("--fallback-toward-g", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--offboard", action="store_true")
    p.add_argument("--arm", action="store_true")
    p.add_argument("--run", action="store_true", help="Execute closed-loop steps")
    p.add_argument("--i-know-props-are-on", action="store_true")
    p.add_argument(
        "--wm-ckpt",
        default="experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt",
    )
    p.add_argument(
        "--actor-ckpt",
        default=(
            "experiments/aerial/rl/artifacts/"
            "v4_ac_ckpt_phase2_toward_g_20260905_112006/v4_ac_latest.pt"
        ),
    )
    p.add_argument(
        "--depth-ckpt",
        default="experiments/aerial/rl/artifacts/depth_ckpt_p45mid_s8j_20260825/depth_best_holdout_da3_ft_head.pt",
    )
    p.add_argument(
        "--tau-ckpt",
        default="experiments/aerial/rl/artifacts/tau_ckpt_foe_r60_20260815/tau_foe_calibrator.pt",
    )
    p.add_argument("--device", default="cuda")
    p.add_argument(
        "--no-depth-shield",
        action="store_true",
        help="Disable TTI depth shield (recommended for 24F bench / untrusted depth)",
    )
    return p.parse_args()


def _goal_from_args(args: argparse.Namespace, origin: np.ndarray) -> Optional[np.ndarray]:
    if args.goal_x is None or args.goal_y is None or args.goal_z is None:
        return None
    return np.array([args.goal_x, args.goal_y, args.goal_z], dtype=np.float64)


def main() -> int:
    args = _parse()
    if args.arm and not args.i_know_props_are_on:
        logger.error("Refusing --arm without --i-know-props-are-on")
        return 2
    if args.run and not args.offboard:
        logger.error("--run requires --offboard")
        return 2
    if args.arm and not args.offboard:
        logger.error("--arm requires --offboard")
        return 2

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
    from experiments.aerial.rl.depth_predictor import DepthMinPredictor
    from experiments.aerial.rl.env.action import body_delta_limits
    from experiments.aerial.rl.env.pixhawk_env import PixhawkDroneEnv, PixhawkEnvConfig
    from experiments.aerial.rl.scene_intent import TowardGoalIntent
    from experiments.aerial.rl.tau_predictor import make_tau_predictor
    from experiments.aerial.rl.train_rl import _build_safety, load_torch_dynamics
    from experiments.aerial.scripts.wam_vgoal_eval import _build_detector, _vision_step

    cfg = yaml.safe_load((root / args.config).read_text()) if (root / args.config).is_file() else {}
    device_str = str(args.device)
    if device_str == "cuda" and not torch.cuda.is_available():
        device_str = "cpu"
    if device_str == "cuda":
        try:
            torch.zeros(1, device="cuda")
        except Exception as exc:  # noqa: BLE001
            logger.warning("CUDA unusable (%s) — falling back to cpu", exc)
            device_str = "cpu"
    device = torch.device(device_str)
    logger.info("deploy device=%s mock_camera=%s", device, args.mock_camera)

    env = PixhawkDroneEnv(
        PixhawkEnvConfig(
            mavlink_port=args.mavlink_port,
            step_hz=float(args.step_hz),
            camera_device=str(args.camera),
            capture_w=int(args.capture_w),
            capture_h=int(args.capture_h),
            capture_fps=int(args.capture_fps),
            wam_encode_size=int(args.wam_encode_size),
            offboard_on_reset=bool(args.offboard),
            arm_on_reset=bool(args.arm),
            mock_camera=bool(args.mock_camera),
        )
    )

    wm_cfg = cfg.get("world_model") or {}
    wm_path = (root / args.wm_ckpt).resolve()
    dynamics, _ = load_torch_dynamics(wm_cfg, str(wm_path), device=device_str, success_dist_m=float(args.success_dist))

    actor_path = (root / args.actor_ckpt).resolve()
    actor_ac = LatentActorCritic.load_from_checkpoint(actor_path, device=device_str)
    actor_ac.config.goal_feat_mode = "meter"
    policy = LatentActorDeployPolicy(dynamics, actor_ac, deterministic=True, stream_latent=True)

    depth_path = (root / args.depth_ckpt).resolve()
    depth_pred = DepthMinPredictor.from_checkpoint(depth_path, device=device_str)
    tau_pred = make_tau_predictor(
        kind="foe_calibrated",
        ckpt=(root / args.tau_ckpt).resolve(),
        device=device_str,
    )

    dt_step = 1.0 / float(args.step_hz)
    phys_limits = body_delta_limits(dt_step)
    vx_max_step = float(min(float(args.cruise_speed) / float(args.step_hz), float(phys_limits[0])))
    action_limits = np.array(
        [vx_max_step, float(phys_limits[1]), float(phys_limits[2]), float(phys_limits[3])],
        dtype=np.float64,
    )

    safety_cfg = dict(cfg.get("safety") or {})
    if args.no_depth_shield:
        safety_cfg["kind"] = "null"
    elif str(safety_cfg.get("kind", "null")) in ("null", "none", "None"):
        safety_cfg["kind"] = "three_zone"
    safety_cfg["v_cruise_m_s"] = float(args.cruise_speed)
    safety_cfg["tti_coeff"] = float(args.tti_coeff)
    shield = _build_safety(safety_cfg)

    fallback_intent = (
        TowardGoalIntent(r_m=100.0, mode="toward_g", cruise_speed=float(args.cruise_speed))
        if args.fallback_toward_g
        else None
    )

    intrinsics = CameraIntrinsics.from_fov(
        float(args.camera_fov_deg),
        width=int(args.capture_w),
        height=int(args.capture_h),
    )
    tracker = TargetTracker(
        TrackerConfig(
            success_dist_m=float(args.success_dist),
            max_occlusion_s=2.0,
            min_confidence=float(max(0.15, args.yolo_conf)),
        )
    )
    detector = _build_detector(
        argparse.Namespace(
            detector="yolo",
            target_class=args.target_class,
            visual_prompt=args.visual_prompt or args.target_class,
            yolo_model=args.yolo_model,
            yolo_conf=args.yolo_conf,
            yolo_imgsz=640,
            yolo_device=device_str,
            camera_fov_deg=args.camera_fov_deg,
            capture_w=args.capture_w,
            capture_h=args.capture_h,
        ),
        vgoal_repo,
    )

    try:
        obs = env.reset()
        p_curr = np.asarray(obs.position, dtype=np.float64)
        curr_yaw = float(obs.yaw)
        annot_goal = _goal_from_args(args, p_curr)
        if annot_goal is None:
            annot_goal = p_curr + np.array([20.0, 0.0, 0.0], dtype=np.float64)
            logger.warning("No --goal-x/y/z; using fallback annot_goal=%s", annot_goal.tolist())

        policy.reset()
        shield.reset()
        tau_pred.reset()
        depth_pred.reset()
        if fallback_intent is not None:
            fallback_intent.reset()

        logger.info(
            "obs pos=%s yaw=%.1f° armed=%s offboard=%s",
            [round(float(x), 2) for x in p_curr],
            math.degrees(curr_yaw),
            env._bridge.is_armed(),
            env._offboard_active,
        )

        if not args.run:
            logger.info("Bench load OK — pass --run --offboard to close the loop")
            return 0

        search_fwd_step = min(0.5 / float(args.step_hz), vx_max_step)
        p_prev = p_curr.copy()
        prev_yaw = curr_yaw

        for step in range(int(args.max_steps)):
            obs.info.pop("depth_min_pred", None)
            obs.info.pop("tau_pred", None)
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
                dynamic_tracker=None,
                dynamic_min_meas_conf=float(max(0.15, args.yolo_conf)),
                depth_pred=depth_pred,
                intrinsics=intrinsics,
                pos=p_curr,
                yaw=curr_yaw,
                prev_pos=p_prev,
                prev_yaw=prev_yaw,
                dt=dt_step,
                search_fwd_step=search_fwd_step,
                search_yaw_rate=0.1,
                area_search_planner=None,
                fallback_intent=fallback_intent,
                annot_goal=annot_goal,
                allow_fallback=bool(args.fallback_toward_g),
                prefer_nearest=False,
                camera_fov_deg=float(args.camera_fov_deg),
            )
            p_prev = p_curr.copy()
            prev_yaw = curr_yaw

            if vstep.search_action is not None:
                action = vstep.search_action
                goal_rel = None
            elif vstep.goal_rel is not None:
                goal_rel = np.asarray(vstep.goal_rel, dtype=np.float32)
                z = dynamics.encode(obs)
                action = policy.act_latent(z, goal_rel)
            else:
                action = np.zeros(4, dtype=np.float64)
                goal_rel = None

            wm_out = None
            if depth_pred is not None:
                wm_out = {"depth_min_pred": obs.info.get("depth_min_pred")}
            act_safe, overridden = shield.apply_action(action, obs, wm_out=wm_out, limits=action_limits)
            if overridden:
                action = act_safe

            obs, step_info = env.step(action)
            p_curr = np.asarray(obs.position, dtype=np.float64)
            curr_yaw = float(obs.yaw)

            if step % max(1, int(args.step_hz)) == 0:
                gr = goal_rel.tolist() if goal_rel is not None else None
                logger.info(
                    "step=%04d pos=%s tracker=%s fallback=%s goal_rel=%s ir=%s",
                    step,
                    [round(float(x), 1) for x in p_curr],
                    vstep.tracker_state,
                    vstep.using_fallback,
                    [round(float(x), 2) for x in gr] if gr else None,
                    step_info.get("armed"),
                )

            if annot_goal is not None:
                dist = float(np.linalg.norm(annot_goal - p_curr))
                if dist <= float(args.success_dist):
                    logger.info("SUCCESS dist=%.1fm at step %d", dist, step)
                    break

        return 0
    except KeyboardInterrupt:
        logger.warning("Interrupted")
        return 130
    finally:
        env.close()


if __name__ == "__main__":
    sys.exit(main())
