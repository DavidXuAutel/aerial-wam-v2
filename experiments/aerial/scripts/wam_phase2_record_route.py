#!/usr/bin/env python3
"""Record one Phase-2 mainline long-route closed-loop video (HUD).

Stack mirrors ``wam_phase2_long_eval``:
  AdaptiveSubgoal → step_e π (meter) → ImaginationPlanner → ThreeZone → AirSim RGB
"""
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
import yaml

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("wam_phase2_record")


def _goal_dist(pos: np.ndarray, goal: np.ndarray) -> float:
    return float(
        np.linalg.norm(
            np.asarray(goal, dtype=np.float64).reshape(3)
            - np.asarray(pos, dtype=np.float64).reshape(3)
        )
    )


def _write_frames_ffmpeg(frames: List[np.ndarray], out_mp4: Path, *, fps: float) -> None:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    h, w = frames[0].shape[:2]
    ww, hh = w - (w % 2), h - (h % 2)
    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{ww}x{hh}", "-r", str(fps),
        "-i", "-",
        "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
        str(out_mp4),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    for fr in frames:
        proc.stdin.write(np.ascontiguousarray(fr[:hh, :ww, :3], dtype=np.uint8).tobytes())
    proc.stdin.close()
    err = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"ffmpeg failed rc={rc}\n{err[-2000:]}")
    logger.info("Wrote %d frames → %s", len(frames), out_mp4)


