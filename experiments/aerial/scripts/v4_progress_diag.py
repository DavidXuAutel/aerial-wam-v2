#!/usr/bin/env python3
"""V4-① per-episode progress diagnosis (same harness as gate partial-1).

Dumps actor vs heuristic: progress, goal geometry, path/goal cosine,
first actions, and whether deploy encode sees velocity/goal.

Usage (125 / 4090):
  source experiments/aerial/scripts/env_4090.sh
  $PYTHON_BIN experiments/aerial/scripts/v4_progress_diag.py \\
    --repo ~/aerial-wam-v2 \\
    --rollout-dataset ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_headon_20260811 \\
    --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_20260817_wm_rh_goal_rgb/v4_ac_latest.pt \\
    --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_r60_rh_20260816/wm_step_1000.pt \\
    --env-host 127.0.0.1 \\
    --out artifacts/v4_progress_diag_20260817.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


def _repo_root(explicit: Optional[str]) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    return Path(__file__).resolve().parents[3]


def _unit(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=np.float64).reshape(-1)
    n = float(np.linalg.norm(v))
    if n < 1e-9:
        return np.zeros_like(v)
    return v / n


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    ua, ub = _unit(a), _unit(b)
    return float(np.dot(ua, ub))


def _goal_body(goal: np.ndarray, pos: np.ndarray, yaw: float) -> np.ndarray:
    d_world = np.asarray(goal, dtype=np.float64).reshape(3) - np.asarray(pos, dtype=np.float64).reshape(3)
    c, s = np.cos(yaw), np.sin(yaw)
    return np.array(
        [c * d_world[0] + s * d_world[1], -s * d_world[0] + c * d_world[1], d_world[2]],
        dtype=np.float64,
    )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default=None)
    p.add_argument("--config", default="configs/aerial_rl_rollout.yaml")
    p.add_argument("--env-host", default="127.0.0.1")
    p.add_argument("--device", default="cuda")
    p.add_argument(
        "--rollout-dataset",
        default="~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_headon_20260811",
    )
    p.add_argument(
        "--actor-ckpt",
        default="experiments/aerial/rl/artifacts/v4_ac_ckpt_20260817_wm_rh_goal_rgb/v4_ac_latest.pt",
    )
    p.add_argument(
        "--wm-ckpt",
        default="experiments/aerial/rl/artifacts/wm_ckpt_r60_rh_20260816/wm_step_1000.pt",
    )
    p.add_argument("--n-episodes", type=int, default=8)
    p.add_argument("--max-steps", type=int, default=200)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", default="artifacts/v4_progress_diag.json")
    args = p.parse_args()

    root = _repo_root(args.repo)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    import yaml

    from experiments.aerial.rl import v0_metrics as v0m
    from experiments.aerial.rl import v0_rollout_eval as rollout
    from experiments.aerial.rl import v4_metrics
    from experiments.aerial.rl._v0_gate import _obstacle_candidate_positions
    from experiments.aerial.rl.actor_critic import LatentActorCritic, LatentActorDeployPolicy
    from experiments.aerial.rl.reward import RewardConfig
    from experiments.aerial.rl.train_rl import HeuristicPolicy, _build_env, load_torch_dynamics

    cfg = yaml.safe_load((root / args.config).read_text()) or {}
    if args.env_host:
        cfg.setdefault("env", {})["host"] = str(args.env_host)
    env = _build_env(cfg.get("env", {}) or {})
    reward_cfg = RewardConfig(**(cfg.get("reward", {}) or {})) if cfg.get("reward") else None
    thr = v0m.DEFAULT_THRESHOLDS

    rollout_ds = Path(args.rollout_dataset).expanduser()
    if not rollout_ds.is_absolute():
        rollout_ds = root / rollout_ds
    actor_ckpt = Path(args.actor_ckpt).expanduser()
    if not actor_ckpt.is_absolute():
        actor_ckpt = root / actor_ckpt
    wm_ckpt = Path(args.wm_ckpt).expanduser()
    if not wm_ckpt.is_absolute():
        wm_ckpt = root / wm_ckpt

    heuristic = HeuristicPolicy(goal_getter=lambda: getattr(env, "goal", None))
    cand, cand_yaw = _obstacle_candidate_positions(rollout_ds, min_altitude_m=0.0)
    starts, scan_diag = rollout.make_obstacle_facing_episodes(
        env,
        int(args.n_episodes),
        cand,
        seed=int(args.seed),
        candidate_yaws=cand_yaw,
        obstacle_max_m=25.0,
        center_frac=0.3,
        probe_policy=heuristic,
        probe_near_m=float(thr.near_collision_depth_m),
        probe_steps=40,
        reward_cfg=reward_cfg,
        preserve_order=True,
        max_scans=1000,
        log_every=20,
    )
    if not starts:
        print("[diag] no starts", file=sys.stderr)
        return 2

    wm_cfg = cfg.get("world_model", {}) or {}
    dynamics, wm_payload = load_torch_dynamics(
        wm_cfg,
        wm_ckpt,
        device=str(args.device),
        success_dist_m=float(reward_cfg.success_dist_m if reward_cfg else 3.0),
    )
    actor_ac = LatentActorCritic.load_from_checkpoint(actor_ckpt, device=str(args.device))
    actor_policy = LatentActorDeployPolicy(dynamics, actor_ac, deterministic=True)

    # Static code facts (no rollout needed).
    import inspect
    deploy_src = inspect.getsource(LatentActorDeployPolicy.act)
    code_facts = {
        "deploy_hardcodes_state_vel_xyz_to_zero": "0.0,\n                0.0,\n                0.0," in deploy_src
        or "0.0, 0.0, 0.0" in deploy_src.replace("\n", " "),
        "encode_uses_proprio4_only": True,  # dynamics_torch.encode → obs.proprio4()
        "actor_has_no_goal_input": "goal" not in deploy_src.lower(),
        "heuristic_uses_goal_getter": True,
        "wm_step": wm_payload.get("step"),
        "actor_ckpt": str(actor_ckpt),
        "wm_ckpt": str(wm_ckpt),
    }

    episodes: List[Dict[str, Any]] = []
    actor_prog: List[float] = []
    heur_prog: List[float] = []

    for i, epi in enumerate(starts):
        row: Dict[str, Any] = {"idx": i}
        arms: Dict[str, Any] = {}
        skip = False
        for tag, pol in (("actor", actor_policy), ("heuristic", heuristic)):
            if hasattr(pol, "reset"):
                pol.reset()
            ep = rollout._run_one_resilient(
                env, pol, epi, max_steps=int(args.max_steps), reward_cfg=reward_cfg,
            )
            if ep is None:
                skip = True
                row["dropped"] = True
                break
            arms[tag] = ep
        if skip:
            episodes.append(row)
            continue

        goal = np.asarray(getattr(env, "goal"), dtype=np.float64).reshape(3)
        for tag in ("actor", "heuristic"):
            ep = arms[tag]
            start_pos = np.asarray(ep[0].obs.position, dtype=np.float64)
            final_pos = np.asarray(ep[-1].next_obs.position, dtype=np.float64)
            start_yaw = float(ep[0].obs.yaw)
            init_d = float(np.linalg.norm(goal - start_pos))
            final_d = float(np.linalg.norm(goal - final_pos))
            progress = init_d - final_d
            disp = final_pos - start_pos
            goal_dir = goal - start_pos
            goal_body0 = _goal_body(goal, start_pos, start_yaw)
            first_act = np.asarray(ep[0].action, dtype=np.float64).reshape(-1)
            # first ~10 steps mean action body xy
            acts = np.stack([np.asarray(tr.action, dtype=np.float64).reshape(-1) for tr in ep[:10]])
            mean_act_xy = acts[:, :2].mean(axis=0)
            collided = bool(any(getattr(tr.next_obs, "collided", False) for tr in ep))
            # proprio / state at t0
            st = np.asarray(ep[0].obs.state, dtype=np.float64).reshape(-1)
            vel_in_state = st[3:6].tolist() if st.size >= 6 else None
            entry = {
                "n_steps": len(ep),
                "progress": progress,
                "init_dist_m": init_d,
                "final_dist_m": final_d,
                "start_pos": start_pos.tolist(),
                "final_pos": final_pos.tolist(),
                "start_yaw": start_yaw,
                "path_len_m": float(np.linalg.norm(disp)),
                "cos_path_goal": _cosine(disp, goal_dir),
                "cos_first_act_goal_body": _cosine(first_act[:3], goal_body0),
                "cos_mean10_act_xy_goal_body_xy": _cosine(mean_act_xy, goal_body0[:2]),
                "first_action": first_act.tolist(),
                "mean10_action": acts.mean(axis=0).tolist(),
                "goal_body0": goal_body0.tolist(),
                "state_vel_xyz_t0": vel_in_state,
                "collided": collided,
            }
            row[tag] = entry
            if tag == "actor":
                actor_prog.append(progress)
            else:
                heur_prog.append(progress)

        row["goal"] = goal.tolist()
        row["delta_progress_actor_minus_heur"] = (
            float(row["actor"]["progress"] - row["heuristic"]["progress"])
        )
        episodes.append(row)
        print(
            f"[diag] ep{i}: actor_prog={row['actor']['progress']:+.2f} "
            f"heur={row['heuristic']['progress']:+.2f} "
            f"cos_path_a={row['actor']['cos_path_goal']:+.2f} "
            f"cos_path_h={row['heuristic']['cos_path_goal']:+.2f} "
            f"cos_act_a={row['actor']['cos_first_act_goal_body']:+.2f} "
            f"cos_act_h={row['heuristic']['cos_first_act_goal_body']:+.2f}"
        )

    gate = v4_metrics.check_progress_vs_heuristic(actor_prog, heur_prog, delta_p=0.10)
    summary = {
        "n_scored": len(actor_prog),
        "mean_actor": float(np.mean(actor_prog)) if actor_prog else None,
        "mean_heur": float(np.mean(heur_prog)) if heur_prog else None,
        "mean_cos_path_actor": float(np.mean([e["actor"]["cos_path_goal"] for e in episodes if "actor" in e])),
        "mean_cos_path_heur": float(np.mean([e["heuristic"]["cos_path_goal"] for e in episodes if "heuristic" in e])),
        "mean_cos_first_act_actor": float(
            np.mean([e["actor"]["cos_first_act_goal_body"] for e in episodes if "actor" in e])
        ),
        "mean_cos_first_act_heur": float(
            np.mean([e["heuristic"]["cos_first_act_goal_body"] for e in episodes if "heuristic" in e])
        ),
        "frac_actor_cos_path_neg": float(
            np.mean([e["actor"]["cos_path_goal"] < 0 for e in episodes if "actor" in e])
        ),
        "gate": gate,
        "code_facts": code_facts,
        "scan": {
            "accepted": scan_diag.get("accepted"),
            "requested": scan_diag.get("requested"),
        },
    }

    out = {
        "summary": summary,
        "episodes": episodes,
    }
    out_path = Path(args.out).expanduser()
    if not out_path.is_absolute():
        out_path = root / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    print(f"[diag] wrote {out_path}")
    return 0 if gate.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
