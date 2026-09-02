#!/usr/bin/env python3
"""Phase-2 per-route trajectory forensics (16 long routes).

Honest geometry audit — not aggregate Prog cosplay:
  * XY flown vs ref polyline
  * d_min / d_final / max CTE / early off-track
  * monotone-lock inflation (prog high while d_goal large)
  * fail tags per route + summary markdown

Stack matches ``wam_phase2_long_eval`` (step_e + meter + subgoal + planner + ThreeZone).
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import yaml

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("wam_phase2_forensics")


def _goal_dist(pos: np.ndarray, goal: np.ndarray) -> float:
    return float(
        np.linalg.norm(
            np.asarray(goal, dtype=np.float64).reshape(3)
            - np.asarray(pos, dtype=np.float64).reshape(3)
        )
    )


def _write_traj_plot(
    ref_pts: np.ndarray,
    flown: np.ndarray,
    out_png: Path,
    *,
    title: str,
    tag: str,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ref = np.asarray(ref_pts, dtype=np.float64).reshape(-1, 3)
    fly = np.asarray(flown, dtype=np.float64).reshape(-1, 3)
    fig, ax = plt.subplots(figsize=(7.5, 7.5), dpi=120)
    ax.plot(ref[:, 0], ref[:, 1], "k--", lw=1.5, label="ref", zorder=2)
    if len(fly) > 1:
        ax.plot(fly[:, 0], fly[:, 1], color="#1f77b4", lw=1.6, label="flown", zorder=3)
        ax.scatter(fly[-1, 0], fly[-1, 1], c="#ff7f0e", s=36, zorder=4, label="final")
    ax.scatter(ref[0, 0], ref[0, 1], c="#2ca02c", s=50, zorder=4, label="start")
    ax.scatter(ref[-1, 0], ref[-1, 1], c="#d62728", s=70, marker="*", zorder=4, label="goal")
    ax.set_aspect("equal", adjustable="datalim")
    ax.grid(True, alpha=0.3)
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_title(title, fontsize=10)
    ax.text(
        0.02,
        0.98,
        tag,
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=9,
        color="#a00000",
        bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#a00000", alpha=0.85),
    )
    ax.legend(loc="best", fontsize=7)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)


def _classify(
    *,
    spawn_fail: bool,
    severe: bool,
    arrived: bool,
    prog: float,
    d_min: float,
    d_final: float,
    max_cte: float,
    early_cte: float,
    success_dist: float,
    early_cte_thr: float,
    offtrack_cte_thr: float,
) -> str:
    if spawn_fail:
        return "F1_SPAWN"
    if severe:
        return "F_SCR"
    if arrived:
        return "OK_ARRIVED"
    if early_cte >= early_cte_thr:
        return "F_OFFTRACK_EARLY"
    if max_cte >= offtrack_cte_thr and prog >= 0.85 and d_min > 20.0:
        return "F_MONOTONE_INFLATE"
    if prog >= 0.85 and d_min > success_dist * 5:
        return "F_TERMINAL_GAP"
    if max_cte >= offtrack_cte_thr:
        return "F_OFFTRACK"
    if d_final > success_dist:
        return "F_NO_ARRIVAL"
    return "F_OTHER"


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
    p.add_argument("--episodes", type=int, default=16)
    p.add_argument(
        "--route-indices",
        default="",
        help="Comma-separated 0-based route indices (overrides --episodes when set).",
    )
    p.add_argument("--cruise-speed", type=float, default=10.0)
    p.add_argument("--max-steps", type=int, default=1000)
    p.add_argument("--step-hz", type=float, default=5.0)
    p.add_argument("--success-dist", type=float, default=3.0)
    p.add_argument("--planner-horizon", type=int, default=5)
    p.add_argument("--goal-feat-mode", choices=("meter", "g_norm"), default="meter")
    p.add_argument("--spawn-tol-m", type=float, default=12.0)
    p.add_argument("--early-steps", type=int, default=50)
    p.add_argument("--early-cte-thr", type=float, default=15.0)
    p.add_argument("--offtrack-cte-thr", type=float, default=25.0)
    p.add_argument(
        "--heading-assist",
        action="store_true",
        default=False,
        help="F7 fuse: path-tangent dyaw (OFF by default; mainline forensics must not rely on this)",
    )
    p.add_argument(
        "--out-dir",
        default="artifacts/videos/wam_phase2_reanchor_forensics_20260830",
    )
    args = p.parse_args()

    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    import torch
    from experiments.aerial.rl.actor_critic import LatentActorCritic, LatentActorDeployPolicy
    from experiments.aerial.rl.depth_predictor import DepthMinPredictor
    from experiments.aerial.rl.env.action import body_delta_limits, clip_body_delta
    from experiments.aerial.rl.path_heading_assist import apply_path_heading_assist
    from experiments.aerial.rl.goal_features import body_vel_from_obs
    from experiments.aerial.rl.planner import ImaginationPlanner
    from experiments.aerial.rl.reward import RewardConfig
    from experiments.aerial.rl.subgoal_generator import (
        AdaptiveSubgoalGenerator,
        project_to_polyline,
    )
    from experiments.aerial.rl.train_rl import _build_env, _build_safety, load_torch_dynamics

    cfg = yaml.safe_load((root / args.config).read_text())
    device_str = "cuda" if torch.cuda.is_available() else "cpu"

    with open(root / args.annotation, "r", encoding="utf-8") as f:
        anno = json.load(f)
    routes = anno.get("routes", anno) if isinstance(anno, dict) else anno
    if str(args.route_indices).strip():
        route_indices = [int(x) for x in str(args.route_indices).split(",") if str(x).strip() != ""]
        for i in route_indices:
            if i < 0 or i >= len(routes):
                raise SystemExit(f"--route-indices out of range: {i} (n_routes={len(routes)})")
    else:
        route_indices = list(range(min(int(args.episodes), len(routes))))

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

    out_dir = root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: List[Dict[str, Any]] = []

    for ep_idx in route_indices:
        r_info = routes[ep_idx]
        pts = np.array(r_info.get("pos", r_info.get("positions")), dtype=np.float64)
        yaws = np.array(r_info.get("yaw", [0.0] * len(pts)), dtype=np.float64)
        goal_pos = pts[-1].copy()
        start_pos = pts[0].copy()
        start_yaw = float(yaws[0]) if len(yaws) else 0.0
        ref_len = float(np.sum(np.linalg.norm(pts[1:] - pts[:-1], axis=1)))

        subgoal_gen.reset()
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

        if spawn_err > float(args.spawn_tol_m):
            row = {
                "route_idx": ep_idx,
                "route_label": f"R{ep_idx+1:02d}",
                "fail_tag": "F1_SPAWN",
                "spawn_fail": True,
                "spawn_err_m": round(spawn_err, 2),
                "arrived": False,
                "progress_ratio": 0.0,
                "d_min_m": None,
                "d_final_m": None,
                "max_cte_m": None,
                "early_cte_m": None,
                "steps": 0,
            }
            rows.append(row)
            logger.error("R%02d F1 spawn_fail err=%.1f", ep_idx + 1, spawn_err)
            continue

        d0 = _goal_dist(p_curr, goal_pos)
        min_d = d0
        traj = [p_curr.copy()]
        ctes: List[float] = []
        rem_hist: List[float] = []
        d_hist: List[float] = []
        s_locked_hist: List[float] = []
        s_true_hist: List[float] = []
        arrived = False
        severe = False
        collided = False
        interventions = 0
        s_prog = 0.0

        for step in range(int(args.max_steps)):
            d_fwd = None
            if depth_pred is not None and obs.rgb is not None:
                pred_both = getattr(depth_pred, "predict_min_and_cones", None)
                if callable(pred_both):
                    d_min_pred, cones = pred_both(obs)
                    if d_min_pred is not None:
                        obs.info["depth_min_pred"] = float(d_min_pred)
                    if isinstance(cones, dict):
                        # Must match collector / long_eval: shield reads cones via
                        # _forward_d_hat; without this it falls back to full-frame
                        # min and L3-brakes every step in open air.
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

            # unlocked projection for forensics
            _proj, _seg, s_true, rem_true = project_to_polyline(
                p_curr, pts, prev_s_max=0.0
            )
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
            ctes.append(cte)
            rem_hist.append(rem_dist)
            s_locked_hist.append(s_prog)
            s_true_hist.append(float(s_true))

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
            min_d = min(min_d, d_to_goal)
            d_hist.append(d_to_goal)

            if rem_dist <= float(args.success_dist) and d_to_goal <= float(args.success_dist):
                arrived = True
                break

            obs.info["goal"] = target_world.tolist()
            obs.info["goal_rel"] = g_rel_body.tolist()
            planner.set_goal(target_world)
            action = policy.act(obs)
            action = planner.plan(obs, action, latent=policy._latent)
            action = clip_body_delta(action, cur_limits)
            if bool(args.heading_assist):
                action, _ha, _ = apply_path_heading_assist(
                    action,
                    yaw=curr_yaw,
                    path=pts,
                    seg_idx=int(s_info.get("seg_idx", 0)),
                    cte_m=float(cte),
                    limits=cur_limits,
                )
                if _ha:
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
                collided = bool(
                    getattr(obs, "collided", False) or step_info.get("collided", False)
                )
                severe = bool(step_info.get("severe_collision", False) or collided)
                break

        flown = np.asarray(traj, dtype=np.float64)
        prog = float(np.clip(s_prog / max(1e-3, ref_len), 0.0, 1.0))
        d_final = _goal_dist(p_curr, goal_pos)
        max_cte = float(max(ctes)) if ctes else 0.0
        early_n = min(int(args.early_steps), len(ctes))
        early_cte = float(max(ctes[:early_n])) if early_n else 0.0
        # monotone inflation: locked s ahead of true projection
        lock_gap = 0.0
        if s_locked_hist and s_true_hist:
            lock_gap = float(max(np.asarray(s_locked_hist) - np.asarray(s_true_hist)))

        tag = _classify(
            spawn_fail=False,
            severe=severe,
            arrived=arrived,
            prog=prog,
            d_min=min_d,
            d_final=d_final,
            max_cte=max_cte,
            early_cte=early_cte,
            success_dist=float(args.success_dist),
            early_cte_thr=float(args.early_cte_thr),
            offtrack_cte_thr=float(args.offtrack_cte_thr),
        )

        label = f"R{ep_idx+1:02d}"
        png = out_dir / f"{label}_traj_xy.png"
        _write_traj_plot(
            pts,
            flown,
            png,
            title=(
                f"{label}  prog={prog*100:.0f}%  d_min={min_d:.1f}  "
                f"d_fin={d_final:.1f}  maxCTE={max_cte:.1f}  earlyCTE={early_cte:.1f}"
            ),
            tag=tag,
        )
        (out_dir / f"{label}_traj.json").write_text(
            json.dumps(
                {
                    "route_idx": ep_idx,
                    "fail_tag": tag,
                    "ref_polyline": pts.tolist(),
                    "flown": flown.tolist(),
                    "cte": ctes,
                    "rem_locked": rem_hist,
                    "d_goal": d_hist,
                    "s_locked": s_locked_hist,
                    "s_true": s_true_hist,
                }
            ),
            encoding="utf-8",
        )

        row = {
            "route_idx": ep_idx,
            "route_label": label,
            "fail_tag": tag,
            "spawn_fail": False,
            "spawn_err_m": round(spawn_err, 2),
            "arrived": arrived,
            "collided": collided,
            "severe_collision": severe,
            "progress_ratio": round(prog, 4),
            "d0_m": round(d0, 2),
            "d_min_m": round(min_d, 2),
            "d_final_m": round(d_final, 2),
            "max_cte_m": round(max_cte, 2),
            "early_cte_m": round(early_cte, 2),
            "lock_gap_max_m": round(lock_gap, 2),
            "L_ref_m": round(ref_len, 2),
            "L_act_m": round(
                float(np.sum(np.linalg.norm(np.diff(flown, axis=0), axis=1)))
                if len(flown) > 1
                else 0.0,
                2,
            ),
            "steps": len(flown),
            "intervention_rate": round(interventions / max(1, len(flown)), 4),
            "plot": str(png.relative_to(root)),
        }
        rows.append(row)
        logger.info(
            "%s tag=%s prog=%.2f d_min=%.1f d_fin=%.1f maxCTE=%.1f earlyCTE=%.1f lock_gap=%.1f",
            label,
            tag,
            prog,
            min_d,
            d_final,
            max_cte,
            early_cte,
            lock_gap,
        )

    # aggregates
    tag_counts: Dict[str, int] = {}
    for r in rows:
        tag_counts[r["fail_tag"]] = tag_counts.get(r["fail_tag"], 0) + 1

    summary = {
        "protocol": "step_e+meter+subgoal+planner+three_zone",
        "n_routes": len(rows),
        "tag_counts": tag_counts,
        "early_cte_thr_m": float(args.early_cte_thr),
        "offtrack_cte_thr_m": float(args.offtrack_cte_thr),
        "early_steps": int(args.early_steps),
        "routes": rows,
    }
    (out_dir / "forensics_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    # markdown report
    lines = [
        "# Phase-2 回锚 16 路航迹法医（2026-08-30）",
        "",
        "> 协议：`step_e` + `goal_feat_mode=meter` + AdaptiveSubgoal + planner H=5 + ThreeZone · cruise=10",
        "",
        "## 标签计数",
        "",
        "| tag | n |",
        "|-----|---|",
    ]
    for k, v in sorted(tag_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"| `{k}` | {v} |")
    lines += [
        "",
        "## 逐路",
        "",
        "| 路 | tag | prog | d_min | d_final | maxCTE | earlyCTE | lock_gap | IR | plot |",
        "|----|-----|------|-------|---------|--------|----------|----------|----|------|",
    ]
    for r in rows:
        lines.append(
            "| {lab} | `{tag}` | {prog:.0%} | {dmin} | {dfin} | {mcte} | {ecte} | {lg} | {ir:.2f} | `{plot}` |".format(
                lab=r["route_label"],
                tag=r["fail_tag"],
                prog=float(r.get("progress_ratio") or 0.0),
                dmin=r.get("d_min_m"),
                dfin=r.get("d_final_m"),
                mcte=r.get("max_cte_m"),
                ecte=r.get("early_cte_m"),
                lg=r.get("lock_gap_max_m"),
                ir=float(r.get("intervention_rate") or 0.0),
                plot=Path(r.get("plot") or "").name,
            )
        )
    lines += [
        "",
        "## 读数",
        "",
        "- `F_OFFTRACK_EARLY`：前 "
        f"{args.early_steps} 步 CTE≥{args.early_cte_thr}m → **方向性失败**，汇总 Prog 无意义。",
        "- `F_MONOTONE_INFLATE`：高 Prog + 大 CTE/`d_min` → **单调锁虚高进度**。",
        "- `F_TERMINAL_GAP`：走廊进度高但从未进到达邻域。",
        "- `F_SCR`：严重碰撞。",
        "",
        f"产物目录：`{args.out_dir}`",
        "",
    ]
    md_path = out_dir / "FORENSICS_REPORT.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    # also drop a copy under docs/handover for living-doc discipline
    handover = root / "docs" / "handover" / "WAM_PHASE2_REANCHOR_TRAJ_FORENSICS_20260830.md"
    handover.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Wrote %s and %s", md_path, handover)
    logger.info("TAG_COUNTS %s", json.dumps(tag_counts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