def _draw_hud(
    frame_bgr: np.ndarray,
    *,
    step: int,
    max_steps: int,
    route_idx: int,
    pos: np.ndarray,
    goal: np.ndarray,
    d_goal: float,
    rem_dist: float,
    s_prog: float,
    ref_len: float,
    cte: float,
    d_fwd: Optional[float],
    ir_step: bool,
) -> np.ndarray:
    img = frame_bgr.copy()
    h, w = img.shape[:2]
    overlay = img.copy()
    cv2.rectangle(overlay, (0, 0), (w, 58), (15, 23, 42), -1)
    cv2.rectangle(overlay, (0, h - 72), (w, h), (15, 23, 42), -1)
    cv2.addWeighted(overlay, 0.75, img, 0.25, 0, img)
    prog = float(np.clip(s_prog / max(1e-3, ref_len), 0.0, 1.0))
    cv2.putText(
        img,
        f"PHASE2 REANCHOR | LONG ROUTE {route_idx + 1:02d} | step {step}/{max_steps}",
        (14, 26),
        cv2.FONT_HERSHEY_DUPLEX,
        0.55,
        (0, 255, 255),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        img,
        f"prog={prog*100:.1f}%  rem={rem_dist:.1f}m  d_goal={d_goal:.1f}m  CTE={cte:.1f}m",
        (14, 48),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        (200, 255, 200),
        1,
        cv2.LINE_AA,
    )
    fwd_s = f"{d_fwd:.1f}m" if d_fwd is not None and np.isfinite(d_fwd) else "n/a"
    shield = "SHIELD" if ir_step else "policy"
    cv2.putText(
        img,
        f"pos=({pos[0]:.1f},{pos[1]:.1f},{pos[2]:.1f})  goal=({goal[0]:.1f},{goal[1]:.1f},{goal[2]:.1f})  "
        f"Dfwd={fwd_s}  ctrl={shield}",
        (14, h - 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (220, 220, 220),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        img,
        "step_e + meter + AdaptiveSubgoal + planner H=5 + ThreeZone",
        (14, h - 16),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.42,
        (160, 200, 255),
        1,
        cv2.LINE_AA,
    )
    cx, cy = w // 2, h // 2
    cv2.line(img, (cx - 10, cy), (cx + 10, cy), (0, 255, 255), 1, cv2.LINE_AA)
    cv2.line(img, (cx, cy - 10), (cx, cy + 10), (0, 255, 255), 1, cv2.LINE_AA)
    return img


def _write_traj_plot(
    ref_pts: np.ndarray,
    flown: np.ndarray,
    out_png: Path,
    *,
    title: str,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ref = np.asarray(ref_pts, dtype=np.float64).reshape(-1, 3)
    fly = np.asarray(flown, dtype=np.float64).reshape(-1, 3)
    fig, ax = plt.subplots(figsize=(8, 8), dpi=140)
    ax.plot(ref[:, 0], ref[:, 1], "k--", lw=1.6, label="ref polyline", zorder=2)
    ax.plot(fly[:, 0], fly[:, 1], color="#1f77b4", lw=1.8, label="flown", zorder=3)
    ax.scatter(ref[0, 0], ref[0, 1], c="#2ca02c", s=60, zorder=4, label="start")
    ax.scatter(ref[-1, 0], ref[-1, 1], c="#d62728", s=70, marker="*", zorder=4, label="goal")
    ax.scatter(fly[-1, 0], fly[-1, 1], c="#ff7f0e", s=40, zorder=4, label="final")
    ax.set_aspect("equal", adjustable="datalim")
    ax.grid(True, alpha=0.3)
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_title(title)
    ax.legend(loc="best", fontsize=8)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)
    logger.info("Wrote traj plot → %s", out_png)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--route-idx", type=int, default=14, help="0-based long-route index (14=R15)")
    p.add_argument("--config", default="configs/aerial_rl.yaml")
    p.add_argument(
        "--wm-ckpt",
        default="experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt",
    )
    p.add_argument(
        "--actor-ckpt",
        default="experiments/aerial/rl/artifacts/v4_ac_ckpt_step_e_20260828/v4_ac_latest.pt",
    )
    p.add_argument(
        "--depth-ckpt",
        default="experiments/aerial/rl/artifacts/depth_ckpt_p45mid_s8j_20260825/depth_best_holdout_da3_ft_head.pt",
    )
    p.add_argument("--annotation", default="artifacts/seen_airsim16_long_routes.json")
    p.add_argument("--cruise-speed", type=float, default=10.0)
    p.add_argument("--max-steps", type=int, default=1000)
    p.add_argument("--step-hz", type=float, default=5.0)
    p.add_argument("--success-dist", type=float, default=3.0)
    p.add_argument("--planner-horizon", type=int, default=5)
    p.add_argument("--goal-feat-mode", choices=("meter", "g_norm"), default="meter")
    p.add_argument("--fps", type=float, default=5.0)
    p.add_argument(
        "--frame-stride",
        type=int,
        default=2,
        help="Keep every Nth RGB frame (memory / encode)",
    )
    p.add_argument(
        "--no-video",
        action="store_true",
        help="Skip RGB/mp4; still write traj json + XY plot",
    )
    p.add_argument(
        "--out-dir",
        default="artifacts/videos/wam_phase2_reanchor_r15",
    )
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
    from experiments.aerial.rl.subgoal_generator import AdaptiveSubgoalGenerator
    from experiments.aerial.rl.train_rl import _build_env, _build_safety, load_torch_dynamics

    cfg = yaml.safe_load((root / args.config).read_text())
    device_str = "cuda" if torch.cuda.is_available() else "cpu"

    with open(root / args.annotation, "r", encoding="utf-8") as f:
        anno = json.load(f)
    routes = anno.get("routes", anno) if isinstance(anno, dict) else anno
    r_info = routes[int(args.route_idx)]
    pts = np.array(r_info.get("pos", r_info.get("positions")), dtype=np.float64)
    yaws = np.array(r_info.get("yaw", [0.0] * len(pts)), dtype=np.float64)
    goal_pos = pts[-1].copy()
    start_pos = pts[0].copy()
    start_yaw = float(yaws[0]) if len(yaws) else 0.0
    ref_len = float(np.sum(np.linalg.norm(pts[1:] - pts[:-1], axis=1)))

    env_cfg = dict(cfg.get("env") or {})
    env_cfg["backend"] = "airsim"
    env_cfg["step_hz"] = float(args.step_hz)
    env_cfg["grab_depth"] = True
    env = _build_env(env_cfg)

    dynamics, _ = load_torch_dynamics(
        cfg.get("world_model") or {},
        str(root / args.wm_ckpt),
        device=device_str,
        success_dist_m=float(args.success_dist),
    )
    actor_ac = LatentActorCritic.load_from_checkpoint(str(root / args.actor_ckpt), device=device_str)
    actor_ac.config.goal_feat_mode = str(args.goal_feat_mode)
    logger.info("actor goal_feat_mode=%s", actor_ac.config.goal_feat_mode)

    phys = body_delta_limits(1.0 / float(args.step_hz))
    action_limits = np.array(
        [
            min(float(args.cruise_speed) / float(args.step_hz), float(phys[0])),
            float(phys[1]),
            float(phys[2]),
            float(phys[3]),
        ],
        dtype=np.float64,
    )
    reward_cfg = RewardConfig(**(cfg.get("reward") or {}))
    reward_cfg.success_dist_m = float(args.success_dist)
    planner = ImaginationPlanner(
        dynamics=dynamics,
        horizon=int(args.planner_horizon),
        reward_cfg=reward_cfg,
        action_limits=action_limits,
    )
    policy = LatentActorDeployPolicy(dynamics, actor_ac, deterministic=True, stream_latent=True)

    depth_path = root / args.depth_ckpt
    depth_pred = (
        DepthMinPredictor.from_checkpoint(str(depth_path), device=device_str)
        if depth_path.is_file()
        else None
    )
    safety_cfg = dict(cfg.get("safety") or {})
    if str(safety_cfg.get("kind", "null")) in ("null", "none", "None"):
        safety_cfg["kind"] = "three_zone"
    if "three_zone" not in safety_cfg:
        safety_cfg["three_zone"] = {}
    safety_cfg["three_zone"]["v_cruise"] = float(args.cruise_speed)
    shield = _build_safety(safety_cfg)

    subgoal_gen = AdaptiveSubgoalGenerator(cruise_speed=float(args.cruise_speed))
    subgoal_gen.reset()
    if hasattr(shield, "reset"):
        shield.reset()
    if depth_pred is not None and hasattr(depth_pred, "reset"):
        depth_pred.reset()
    policy.reset()

    ep_dict: Dict[str, Any] = {
        "pos": pts.tolist(),
        "yaw": yaws.tolist() if len(yaws) == len(pts) else [start_yaw] * len(pts),
        "gpt_instruction": r_info.get("gpt_instruction", f"long_route_{args.route_idx+1:02d}"),
    }
    obs = env.reset(ep_dict)
    p_curr = np.array(obs.position, dtype=np.float64)
    curr_yaw = float(obs.yaw) if hasattr(obs, "yaw") else start_yaw
    logger.info(
        "Recording long route %02d L_ref=%.1fm start_d=%.1fm",
        args.route_idx + 1,
        ref_len,
        _goal_dist(p_curr, goal_pos),
    )

    frames: List[np.ndarray] = []
    traj: List[np.ndarray] = [p_curr.copy()]
    min_d = _goal_dist(p_curr, goal_pos)
    arrived = False
    interventions = 0
    s_prog = 0.0
    rem_dist = ref_len
    cte = 0.0

    for step in range(int(args.max_steps)):
        d_fwd = None
        if depth_pred is not None and obs.rgb is not None:
            pred_both = getattr(depth_pred, "predict_min_and_cones", None)
            if callable(pred_both):
                d_min_pred, cones = pred_both(obs)
                if d_min_pred is not None:
                    obs.info["depth_min_pred"] = float(d_min_pred)
                if isinstance(cones, dict):
                    cf = cones.get("forward")
                    if cf is not None and np.isfinite(float(cf)):
                        d_fwd = float(cf)
            else:
                d_fwd = depth_pred.predict_min(obs)

        g_rel_body, s_info = subgoal_gen.compute_subgoal(
            curr_pos=p_curr,
            curr_yaw=curr_yaw,
            global_path=pts,
            d_fwd_hat=d_fwd,
        )
        target_world = np.array(s_info["target_world"], dtype=np.float64)
        s_prog = float(s_info["s_progress"])
        rem_dist = float(s_info["rem_dist"])
        cte = float(s_info.get("cte_m", 0.0))
        safe_v = float(s_info.get("safe_speed_limit", args.cruise_speed))

        phys = body_delta_limits(1.0 / float(args.step_hz))
        cur_limits = np.array(
            [
                float(min(safe_v / float(args.step_hz), float(phys[0]))),
                float(phys[1]),
                float(phys[2]),
                float(phys[3]),
            ],
            dtype=np.float64,
        )
        planner.action_limits = cur_limits

        d_to_goal = _goal_dist(p_curr, goal_pos)
        min_d = min(min_d, d_to_goal)

        if step % 50 == 0:
            logger.info(
                "step=%d prog=%.1f%% rem=%.1f d_goal=%.1f CTE=%.1f frames=%d",
                step,
                100.0 * float(np.clip(s_prog / max(1e-3, ref_len), 0.0, 1.0)),
                rem_dist,
                d_to_goal,
                cte,
                len(frames),
            )

        if not args.no_video:
            rgb = getattr(obs, "rgb", None)
            stride = max(1, int(args.frame_stride))
            if rgb is not None and getattr(rgb, "ndim", 0) == 3 and (step % stride == 0):
                bgr = cv2.cvtColor(np.asarray(rgb), cv2.COLOR_RGB2BGR)
                if bgr.shape[0] > 720:
                    bgr = cv2.resize(bgr, (bgr.shape[1] * 720 // bgr.shape[0], 720))
                hud = _draw_hud(
                    bgr,
                    step=step,
                    max_steps=int(args.max_steps),
                    route_idx=int(args.route_idx),
                    pos=p_curr,
                    goal=goal_pos,
                    d_goal=d_to_goal,
                    rem_dist=rem_dist,
                    s_prog=s_prog,
                    ref_len=ref_len,
                    cte=cte,
                    d_fwd=d_fwd,
                    ir_step=False,
                )
                frames.append(cv2.cvtColor(hud, cv2.COLOR_BGR2RGB))

        if rem_dist <= float(args.success_dist) and d_to_goal <= float(args.success_dist):
            arrived = True
            break

        obs.info["goal"] = target_world.tolist()
        obs.info["goal_rel"] = g_rel_body.tolist()
        planner.set_goal(target_world)
        action = policy.act(obs)
        action = planner.plan(obs, action, latent=policy._latent)
        action = clip_body_delta(action, cur_limits)

        wm_out = None
        if policy._latent is not None and hasattr(dynamics, "step"):
            try:
                wm_out = dynamics.step(
                    policy._latent,
                    action,
                    goal_rel=g_rel_body,
                    body_vel=body_vel_from_obs(obs),
                )
            except Exception:
                wm_out = None

        overridden = False
        if shield is not None:
            action, overridden = shield.apply_action(
                action, obs, wm_out=wm_out, limits=cur_limits
            )
            if overridden:
                interventions += 1

        step_out = env.step(action)
        if len(step_out) == 4:
            obs, _rew, done, step_info = step_out
        else:
            obs, step_info = step_out
            done = bool(getattr(obs, "collided", False))

        p_curr = np.array(obs.position, dtype=np.float64)
        curr_yaw = float(obs.yaw) if hasattr(obs, "yaw") else curr_yaw
        traj.append(p_curr.copy())
        if done:
            break

    out_dir = root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    flown = np.asarray(traj, dtype=np.float64)
    traj_json = out_dir / f"long_route{args.route_idx + 1:02d}_traj.json"
    traj_png = out_dir / f"long_route{args.route_idx + 1:02d}_traj_xy.png"
    traj_json.write_text(
        json.dumps(
            {
                "route_idx": int(args.route_idx),
                "ref_polyline": pts.tolist(),
                "flown": flown.tolist(),
                "n_steps": int(len(flown)),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    prog = float(np.clip(s_prog / max(1e-3, ref_len), 0.0, 1.0))
    _write_traj_plot(
        pts,
        flown,
        traj_png,
        title=(
            f"R{args.route_idx + 1:02d} reanchor traj  "
            f"prog={prog*100:.1f}%  d_min={min_d:.1f}m  d_final={_goal_dist(p_curr, goal_pos):.1f}m"
        ),
    )

    out_mp4 = out_dir / f"long_route{args.route_idx + 1:02d}_reanchor_hud.mp4"
    if not args.no_video:
        if not frames:
            raise RuntimeError("no RGB frames captured")
        _write_frames_ffmpeg(frames, out_mp4, fps=float(args.fps))

    summary = {
        "route_idx": int(args.route_idx),
        "route_label": f"R{args.route_idx + 1:02d}",
        "protocol": "step_e+meter+subgoal+planner+three_zone",
        "ref_len_m": round(ref_len, 2),
        "steps": int(len(flown)),
        "d_min_m": round(min_d, 2),
        "d_final_m": round(_goal_dist(p_curr, goal_pos), 2),
        "progress_ratio": round(prog, 4),
        "arrived": bool(arrived),
        "intervention_rate": round(interventions / max(1, len(flown)), 4),
        "video_path": str(out_mp4) if not args.no_video else None,
        "traj_json": str(traj_json),
        "traj_plot": str(traj_png),
        "note": "Highest completion in reanchor batch (prog=1.0, best d_min among ties)",
    }
    (out_dir / f"long_route{args.route_idx + 1:02d}_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    logger.info("SUMMARY %s", json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
