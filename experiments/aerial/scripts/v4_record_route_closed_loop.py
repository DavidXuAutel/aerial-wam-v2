#!/usr/bin/env python3
"""Record actual closed-loop flight video for any benchmark route from seen_airsim16_m1a20.json.

Captures real-time AirSim camera frames and renders telemetry HUD overlay:
- Route Index & Instruction
- Current Step & Total Steps
- 3D Position (X, Y, Z) & Goal Distance
- Forward & Minimum Predicted Clearance
- Applied Action vector
- Active Safety Shield & Brake status
"""
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("record_route")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _write_frames_ffmpeg(
    frames: List[np.ndarray],
    out_mp4: Path,
    *,
    fps: float = 10.0,
) -> None:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    h, w = frames[0].shape[:2]
    ww, hh = w - (w % 2), h - (h % 2)
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{ww}x{hh}",
        "-r",
        str(fps),
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        "18",
        str(out_mp4),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    for fr in frames:
        rgb = np.ascontiguousarray(fr[:hh, :ww, :3], dtype=np.uint8)
        proc.stdin.write(rgb.tobytes())
    proc.stdin.close()
    err = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"ffmpeg failed rc={rc}\n{err[-2000:]}")
    logger.info(f"Wrote {len(frames)} frames to {out_mp4}")


