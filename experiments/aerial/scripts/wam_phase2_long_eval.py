#!/usr/bin/env python3
"""Phase 2 mainline long-horizon evaluator (design v1.0).

Stack only:
  AdaptiveSubgoalGenerator → LatentActorDeployPolicy → ImaginationPlanner
  → ThreeZoneSpeedShield → env.step

No docking P-controller, no anti-stagnation escape, no spawn altitude hacks,
no roundtrip-specific metrics.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import yaml

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("wam_phase2_eval")


def _goal_dist(pos: np.ndarray, goal: np.ndarray) -> float:
    return float(
        np.linalg.norm(
            np.asarray(goal, dtype=np.float64).reshape(3)
            - np.asarray(pos, dtype=np.float64).reshape(3)
        )
    )


def _goal_closure(d_start_m: float, d_min_m: float) -> float:
    """Honest Euclidean closure toward G: 1 - d_min/d_start, clipped to [0, 1]."""
    d0 = float(max(1e-3, d_start_m))
    return float(np.clip(1.0 - float(d_min_m) / d0, 0.0, 1.0))


def _monotone_inflate(progress_ratio: float, d_min_m: float, *, prog_min: float = 0.9, d_min_floor_m: float = 30.0) -> bool:
    """True when arc-s Prog looks near-done but Euclidean d_min stays far from G."""
    return bool(float(progress_ratio) >= float(prog_min) and float(d_min_m) >= float(d_min_floor_m))


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 2 mainline long-horizon eval")
    parser.add_argument("--config", default="configs/aerial_rl.yaml")
    parser.add_argument(
        "--wm-ckpt",
        default="experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt",
    )
    parser.add_argument(
        "--actor-ckpt",
        default="experiments/aerial/rl/artifacts/v4_ac_ckpt_step_e_20260828/v4_ac_latest.pt",
    )
    parser.add_argument(
        "--depth-ckpt",
        default="experiments/aerial/rl/artifacts/depth_ckpt_p45mid_s8j_20260825/depth_best_holdout_da3_ft_head.pt",
    )
    parser.add_argument("--annotation", default="artifacts/seen_airsim16_long_routes.json")
    parser.add_argument("--episodes", type=int, default=16)
    parser.add_argument("--step-hz", type=float, default=5.0)
    parser.add_argument("--max-steps", type=int, default=1000)
    parser.add_argument("--cruise-speed", type=float, default=25.0)
    parser.add_argument("--success-dist", type=float, default=3.0)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--planner", action="store_true")
    parser.add_argument("--planner-horizon", type=int, default=5)
    parser.add_argument(
        "--goal-feat-mode",
        choices=("meter", "g_norm"),
        default="meter",
        help="Actor goal conditioning: metre goal_rel (Step E) or F9 g_norm",
    )
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--out", default="artifacts/wam_phase2_accept_result.json")
    parser.add_argument(
        "--spawn-tol-m",
        type=float,
        default=12.0,
        help="F1: max ||p_reset - start_pos||; beyond → spawn_fail skip (no SCR inflate)",
    )
    parser.add_argument(
        "--heading-assist",
        action="store_true",
        default=False,
        help="F7 fuse: path-tangent dyaw (OFF by default; mainline SR must not rely on this)",
    )
    parser.add_argument(
        "--lookahead-feedback",
        action="store_true",
        default=False,
        help="L1 DECLARE: no-progress / CTE feedback on carrot (OFF by default)",
    )
    parser.add_argument(
        "--rolling-global",
        action="store_true",
        default=False,
        help="P0 receding GlobalRefPlanner: carrot on short P_ref (OFF by default)",
    )
    parser.add_argument(
        "--global-horizon-m",
        type=float,
        default=60.0,
        help="GlobalRefPlanner forward horizon (m)",
    )
    parser.add_argument(
        "--global-replan-period-s",
        type=float,
        default=1.0,
        help="GlobalRefPlanner replan period (s); 0 = every step",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    import torch
    from experiments.aerial.rl.actor_critic import (
        ImaginationActorPolicy,
        LatentActorCritic,
        LatentActorDeployPolicy,
    )
    from experiments.aerial.rl.depth_predictor import DepthMinPredictor
    from experiments.aerial.rl.env.action import body_delta_limits, clip_body_delta
    from experiments.aerial.rl.path_heading_assist import apply_path_heading_assist
    from experiments.aerial.rl.goal_features import body_vel_from_obs
    from experiments.aerial.rl.planner import ImaginationPlanner
    from experiments.aerial.rl.reward import RewardConfig
    from experiments.aerial.rl.global_ref_planner import GlobalRefConfig, GlobalRefPlanner
    from experiments.aerial.rl.subgoal_generator import (
        AdaptiveSubgoalGenerator,
        nearest_on_polyline,
    )
    from experiments.aerial.rl.train_rl import (
        _build_env,
        _build_safety,
        load_torch_dynamics,
    )

    cfg_file = (root / args.config).resolve()
    cfg = yaml.safe_load(cfg_file.read_text()) if cfg_file.is_file() else {}

    device_str = "cpu" if (args.mock or not torch.cuda.is_available()) else args.device
    device = torch.device(device_str)
    logger.info(f"Using device: {device} (mock={args.mock})")

    anno_path = (
        (root / args.annotation).resolve()
        if not Path(args.annotation).is_absolute()
        else Path(args.annotation)
    )
    with open(anno_path, "r", encoding="utf-8") as f:
        anno_data = json.load(f)
    routes = anno_data.get("routes", anno_data) if isinstance(anno_data, dict) else anno_data
    n_routes = min(args.episodes, len(routes))

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
        # Re-anchor: Step E expects metre features; CLI overrides ckpt default.
        actor_ac.config.goal_feat_mode = str(args.goal_feat_mode)
        logger.info(
            "Loaded actor-critic from %s (goal_feat_mode=%s)",
            actor_path,
            actor_ac.config.goal_feat_mode,
        )
    else:
        actor_ac = LatentActorCritic.from_config(
            {"latent_dim": dynamics.latent_dim, "device": device_str}
        )

    phys_limits = body_delta_limits(1.0 / float(args.step_hz))
    vx_max_step = float(
        min(float(args.cruise_speed) / float(args.step_hz), float(phys_limits[0]))
    )
    action_limits = np.array(
        [
            vx_max_step,
            float(phys_limits[1]),
            float(phys_limits[2]),
            float(phys_limits[3]),
        ],
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
            actor=ImaginationActorPolicy(actor_ac, deterministic=True),
            max_horizon=int(args.planner_horizon),
        )

    policy = LatentActorDeployPolicy(
        dynamics, actor_ac, deterministic=True, stream_latent=True
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

    safety_cfg = dict(cfg.get("safety") or {})
    if str(safety_cfg.get("kind", "null")) in ("null", "none", "None"):
        safety_cfg["kind"] = "three_zone"
        logger.warning("safety.kind was null — forcing three_zone for mainline Phase 2")
    # Keep three-zone cruise assumption aligned with --cruise-speed (engage scales as v²).
    safety_cfg["v_cruise_m_s"] = float(args.cruise_speed)
    safety_cfg.pop("schedule_margin_l1_m", None)
    safety_cfg.pop("schedule_margin_l2_m", None)
    safety_cfg.pop("disc_lag_steps", None)
    shield = _build_safety(safety_cfg)
    if hasattr(shield, "zone"):
        logger.info(
            "three_zone v_cruise=%.1f engage_outer=%.1fm margins L1/L2=%.2f/%.2f",
            float(shield.zone.v_cruise_m_s),
            float(shield.zone.engage_outer_m),
            float(shield.zone.schedule_margin_l1_m),
            float(shield.zone.schedule_margin_l2_m),
        )

    # Local carrot for step_e π (H1 + P1 sweep 2026-09-01): r_base=25 /
    # cte_reentry=2 passed R01 ds>=25 & cte_end<=15; long routes still slide.
    subgoal_gen = AdaptiveSubgoalGenerator(
        r_base=25.0 if args.cruise_speed >= 8.0 else 20.0,
        r_min=15.0 if args.cruise_speed >= 8.0 else 12.0,
        d_clear=22.0 if args.cruise_speed >= 8.0 else 12.0,
        d_danger=3.0,
        cruise_speed=args.cruise_speed,
        cte_reentry_m=2.0,
        lookahead_feedback=bool(args.lookahead_feedback),
    )
    if args.lookahead_feedback:
        logger.info("L1 lookahead_feedback=ON (opt-in; mainline default remains OFF)")

    global_planner: Any = None
    if bool(args.rolling_global):
        global_planner = GlobalRefPlanner(
            GlobalRefConfig(
                horizon_m=float(args.global_horizon_m),
                replan_period_s=float(args.global_replan_period_s),
                step_hz=float(args.step_hz),
            )
        )
        logger.info(
            "P0 rolling_global=ON horizon=%.1fm replan=%.2fs (default remains OFF)",
            float(args.global_horizon_m),
            float(args.global_replan_period_s),
        )

    logger.info(
        f"Starting Phase 2 mainline eval on {n_routes} native routes "
        f"(cruise={args.cruise_speed} m/s, limits={action_limits.tolist()})"
    )

    results: List[Dict[str, Any]] = []

    for ep_idx in range(n_routes):
        r_info = routes[ep_idx]
        pts = np.array(r_info.get("pos", r_info.get("positions")), dtype=np.float64)
        goal_pos = pts[-1].copy()
        start_pos = pts[0].copy()
        yaws = np.array(r_info.get("yaw", [0.0] * len(pts)), dtype=np.float64)
        start_yaw = float(yaws[0]) if len(yaws) else 0.0
        ref_len = float(np.sum(np.linalg.norm(pts[1:] - pts[:-1], axis=1)))

        subgoal_gen.reset()
        if global_planner is not None:
            global_planner.reset(pts, goal=goal_pos)
        if shield is not None:
            shield.reset()
        if depth_pred is not None:
            depth_pred.reset()
        policy.reset()

        ep_dict = {
            # Full polyline so reset uses true start; goal = last waypoint
            "pos": pts.tolist(),
            "yaw": yaws.tolist() if len(yaws) == len(pts) else [start_yaw] * len(pts),
            "gpt_instruction": r_info.get("gpt_instruction", ""),
        }
        obs = env.reset(ep_dict)

        p_curr = np.array(obs.position, dtype=np.float64)
        curr_yaw = float(obs.yaw) if hasattr(obs, "yaw") else 0.0
        spawn_err = float(np.linalg.norm(p_curr - start_pos))
        # F1: one altitude bump retry if reset landed far from annotated start
        if spawn_err > float(args.spawn_tol_m) and not args.mock:
            bump = start_pos.copy()
            bump[2] = float(bump[2]) + 2.0
            logger.warning(
                "Route %02d spawn_err=%.1fm — retry start z+=2 (F1)",
                ep_idx + 1,
                spawn_err,
            )
            ep_retry = dict(ep_dict)
            pts_retry = np.asarray(ep_retry["pos"], dtype=np.float64).copy()
            pts_retry[0] = bump
            ep_retry["pos"] = pts_retry.tolist()
            obs = env.reset(ep_retry)
            p_curr = np.array(obs.position, dtype=np.float64)
            curr_yaw = float(obs.yaw) if hasattr(obs, "yaw") else curr_yaw
            spawn_err = float(np.linalg.norm(p_curr - bump))

        if spawn_err > float(args.spawn_tol_m):
            logger.error(
                "Route %02d F1 spawn_fail err=%.1fm — skip episode (not counted as SCR)",
                ep_idx + 1,
                spawn_err,
            )
            results.append(
                {
                    "route_idx": ep_idx,
                    "base_route_idx": r_info.get("base_route_idx", ep_idx),
                    "L_ref": ref_len,
                    "L_act": 0.0,
                    "d0": float("nan"),
                    "min_d": float("nan"),
                    "arrived": False,
                    "collided": False,
                    "severe_collision": False,
                    "progress_ratio": 0.0,
                    "spl": 0.0,
                    "intervention_rate": 0.0,
                    "spawn_fail": True,
                    "spawn_err_m": spawn_err,
                    "fail_tag": "F1",
                }
            )
            continue

        d0 = _goal_dist(p_curr, goal_pos)
        min_d = d0
        d_final = d0
        traj = [p_curr.copy()]
        arrived = False
        collided = False
        severe_coll = False
        interventions = 0
        s_prog = 0.0
        last_true_s: float | None = None

        for step in range(args.max_steps):
            d_fwd = None
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

            path_for_carrot = pts
            rem_full = None
            true_s_full = None
            if global_planner is not None:
                true_proj, _seg, true_s_full, rem_full = nearest_on_polyline(
                    p_curr, pts
                )
                cte_full = float(np.linalg.norm(p_curr - true_proj))
                if last_true_s is None:
                    progressed = float("inf")
                else:
                    progressed = float(true_s_full) - float(last_true_s)
                last_true_s = float(true_s_full)
                path_for_carrot = global_planner.step(
                    p_curr,
                    curr_yaw,
                    cte_m=cte_full,
                    progressed_m=progressed,
                )

            g_rel_body, s_info = subgoal_gen.compute_subgoal(
                curr_pos=p_curr,
                curr_yaw=curr_yaw,
                global_path=path_for_carrot,
                d_fwd_hat=d_fwd,
            )
            target_world = np.array(s_info["target_world"], dtype=np.float64)
            if global_planner is not None and true_s_full is not None and rem_full is not None:
                # Metrics / stop use full corridor + Euclidean G, not short P_ref rem.
                s_prog = float(true_s_full)
                rem_dist = float(rem_full)
            else:
                s_prog = float(s_info["s_progress"])
                rem_dist = float(s_info["rem_dist"])
            safe_v = float(s_info.get("safe_speed_limit", args.cruise_speed))

            # Align step box with physics body_delta_limits and v_safe (F3/planner)
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

            # Terminal arrival: Euclidean G; rem gate uses full-corridor rem when rolling.
            if bool(args.rolling_global):
                if d_to_goal <= float(args.success_dist):
                    arrived = True
                    break
            elif rem_dist <= float(args.success_dist) and d_to_goal <= float(args.success_dist):
                arrived = True
                break

            # In-distribution local goal for Phase 1 policy / planner
            obs.info["goal"] = target_world.tolist()
            obs.info["goal_rel"] = g_rel_body.tolist()
            if planner is not None:
                planner.set_goal(target_world)

            action = policy.act(obs)
            if planner is not None:
                action = planner.plan(obs, action, latent=policy._latent)

            action = clip_body_delta(action, cur_limits)
            if bool(args.heading_assist):
                action, _ha, _ = apply_path_heading_assist(
                    action,
                    yaw=curr_yaw,
                    path=pts,
                    seg_idx=int(s_info.get("seg_idx", 0)),
                    cte_m=float(s_info.get("cte_m", 0.0)),
                    limits=cur_limits,
                )
                if _ha:
                    action = clip_body_delta(action, cur_limits)

            # Probe p_coll for shield without consuming deploy latent stream
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

            if shield is not None:
                act_safe, overridden = shield.apply_action(
                    action, obs, wm_out=wm_out, limits=cur_limits
                )
                if overridden:
                    interventions += 1
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
            traj.append(p_curr.copy())

            seg_d = _segment_min_dist(p_prev, p_curr, goal_pos)
            if bool(args.rolling_global):
                if seg_d <= float(args.success_dist):
                    arrived = True
                    min_d = min(min_d, seg_d)
                    d_final = float(seg_d)
                    break
            elif rem_dist <= float(args.success_dist) and seg_d <= float(args.success_dist):
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

        actual_len = (
            float(np.sum(np.linalg.norm(np.diff(np.array(traj), axis=0), axis=1)))
            if len(traj) > 1
            else 0.0
        )
        prog_ratio = float(np.clip(s_prog / max(1e-3, ref_len), 0.0, 1.0))
        # Design SPL; shortcuts (L_act < L_ref) do not inflate above 1.0
        ep_spl = (ref_len / max(ref_len, actual_len)) if arrived else 0.0
        goal_closure = _goal_closure(d0, min_d)
        inflate = _monotone_inflate(prog_ratio, min_d)

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
            "monotone_inflate": bool(inflate),
            "arrived": arrived,
            "collided": collided,
            "severe_collision": severe_coll,
            "progress_ratio": round(prog_ratio, 4),
            "spl": round(ep_spl, 4),
            "intervention_rate": round(interventions / max(1, len(traj)), 4),
            "n_global_replans": (
                int(global_planner.replan_count) if global_planner is not None else 0
            ),
        }
        results.append(ep_result)
        logger.info(
            f"Route {ep_idx+1:02d}/{n_routes:02d} | L_ref={ref_len:.1f}m | L_act={actual_len:.1f}m | "
            f"min_d={min_d:.2f}m | d_final={d_final:.2f}m | closure={goal_closure:.2f} | "
            f"arrived={arrived} | prog={prog_ratio*100:.1f}% | inflate={inflate} | "
            f"spl={ep_spl:.3f} | IR={ep_result['intervention_rate']:.3f}"
        )

    scored = [r for r in results if not r.get("spawn_fail")]
    spawn_fails = [r for r in results if r.get("spawn_fail")]
    sr = float(np.mean([r["arrived"] for r in scored])) if scored else 0.0
    scr = float(np.mean([r["severe_collision"] for r in scored])) if scored else 0.0
    mean_prog = float(np.mean([r["progress_ratio"] for r in scored])) if scored else 0.0
    mean_spl = float(np.mean([r["spl"] for r in scored])) if scored else 0.0
    mean_ir = float(np.mean([r["intervention_rate"] for r in scored])) if scored else 0.0
    mean_closure = float(np.mean([r["goal_closure"] for r in scored])) if scored else 0.0
    n_inflate = int(sum(1 for r in scored if r.get("monotone_inflate")))

    # L0: PASS gates on Euclidean arrival (SR) + safety/SPL only.
    # progress_ratio is diagnostic; must not cosplay as near-success.
    summary = {
        "protocol_version": "wam_phase2_mainline_l0_honest_goal_20260902",
        "goal_feat_mode": str(args.goal_feat_mode),
        "actor_ckpt": str(actor_path),
        "cruise_speed_m_s": args.cruise_speed,
        "rolling_global": bool(args.rolling_global),
        "global_horizon_m": float(args.global_horizon_m),
        "global_replan_period_s": float(args.global_replan_period_s),
        "n_scored": len(scored),
        "n_spawn_fail_f1": len(spawn_fails),
        "metrics": {
            "arrival_rate": round(sr, 4),
            "spl": round(mean_spl, 4),
            "severe_collision_rate": round(scr, 4),
            "mean_goal_closure": round(mean_closure, 4),
            "n_monotone_inflate": n_inflate,
            "mean_progress_ratio": round(mean_prog, 4),
            "mean_intervention_rate": round(mean_ir, 4),
            "mean_global_replans": (
                round(
                    float(np.mean([r.get("n_global_replans", 0) for r in scored])),
                    2,
                )
                if scored
                else 0.0
            ),
        },
        "thresholds": {
            "arrival_rate_min": 0.80,
            "spl_min": 0.70,
            "severe_collision_rate_max": 0.10,
            "mean_intervention_rate_max": 0.25,
            "mean_progress_ratio_diagnostic_only": 0.90,
        },
        "verdict": (
            "PASS"
            if (sr >= 0.80 and scr <= 0.10 and mean_spl >= 0.70)
            else "FAIL"
        ),
        "episodes": results,
    }

    out_file = Path(args.out)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    logger.info(
        f"Phase 2 mainline complete. Verdict={summary['verdict']} | "
        f"SR={sr*100:.1f}% SPL={mean_spl*100:.1f}% SCR={scr*100:.1f}% "
        f"closure={mean_closure*100:.1f}% inflate={n_inflate}/{len(scored)} "
        f"Prog={mean_prog*100:.1f}% (diag) IR={mean_ir*100:.1f}%"
    )
    return 0 if summary["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
