#!/usr/bin/env python3
"""Eval Phase-3 actor on real Building_99 indoor micro segments (separate renderer)."""
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import yaml

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("eval_phase3_b99")


def _switch_building99(scene_sh: Path) -> None:
    logger.info("switching AirSim scene -> building99")
    subprocess.run(["bash", str(scene_sh), "building99"], check=True)
    time.sleep(15)


def _dedupe_segments(episodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []
    for ep in episodes:
        key = str(ep.get("segment_name") or ep.get("trajectory_id") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(ep)
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Phase-3 Building_99 indoor eval")
    p.add_argument("--config", default="configs/aerial_rl_phase3_unified.yaml")
    p.add_argument(
        "--annotation",
        default="experiments/aerial/phase3_unified/annotations/handover_seen_filtered.json",
    )
    p.add_argument(
        "--actor-ckpt",
        default="experiments/aerial/rl/artifacts/v4_ac_ckpt_phase3_unified_20260911/v4_ac_latest.pt",
    )
    p.add_argument(
        "--wm-ckpt",
        default="experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt",
    )
    p.add_argument("--pose-source", default="gt_proxy", choices=("gt_proxy", "odom_from_imu_rgb"))
    p.add_argument("--success-dist", type=float, default=0.5)
    p.add_argument("--max-steps", type=int, default=60)
    p.add_argument("--device", default="cuda")
    p.add_argument(
        "--scene-script",
        default="experiments/aerial/phase3_unified/scripts/recover_renderer_scene.sh",
    )
    p.add_argument("--out", default="artifacts/phase3_unified_eval_20260911/building99_indoor_eval.json")
    args = p.parse_args()

    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from experiments.aerial.eval.run_closed_loop import load_annotation
    from experiments.aerial.rl.actor_critic import LatentActorCritic, LatentActorDeployPolicy
    from experiments.aerial.rl.collector import act_delta, clip_body_delta
    from experiments.aerial.rl.goal_features import body_vel_from_obs, goal_rel_from_obs
    from experiments.aerial.rl.pose_estimate import make_pose_estimator, stamp_pose_on_obs
    from experiments.aerial.rl.scene_profile import apply_episode_scene_profile, restore_scene_profile_context
    from experiments.aerial.rl.train_rl import _build_env, load_torch_dynamics

    ann_path = root / args.annotation
    episodes = [e for e in load_annotation(ann_path) if e.get("leg") == "indoor" or e.get("map_id") == "building_99"]
    segments = _dedupe_segments(episodes)
    if not segments:
        logger.error("no indoor segments in %s", ann_path)
        return 1

    scene_sh = Path(args.scene_script)
    if not scene_sh.is_file():
        alt = Path.home() / "aerial-indoor-wam/experiments/aerial/scripts/recover_renderer_scene.sh"
        scene_sh = alt if alt.is_file() else scene_sh
    _switch_building99(scene_sh)

    cfg = yaml.safe_load((root / args.config).read_text()) or {}
    cfg.setdefault("env", {})["backend"] = "airsim"
    cfg["env"]["grab_depth"] = False
    cfg["env"]["step_hz"] = 5.0
    env = _build_env(cfg["env"])

    wm_path = root / args.wm_ckpt
    dynamics, _ = load_torch_dynamics(
        cfg.get("world_model") or {},
        str(wm_path),
        device=str(args.device),
        success_dist_m=float(args.success_dist),
    )
    actor_path = root / args.actor_ckpt
    actor_ac = LatentActorCritic.load_from_checkpoint(actor_path, device=str(args.device))
    policy = LatentActorDeployPolicy(dynamics, actor_ac, deterministic=True, stream_latent=True)
    pose_est = make_pose_estimator(args.pose_source)

    from experiments.aerial.rl.reward import RewardConfig
    from experiments.aerial.rl.scene_profile import load_scene_profiles_from_mapping

    profiles = load_scene_profiles_from_mapping(cfg.get("scene_profiles") or {})
    reward_cfg = RewardConfig(**(cfg.get("reward") or {}))

    results: List[Dict[str, Any]] = []
    try:
        for seg in segments:
            label = str(seg.get("segment_name") or seg.get("trajectory_id"))
            goal = np.asarray(seg["pos"][1], dtype=np.float64)
            d0 = float(np.linalg.norm(goal - np.asarray(seg["pos"][0], dtype=np.float64)))
            logger.info("--- %s d0=%.2fm pose=%s ---", label, d0, args.pose_source)

            ctx = apply_episode_scene_profile(
                seg, reward_cfg=reward_cfg, safety=None, step_hz=5.0, profiles=profiles,
            )
            limits = np.asarray(ctx.limits, dtype=np.float64)

            obs = env.reset(seg)
            if obs is None or bool(getattr(obs, "collided", False)):
                results.append({"segment_name": label, "ok": False, "reason": "spawn_collision"})
                restore_scene_profile_context(ctx, reward_cfg, None)
                continue

            pe = pose_est.reset(obs)
            stamp_pose_on_obs(obs, pe)
            if hasattr(policy, "reset"):
                policy.reset()
            latent = np.asarray(dynamics.encode(obs), dtype=np.float64)
            arrived = False
            collided = False

            for _ in range(int(args.max_steps)):
                action = act_delta(policy, obs, str(seg.get("gpt_instruction", "")), limits)
                action = clip_body_delta(action, limits)
                next_obs, _info = env.step(action)
                out = dynamics.step(
                    latent,
                    action,
                    goal_rel=goal_rel_from_obs(obs),
                    body_vel=body_vel_from_obs(obs),
                )
                latent = np.asarray(out.z_next, dtype=np.float64)
                obs = next_obs
                pe = pose_est.update(obs, action=action, dt=0.2)
                stamp_pose_on_obs(obs, pe)
                collided = collided or bool(getattr(obs, "collided", False))
                d_now = float(np.linalg.norm(np.asarray(obs.position, dtype=np.float64).reshape(3) - goal))
                if d_now <= float(args.success_dist):
                    arrived = True
                    break
                if collided:
                    break

            d_end = float(np.linalg.norm(np.asarray(obs.position, dtype=np.float64).reshape(3) - goal))
            results.append({
                "segment_name": label,
                "ok": True,
                "arrived": arrived,
                "collided": collided,
                "d0_m": round(d0, 3),
                "d_end_m": round(d_end, 3),
                "pose_source": args.pose_source,
                "success_dist_m": float(args.success_dist),
            })
            logger.info("%s arrived=%s d_end=%.3f collided=%s", label, arrived, d_end, collided)
            restore_scene_profile_context(ctx, reward_cfg, None)
    finally:
        close = getattr(env, "close", None)
        if callable(close):
            close()

    n_ok = sum(1 for r in results if r.get("ok"))
    n_arr = sum(1 for r in results if r.get("arrived"))
    payload = {
        "evaluation_title": "Phase-3 Building_99 indoor micro eval",
        "actor_ckpt": str(actor_path),
        "pose_source": args.pose_source,
        "success_dist_m": float(args.success_dist),
        "n_segments": len(results),
        "arrival_rate": round(n_arr / max(len(results), 1), 4),
        "arrival_rate_ok": round(n_arr / max(n_ok, 1), 4),
        "episodes": results,
    }
    out_path = root / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Wrote %s arrival_rate=%.1f%% (%d/%d)", out_path, 100 * payload["arrival_rate"], n_arr, len(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