def _draw_hud(
    frame: np.ndarray,
    step: int,
    max_steps: int,
    pos: np.ndarray,
    goal: np.ndarray,
    dist: float,
    action: np.ndarray,
    d_fwd: Optional[float],
    d_min: Optional[float],
    shield_channels: List[str],
    route_idx: int,
    instruction: str,
) -> np.ndarray:
    """Draw professional telemetry HUD overlay on camera frame."""
    img = frame.copy()
    h, w = img.shape[:2]

    # Top overlay header banner
    overlay = img.copy()
    cv2.rectangle(overlay, (0, 0), (w, 54), (15, 23, 42), -1)
    # Bottom telemetry banner
    cv2.rectangle(overlay, (0, h - 80), (w, h), (15, 23, 42), -1)
    cv2.addWeighted(overlay, 0.75, img, 0.25, 0, img)

    # Header text
    cv2.putText(
        img,
        f"AERIAL-WAM CLOSED-LOOP | ROUTE {route_idx + 1:02d}",
        (16, 24),
        cv2.FONT_HERSHEY_DUPLEX,
        0.65,
        (0, 255, 255),
        1,
        cv2.LINE_AA,
    )
    # Truncated instruction
    instr_short = (instruction[:75] + "...") if len(instruction) > 75 else instruction
    cv2.putText(
        img,
        instr_short,
        (16, 44),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.38,
        (200, 200, 200),
        1,
        cv2.LINE_AA,
    )

    # Step & Distance status
    prog_color = (0, 255, 0) if dist <= 3.0 else (0, 220, 255)
    cv2.putText(
        img,
        f"STEP {step:03d}/{max_steps} | DIST: {dist:.1f} m",
        (w - 280, 24),
        cv2.FONT_HERSHEY_DUPLEX,
        0.55,
        prog_color,
        1,
        cv2.LINE_AA,
    )

    # Telemetry bottom row 1: Position & Altitude
    cv2.putText(
        img,
        f"POS: X={pos[0]:.1f} Y={pos[1]:.1f} Z={pos[2]:.1f}m",
        (16, h - 52),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )

    # Telemetry bottom row 1: Clearance
    fwd_str = f"{d_fwd:.2f}m" if d_fwd is not None else "N/A"
    min_str = f"{d_min:.2f}m" if d_min is not None else "N/A"
    clr_color = (0, 255, 0) if (d_min or 5.0) > 2.0 else (0, 165, 255) if (d_min or 5.0) > 1.2 else (0, 0, 255)
    cv2.putText(
        img,
        f"CLEARANCE: FWD={fwd_str} | MIN={min_str}",
        (280, h - 52),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        clr_color,
        1,
        cv2.LINE_AA,
    )

    # Telemetry bottom row 2: Action
    act_str = f"ACT: [{action[0]:+.2f}, {action[1]:+.2f}, {action[2]:+.2f}, {action[3]:+.2f}]"
    cv2.putText(
        img,
        act_str,
        (16, h - 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (220, 220, 220),
        1,
        cv2.LINE_AA,
    )

    # Telemetry bottom row 2: Shield Status
    if shield_channels:
        sh_color = (0, 0, 255) if "three_zone_brake" in shield_channels else (0, 165, 255)
        sh_text = f"SHIELD: {', '.join(shield_channels)}"
    else:
        sh_color = (0, 255, 0)
        sh_text = "SHIELD: NOMINAL"
    cv2.putText(
        img,
        sh_text,
        (w - 380, h - 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        sh_color,
        1,
        cv2.LINE_AA,
    )

    # Crosshair in center
    cx, cy = w // 2, h // 2
    cv2.line(img, (cx - 10, cy), (cx + 10, cy), (0, 255, 255), 1, cv2.LINE_AA)
    cv2.line(img, (cx, cy - 10), (cx, cy + 10), (0, 255, 255), 1, cv2.LINE_AA)

    return img


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--route-idx", type=int, default=13, help="0-indexed route index (13 = Route 14)")
    p.add_argument("--config", default="configs/aerial_rl.yaml")
    p.add_argument("--wm-ckpt", default="experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt")
    p.add_argument("--actor-ckpt", default="experiments/aerial/rl/artifacts/v4_ac_ckpt_step_e_20260828/v4_ac_latest.pt")
    p.add_argument("--depth-ckpt", default="experiments/aerial/rl/artifacts/depth_ckpt_p45mid_s8j_20260825/depth_best_holdout_da3_ft_head.pt")
    p.add_argument("--annotation", default="artifacts/seen_airsim16_m1a20.json")
    p.add_argument("--max-steps", type=int, default=250)
    p.add_argument("--fps", type=float, default=10.0)
    p.add_argument("--out-dir", default="artifacts/videos/route14_closed_loop")
    args = p.parse_args()

    root = _repo_root()
    from experiments.aerial.rl.train_rl import _build_env, _build_safety, load_torch_dynamics
    from experiments.aerial.rl.actor_critic import LatentActorCritic, LatentActorDeployPolicy
    from experiments.aerial.rl.collector import RolloutCollector
    from experiments.aerial.rl.depth_predictor import DepthMinPredictor
    from experiments.aerial.rl.planner import ImaginationPlanner
    from experiments.aerial.rl.reward import RewardConfig
    from experiments.aerial.rl.buffer import ReplayBuffer

    with open(root / args.config) as f:
        cfg = yaml.safe_load(f)

    cfg["env"]["backend"] = "airsim"
    cfg["env"]["step_hz"] = 5.0
    cfg["env"]["grab_depth"] = True
    env = _build_env(cfg["env"])
    reward_cfg = RewardConfig(**(cfg.get("reward") or {}))
    reward_cfg.success_dist_m = 3.0

    dynamics, _ = load_torch_dynamics(
        cfg.get("world_model") or {},
        str(root / args.wm_ckpt),
        device="cuda",
        success_dist_m=3.0,
    )
    actor_ac = LatentActorCritic.load_from_checkpoint(
        str(root / args.actor_ckpt),
        device="cuda",
    )
    policy = LatentActorDeployPolicy(dynamics, actor_ac, deterministic=True)
    depth_pred = DepthMinPredictor.from_checkpoint(
        str(root / args.depth_ckpt),
        device="cuda",
    )
    shield = _build_safety(cfg.get("safety") or {})
    limits = np.array([1.0, 0.4, 0.4, 0.314], dtype=np.float64)
    planner = ImaginationPlanner(
        dynamics=dynamics,
        horizon=5,
        reward_cfg=reward_cfg,
        action_limits=limits,
        policy=actor_ac,
        critic=actor_ac,
    )

    col = RolloutCollector(
        env,
        policy,
        ReplayBuffer(),
        max_steps=args.max_steps,
        reward_cfg=reward_cfg,
        safety=shield,
        depth_predictor=depth_pred,
        planner=planner,
        skip_reset_collision=True,
    )

    with open(root / args.annotation) as f:
        routes = json.load(f)

    route = routes[args.route_idx]
    pos = np.asarray(route["pos"], dtype=np.float64).reshape(-1, 3)
    yaws = np.asarray(route["yaw"], dtype=np.float64).reshape(-1)
    start_pos = pos[0].copy()
    goal_pos = pos[-1].copy()
    start_yaw = float(yaws[0])
    instruction = route.get("gpt_instruction", "")

    ep_dict = {
        "pos": [start_pos.tolist(), goal_pos.tolist()],
        "yaw": [start_yaw, start_yaw],
        "gpt_instruction": instruction,
    }

    logger.info(f"Starting closed-loop recording for Route {args.route_idx + 1}...")
    ep_trans, stats = col.collect_episode(ep_dict)
    if not ep_trans:
        time.sleep(1.0)
        ep_trans, stats = col.collect_episode(ep_dict)

    logger.info(f"Collected {len(ep_trans)} steps. Rendering HUD...")
    hud_frames = []
    for step, tr in enumerate(ep_trans):
        rgb = tr.obs.rgb
        # RGB to BGR for cv2
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR) if rgb.ndim == 3 else np.zeros((480, 640, 3), dtype=np.uint8)
        p = tr.obs.position
        dist = float(np.linalg.norm(p - goal_pos))
        ch = tr.info.get("shield_channels", [])
        cones = tr.obs.info.get("depth_cones_pred", {})
        fwd = cones.get("forward", None)
        min_d = tr.obs.info.get("depth_min_pred", None)

        hud_bgr = _draw_hud(
            bgr,
            step=step,
            max_steps=len(ep_trans),
            pos=p,
            goal=goal_pos,
            dist=dist,
            action=tr.action,
            d_fwd=fwd,
            d_min=min_d,
            shield_channels=ch,
            route_idx=args.route_idx,
            instruction=instruction,
        )
        hud_rgb = cv2.cvtColor(hud_bgr, cv2.COLOR_BGR2RGB)
        hud_frames.append(hud_rgb)

    out_dir = root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_mp4 = out_dir / f"route{args.route_idx + 1:02d}_closed_loop_hud.mp4"
    _write_frames_ffmpeg(hud_frames, out_mp4, fps=args.fps)

    # Save summary metadata
    p_last = (ep_trans[-1].next_obs or ep_trans[-1].obs).position
    d_last = float(np.linalg.norm(p_last - goal_pos))
    summary = {
        "route_idx": args.route_idx,
        "total_steps": len(ep_trans),
        "start_pos": start_pos.tolist(),
        "goal_pos": goal_pos.tolist(),
        "final_pos": p_last.tolist(),
        "initial_dist_m": float(np.linalg.norm(start_pos - goal_pos)),
        "final_dist_m": d_last,
        "arrived": bool(d_last <= 3.0),
        "instruction": instruction,
        "video_path": str(out_mp4),
    }
    with open(out_dir / f"route{args.route_idx + 1:02d}_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    logger.info(f"Done! Saved to {out_mp4}")


if __name__ == "__main__":
    main()
