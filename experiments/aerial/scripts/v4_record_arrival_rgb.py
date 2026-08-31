#!/usr/bin/env python3
"""Record AirSim front-camera RGB mp4 for first successful arrival (ego FP).

125 / 4090:
  source experiments/aerial/scripts/env_4090.sh
  $AERIAL_PY experiments/aerial/scripts/v4_record_arrival_rgb.py \\
    --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_tz_pp8_20260827/v4_ac_latest.pt \\
    --diag-seed 6700 --out-dir artifacts/videos/arrival_rgb_pp8_20260827
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _goal_dist(pos: np.ndarray, goal: np.ndarray) -> float:
    return float(np.linalg.norm(np.asarray(goal, dtype=np.float64).reshape(3) - np.asarray(pos).reshape(3)))


def _write_frames_ffmpeg(
    frames: List[np.ndarray],
    out_mp4: Path,
    *,
    fps: float = 5.0,
) -> None:
    """Pipe RGB frames to ffmpeg (yuv420p h264)."""
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    h, w = frames[0].shape[:2]
    # even dims for yuv420p
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


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default=None)
    p.add_argument("--deploy-config", default="configs/aerial_rl.yaml")
    p.add_argument("--config", default="configs/aerial_rl_rollout.yaml")
    p.add_argument("--env-host", default="127.0.0.1")
    p.add_argument("--device", default="cuda")
    p.add_argument(
        "--rollout-dataset",
        default="experiments/aerial/rl/artifacts/dataset_v0_p45_merged_20260821",
    )
    p.add_argument(
        "--wm-ckpt",
        default="experiments/aerial/rl/artifacts/wm_ckpt_p45_merged_20260821/wm_step_500.pt",
    )
    p.add_argument(
        "--depth-ckpt",
        default=(
            "experiments/aerial/rl/artifacts/depth_ckpt_p45mid_s8j_20260825/"
            "depth_best_holdout_da3_ft_head.pt"
        ),
    )
    p.add_argument(
        "--tau-ckpt",
        default="experiments/aerial/rl/artifacts/tau_ckpt_foe_r60_20260815/tau_foe_calibrator.pt",
    )
    p.add_argument(
        "--actor-ckpt",
        default="experiments/aerial/rl/artifacts/v4_ac_ckpt_tz_pp8_20260827/v4_ac_latest.pt",
    )
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--diag-seed", type=int, default=6700)
    p.add_argument("--scan-n", type=int, default=64)
    p.add_argument("--scan-max", type=int, default=800)
    p.add_argument("--max-steps", type=int, default=200)
    p.add_argument("--goal-dist-m", type=float, default=30.0)
    p.add_argument("--probe-steps", type=int, default=40)
    p.add_argument("--reset-retries", type=int, default=2)
    p.add_argument("--fps", type=float, default=5.0)
    p.add_argument(
        "--out-dir",
        default="artifacts/videos/arrival_rgb_pp8_20260827",
    )
    p.add_argument("--max-episodes", type=int, default=48, help="Stop if no arrival by then.")
    p.add_argument(
        "--planner",
        action="store_true",
        help="Enable ImaginationPlanner (default OFF; PL-A 2026-08-27).",
    )
    args = p.parse_args()

    root = Path(args.repo).expanduser().resolve() if args.repo else _repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from experiments.aerial.rl import v0_rollout_eval as rollout
    from experiments.aerial.rl._v0_gate import _obstacle_candidate_positions
    from experiments.aerial.rl.actor_critic import LatentActorCritic, LatentActorDeployPolicy
    from experiments.aerial.rl.buffer import ReplayBuffer
    from experiments.aerial.rl.collector import RolloutCollector
    from experiments.aerial.rl.depth_predictor import DepthMinPredictor
    from experiments.aerial.rl.reward import RewardConfig
    from experiments.aerial.rl.tau_predictor import make_tau_predictor
    from experiments.aerial.rl.train_rl import (
        HeuristicPolicy,
        _build_env,
        _build_planner,
        _build_safety,
        load_torch_dynamics,
    )
    from experiments.aerial.scripts.v4_p7_diag import _load_merged_cfg

    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = root / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    cfg = _load_merged_cfg(root, args.deploy_config, args.config)
    if args.env_host:
        cfg.setdefault("env", {})["host"] = str(args.env_host)
    cfg.setdefault("env", {})["grab_depth"] = True
    env = _build_env(cfg.get("env", {}) or {})
    reward_cfg = (
        RewardConfig(**(cfg.get("reward", {}) or {})) if cfg.get("reward") else RewardConfig()
    )
    arrival_m = float(reward_cfg.success_dist_m)

    def _abs(p: str) -> Path:
        path = Path(p).expanduser()
        return path if path.is_absolute() else root / path

    wm_ckpt = _abs(args.wm_ckpt)
    depth_ckpt = _abs(args.depth_ckpt)
    tau_ckpt = _abs(args.tau_ckpt)
    actor_ckpt = _abs(args.actor_ckpt)
    rollout_ds = _abs(args.rollout_dataset)

    dynamics, wm_payload = load_torch_dynamics(
        cfg.get("world_model", {}) or {},
        wm_ckpt,
        device=str(args.device),
        success_dist_m=arrival_m,
    )
    want_planner = bool(getattr(args, "planner", False))
    cfg.setdefault("planner", {})["enable"] = want_planner
    planner = _build_planner(cfg, dynamics, reward_cfg) if want_planner else None
    depth_pred = DepthMinPredictor.from_checkpoint(depth_ckpt, device=str(args.device))
    tau_cfg = cfg.get("tau_predictor", {}) or {}
    tau_pred = make_tau_predictor(
        kind=str(tau_cfg.get("kind", "foe_calibrated")),
        ckpt=tau_ckpt,
        device=str(args.device),
        center_frac=float(tau_cfg.get("center_frac", 0.5)),
        min_closing_m_s=float(tau_cfg.get("min_closing_m_s", 0.05)),
        max_tau_s=float(tau_cfg.get("max_tau_s", 60.0)),
        dt_s=float(tau_cfg.get("dt_s", 0.1)),
        use_gt_depth=False,
    )
    shield = _build_safety(dict(cfg.get("safety") or {}))
    heuristic = HeuristicPolicy(goal_getter=lambda: getattr(env, "goal", None))
    actor_ac = LatentActorCritic.load_from_checkpoint(actor_ckpt, device=str(args.device))
    if int(actor_ac.config.latent_dim) != int(dynamics.latent_dim):
        raise ValueError("actor/WM latent_dim mismatch")
    base_policy = LatentActorDeployPolicy(dynamics, actor_ac, deterministic=True)

    cand, cand_yaw = _obstacle_candidate_positions(rollout_ds, min_altitude_m=0.0)
    blocked_eps, blocked_scan = rollout.make_obstacle_facing_episodes(
        env,
        int(args.scan_n),
        cand,
        seed=int(args.seed),
        candidate_yaws=cand_yaw,
        goal_dist_m=float(args.goal_dist_m),
        obstacle_max_m=25.0,
        center_frac=0.3,
        max_scans=int(args.scan_max),
        probe_policy=heuristic,
        probe_steps=int(args.probe_steps),
        probe_near_m=1.5,
        reward_cfg=reward_cfg,
        preserve_order=True,
        log_every=25,
    )
    # Deterministic shuffle with diag-seed (same spirit as spare split).
    rng = np.random.default_rng(int(args.diag_seed))
    order = np.arange(len(blocked_eps))
    rng.shuffle(order)
    pool = [blocked_eps[i] for i in order]

    print(
        f"[record-rgb] pool={len(pool)} scan={blocked_scan} "
        f"actor={actor_ckpt} wm_step={wm_payload.get('step')}"
    )

    buf = ReplayBuffer(capacity_episodes=4, seed=0)
    retries = int(args.reset_retries)

    for k, epi in enumerate(pool[: int(args.max_episodes)]):
        ep = None
        stats = None
        for attempt in range(retries + 1):
            if hasattr(base_policy, "reset"):
                base_policy.reset()
            if hasattr(shield, "reset"):
                shield.reset()
            col = RolloutCollector(
                env,
                base_policy,
                buf,
                reward_cfg=reward_cfg,
                safety=shield,
                max_steps=int(args.max_steps),
                target_hz=0.0,
                depth_predictor=depth_pred,
                tau_predictor=tau_pred,
                planner=planner,
                dynamics=dynamics,
            )
            ep, stats = col.collect_episode(epi)
            if ep:
                break
            time.sleep(0.5)
        if not ep:
            print(f"[record-rgb] ep{k}: invalid_spawn skip")
            continue

        goal = np.asarray(getattr(env, "goal"), dtype=np.float64).reshape(3)
        frames: List[np.ndarray] = []
        dists: List[float] = []
        arrived = False
        best_d = float("inf")
        for tr in ep:
            obs = tr.obs
            frames.append(np.asarray(obs.rgb, dtype=np.uint8).copy())
            post = tr.next_obs if tr.next_obs is not None else obs
            d = _goal_dist(post.position, goal)
            dists.append(d)
            best_d = min(best_d, d)
            if d <= arrival_m:
                arrived = True
        hard_coll = any(bool(getattr(tr.next_obs or tr.obs, "collided", False)) for tr in ep)
        print(
            f"[record-rgb] ep{k}: arrived={arrived} hard_coll={hard_coll} "
            f"best_d={best_d:.2f} steps={len(frames)}"
        )
        if not arrived:
            continue

        mp4 = out_dir / f"arrival_ego_rgb_ep{k}_steps{len(frames)}.mp4"
        _write_frames_ffmpeg(frames, mp4, fps=float(args.fps))
        meta = {
            "episode_idx_in_pool": k,
            "n_steps": len(frames),
            "arrived": True,
            "hard_coll": bool(hard_coll),
            "best_dist_m": round(best_d, 4),
            "final_dist_m": round(dists[-1], 4) if dists else None,
            "goal": [round(float(x), 4) for x in goal.tolist()],
            "actor_ckpt": str(actor_ckpt),
            "wm_ckpt": str(wm_ckpt),
            "depth_ckpt": str(depth_ckpt),
            "diag_seed": int(args.diag_seed),
            "goal_dist_m": float(args.goal_dist_m),
            "fps": float(args.fps),
            "mp4": str(mp4),
            "frame_hw": [int(frames[0].shape[0]), int(frames[0].shape[1])],
            "note": "AirSim front_custom Scene RGB; control step_hz=5 → fps=5",
        }
        meta_path = out_dir / f"arrival_ego_rgb_ep{k}_meta.json"
        meta_path.write_text(json.dumps(meta, indent=2) + "\n")
        print(f"[record-rgb] WROTE {mp4}")
        print(f"[record-rgb] META {meta_path}")
        return 0

    print("[record-rgb] no arrival within max_episodes", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
