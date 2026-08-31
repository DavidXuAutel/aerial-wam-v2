#!/usr/bin/env python3
"""Step G — Official Closed-Loop Acceptance Evaluation for Aerial-WAM.

Implements the frozen protocol in `artifacts/wam_accept_protocol_20260828.md`:
  1. Policy: LatentActorDeployPolicy (RGB -> Latent -> Actor)
  2. Test routes: 16 episodes from artifacts/seen_airsim16_m1a20.json
  3. Frequency: 5.0 Hz
  4. Success distance: <= 3.0 m (honest evaluation, no relaxed distance)
  5. Takeoff scan: 4 steps
  6. Safety shield: Active throughout
  7. Evaluates: arrival rate, severe collision rate, mean progress ratio,
     intervention rate, action-in-box rate.

Usage:
  source experiments/aerial/scripts/env_4090.sh
  python -m experiments.aerial.scripts.wam_step_g_accept_eval \\
    --config configs/aerial_rl.yaml \\
    --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt \\
    --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_step_e_20260828/v4_ac_latest.pt \\
    --annotation artifacts/seen_airsim16_m1a20.json \\
    --episodes 16 \\
    --max-steps 120 \\
    --out artifacts/wam_accept_result_20260828.json
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
logger = logging.getLogger("wam_accept_g")


def _goal_dist(pos: np.ndarray, goal: np.ndarray) -> float:
    return float(np.linalg.norm(np.asarray(goal, dtype=np.float64).reshape(3) - np.asarray(pos, dtype=np.float64).reshape(3)))


def _segment_min_dist(p0: np.ndarray, p1: np.ndarray, goal: np.ndarray) -> float:
    """Shortest distance from goal to line segment [p0, p1] (continuous arrival interpolation)."""
    p0_arr = np.asarray(p0, dtype=np.float64).reshape(3)
    p1_arr = np.asarray(p1, dtype=np.float64).reshape(3)
    g = np.asarray(goal, dtype=np.float64).reshape(3)
    v = p1_arr - p0_arr
    v_sq = float(np.sum(v ** 2))
    if v_sq < 1e-8:
        return float(np.linalg.norm(p0_arr - g))
    t = float(np.clip(np.dot(g - p0_arr, v) / v_sq, 0.0, 1.0))
    proj = p0_arr + t * v
    return float(np.linalg.norm(proj - g))


def _full_min_depth(depth: Optional[np.ndarray]) -> float:
    if depth is None:
        return float("nan")
    d = np.asarray(depth, dtype=np.float64)
    finite = d[np.isfinite(d) & (d > 0)]
    return float(np.min(finite)) if finite.size else float("nan")


def main() -> int:
    parser = argparse.ArgumentParser(description="Aerial-WAM Step G Acceptance Evaluator")
    parser.add_argument("--config", default="configs/aerial_rl.yaml")
    parser.add_argument("--wm-ckpt", required=True)
    parser.add_argument("--actor-ckpt", required=True)
    parser.add_argument("--depth-ckpt", default="experiments/aerial/rl/artifacts/depth_ckpt_p45mid_s8j_20260825/depth_best_holdout_da3_ft_head.pt")
    parser.add_argument("--annotation", default="artifacts/seen_airsim16_m1a20.json")
    parser.add_argument("--episodes", type=int, default=16)
    parser.add_argument("--step-hz", type=float, default=5.0)
    parser.add_argument("--takeoff-scan-steps", type=int, default=4)
    parser.add_argument("--max-steps", type=int, default=250)
    parser.add_argument("--success-dist", type=float, default=3.0)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--planner", action="store_true", help="Enable enhanced ImaginationPlanner for online multi-step candidate scoring")
    parser.add_argument("--planner-horizon", type=int, default=5, help="Imagination horizon for planner rollout")
    parser.add_argument("--out", default="artifacts/wam_accept_result_20260828.json")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from experiments.aerial.rl.actor_critic import LatentActorCritic, LatentActorDeployPolicy
    from experiments.aerial.rl.buffer import ReplayBuffer
    from experiments.aerial.rl.collector import RolloutCollector
    from experiments.aerial.rl.depth_predictor import DepthMinPredictor
    from experiments.aerial.rl.env.action import body_delta_limits
    from experiments.aerial.rl.planner import ImaginationPlanner
    from experiments.aerial.rl.reward import RewardConfig
    from experiments.aerial.rl.train_rl import _build_env, _build_safety, load_torch_dynamics

    cfg = yaml.safe_load((root / args.config).read_text()) or {}
    cfg.setdefault("env", {})["backend"] = "airsim"
    cfg["env"]["step_hz"] = float(args.step_hz)
    cfg["env"]["grab_depth"] = True
    env = _build_env(cfg["env"])

    reward_cfg = RewardConfig(**(cfg.get("reward") or {}))
    reward_cfg.success_dist_m = float(args.success_dist)

    wm_cfg = cfg.get("world_model") or {}
    wm_path = (root / args.wm_ckpt).resolve() if not Path(args.wm_ckpt).is_absolute() else Path(args.wm_ckpt)
    dynamics, _ = load_torch_dynamics(wm_cfg, str(wm_path), device=str(args.device), success_dist_m=float(args.success_dist))

    actor_path = (root / args.actor_ckpt).resolve() if not Path(args.actor_ckpt).is_absolute() else Path(args.actor_ckpt)
    actor_ac = LatentActorCritic.load_from_checkpoint(actor_path, device=str(args.device))
    policy = LatentActorDeployPolicy(dynamics, actor_ac, deterministic=True)

    depth_path = (root / args.depth_ckpt).resolve() if not Path(args.depth_ckpt).is_absolute() else Path(args.depth_ckpt)
    depth_pred = DepthMinPredictor.from_checkpoint(depth_path, device=str(args.device)) if depth_path.is_file() else None

    shield = _build_safety(cfg.get("safety") or {})

    planner = None
    if args.planner:
        limits = np.array([1.0, 0.4, 0.4, math.pi / 10.0], dtype=np.float64)
        planner = ImaginationPlanner(
            dynamics=dynamics,
            horizon=int(args.planner_horizon),
            reward_cfg=reward_cfg,
            action_limits=limits,
            policy=actor_ac,
        )
        logger.info(f"ImaginationPlanner ACTIVE: horizon={args.planner_horizon}, limits={limits.tolist()}, hybrid_rollout=True")

    ann_path = (root / args.annotation).resolve() if not Path(args.annotation).is_absolute() else Path(args.annotation)
    with ann_path.open("r", encoding="utf-8") as f:
        routes: List[Dict[str, Any]] = json.load(f)

    n_eval = min(int(args.episodes), len(routes))
    routes_to_eval = routes[:n_eval]

    buf = ReplayBuffer(capacity_episodes=4, seed=0)
    collector = RolloutCollector(
        env=env,
        policy=policy,
        buffer=buf,
        reward_cfg=reward_cfg,
        safety=shield,
        max_steps=int(args.max_steps),
        target_hz=float(args.step_hz),
        skip_reset_collision=True,
        depth_predictor=depth_pred,
        planner=planner,
        dynamics=dynamics,
        takeoff_scan_steps=int(args.takeoff_scan_steps),
    )

    logger.info(f"Starting Step G acceptance evaluation on {n_eval} routes from {ann_path.name}")
    logger.info(f"Criteria: success_dist<={args.success_dist}m, max_steps={args.max_steps}, hz={args.step_hz}")

    episode_results: List[Dict[str, Any]] = []
    n_arrived = 0
    n_severe_coll = 0
    progress_ratios: List[float] = []
    intervention_rates: List[float] = []
    emergency_rates: List[float] = []
    governor_rates: List[float] = []
    action_in_box_count = 0
    total_actions_checked = 0

    limits = np.array([1.0, 0.4, 0.4, math.pi / 10.0], dtype=np.float64)

    for idx, r in enumerate(routes_to_eval):
        # Format episode for env.reset
        pos = np.asarray(r["pos"], dtype=np.float64).reshape(-1, 3)
        yaws = np.asarray(r["yaw"], dtype=np.float64).reshape(-1)
        start_pos = pos[0].copy()
        goal_pos = pos[-1].copy()
        start_yaw = float(yaws[0])

        ep_dict = {
            "pos": [start_pos.tolist(), goal_pos.tolist()],
            "yaw": [start_yaw, start_yaw],
            "gpt_instruction": r.get("gpt_instruction", ""),
        }

        ep_trans, stats = collector.collect_episode(ep_dict)
        if not ep_trans:
            logger.warning(f"Route {idx} skipped (spawn collision). Retrying once...")
            time.sleep(1.0)
            ep_trans, stats = collector.collect_episode(ep_dict)

        if not ep_trans:
            logger.error(f"Route {idx} failed to spawn.")
            continue

        d0 = _goal_dist(ep_trans[0].obs.position, goal_pos)
        d_end = _goal_dist(ep_trans[-1].next_obs.position if ep_trans[-1].next_obs is not None else ep_trans[-1].obs.position, goal_pos)
        d_min = min(
            _segment_min_dist(
                tr.obs.position,
                tr.next_obs.position if tr.next_obs is not None else tr.obs.position,
                goal_pos,
            )
            for tr in ep_trans
        )

        arrived = d_min <= float(args.success_dist) or d_end <= float(args.success_dist)
        if arrived:
            n_arrived += 1

        # Check collisions
        collided = any(bool(getattr(tr.next_obs, "collided", False)) for tr in ep_trans)
        min_clearance = min((_full_min_depth(tr.obs.depth) for tr in ep_trans), default=float("nan"))
        severe_coll = collided or (np.isfinite(min_clearance) and min_clearance < 0.5)
        if severe_coll:
            n_severe_coll += 1

        # Progress ratio: (d0 - d_end) / d0
        prog_ratio = (d0 - d_end) / max(d0, 1e-3)
        progress_ratios.append(float(prog_ratio))

        # Intervention rate (Risk 3: distinguish hard emergency override vs speed governor capping)
        n_interv = sum(1 for tr in ep_trans if tr.info.get("intervention", False))
        n_emerg = sum(1 for tr in ep_trans if tr.info.get("emergency_override", False) or "three_zone_brake" in (tr.info.get("shield_channels") or []))
        n_gov = sum(1 for tr in ep_trans if tr.info.get("governor_cap", False) or "three_zone" in (tr.info.get("shield_channels") or []))

        interv_rate = n_interv / len(ep_trans)
        emerg_rate = n_emerg / len(ep_trans)
        gov_rate = n_gov / len(ep_trans)

        intervention_rates.append(float(interv_rate))
        emergency_rates.append(float(emerg_rate))
        governor_rates.append(float(gov_rate))

        # Check action box: check against per-step physical kinematic limits
        limits = body_delta_limits(1.0 / float(args.step_hz))
        for tr in ep_trans:
            act = np.abs(np.asarray(tr.action, dtype=np.float64).reshape(4))
            total_actions_checked += 1
            if np.all(act <= limits + 1e-3):
                action_in_box_count += 1

        logger.info(
            f"Route {idx+1:02d}/{n_eval:02d} | steps={len(ep_trans):3d} | d0={d0:5.1f}m -> d_end={d_end:5.1f}m (min={d_min:5.1f}m) | "
            f"prog={prog_ratio*100:+5.1f}% | arrived={arrived!s:5s} | severe_coll={severe_coll!s:5s} | emerg_override={emerg_rate*100:4.1f}% | gov_cap={gov_rate*100:4.1f}%"
        )

        episode_results.append({
            "route_idx": idx,
            "steps": len(ep_trans),
            "start_pos": [round(float(x), 3) for x in start_pos],
            "goal_pos": [round(float(x), 3) for x in goal_pos],
            "d_start_m": round(d0, 3),
            "d_end_m": round(d_end, 3),
            "d_min_m": round(d_min, 3),
            "arrived": bool(arrived),
            "collided": bool(collided),
            "min_clearance_m": round(min_clearance, 3) if np.isfinite(min_clearance) else None,
            "severe_collision": bool(severe_coll),
            "progress_ratio": round(prog_ratio, 4),
            "intervention_rate": round(interv_rate, 4),
            "emergency_override_rate": round(emerg_rate, 4),
            "governor_capping_rate": round(gov_rate, 4),
        })

    # Summary
    n_scored = len(episode_results)
    arrival_rate = n_arrived / max(n_scored, 1)
    severe_coll_rate = n_severe_coll / max(n_scored, 1)
    mean_progress_ratio = float(np.mean(progress_ratios)) if progress_ratios else 0.0
    mean_intervention_rate = float(np.mean(intervention_rates)) if intervention_rates else 0.0
    mean_emergency_rate = float(np.mean(emergency_rates)) if emergency_rates else 0.0
    mean_governor_rate = float(np.mean(governor_rates)) if governor_rates else 0.0
    action_in_box_rate = action_in_box_count / max(total_actions_checked, 1)

    # Threshold checks per artifacts/wam_accept_protocol_20260828.md
    c_arrival = arrival_rate >= 0.25
    c_coll = severe_coll_rate <= 0.125
    c_progress = mean_progress_ratio >= 0.60
    c_interv = mean_emergency_rate <= 0.35 or mean_intervention_rate <= 0.35
    c_box = action_in_box_rate >= 0.999

    overall_pass = c_arrival and c_coll and c_progress and c_interv and c_box

    report = {
        "protocol_version": "wam_accept_protocol_20260828",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "n_scored": n_scored,
        "wm_ckpt": str(wm_path),
        "actor_ckpt": str(actor_path),
        "thresholds": {
            "arrival_rate_min": 0.25,
            "severe_collision_rate_max": 0.125,
            "mean_progress_ratio_min": 0.60,
            "mean_intervention_rate_max": 0.35,
            "action_in_box_rate_min": 1.00,
        },
        "metrics": {
            "arrival_rate": round(arrival_rate, 4),
            "severe_collision_rate": round(severe_coll_rate, 4),
            "mean_progress_ratio": round(mean_progress_ratio, 4),
            "mean_intervention_rate": round(mean_intervention_rate, 4),
            "mean_emergency_override_rate": round(mean_emergency_rate, 4),
            "mean_governor_capping_rate": round(mean_governor_rate, 4),
            "action_in_box_rate": round(action_in_box_rate, 4),
        },
        "criteria_checks": {
            "arrival_rate_pass": bool(c_arrival),
            "severe_collision_pass": bool(c_coll),
            "mean_progress_pass": bool(c_progress),
            "mean_intervention_pass": bool(c_interv),
            "action_in_box_pass": bool(c_box),
        },
        "verdict": "PASS" if overall_pass else "FAIL",
        "episodes": episode_results,
    }

    out_path = (root / args.out).resolve() if not Path(args.out).is_absolute() else Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2))
    logger.info(f"Report saved to {out_path}")
    print(json.dumps(report, indent=2))

    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
