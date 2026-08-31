#!/usr/bin/env python3
"""P7-diag — S_diag rollouts; log C_P7 + step traces (θ undefined).

Planner default OFF (yaml / PL-A 2026-08-27). Pass --planner for ablation.

Usage (125 / 4090):
  source experiments/aerial/scripts/env_4090.sh
  $AERIAL_PY experiments/aerial/scripts/v4_p7_diag.py \\
    --env-host 127.0.0.1 \\
    --depth-ckpt experiments/aerial/rl/artifacts/depth_ckpt_p45mid_s8j_20260825/depth_best_holdout_da3_ft_head.pt \\
    --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_p45_merged_20260821/wm_step_500.pt \\
    --out artifacts/v4_p7_diag_s8j_20260826.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


def _repo_root(explicit: Optional[str]) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    return Path(__file__).resolve().parents[3]


def _full_min_depth(depth: Optional[np.ndarray]) -> float:
    if depth is None:
        return float("nan")
    d = np.asarray(depth, dtype=np.float64)
    finite = d[np.isfinite(d) & (d > 0)]
    return float(np.min(finite)) if finite.size else float("nan")


def _goal_dist(pos: np.ndarray, goal: np.ndarray) -> float:
    return float(
        np.linalg.norm(
            np.asarray(goal, dtype=np.float64).reshape(3)
            - np.asarray(pos, dtype=np.float64).reshape(3)
        )
    )


def _extract_step_trace(
    ep: Any, *, goal: np.ndarray, arrival_m: float
) -> Tuple[List[Dict[str, Any]], bool, float]:
    rows: List[Dict[str, Any]] = []
    best_d = float("inf")
    arrived = False
    for i, tr in enumerate(ep):
        obs = tr.obs
        post = tr.next_obs if tr.next_obs is not None else obs
        clearance = _full_min_depth(getattr(obs, "depth", None))
        d_hat = tr.info.get("depth_min_pred")
        if d_hat is None:
            d_hat = obs.info.get("depth_min_pred")
        tau = tr.info.get("tau_pred")
        if tau is None:
            tau = obs.info.get("tau_pred")
        p_coll = None
        if isinstance(tr.info.get("wm_out"), dict):
            p_coll = tr.info["wm_out"].get("p_coll")
        ch = tr.info.get("shield_channels") or obs.info.get("shield_channels") or []
        pos = np.asarray(getattr(obs, "position", None), dtype=np.float64).reshape(-1)
        yaw = None
        st = getattr(obs, "state", None)
        if st is not None and len(np.asarray(st).reshape(-1)) >= 7:
            yaw = float(np.asarray(st, dtype=np.float64).reshape(-1)[6])
        rows.append(
            {
                "t": i,
                "clearance_fov": round(clearance, 4) if np.isfinite(clearance) else None,
                "d_hat_fovmin": round(float(d_hat), 4) if d_hat is not None else None,
                "tau_hat": round(float(tau), 4) if tau is not None else None,
                "p_coll": round(float(p_coll), 4) if p_coll is not None else None,
                "engaged": bool(tr.info.get("intervention", False)),
                "shield_channels": list(ch),
                "dist_goal": round(_goal_dist(post.position, goal), 4),
                "collided": bool(getattr(post, "collided", False)),
                "position": [round(float(x), 4) for x in pos[:3]] if pos.size >= 3 else None,
                "yaw": round(yaw, 4) if yaw is not None and np.isfinite(yaw) else None,
            }
        )
        best_d = min(best_d, rows[-1]["dist_goal"])
        if rows[-1]["dist_goal"] <= float(arrival_m):
            arrived = True
    return rows, arrived, best_d


def _load_merged_cfg(root: Path, deploy_config: str, env_config: str) -> Dict[str, Any]:
    """Deploy stack (safety / WM / tau) + rollout env overlay."""
    import yaml

    deploy = yaml.safe_load((root / deploy_config).read_text()) or {}
    env_cfg = yaml.safe_load((root / env_config).read_text()) or {}
    out = dict(deploy)
    out["env"] = {**(deploy.get("env") or {}), **(env_cfg.get("env") or {})}
    if env_cfg.get("reward"):
        out["reward"] = env_cfg["reward"]
    return out


def run_p7_diag(args: argparse.Namespace) -> Dict[str, Any]:
    root = _repo_root(args.repo)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from experiments.aerial.rl import v0_rollout_eval as rollout
    from experiments.aerial.rl._v0_gate import _obstacle_candidate_positions
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
    from experiments.aerial.rl.v4_episode_pool import (
        EpisodeDropCounters,
        FROZEN_N_PER_LAYER,
        fill_to_target_n,
        split_primary_spare,
    )
    import time

    cfg = _load_merged_cfg(root, args.deploy_config, args.config)
    if args.env_host:
        cfg.setdefault("env", {})["host"] = str(args.env_host)
    cfg.setdefault("env", {})["grab_depth"] = True
    env = _build_env(cfg.get("env", {}) or {})
    reward_cfg = (
        RewardConfig(**(cfg.get("reward", {}) or {})) if cfg.get("reward") else RewardConfig()
    )
    arrival_m = float(reward_cfg.success_dist_m)

    rollout_ds = Path(args.rollout_dataset).expanduser()
    if not rollout_ds.is_absolute():
        rollout_ds = root / rollout_ds
    wm_ckpt = Path(args.wm_ckpt).expanduser()
    if not wm_ckpt.is_absolute():
        wm_ckpt = root / wm_ckpt
    depth_ckpt = Path(args.depth_ckpt).expanduser()
    if not depth_ckpt.is_absolute():
        depth_ckpt = root / depth_ckpt
    tau_ckpt = Path(args.tau_ckpt).expanduser()
    if not tau_ckpt.is_absolute():
        tau_ckpt = root / tau_ckpt

    wm_cfg = cfg.get("world_model", {}) or {}
    dynamics, wm_payload = load_torch_dynamics(
        wm_cfg, wm_ckpt, device=str(args.device), success_dist_m=arrival_m
    )
    # PL-A (2026-08-27): default OFF (yaml); explicit --planner only.
    want_planner = bool(getattr(args, "planner", False))
    cfg.setdefault("planner", {})["enable"] = want_planner
    planner = _build_planner(cfg, dynamics, reward_cfg) if want_planner else None
    if want_planner and planner is None:
        raise RuntimeError("--planner set but _build_planner returned None")
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
    safety_cfg = dict(cfg.get("safety") or {})
    if args.shield_kind:
        safety_cfg["kind"] = str(args.shield_kind)
    shield = _build_safety(safety_cfg)
    heuristic = HeuristicPolicy(goal_getter=lambda: getattr(env, "goal", None))
    actor_ckpt_path: Optional[Path] = None
    if getattr(args, "actor_ckpt", None):
        from experiments.aerial.rl.actor_critic import LatentActorCritic, LatentActorDeployPolicy

        actor_ckpt_path = Path(args.actor_ckpt).expanduser()
        if not actor_ckpt_path.is_absolute():
            actor_ckpt_path = root / actor_ckpt_path
        if not actor_ckpt_path.is_file():
            raise FileNotFoundError(f"missing actor ckpt {actor_ckpt_path}")
        actor_ac = LatentActorCritic.load_from_checkpoint(
            actor_ckpt_path, device=str(args.device)
        )
        if int(actor_ac.config.latent_dim) != int(dynamics.latent_dim):
            raise ValueError(
                f"actor latent_dim={actor_ac.config.latent_dim} != "
                f"WM latent_dim={dynamics.latent_dim}"
            )
        base_policy = LatentActorDeployPolicy(dynamics, actor_ac, deterministic=True)
        policy_kind = "actor"
    else:
        base_policy = heuristic
        policy_kind = "heuristic"

    cand, cand_yaw = _obstacle_candidate_positions(rollout_ds, min_altitude_m=0.0)
    goal_dist = float(getattr(args, "goal_dist_m", 30.0))
    target_n = int(args.target_n)
    spare_count = int(args.spare_count)
    if target_n <= 0:
        target_n = int(FROZEN_N_PER_LAYER)
    scan_n = target_n + spare_count

    blocked_eps, blocked_scan = rollout.make_obstacle_facing_episodes(
        env,
        int(scan_n),
        cand,
        seed=int(args.seed),
        candidate_yaws=cand_yaw,
        goal_dist_m=goal_dist,
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
    primary, spare, spare_manifest = split_primary_spare(
        blocked_eps,
        target_n=target_n,
        spare_count=spare_count,
        layer="S_diag_blocked",
        seed=int(args.diag_seed),
    )
    spare_manifest.write(
        root / "artifacts" / f"v4_p7_diag_spare_manifest_{args.stamp}.json"
    )

    episodes_out: List[Dict[str, Any]] = []
    c_p7: List[float] = []
    buf = ReplayBuffer(capacity_episodes=4, seed=0)
    retries = int(args.reset_retries)
    retry_sleep_s = float(args.retry_sleep_s)

    def _score_one(epi: Dict[str, Any], counters: EpisodeDropCounters) -> bool:
        ep = None
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
            if attempt < retries and retry_sleep_s > 0:
                time.sleep(retry_sleep_s)
        if not ep:
            counters.record_invalid_spawn()
            print(
                f"[p7-diag] drop invalid_spawn "
                f"(retries={retries} skipped={getattr(stats, 'skipped', 1)})"
            )
            return False
        goal = np.asarray(getattr(env, "goal"), dtype=np.float64).reshape(3)
        from experiments.aerial.rl.tz_band import (
            annotate_trace_in_band,
            band_frac,
            band_frac_buckets,
        )

        trace, arrived, best_d = _extract_step_trace(ep, goal=goal, arrival_m=arrival_m)
        trace = annotate_trace_in_band(trace)
        hard_coll = any(bool(row.get("collided")) for row in trace)
        bf = band_frac(trace)  # E1: NaN if hard_coll episode
        buckets = band_frac_buckets(trace)
        for row in trace:
            c = row.get("clearance_fov")
            if c is not None and np.isfinite(c):
                c_p7.append(float(c))
        episodes_out.append(
            {
                "idx": len(episodes_out),
                "layer": "blocked",
                "arrived": bool(arrived),
                "hard_coll": bool(hard_coll),
                "band_frac": round(float(bf), 4) if np.isfinite(bf) else None,
                "band_frac_buckets": {
                    k: (round(float(v), 4) if np.isfinite(v) else None)
                    for k, v in buckets.items()
                },
                "band_frac_excluded_hard_coll": bool(hard_coll),
                "best_dist_m": round(float(best_d), 4),
                "n_steps": len(trace),
                "steps": trace,
            }
        )
        print(
            f"[p7-diag] ep{len(episodes_out)-1}: arrived={arrived} "
            f"hard_coll={hard_coll} band_frac={bf if np.isfinite(bf) else float('nan'):.3f} "
            f"best_d={best_d:.2f} steps={len(trace)}"
        )
        return True

    fill = fill_to_target_n(
        env,
        primary,
        spare,
        spare_manifest,
        target_n=target_n,
        score_one=_score_one,
    )

    from experiments.aerial.rl.tz_band import (
        ERRATA_ID,
        REFREEZE_ID,
        TZ_BAND_HI_M,
        TZ_BAND_LO_M,
        TZ_BAND_MID_M,
    )

    q25 = float(np.percentile(c_p7, 25)) if c_p7 else float("nan")
    n_arrived = sum(1 for e in episodes_out if e.get("arrived"))
    n_hard = sum(1 for e in episodes_out if e.get("hard_coll"))
    arrival_rate = float(n_arrived / fill.n_scored) if fill.n_scored else float("nan")
    hard_coll_rate = float(n_hard / fill.n_scored) if fill.n_scored else float("nan")
    band_fracs = [
        float(e["band_frac"])
        for e in episodes_out
        if e.get("band_frac") is not None and np.isfinite(float(e["band_frac"]))
    ]
    n_excluded_hard = sum(
        1 for e in episodes_out if e.get("band_frac_excluded_hard_coll")
    )
    band_frac_median = float(np.median(band_fracs)) if band_fracs else float("nan")
    # E0 half-band medians (report-only).
    inner_fracs = []
    outer_fracs = []
    for e in episodes_out:
        b = e.get("band_frac_buckets") or {}
        iv = b.get("inner_l3_to_l2")
        ov = b.get("outer_l2_to_l1")
        if iv is not None and np.isfinite(float(iv)):
            inner_fracs.append(float(iv))
        if ov is not None and np.isfinite(float(ov)):
            outer_fracs.append(float(ov))
    # E1: band_frac↑ with hard_coll↑ ⇒ FAIL with reason (not PASS evidence).
    band_hard_corise_fail = False
    band_hard_corise_note = None
    if (
        np.isfinite(band_frac_median)
        and np.isfinite(hard_coll_rate)
        and hard_coll_rate > 0.0
        and band_frac_median > 0.0
    ):
        # Same-direction rise vs prior accept′ baseline is recorded by caller;
        # here we flag when excluded-hard median still co-moves with collision rate
        # above a soft diagnostic threshold (report gate, not θ freeze).
        if hard_coll_rate >= 0.05 and band_frac_median >= 0.25:
            band_hard_corise_fail = True
            band_hard_corise_note = (
                "E1: median band_frac and hard_coll_rate both elevated; "
                "must not be treated as safe-reroute PASS evidence"
            )
    # TZ-2: geometric band is frozen; old 5ab empty-band fork superseded.
    payload = {
        "step": "P7-diag",
        "refreeze_id": REFREEZE_ID,
        "errata_id": ERRATA_ID,
        "theta": None,
        "band_lo_hi": [TZ_BAND_LO_M, TZ_BAND_HI_M],
        "band_mid_m": TZ_BAND_MID_M,
        "band_empty_5ab": False,
        "d_prime_b": "primary",
        "band_frac": {
            "n": len(band_fracs),
            "n_excluded_hard_coll_episodes": int(n_excluded_hard),
            "exclude_hard_coll_episode": True,
            "median": round(band_frac_median, 4) if np.isfinite(band_frac_median) else None,
            "mean": round(float(np.mean(band_fracs)), 4) if band_fracs else None,
            "buckets": {
                "inner_l3_to_l2": {
                    "lo_hi": [TZ_BAND_LO_M, TZ_BAND_MID_M],
                    "n": len(inner_fracs),
                    "median": (
                        round(float(np.median(inner_fracs)), 4) if inner_fracs else None
                    ),
                },
                "outer_l2_to_l1": {
                    "lo_hi": [TZ_BAND_MID_M, TZ_BAND_HI_M],
                    "n": len(outer_fracs),
                    "median": (
                        round(float(np.median(outer_fracs)), 4) if outer_fracs else None
                    ),
                },
            },
            "band_hard_corise_fail": bool(band_hard_corise_fail),
            "band_hard_corise_note": band_hard_corise_note,
        },
        "note": (
            "TZ diagnostic; geometric band (1.5,8.0] frozen; θ from this log only; "
            "E1 hard_coll episodes excluded from band_frac; E0 half-band buckets; "
            "deploy = three_zone + S-8j; P0c spare refill enabled; "
            "θ=0.2344 INVALID after this E1 redefine — must refreeze"
        ),
        "s_diag_seed": int(args.diag_seed),
        "accept_seed_reserved": int(args.accept_seed),
        "n_blocked_pool": len(blocked_eps),
        "n_open_pool": 0,
        "open_scan_rejections": {"skipped": "P7-diag only scores S_blocked for C_P7"},
        "blocked_scan": blocked_scan,
        "spare_manifest": spare_manifest.to_dict(),
        "p0c": fill.drop_summary(),
        "n_scored": fill.n_scored,
        "authoritative": bool(fill.authoritative),
        "arrival_rate": round(arrival_rate, 4) if np.isfinite(arrival_rate) else None,
        "hard_coll_rate": round(hard_coll_rate, 4) if np.isfinite(hard_coll_rate) else None,
        "C_P7": {
            "n": len(c_p7),
            "p25": round(q25, 4) if np.isfinite(q25) else None,
            "median": round(float(np.median(c_p7)), 4) if c_p7 else None,
        },
        "episodes": episodes_out,
        "wm_ckpt": str(wm_ckpt),
        "wm_step": wm_payload.get("step"),
        "depth_ckpt": str(depth_ckpt),
        "tau_ckpt": str(tau_ckpt),
        "safety_kind": str(safety_cfg.get("kind", "")),
        "policy_kind": policy_kind,
        "planner_enabled": bool(want_planner),
        "deploy_config": str(args.deploy_config),
    }
    if actor_ckpt_path is not None:
        payload["actor_ckpt"] = str(actor_ckpt_path)
    if bool(getattr(args, "attr", False)):
        from experiments.aerial.rl.attr_fork import ATTR_ID, decide_fork

        fork = decide_fork(episodes_out)
        for ep, ann in zip(episodes_out, fork["episodes"]):
            ep["outcome"] = ann.get("outcome")
            if "hard_coll_label" in ann:
                ep["hard_coll_label"] = ann["hard_coll_label"]
                ep["hard_coll_stats"] = ann.get("hard_coll_stats")
        payload["step"] = "P7-attr"
        payload["attr_id"] = ATTR_ID
        payload["refreeze_id"] = ATTR_ID
        payload["fork"] = {
            "label": fork["label"],
            "reason": fork["reason"],
            "next_action": fork["next_action"],
            "n_percept": fork["n_percept"],
            "n_plan": fork["n_plan"],
            "n_unclear_hard_coll": fork["n_unclear_hard_coll"],
            "n_hard_coll": fork["n_hard_coll"],
            "outcomes": fork["outcomes"],
            "gt_source_note": fork["gt_source_note"],
        }
        payload["note"] = (
            "ATTR diagnostic n≥32 blocked; d̂/τ via collector ep_info; "
            "GT=clearance_fov (same-Hz depth cam); fork per V4_5AIP_ATTR_20260826; "
            "NOT a P7-accept′ certificate"
        )
    return payload


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default=None)
    p.add_argument(
        "--deploy-config",
        default="configs/aerial_rl.yaml",
        help="Deploy stack (safety / WM / tau).",
    )
    p.add_argument(
        "--config",
        default="configs/aerial_rl_rollout.yaml",
        help="Env overlay (AirSim host / grab_depth).",
    )
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
    p.add_argument("--target-n", type=int, default=16)
    p.add_argument(
        "--spare-count",
        type=int,
        default=16,
        help="P0c spare starts scanned beyond target_n (refill on invalid spawn).",
    )
    p.add_argument(
        "--reset-retries",
        type=int,
        default=2,
        help="Same-episode reset retries before counting invalid_spawn.",
    )
    p.add_argument("--retry-sleep-s", type=float, default=0.5)
    p.add_argument("--scan-max", type=int, default=800)
    p.add_argument("--probe-steps", type=int, default=40)
    p.add_argument("--max-steps", type=int, default=200)
    p.add_argument("--goal-dist-m", type=float, default=30.0)
    p.add_argument(
        "--shield-kind",
        default="",
        help="Override safety.kind (default: from deploy-config).",
    )
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--diag-seed", type=int, default=1100)
    p.add_argument("--accept-seed", type=int, default=2100)
    p.add_argument("--stamp", default="20260826_tz")
    p.add_argument("--out", default="artifacts/v4_p7_diag_tz_s8j_20260826.json")
    p.add_argument(
        "--attr",
        action="store_true",
        help="ATTR mode: outcome labels + percept/plan fork (V4_5AIP_ATTR_20260826).",
    )
    p.add_argument(
        "--actor-ckpt",
        default=None,
        help="Optional LatentActorCritic ckpt; default heuristic policy.",
    )
    p.add_argument(
        "--planner",
        action="store_true",
        help="Enable ImaginationPlanner (default OFF; PL-A 2026-08-27).",
    )
    args = p.parse_args()

    payload = run_p7_diag(args)
    out = Path(args.out).expanduser()
    if not out.is_absolute():
        out = _repo_root(args.repo) / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    fork = payload.get("fork") or {}
    print(
        f"[p7-diag] wrote {out} n_scored={payload['n_scored']} "
        f"authoritative={payload.get('authoritative')} "
        f"arrival={payload.get('arrival_rate')} "
        f"band_frac.median={((payload.get('band_frac') or {}).get('median'))} "
        f"C_P7.p25={payload['C_P7'].get('p25')}"
        + (
            f" fork={fork.get('label')} next={fork.get('next_action')}"
            if fork
            else ""
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
