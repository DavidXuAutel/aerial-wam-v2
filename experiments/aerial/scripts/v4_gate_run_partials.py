#!/usr/bin/env python3
"""Run V4 gate partials (4090 rollout) and merge (frozen spec §4).

Usage (4090 @ configs/aerial_rl_rollout.yaml):
  python experiments/aerial/scripts/v4_gate_run_partials.py rollout4090 \\
    --repo ~/aerial-wam-v2 \\
    --rollout-dataset ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_local_depth_r60_20260814 \\
    --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_20260816/v4_ac_latest.pt \\
    --depth-ckpt experiments/aerial/rl/artifacts/depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt \\
    --tau-ckpt experiments/aerial/rl/artifacts/tau_ckpt_foe_r60_20260815/tau_foe_calibrator.pt \\
    --env-host 127.0.0.1 \\
    --out-dir experiments/aerial/rl/artifacts/v4_gate_r60_20260816

  python experiments/aerial/scripts/v4_gate_run_partials.py merge \\
    --repo ~/aerial-wam-v2 \\
    --out-dir experiments/aerial/rl/artifacts/v4_gate_r60_20260816
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_PARTIAL1 = "v4_partial_1_r60_20260816.json"
_PARTIAL4 = "v4_partial_4_r60_20260816.json"
_MERGE_OUT = "v4_gate_r60_20260816.json"


def _repo_root(explicit: Optional[str]) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    return Path(__file__).resolve().parents[3]


def _emit(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")
    print(f"[v4-run] wrote {path}")


def _episode_collision_rate(collided: List[List[bool]]) -> float:
    if not collided:
        return float("nan")
    hits = sum(1 for ep in collided if any(ep))
    return float(hits / len(collided))


def _frame_near_coll_rate(near: List[List[bool]]) -> float:
    total = sum(len(ep) for ep in near)
    if total <= 0:
        return float("nan")
    return float(sum(sum(1 for x in ep if x) for ep in near) / total)


def run_rollout4090(args: argparse.Namespace) -> int:
    root = _repo_root(args.repo)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    import numpy as np
    import yaml

    from experiments.aerial.rl import v0_metrics as v0m
    from experiments.aerial.rl import v0_rollout_eval as rollout
    from experiments.aerial.rl import v4_metrics
    from experiments.aerial.rl._v0_gate import _obstacle_candidate_positions
    from experiments.aerial.rl.actor_critic import LatentActorCritic, LatentActorDeployPolicy
    from experiments.aerial.rl.depth_predictor import DepthMinPredictor
    from experiments.aerial.rl.dynamics import StubLatentDynamics
    from experiments.aerial.rl.reward import RewardConfig
    from experiments.aerial.rl.safety import DepthTauShield
    from experiments.aerial.rl.tau_predictor import make_tau_predictor
    from experiments.aerial.rl.train_rl import HeuristicPolicy, _build_env

    out_dir = Path(args.out_dir).expanduser()
    if not out_dir.is_absolute():
        out_dir = root / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    cfg_path = root / args.config
    cfg = yaml.safe_load(cfg_path.read_text()) or {}
    if args.env_host:
        cfg.setdefault("env", {})["host"] = str(args.env_host)
    env = _build_env(cfg.get("env", {}) or {})
    reward_cfg = RewardConfig(**(cfg.get("reward", {}) or {})) if cfg.get("reward") else None
    thr = v0m.DEFAULT_THRESHOLDS
    shield_trigger_m = float(args.shield_trigger_m)

    rollout_ds = Path(args.rollout_dataset).expanduser()
    if not rollout_ds.is_absolute():
        rollout_ds = root / rollout_ds
    if not rollout_ds.is_dir():
        print(f"[v4-run] missing rollout dataset {rollout_ds}", file=sys.stderr)
        return 2

    actor_ckpt = Path(args.actor_ckpt).expanduser()
    if not actor_ckpt.is_absolute():
        actor_ckpt = root / actor_ckpt
    if not actor_ckpt.is_file():
        print(f"[v4-run] missing actor ckpt {actor_ckpt}", file=sys.stderr)
        return 2

    depth_ckpt = Path(args.depth_ckpt).expanduser()
    if not depth_ckpt.is_absolute():
        depth_ckpt = root / depth_ckpt
    if not depth_ckpt.is_file():
        print(f"[v4-run] missing depth ckpt {depth_ckpt}", file=sys.stderr)
        return 2

    tau_cfg = cfg.get("tau_predictor", {}) or {}
    tau_kind = str(args.tau_kind or tau_cfg.get("kind") or "foe_calibrated")
    tau_ckpt = args.tau_ckpt or tau_cfg.get("ckpt")
    if tau_ckpt:
        tau_ckpt = Path(str(tau_ckpt)).expanduser()
        if not tau_ckpt.is_absolute():
            tau_ckpt = root / tau_ckpt
    if tau_ckpt and not tau_ckpt.is_file():
        print(f"[v4-run] missing tau ckpt {tau_ckpt}", file=sys.stderr)
        return 2

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
        s1 = {"ok": False, "reason": "no obstacle-facing starts", "scan": scan_diag}
        partial1 = {"partial": True, "signals_requested": ["1"], "ok": False, "signals": {"1": s1}}
        _emit(out_dir / _PARTIAL1, partial1)
        s4 = {"ok": False, "reason": "no starts for safety eval", "scan": scan_diag}
        partial4 = {"partial": True, "signals_requested": ["4"], "ok": False, "signals": {"4": s4}}
        _emit(out_dir / _PARTIAL4, partial4)
        return 1

    probe = scan_diag.get("probe") or {}
    if int(probe.get("collided", 0)) <= 0 and not (
        probe.get("reached_fwd_m")
        and float((probe["reached_fwd_m"] or {}).get("min") or 1e9)
        < float(thr.near_collision_depth_m)
    ):
        reason = "starts not collision-bearing (probe forward-near/collided required)"
        s1 = {"ok": False, "reason": reason, "scan": scan_diag}
        partial1 = {"partial": True, "signals_requested": ["1"], "ok": False, "signals": {"1": s1}}
        _emit(out_dir / _PARTIAL1, partial1)
        s4 = {"ok": False, "reason": reason, "scan": scan_diag}
        partial4 = {"partial": True, "signals_requested": ["4"], "ok": False, "signals": {"4": s4}}
        _emit(out_dir / _PARTIAL4, partial4)
        return 1

    dyn_cfg = cfg.get("dynamics", {}) or {}
    dynamics = StubLatentDynamics(
        goal=None,
        latent_dim=int(dyn_cfg.get("latent_dim", 8)),
        collide_radius_m=float(dyn_cfg.get("collide_radius_m", 2.0)),
        success_dist_m=float(reward_cfg.success_dist_m if reward_cfg else 3.0),
    )
    actor_ac = LatentActorCritic.load_from_checkpoint(actor_ckpt, device=str(args.device))
    actor_policy = LatentActorDeployPolicy(
        dynamics, actor_ac, deterministic=not bool(args.actor_stochastic),
    )

    # --- V4-① progress vs Heuristic (same harness as V0-② pairing) ---
    prog = rollout.run_progress_eval(
        env,
        actor_policy,
        heuristic,
        starts,
        max_steps=int(args.max_steps),
        reward_cfg=reward_cfg,
    )
    s1 = v4_metrics.check_progress_vs_heuristic(
        prog["policy_progress_sums"],
        prog["random_progress_sums"],
        delta_p=float(args.delta_p),
    )
    s1["actor_progress_sums"] = prog["policy_progress_sums"]
    s1["heuristic_progress_sums"] = prog["random_progress_sums"]
    s1["actor_final_dists"] = prog["policy_final_dists"]
    s1["heuristic_final_dists"] = prog["random_final_dists"]
    s1["scan"] = scan_diag
    s1["actor_ckpt"] = str(actor_ckpt)
    s1["n_starts_scored"] = len(prog["policy_progress_sums"])

    partial1 = {
        "partial": True,
        "signals_requested": ["1"],
        "ok": bool(s1.get("ok")),
        "signals": {"1": s1},
    }
    _emit(out_dir / _PARTIAL1, partial1)
    print(
        f"[v4-run] signal1 ok={s1.get('ok')} actor_mean={s1.get('mean_progress_actor'):.4f} "
        f"heur_mean={s1.get('mean_progress_heuristic'):.4f} target={s1.get('target_min'):.4f}"
    )

    # --- V4-④ safety (shield-on hard coll + optional V0-④ near ratio) ---
    predictor = DepthMinPredictor.from_checkpoint(depth_ckpt, device=args.device)
    tau_pred = make_tau_predictor(
        kind=tau_kind,
        ckpt=tau_ckpt,
        device=str(args.device),
        center_frac=float(tau_cfg.get("center_frac", 0.5)),
        min_closing_m_s=float(tau_cfg.get("min_closing_m_s", 0.05)),
        max_tau_s=float(tau_cfg.get("max_tau_s", 60.0)),
        dt_s=float(tau_cfg.get("dt_s", 0.1)),
        use_gt_depth=False,
    )

    def _run_arm(
        policy: Any,
        *,
        shield_on: bool,
        label: str,
    ) -> Dict[str, Any]:
        collided_on: List[List[bool]] = []
        near_on: List[List[bool]] = []
        near_off: List[List[bool]] = []
        collided_off: List[List[bool]] = []
        drop_stats: Dict[str, int] = {}
        for epi in starts:
            if hasattr(policy, "reset"):
                policy.reset()
            if hasattr(tau_pred, "reset"):
                tau_pred.reset()
            shield = None
            if shield_on:
                shield = DepthTauShield(
                    min_depth_m=shield_trigger_m,
                    min_tau_s=float(cfg.get("safety", {}).get("min_tau_s", 1.0)),
                )
            ep_on = rollout._run_one_resilient(
                env,
                policy,
                epi,
                max_steps=int(args.max_steps),
                reward_cfg=reward_cfg,
                shield=shield,
                depth_predictor=predictor if shield is not None else None,
                tau_predictor=tau_pred if shield is not None else None,
                drop_stats=drop_stats,
            )
            if ep_on is None:
                continue
            m_on = rollout._episode_masks(
                ep_on, near_collision_depth_m=float(thr.near_collision_depth_m),
            )
            collided_on.append(m_on["collided"])
            near_on.append(m_on["near"])

            if hasattr(policy, "reset"):
                policy.reset()
            ep_off = rollout._run_one_resilient(
                env,
                policy,
                epi,
                max_steps=int(args.max_steps),
                reward_cfg=reward_cfg,
                shield=None,
                drop_stats=drop_stats,
            )
            if ep_off is None:
                collided_off.append([])
                near_off.append([])
                continue
            m_off = rollout._episode_masks(
                ep_off, near_collision_depth_m=float(thr.near_collision_depth_m),
            )
            collided_off.append(m_off["collided"])
            near_off.append(m_off["near"])

        hard_rate = _episode_collision_rate(collided_on)
        near_on_rate = _frame_near_coll_rate(near_on)
        near_off_rate = _frame_near_coll_rate(near_off)
        ratio = (
            float(near_on_rate / near_off_rate)
            if np.isfinite(near_on_rate) and np.isfinite(near_off_rate) and near_off_rate > 0
            else float("nan")
        )
        return {
            "label": label,
            "collision_rate": hard_rate,
            "near_coll_rate_on": near_on_rate,
            "near_coll_rate_off": near_off_rate,
            "near_coll_rate_ratio": ratio,
            "n_episodes": len(collided_on),
            "drop_stats": drop_stats,
            "shield_trigger_m": shield_trigger_m if shield_on else None,
        }

    v4_on = _run_arm(actor_policy, shield_on=True, label="v4_actor_shield_on")
    v4_off = _run_arm(actor_policy, shield_on=False, label="v4_actor_shield_off")
    v1_on = _run_arm(heuristic, shield_on=True, label="v1_heuristic_shield_on")

    v4_coll = float(v4_on["collision_rate"])
    if args.v1_coll_rate is not None:
        v1_coll = float(args.v1_coll_rate)
        v1_source = "cli_baseline"
    else:
        v1_coll = float(v1_on["collision_rate"])
        v1_source = "remeasured_same_starts"

    near_ratio = v4_on.get("near_coll_rate_ratio")
    if not np.isfinite(near_ratio):
        near_ratio = None

    s4 = v4_metrics.check_safety_no_regression(
        v4_coll,
        v1_coll,
        near_coll_rate_ratio=near_ratio,
    )
    s4["v4_measured"] = v4_on
    s4["v4_shield_off"] = v4_off
    s4["v1_measured"] = v1_on
    s4["v1_coll_source"] = v1_source
    s4["v1_partial_baseline"] = 0.50
    s4["tau_kind"] = tau_kind
    s4["tau_ckpt"] = str(tau_ckpt) if tau_ckpt else None
    s4["scan"] = scan_diag
    s4["actor_ckpt"] = str(actor_ckpt)
    s4["depth_ckpt"] = str(depth_ckpt)

    partial4 = {
        "partial": True,
        "signals_requested": ["4"],
        "ok": bool(s4.get("ok")),
        "signals": {"4": s4},
    }
    _emit(out_dir / _PARTIAL4, partial4)
    print(
        f"[v4-run] signal4 ok={s4.get('ok')} v4_hard={v4_coll:.4f} v1_hard={v1_coll:.4f} "
        f"near_ratio={near_ratio} source={v1_source}"
    )

    ok = bool(s1.get("ok")) and bool(s4.get("ok"))
    return 0 if ok else 1


def run_merge(args: argparse.Namespace) -> int:
    root = _repo_root(args.repo)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from experiments.aerial.rl._v4_gate import _merge_partials, assemble_verdict

    out_dir = Path(args.out_dir).expanduser()
    if not out_dir.is_absolute():
        out_dir = root / out_dir
    paths = [out_dir / _PARTIAL1, out_dir / _PARTIAL4]
    for p in paths:
        if not p.exists():
            print(f"[v4-run] missing {p}", file=sys.stderr)
            return 2
    signals = _merge_partials(paths)
    verdict = assemble_verdict(signals["1"], signals["4"])
    verdict["merged_from"] = [str(p) for p in paths]
    out = out_dir / _MERGE_OUT
    _emit(out, verdict)
    return 0 if verdict.get("ok") else 1


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("rollout4090", "merge"))
    p.add_argument("--repo", default=None)
    p.add_argument(
        "--out-dir",
        default="experiments/aerial/rl/artifacts/v4_gate_r60_20260816",
    )
    p.add_argument("--config", default="configs/aerial_rl_rollout.yaml")
    p.add_argument("--env-host", default=None, help="override env.host (e.g. 127.0.0.1)")
    p.add_argument("--device", default="cuda")
    p.add_argument(
        "--rollout-dataset",
        default="~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_local_depth_r60_20260814",
    )
    p.add_argument(
        "--actor-ckpt",
        default="experiments/aerial/rl/artifacts/v4_ac_ckpt_20260816/v4_ac_latest.pt",
    )
    p.add_argument(
        "--depth-ckpt",
        default="experiments/aerial/rl/artifacts/depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt",
    )
    p.add_argument("--tau-kind", default="foe_calibrated")
    p.add_argument(
        "--tau-ckpt",
        default="experiments/aerial/rl/artifacts/tau_ckpt_foe_r60_20260815/tau_foe_calibrator.pt",
    )
    p.add_argument("--n-episodes", type=int, default=8)
    p.add_argument("--max-steps", type=int, default=200)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--shield-trigger-m", type=float, default=1.5)
    p.add_argument("--delta-p", type=float, default=0.10)
    p.add_argument(
        "--v1-coll-rate",
        type=float,
        default=None,
        help="V1-① authoritative baseline; default remeasure heuristic V1 arm",
    )
    p.add_argument(
        "--actor-stochastic",
        action="store_true",
        help="sample actor actions (default deterministic)",
    )
    args = p.parse_args()
    if args.mode == "rollout4090":
        return run_rollout4090(args)
    return run_merge(args)


if __name__ == "__main__":
    raise SystemExit(main())
