#!/usr/bin/env python3
"""Speed fine-tuning for the LatentActorCritic via imagination REINFORCE.

Two-phase workflow:
  Phase 1 (needs AirSim, ~2 min): reset each route, encode start obs → z_bank.
  Phase 2 (pure GPU, no AirSim):  repeatedly sample from z_bank, run imagine()
                                   with speed-biased reward, call ac.update().

Reward additions (vs normal training):
  -w_step_penalty per step          → penalises dithering / slow hover
  +w_forward_vel * action[0]        → rewards body-frame forward displacement
  w_collision reduced (coll_scale)  → reduces WM p_coll bias so actor isn't
                                       punished for fast motion near geometry

Action limits are expanded (default [2.0, 0.6, 0.6, π/5]) and the last actor
layer is rescaled so initial behaviour is magnitude-equivalent to the original.

Usage:
  source experiments/aerial/scripts/env_4090.sh
  python -m experiments.aerial.scripts.finetune_actor_speed \\
    --wm-ckpt   experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt \\
    --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_step_e_20260828/v4_ac_latest.pt \\
    --annotation artifacts/seen_airsim16_m1a20.json \\
    --n-steps 800 \\
    --out-ckpt  artifacts/v4_ac_speed_ft_20260904/v4_ac_speed_latest.pt
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import yaml

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("finetune_speed")


def main() -> int:
    parser = argparse.ArgumentParser(description="Speed fine-tuning for LatentActorCritic")
    parser.add_argument("--config", default="configs/aerial_rl.yaml")
    parser.add_argument("--wm-ckpt", required=True)
    parser.add_argument("--actor-ckpt", required=True)
    parser.add_argument("--annotation", default="artifacts/seen_airsim16_m1a20.json")
    parser.add_argument("--step-hz", type=float, default=5.0)
    parser.add_argument("--device", default="cuda")
    # Fine-tuning hyperparameters
    parser.add_argument("--n-steps", type=int, default=800,
                        help="Number of imagination REINFORCE gradient updates")
    parser.add_argument("--batch-size", type=int, default=16,
                        help="Start latents per gradient update (sampled from z_bank)")
    parser.add_argument("--horizon", type=int, default=15,
                        help="Imagination horizon (must be <= MAX_IMAGINATION_HORIZON=15)")
    parser.add_argument("--action-limits", default="2.0,0.6,0.6,0.6283",
                        help="Expanded action limits as comma-separated values [dx,dy,dz,dyaw]. "
                             "Default: [2.0, 0.6, 0.6, π/5≈0.6283]. "
                             "These override the checkpoint's original limits.")
    parser.add_argument("--w-step-penalty", type=float, default=0.02,
                        help="Constant negative reward per step (penalises dithering)")
    parser.add_argument("--w-forward-vel", type=float, default=0.1,
                        help="Reward coefficient for body-frame forward dx")
    parser.add_argument("--coll-scale", type=float, default=0.1,
                        help="Scale w_collision in imagination reward (default 0.1 reduces WM p_coll bias)")
    parser.add_argument("--lr-actor", type=float, default=1e-4,
                        help="Adam lr for actor (conservative for fine-tuning stability)")
    parser.add_argument("--lr-critic", type=float, default=3e-4,
                        help="Adam lr for critic")
    parser.add_argument("--success-dist", type=float, default=3.0)
    parser.add_argument("--log-interval", type=int, default=50,
                        help="Print loss every N gradient steps")
    parser.add_argument("--save-interval", type=int, default=200,
                        help="Save a checkpoint snapshot every N steps (0 = only at end)")
    parser.add_argument("--out-ckpt", required=True,
                        help="Output checkpoint path (e.g. artifacts/v4_ac_speed_ft/v4_ac_speed_latest.pt)")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    import torch
    from experiments.aerial.rl.actor_critic import LatentActorCritic
    from experiments.aerial.rl.env.rate_gate import DEFAULT_DEPTH_BUDGET_S, assert_link_rate
    from experiments.aerial.rl.goal_features import body_vel_from_obs, goal_rel_from_obs
    from experiments.aerial.rl.imagination import imagine
    from experiments.aerial.rl.reward import RewardConfig
    from experiments.aerial.rl.train_rl import _build_env, load_torch_dynamics

    cfg = yaml.safe_load((root / args.config).read_text()) or {}
    cfg.setdefault("env", {})["backend"] = "airsim"
    cfg["env"]["step_hz"] = float(args.step_hz)
    cfg["env"]["grab_depth"] = True

    # -- Phase 1: collect start latents (AirSim required) -------------------
    logger.info("Phase 1: encoding start latents from AirSim resets")
    env = _build_env(cfg["env"])

    # Link-rate gate: refuse a slow cross-net renderer so latents aren't garbage
    try:
        link_probe = assert_link_rate(
            env, budget_s=DEFAULT_DEPTH_BUDGET_S, n=5, step_hz=float(args.step_hz)
        )
        logger.info("link-rate gate PASS: %s", link_probe)
    except RuntimeError as exc:
        logger.error("link-rate gate FAIL: %s", exc)
        return 1

    wm_path = (root / args.wm_ckpt).resolve() if not Path(args.wm_ckpt).is_absolute() else Path(args.wm_ckpt)
    wm_cfg = cfg.get("world_model") or {}
    dynamics, _ = load_torch_dynamics(
        wm_cfg, str(wm_path), device=str(args.device), success_dist_m=float(args.success_dist)
    )
    dynamics.eval()
    for p in dynamics.parameters():
        p.requires_grad_(False)

    ann_path = (root / args.annotation).resolve() if not Path(args.annotation).is_absolute() else Path(args.annotation)
    with ann_path.open("r") as f:
        routes: List[Dict[str, Any]] = json.load(f)
    logger.info("Loaded %d routes from %s", len(routes), ann_path.name)

    z_bank: List[np.ndarray] = []
    gr_bank: List[np.ndarray] = []
    bv_bank: List[np.ndarray] = []

    for idx, r in enumerate(routes):
        pos = np.asarray(r["pos"], dtype=np.float64).reshape(-1, 3)
        yaws = np.asarray(r["yaw"], dtype=np.float64).reshape(-1)
        ep_dict = {
            "pos": [pos[0].tolist(), pos[-1].tolist()],
            "yaw": [float(yaws[0]), float(yaws[0])],
            "gpt_instruction": r.get("gpt_instruction", ""),
        }
        try:
            obs = env.reset(ep_dict)
        except Exception as exc:
            logger.warning("Route %d reset failed: %s — skipping", idx, exc)
            continue
        try:
            z = np.asarray(dynamics.encode(obs), dtype=np.float64).reshape(-1)
            gr = np.asarray(goal_rel_from_obs(obs), dtype=np.float32).reshape(-1)
            bv = np.asarray(body_vel_from_obs(obs), dtype=np.float32).reshape(-1)
            z_bank.append(z)
            gr_bank.append(gr)
            bv_bank.append(bv)
            logger.info("Route %02d encoded: z_norm=%.3f", idx + 1, float(np.linalg.norm(z)))
        except Exception as exc:
            logger.warning("Route %d encode failed: %s — skipping", idx, exc)

    if not z_bank:
        logger.error("No start latents collected — check AirSim connection")
        return 1

    z_bank_arr = np.stack(z_bank)    # [N, latent_dim]
    gr_bank_arr = np.stack(gr_bank)  # [N, goal_rel_dim]
    bv_bank_arr = np.stack(bv_bank)  # [N, body_vel_dim]
    n_starts = len(z_bank)
    logger.info("Phase 1 complete: %d start latents encoded", n_starts)

    # -- Load and prepare actor -------------------------------------------
    actor_path = (root / args.actor_ckpt).resolve() if not Path(args.actor_ckpt).is_absolute() else Path(args.actor_ckpt)
    actor_ac = LatentActorCritic.load_from_checkpoint(actor_path, device=str(args.device))

    # Expand action limits (scale-consistent rescaling of last actor layer)
    new_limits = np.array([float(x) for x in args.action_limits.split(",")], dtype=np.float64)
    old_limits = actor_ac.action_limits.copy()
    actor_ac.override_action_limits(new_limits)
    logger.info("Action limits: %s → %s", old_limits.tolist(), new_limits.tolist())

    # Override Adam learning rates for fine-tuning
    for pg in actor_ac._actor_opt.param_groups:
        pg["lr"] = float(args.lr_actor)
    for pg in actor_ac._critic_opt.param_groups:
        pg["lr"] = float(args.lr_critic)
    logger.info("Fine-tune lr: actor=%.2e critic=%.2e", args.lr_actor, args.lr_critic)

    # Set actor to training mode
    actor_ac._actor.train()
    actor_ac._critic.train()

    # -- Speed reward config -----------------------------------------------
    base_reward_cfg = RewardConfig(**(cfg.get("reward") or {}))
    speed_reward_cfg = RewardConfig(**(cfg.get("reward") or {}))
    speed_reward_cfg.success_dist_m = float(args.success_dist)
    speed_reward_cfg.w_collision = base_reward_cfg.w_collision * float(args.coll_scale)
    speed_reward_cfg.w_step_penalty = float(args.w_step_penalty)
    speed_reward_cfg.w_forward_vel = float(args.w_forward_vel)
    logger.info(
        "Speed reward: w_progress=%.3g w_collision=%.3g (scale=%.2g) "
        "w_step_penalty=%.3g w_forward_vel=%.3g success_bonus=%.3g",
        speed_reward_cfg.w_progress, speed_reward_cfg.w_collision, args.coll_scale,
        speed_reward_cfg.w_step_penalty, speed_reward_cfg.w_forward_vel,
        speed_reward_cfg.success_bonus,
    )

    # -- Phase 2: pure imagination fine-tuning (no AirSim) -----------------
    logger.info("Phase 2: imagination REINFORCE fine-tuning (%d steps)", args.n_steps)
    out_path = (root / args.out_ckpt).resolve() if not Path(args.out_ckpt).is_absolute() else Path(args.out_ckpt)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(seed=42)
    t_start = time.perf_counter()
    returns_window: List[float] = []

    for step in range(1, args.n_steps + 1):
        # Sample a random batch from z_bank
        idx = rng.integers(0, n_starts, size=min(args.batch_size, n_starts))
        z0 = z_bank_arr[idx]    # [B, latent_dim]
        gr0 = gr_bank_arr[idx]  # [B, goal_rel_dim]
        bv0 = bv_bank_arr[idx]  # [B, body_vel_dim]

        # Set dynamics goal from mean goal_rel (approximate — imagined returns
        # are correct per-trajectory; goal just anchors the reward head)
        set_goal = getattr(dynamics, "set_goal", None)
        if callable(set_goal):
            # Reconstruct approximate world-frame goal from mean goal_rel
            # (exact goal per trajectory isn't needed — imagination uses goal_rel)
            set_goal(None)

        rollout = imagine(
            dynamics,
            actor_ac,
            z0,
            args.horizon,
            reward_cfg=speed_reward_cfg,
            goal_rel0=gr0,
            body_vel0=bv0,
            propagate_goal_rel=True,
            action_limits=None,   # actor tanh already enforces the (expanded) box
            max_horizon=args.horizon,
        )

        out = actor_ac.update(rollout)
        mean_ret = float(np.mean(rollout.returns))
        returns_window.append(mean_ret)
        if len(returns_window) > 100:
            returns_window.pop(0)

        if step % args.log_interval == 0 or step == 1:
            elapsed = time.perf_counter() - t_start
            actor_loss = out.get("actor_loss", float("nan"))
            critic_loss = out.get("critic_loss", float("nan"))
            mean_ent = out.get("mean_entropy", float("nan"))
            avg_ret100 = float(np.mean(returns_window))
            logger.info(
                "step %4d/%d | actor_loss=%.4f critic_loss=%.4f entropy=%.4f "
                "mean_ret=%.3f avg100=%.3f | %.1fs",
                step, args.n_steps,
                actor_loss, critic_loss, mean_ent, mean_ret, avg_ret100, elapsed,
            )

        # Periodic checkpoint snapshots
        if args.save_interval > 0 and step % args.save_interval == 0:
            snap_path = out_path.parent / f"v4_ac_speed_step{step}.pt"
            torch.save(
                {
                    "actor": actor_ac._actor.state_dict(),
                    "critic": actor_ac._critic.state_dict(),
                    "log_std": actor_ac._log_std.detach().cpu(),
                    "config": actor_ac.config.__dict__,
                    "finetune_step": step,
                    "finetune_args": vars(args),
                },
                snap_path,
            )
            logger.info("snapshot saved to %s", snap_path)

    # -- Save final checkpoint -------------------------------------------
    torch.save(
        {
            "actor": actor_ac._actor.state_dict(),
            "critic": actor_ac._critic.state_dict(),
            "log_std": actor_ac._log_std.detach().cpu(),
            "config": actor_ac.config.__dict__,
            "finetune_step": args.n_steps,
            "finetune_args": vars(args),
        },
        out_path,
    )
    logger.info("Final checkpoint saved to %s", out_path)

    total_time = time.perf_counter() - t_start
    logger.info(
        "Fine-tuning complete: %d steps in %.1f s (%.1f steps/s)",
        args.n_steps, total_time, args.n_steps / total_time,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
