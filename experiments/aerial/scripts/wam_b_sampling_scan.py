#!/usr/bin/env python3
"""Sweep sampling parameters (datasets, depth cutoffs, horizons) for B and B′-4."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def main() -> int:
    root = _repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from experiments.aerial.rl import dataset as ds
    from experiments.aerial.rl.coll_oracle_rank import (
        oracle_pairwise_gaps,
        score_oracle_arms_at_t,
        verdict_from_oracle_gaps,
    )
    from experiments.aerial.rl.goal_features import body_vel_from_obs, goal_rel_from_obs
    from experiments.aerial.rl.imagine_coll_rank import (
        pairwise_gaps,
        score_arms_at_z0,
        verdict_from_gaps,
    )
    from experiments.aerial.rl.latent_encode_probe import center_depth_m, encode_single
    from experiments.aerial.rl.reward import RewardConfig
    from experiments.aerial.rl.train_rl import load_torch_dynamics

    p = argparse.ArgumentParser(description="Sweep B / B-4 sampling")
    p.add_argument(
        "--wm-ckpt",
        default="experiments/aerial/rl/artifacts/wm_ckpt_coll_full_20260827/wm_step_1000.pt",
    )
    p.add_argument("--device", default="cuda")
    p.add_argument("--max-samples", type=int, default=32)
    p.add_argument("--out", default="artifacts/wam_b_sampling_scan_20260828.json")
    args = p.parse_args()

    wm_path = Path(args.wm_ckpt)
    if not wm_path.is_absolute():
        wm_path = root / wm_path

    cfg_path = root / "configs/aerial_rl.yaml"
    with cfg_path.open() as f:
        config: Dict[str, Any] = yaml.safe_load(f) or {}

    reward_cfg = (
        RewardConfig(**(config.get("reward", {}) or {}))
        if config.get("reward")
        else RewardConfig()
    )
    wm_cfg = config.get("world_model", {}) or {}

    dynamics, _ = load_torch_dynamics(
        wm_cfg,
        wm_path,
        device=args.device,
        success_dist_m=float(reward_cfg.success_dist_m),
    )

    datasets = {
        "p45_merged": "experiments/aerial/rl/artifacts/dataset_v0_p45_merged_20260821",
        "near_enrich": "experiments/aerial/rl/artifacts/dataset_v0_p45_near_enrich_20260820",
        "coll_heldout": "experiments/aerial/rl/artifacts/dataset_v1_coll_heldout_20260817",
        "wam_loop": "experiments/aerial/rl/artifacts/dataset_wam_loop_20260827",
    }

    depth_cutoffs = [15.0, 12.0, 8.0, 5.0, 3.5, 2.5]
    results = []

    print(f"{'Dataset':<13} | {'max_d':<6} | {'n':<4} | {'WM med_gap':<10} | {'WM (fwd, lat)':<18} | {'Oracle med_gap':<14} | {'Oracle fwd/lat'}")
    print("-" * 90)

    for dname, drel in datasets.items():
        dpath = root / drel
        if not dpath.exists():
            continue
        episodes = ds.load_dataset(dpath, skip_quarantined=True)
        for max_d in depth_cutoffs:
            oracle_gaps = []
            wm_gaps = []
            for ep_i, ep in enumerate(episodes):
                if len(wm_gaps) >= args.max_samples:
                    break
                if not ep:
                    continue
                for t_i in range(0, len(ep), 2):
                    if len(wm_gaps) >= args.max_samples:
                        break
                    tr = ep[t_i]
                    d0 = center_depth_m(tr.obs)
                    if d0 is None or d0 > float(max_d):
                        continue
                    if getattr(tr.obs, "depth", None) is None:
                        continue

                    # Oracle
                    o_arms = score_oracle_arms_at_t(
                        ep, t_i, horizon=15, d_thresh_m=3.0, center_frac=0.5
                    )
                    og = oracle_pairwise_gaps(o_arms)
                    oracle_gaps.append(og)

                    # WM
                    z0 = encode_single(dynamics, tr.obs)
                    g0 = goal_rel_from_obs(tr.obs)
                    v0 = body_vel_from_obs(tr.obs)
                    wm_arms = score_arms_at_z0(
                        dynamics,
                        z0,
                        horizon=15,
                        goal_rel0=g0,
                        body_vel0=v0,
                        reward_cfg=reward_cfg,
                    )
                    wg = pairwise_gaps(wm_arms)
                    wm_gaps.append(wg)

            if len(wm_gaps) >= 8:
                wm_v = verdict_from_gaps(wm_gaps)
                o_v = verdict_from_oracle_gaps(oracle_gaps)
                fwd_pc = float(np.mean([g["forward_mean_p_coll"] for g in wm_gaps]))
                lat_pc = float(np.mean([g["lateral_mean_p_coll"] for g in wm_gaps]))
                row_info = {
                    "dataset": dname,
                    "max_center_depth_m": float(max_d),
                    "n_samples": len(wm_gaps),
                    "wm_median_p_coll_gap": wm_v["median_p_coll_gap"],
                    "wm_mean_fwd_p_coll": round(fwd_pc, 4),
                    "wm_mean_lat_p_coll": round(lat_pc, 4),
                    "wm_useful": wm_v["useful"],
                    "oracle_median_gap": o_v["median_oracle_gap"],
                    "oracle_mean_gap": o_v["mean_oracle_gap"],
                    "oracle_high_ceiling": o_v["high_ceiling"],
                }
                results.append(row_info)
                print(
                    f"{dname:<13} | {max_d:>4.1f}m  | {len(wm_gaps):>4} | "
                    f"{wm_v['median_p_coll_gap']:>10.5f} | "
                    f"({fwd_pc:.3f}, {lat_pc:.3f})      | "
                    f"{o_v['median_oracle_gap']:>14.4f} | "
                    f"{o_v['label']}"
                )

    out_path = root / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    print(f"\nSaved scan to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
