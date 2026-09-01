#!/usr/bin/env python3
"""Phase-2 off-track hypothesis probes (H1/H2/H3) — short diagnostic only.

Not a mainline accept run. Default: R01/R03/R05 × 300 steps, step_e+meter.

Arms
----
* ``wam`` (default): AdaptiveSubgoal → π → Planner → ThreeZone (production stack)
* ``wam_nofreeze``: same but ``cte_lock_freeze_m`` huge (H3 C1: freeze does not pin s)
* ``tangent_subgoal``: H1 C1 — fixed 20 m polyline lookahead from true projection (π/planner unchanged)
* ``rejoin``: privileged rejoin controller toward true projection + tangent (Probe D upper bound)

Per-step log fields prove/falsify:
* H1: ``g_rel`` vs ``to_proj`` cos; CTE delta while ``g_align`` high
* H2: ``v_cmd`` / ``v_after`` / ``v_safe`` / measured step speed; ``d_fwd``
* H3: ``s_lock_frozen`` fraction vs ``s_true`` advance
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import yaml

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("wam_phase2_offtrack_probes")


def _goal_dist(pos: np.ndarray, goal: np.ndarray) -> float:
    return float(
        np.linalg.norm(
            np.asarray(goal, dtype=np.float64).reshape(3)
            - np.asarray(pos, dtype=np.float64).reshape(3)
        )
    )


def _unit2(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=np.float64).reshape(-1)[:2]
    n = float(np.linalg.norm(v))
    if n < 1e-9:
        return np.zeros(2, dtype=np.float64)
    return v / n


def _body_grel_from_target(
    curr_pos: np.ndarray, curr_yaw: float, target_world: np.ndarray
) -> np.ndarray:
    delta_w = np.asarray(target_world, dtype=np.float64).reshape(3) - np.asarray(
        curr_pos, dtype=np.float64
    ).reshape(3)
    c, s = math.cos(curr_yaw), math.sin(curr_yaw)
    dx_b = c * delta_w[0] + s * delta_w[1]
    dy_b = -s * delta_w[0] + c * delta_w[1]
    dz_b = delta_w[2]
    dist = float(np.linalg.norm(delta_w))
    return np.array([dx_b, dy_b, dz_b, dist], dtype=np.float32)


def _g_align_to_path(
    g_xy: np.ndarray,
    to_proj_b: np.ndarray,
    cte: float,
    path: np.ndarray,
    seg_idx: int,
    curr_yaw: float,
) -> float:
    """Cos(g_rel_xy, corridor direction). Uses path tangent when on-line (to_proj ~ 0)."""
    if float(cte) < 2.0 and len(path) > int(seg_idx) + 1:
        tang_w = np.asarray(path[int(seg_idx) + 1, :2] - path[int(seg_idx), :2], dtype=np.float64)
        c, s = math.cos(curr_yaw), math.sin(curr_yaw)
        tang_b = np.array(
            [c * tang_w[0] + s * tang_w[1], -s * tang_w[0] + c * tang_w[1]],
            dtype=np.float64,
        )
        ref = tang_b
    else:
        ref = to_proj_b
    return float(np.dot(_unit2(g_xy), _unit2(ref)))


def _rejoin_action(
    *,
    pos: np.ndarray,
    yaw: float,
    proj: np.ndarray,
    path: np.ndarray,
    seg_idx: int,
    limits: np.ndarray,
    cte: float,
) -> np.ndarray:
    """Body Δ toward projection + along-track (diagnostic only)."""
    path = np.asarray(path, dtype=np.float64)
    i = int(np.clip(seg_idx, 0, max(0, len(path) - 2)))
    tang = path[i + 1, :2] - path[i, :2]
    tang_u = _unit2(tang)
    to_proj = np.asarray(proj, dtype=np.float64).reshape(3) - np.asarray(pos, dtype=np.float64).reshape(3)
    # Blend: strong cross-track pull when CTE large; else cruise along tangent
    w_lat = float(np.clip(cte / 8.0, 0.35, 0.85))
    desired_xy = (1.0 - w_lat) * tang_u * 2.0 + w_lat * _unit2(to_proj[:2]) * min(cte, 4.0)
    desired = np.array([desired_xy[0], desired_xy[1], float(to_proj[2]) * 0.3], dtype=np.float64)
    c, s = math.cos(yaw), math.sin(yaw)
    dx_b = c * desired[0] + s * desired[1]
    dy_b = -s * desired[0] + c * desired[1]
    dz_b = desired[2]
    # yaw toward body-forward of desired
    yaw_err = math.atan2(dy_b, max(dx_b, 1e-3))
    act = np.array([dx_b, dy_b, dz_b, yaw_err], dtype=np.float64)
    return np.clip(act, -limits, limits)


def _summarize_steps(steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not steps:
        return {}
    cte = np.asarray([s["cte_m"] for s in steps], dtype=np.float64)
    s_true = np.asarray([s["s_true"] for s in steps], dtype=np.float64)
    g_align = np.asarray([s["g_align_to_proj"] for s in steps], dtype=np.float64)
    cos_ref = np.asarray([s["cos_heading_ref"] for s in steps], dtype=np.float64)
    v_cmd = np.asarray([s["v_cmd"] for s in steps], dtype=np.float64)
    v_after = np.asarray([s["v_after"] for s in steps], dtype=np.float64)
    v_safe = np.asarray([s["v_safe"] for s in steps], dtype=np.float64)
    v_meas = np.asarray([s["v_meas"] for s in steps], dtype=np.float64)
    frozen = np.asarray([s["s_lock_frozen"] for s in steps], dtype=np.float64)
    intervened = np.asarray([s["intervened"] for s in steps], dtype=np.float64)
    d_fwd = np.asarray([s["d_fwd"] for s in steps], dtype=np.float64)
    d_min_full = np.asarray([s.get("d_min_full", float("nan")) for s in steps], dtype=np.float64)
    d_hat_shield = np.asarray([s.get("d_hat_shield", float("nan")) for s in steps], dtype=np.float64)
    emerg = np.asarray([1.0 if s.get("shield_emergency") else 0.0 for s in steps], dtype=np.float64)
    gov = np.asarray([1.0 if s.get("shield_governor_cap") else 0.0 for s in steps], dtype=np.float64)

    n = len(steps)
    early = min(50, n)
    mid = min(100, n)

    # H1: among steps with high g_align, does CTE still rise?
    hi = g_align >= 0.7
    cte_rise_when_aligned = None
    if int(hi.sum()) >= 10:
        idx = np.where(hi)[0]
        # pair consecutive aligned steps
        rises = []
        for a, b in zip(idx[:-1], idx[1:]):
            if b == a + 1:
                rises.append(float(cte[b] - cte[a]))
        if rises:
            cte_rise_when_aligned = float(np.mean(rises))

    return {
        "n_steps": n,
        "cte0": round(float(cte[0]), 3),
        "cte50": round(float(cte[early - 1]), 3),
        "cte100": round(float(cte[mid - 1]), 3) if n >= 100 else None,
        "cte_end": round(float(cte[-1]), 3),
        "delta_cte_100": round(float(cte[mid - 1] - cte[0]), 3) if n >= 100 else round(float(cte[-1] - cte[0]), 3),
        "s_true_end": round(float(s_true[-1]), 3),
        "ds_true": round(float(s_true[-1] - s_true[0]), 3),
        "frac_frozen": round(float(frozen.mean()), 4),
        "frac_intervened": round(float(intervened.mean()), 4),
        "mean_g_align": round(float(g_align.mean()), 4),
        "mean_g_align_early50": round(float(g_align[:early].mean()), 4),
        "mean_cos_heading_ref_early30": round(float(cos_ref[: min(30, n)].mean()), 4),
        "cte_rise_per_step_when_g_align_ge_0.7": (
            None if cte_rise_when_aligned is None else round(cte_rise_when_aligned, 4)
        ),
        "mean_v_cmd": round(float(v_cmd.mean()), 4),
        "mean_v_after": round(float(v_after.mean()), 4),
        "mean_v_safe": round(float(v_safe.mean()), 4),
        "mean_v_meas": round(float(v_meas.mean()), 4),
        "frac_v_after_lt_1": round(float((v_after < 1.0).mean()), 4),
        "frac_v_safe_lt_1_and_dfwd_gt_8": round(
            float(((v_safe < 1.0) & np.isfinite(d_fwd) & (d_fwd > 8.0)).mean()), 4
        ),
        "mean_d_fwd": round(float(np.nanmean(d_fwd)), 3),
        "mean_d_min_full": round(float(np.nanmean(d_min_full)), 3),
        "mean_d_hat_shield": round(float(np.nanmean(d_hat_shield)), 3),
        "frac_emergency": round(float(emerg.mean()), 4),
        "frac_governor_cap": round(float(gov.mean()), 4),
    }


def _decide_hypotheses(arm: str, summary: Dict[str, Any]) -> Dict[str, str]:
    """Coarse auto-labels; STATUS still needs human read of plots/logs."""
    out = {"H1": "unresolved", "H2": "unresolved", "H3": "unresolved"}
    if not summary:
        return out
    rise = summary.get("cte_rise_per_step_when_g_align_ge_0.7")
    align = summary.get("mean_g_align_early50")
    if align is not None and align >= 0.5 and rise is not None:
        out["H1"] = "supported" if rise > 0.02 else "weakened"
    elif align is not None and align < 0.3:
        out["H1"] = "input_geometry_suspect"

    frac_slow = summary.get("frac_v_after_lt_1")
    frac_miscreep = summary.get("frac_v_safe_lt_1_and_dfwd_gt_8")
    if frac_miscreep is not None and frac_miscreep >= 0.3:
        out["H2"] = "supported"
    elif frac_slow is not None and frac_slow >= 0.5 and (summary.get("mean_v_cmd") or 0) >= 1.5:
        out["H2"] = "supported"
    elif frac_slow is not None and frac_slow < 0.2:
        out["H2"] = "weakened"

    if arm == "wam_nofreeze":
        out["H3"] = "see_vs_wam"
    elif summary.get("frac_frozen", 0) >= 0.4 and summary.get("ds_true", 1) < 5.0:
        out["H3"] = "supported"
    elif summary.get("frac_frozen", 1) < 0.1:
        out["H3"] = "weakened"
    return out


def main() -> int:
    p = argparse.ArgumentParser()
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
    p.add_argument("--routes", default="0,2,4", help="0-based route indices, comma-separated")
    p.add_argument(
        "--arms",
        default="wam,wam_nofreeze,rejoin",
        help="comma list: wam | wam_nofreeze | tangent_subgoal | rejoin",
    )
    p.add_argument("--cruise-speed", type=float, default=10.0)
    p.add_argument("--max-steps", type=int, default=300)
    p.add_argument("--step-hz", type=float, default=5.0)
    p.add_argument("--success-dist", type=float, default=3.0)
    p.add_argument("--planner-horizon", type=int, default=5)
    p.add_argument("--goal-feat-mode", choices=("meter", "g_norm"), default="meter")
    p.add_argument("--spawn-tol-m", type=float, default=12.0)
    p.add_argument(
        "--out-dir",
        default="artifacts/videos/wam_phase2_offtrack_probes_20260901",
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
    from experiments.aerial.rl.subgoal_generator import (
        AdaptiveSubgoalGenerator,
        nearest_on_polyline,
        sample_point_along_polyline,
    )
    from experiments.aerial.rl.train_rl import _build_env, _build_safety, load_torch_dynamics

    route_ids = [int(x) for x in str(args.routes).split(",") if x.strip() != ""]
    arms = [a.strip() for a in str(args.arms).split(",") if a.strip()]

    cfg = yaml.safe_load((root / args.config).read_text())
    device_str = "cuda" if torch.cuda.is_available() else "cpu"

    with open(root / args.annotation, "r", encoding="utf-8") as f:
        anno = json.load(f)
    routes = anno.get("routes", anno) if isinstance(anno, dict) else anno

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
    logger.info("goal_feat_mode=%s", actor_ac.config.goal_feat_mode)

    phys = body_delta_limits(1.0 / float(args.step_hz))
    reward_cfg = RewardConfig(**(cfg.get("reward") or {}))
    reward_cfg.success_dist_m = float(args.success_dist)
    planner = ImaginationPlanner(
        dynamics=dynamics,
        horizon=int(args.planner_horizon),
        reward_cfg=reward_cfg,
        action_limits=phys,
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

    out_dir = root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    report_rows: List[Dict[str, Any]] = []

    for arm in arms:
        for ep_idx in route_ids:
            if ep_idx < 0 or ep_idx >= len(routes):
                logger.error("skip bad route_idx=%s", ep_idx)
                continue
            r_info = routes[ep_idx]
            pts = np.array(r_info.get("pos", r_info.get("positions")), dtype=np.float64)
            yaws = np.array(r_info.get("yaw", [0.0] * len(pts)), dtype=np.float64)
            goal_pos = pts[-1].copy()
            start_pos = pts[0].copy()
            start_yaw = float(yaws[0]) if len(yaws) else 0.0
            ref_tang0 = _unit2(pts[min(5, len(pts) - 1), :2] - pts[0, :2])

            freeze_m = 5.0 if arm == "wam" else 1.0e9
            subgoal_gen = AdaptiveSubgoalGenerator(
                cruise_speed=float(args.cruise_speed),
                cte_lock_freeze_m=float(freeze_m),
            )
            if shield is not None and hasattr(shield, "reset"):
                shield.reset()
            if depth_pred is not None and hasattr(depth_pred, "reset"):
                depth_pred.reset()
            policy.reset()

            ep_dict = {
                "pos": pts.tolist(),
                "yaw": yaws.tolist() if len(yaws) == len(pts) else [start_yaw] * len(pts),
                "gpt_instruction": r_info.get("gpt_instruction", ""),
            }
            obs = env.reset(ep_dict)
            p_curr = np.array(obs.position, dtype=np.float64)
            curr_yaw = float(obs.yaw) if hasattr(obs, "yaw") else start_yaw
            spawn_err = float(np.linalg.norm(p_curr - start_pos))
            if spawn_err > float(args.spawn_tol_m):
                bump = start_pos.copy()
                bump[2] = float(bump[2]) + 2.0
                ep_retry = dict(ep_dict)
                pts_r = np.asarray(ep_retry["pos"], dtype=np.float64).copy()
                pts_r[0] = bump
                ep_retry["pos"] = pts_r.tolist()
                obs = env.reset(ep_retry)
                p_curr = np.array(obs.position, dtype=np.float64)
                curr_yaw = float(obs.yaw) if hasattr(obs, "yaw") else curr_yaw
                spawn_err = float(np.linalg.norm(p_curr - bump))

            label = f"R{ep_idx+1:02d}_{arm}"
            if spawn_err > float(args.spawn_tol_m):
                row = {
                    "label": label,
                    "route_idx": ep_idx,
                    "arm": arm,
                    "fail": "F1_SPAWN",
                    "spawn_err_m": spawn_err,
                }
                report_rows.append(row)
                logger.error("%s spawn_fail err=%.1f", label, spawn_err)
                continue

            step_rows: List[Dict[str, Any]] = []
            for step in range(int(args.max_steps)):
                d_fwd = float("nan")
                if depth_pred is not None and obs.rgb is not None:
                    pred_both = getattr(depth_pred, "predict_min_and_cones", None)
                    if callable(pred_both):
                        d_min_pred, cones = pred_both(obs)
                        if d_min_pred is not None:
                            obs.info["depth_min_pred"] = float(d_min_pred)
                        if isinstance(cones, dict):
                            obs.info["depth_cones_pred"] = {
                                k: (float(v) if v is not None else None)
                                for k, v in cones.items()
                            }
                            if cones.get("forward") is not None and np.isfinite(
                                float(cones["forward"])
                            ):
                                d_fwd = float(cones["forward"])
                    else:
                        dm = depth_pred.predict_min(obs)
                        if dm is not None:
                            d_fwd = float(dm)
                            obs.info["depth_min_pred"] = float(dm)

                true_proj, true_seg, true_s, _rem = nearest_on_polyline(p_curr, pts)
                g_rel_body, s_info = subgoal_gen.compute_subgoal(
                    curr_pos=p_curr,
                    curr_yaw=curr_yaw,
                    global_path=pts,
                    d_fwd_hat=None if not np.isfinite(d_fwd) else float(d_fwd),
                )
                target_world = np.array(s_info["target_world"], dtype=np.float64)
                if arm == "tangent_subgoal":
                    target_world = sample_point_along_polyline(
                        pts,
                        segment_idx=int(true_seg),
                        proj_point=true_proj,
                        r_lookahead=20.0,
                    )
                    g_rel_body = _body_grel_from_target(p_curr, curr_yaw, target_world)
                cte = float(s_info.get("cte_m", 0.0))
                safe_v = float(s_info.get("safe_speed_limit", args.cruise_speed))
                frozen = bool(s_info.get("s_lock_frozen", False))

                to_proj_w = true_proj - p_curr
                c, s = math.cos(curr_yaw), math.sin(curr_yaw)
                to_proj_b = np.array(
                    [
                        c * to_proj_w[0] + s * to_proj_w[1],
                        -s * to_proj_w[0] + c * to_proj_w[1],
                    ],
                    dtype=np.float64,
                )
                g_xy = np.asarray(g_rel_body[:2], dtype=np.float64)
                g_align = _g_align_to_path(
                    g_xy, to_proj_b, cte, pts, int(true_seg), curr_yaw
                )
                heading_xy = np.array([math.cos(curr_yaw), math.sin(curr_yaw)], dtype=np.float64)
                cos_heading_ref = float(np.dot(heading_xy, ref_tang0))

                phys_now = body_delta_limits(1.0 / float(args.step_hz))
                cur_limits = np.array(
                    [
                        float(min(safe_v / float(args.step_hz), float(phys_now[0]))),
                        float(phys_now[1]),
                        float(phys_now[2]),
                        float(phys_now[3]),
                    ],
                    dtype=np.float64,
                )
                planner.action_limits = cur_limits

                d_to_goal = _goal_dist(p_curr, goal_pos)
                if float(s_info["rem_dist"]) <= float(args.success_dist) and d_to_goal <= float(
                    args.success_dist
                ):
                    break

                obs.info["goal"] = target_world.tolist()
                obs.info["goal_rel"] = g_rel_body.tolist()
                planner.set_goal(target_world)

                if arm == "rejoin":
                    action = _rejoin_action(
                        pos=p_curr,
                        yaw=curr_yaw,
                        proj=true_proj,
                        path=pts,
                        seg_idx=int(true_seg),
                        limits=cur_limits,
                        cte=cte,
                    )
                    v_cmd = float(np.linalg.norm(action[:3]) * float(args.step_hz))
                else:
                    action = policy.act(obs)
                    action = planner.plan(obs, action, latent=policy._latent)
                    action = clip_body_delta(action, cur_limits)
                    v_cmd = float(np.linalg.norm(action[:3]) * float(args.step_hz))

                wm_out = None
                if arm != "rejoin" and policy._latent is not None and hasattr(dynamics, "step"):
                    try:
                        wm_out = dynamics.step(
                            policy._latent,
                            action,
                            goal_rel=g_rel_body,
                            body_vel=body_vel_from_obs(obs),
                        )
                    except Exception:
                        wm_out = None

                intervened = False
                if shield is not None:
                    action2, overridden = shield.apply_action(
                        action, obs, wm_out=wm_out, limits=cur_limits
                    )
                    intervened = bool(overridden)
                    action = action2
                v_after = float(np.linalg.norm(np.asarray(action, dtype=np.float64)[:3]) * float(args.step_hz))
                d_min_full = obs.info.get("depth_min_pred")
                d_hat_shield = obs.info.get("three_zone_d_hat_fwd_m")
                shield_ch = list(obs.info.get("shield_channels") or [])
                emerg = bool(obs.info.get("shield_emergency_override", False))
                gov = bool(obs.info.get("shield_governor_cap", False))

                p_before = p_curr.copy()
                step_out = env.step(action)
                if len(step_out) == 4:
                    obs, _rew, done, step_info = step_out
                else:
                    obs, step_info = step_out
                    done = bool(getattr(obs, "collided", False))
                p_curr = np.array(obs.position, dtype=np.float64)
                curr_yaw = float(obs.yaw) if hasattr(obs, "yaw") else curr_yaw
                v_meas = float(np.linalg.norm((p_curr - p_before)[:2]) * float(args.step_hz))

                step_rows.append(
                    {
                        "step": step,
                        "cte_m": cte,
                        "s_true": float(s_info["s_true"]),
                        "s_progress": float(s_info["s_progress"]),
                        "s_lock_frozen": frozen,
                        "r_lookahead": float(s_info.get("r_lookahead", 0.0)),
                        "v_safe": safe_v,
                        "v_cmd": v_cmd,
                        "v_after": v_after,
                        "v_meas": v_meas,
                        "d_fwd": d_fwd,
                        "d_goal": d_to_goal,
                        "intervened": intervened,
                        "shield_channels": shield_ch,
                        "shield_emergency": emerg,
                        "shield_governor_cap": gov,
                        "d_min_full": (
                            float(d_min_full)
                            if d_min_full is not None and np.isfinite(float(d_min_full))
                            else float("nan")
                        ),
                        "d_hat_shield": (
                            float(d_hat_shield)
                            if d_hat_shield is not None and np.isfinite(float(d_hat_shield))
                            else float("nan")
                        ),
                        "g_align_to_proj": g_align,
                        "cos_heading_ref": cos_heading_ref,
                        "g_rel": [float(x) for x in np.asarray(g_rel_body).tolist()],
                    }
                )
                if done or bool(getattr(obs, "collided", False)) or bool(
                    step_info.get("collided", False) if isinstance(step_info, dict) else False
                ):
                    break

            summary = _summarize_steps(step_rows)
            hyp = _decide_hypotheses(arm, summary)
            out_json = out_dir / f"{label}_steps.json"
            payload = {
                "label": label,
                "route_idx": ep_idx,
                "arm": arm,
                "cte_lock_freeze_m": freeze_m,
                "max_steps": int(args.max_steps),
                "summary": summary,
                "hypotheses": hyp,
                "steps": step_rows,
            }
            out_json.write_text(json.dumps(payload), encoding="utf-8")
            row = {
                "label": label,
                "route_idx": ep_idx,
                "arm": arm,
                "summary": summary,
                "hypotheses": hyp,
                "steps_path": str(out_json.relative_to(root)),
            }
            report_rows.append(row)
            logger.info(
                "%s done cte0→end=%s→%s ds=%s frac_frozen=%s mean_v_meas=%s H1=%s H2=%s H3=%s",
                label,
                summary.get("cte0"),
                summary.get("cte_end"),
                summary.get("ds_true"),
                summary.get("frac_frozen"),
                summary.get("mean_v_meas"),
                hyp.get("H1"),
                hyp.get("H2"),
                hyp.get("H3"),
            )

    summary_path = out_dir / "PROBE_SUMMARY.json"
    summary_path.write_text(
        json.dumps(
            {
                "protocol": "offtrack_probes_H1H2H3",
                "routes": route_ids,
                "arms": arms,
                "max_steps": int(args.max_steps),
                "rows": report_rows,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    # short markdown
    lines = [
        "# Phase-2 off-track probes (H1/H2/H3)",
        "",
        f"routes={route_ids} arms={arms} max_steps={args.max_steps}",
        "",
        "| label | H1 | H2 | H3 | ΔCTE@100 | ds_true | frac_frozen | mean_v_meas | mean_g_align_e50 |",
        "|-------|----|----|----|----------|---------|-------------|-------------|------------------|",
    ]
    for r in report_rows:
        s = r.get("summary") or {}
        h = r.get("hypotheses") or {}
        lines.append(
            "| {lab} | {h1} | {h2} | {h3} | {dc} | {ds} | {ff} | {vm} | {ga} |".format(
                lab=r.get("label"),
                h1=h.get("H1"),
                h2=h.get("H2"),
                h3=h.get("H3"),
                dc=s.get("delta_cte_100"),
                ds=s.get("ds_true"),
                ff=s.get("frac_frozen"),
                vm=s.get("mean_v_meas"),
                ga=s.get("mean_g_align_early50"),
            )
        )
    lines.extend(
        [
            "",
            "Read:",
            "- H1 supported ≈ g_rel aligned to proj but CTE still rises",
            "- H1 ablation: compare `wam` vs `tangent_subgoal` ds_true / cte_end per route",
            "- H2 supported ≈ slow v_after / mis-creep with open d_fwd",
            "- H3: compare `wam` vs `wam_nofreeze` ds_true / CTE",
            "- `rejoin` is Probe D upper bound (not mainline)",
            "",
        ]
    )
    by_route: Dict[int, Dict[str, Dict[str, Any]]] = {}
    for r in report_rows:
        idx = int(r.get("route_idx", -1))
        arm = str(r.get("arm", ""))
        by_route.setdefault(idx, {})[arm] = r.get("summary") or {}
    if "tangent_subgoal" in arms and "wam" in arms:
        lines.append("## H1 ablation (wam vs tangent_subgoal)")
        lines.append("")
        lines.append("| route | wam ds | tang ds | wam cte_end | tang cte_end | wam g_align_e50 | tang g_align_e50 | H1 |")
        lines.append("|-------|--------|---------|-------------|--------------|-----------------|------------------|-----|")
        for idx in sorted(by_route):
            w = by_route[idx].get("wam") or {}
            t = by_route[idx].get("tangent_subgoal") or {}
            if not w or not t:
                continue
            ds_w, ds_t = float(w.get("ds_true") or 0), float(t.get("ds_true") or 0)
            ce_w, ce_t = float(w.get("cte_end") or 0), float(t.get("cte_end") or 0)
            ga_w, ga_t = w.get("mean_g_align_early50"), t.get("mean_g_align_early50")
            if ds_t > ds_w + 5.0 and ce_t + 3.0 < ce_w:
                h1v = "supported"
            elif ds_t > ds_w + 2.0 or ce_t + 1.5 < ce_w:
                h1v = "weak_support"
            else:
                h1v = "weakened"
            lines.append(
                f"| R{idx+1:02d} | {ds_w:.1f} | {ds_t:.1f} | {ce_w:.1f} | {ce_t:.1f} | "
                f"{ga_w} | {ga_t} | {h1v} |"
            )
        lines.append("")
    lines.append(f"JSON: `{summary_path}`")
    md_path = out_dir / "PROBE_REPORT.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Wrote %s and %s", summary_path, md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
