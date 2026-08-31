#!/usr/bin/env python3
"""Runbook B′-4 — GT-depth oracle ranking (forward vs lateral ceiling)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def main() -> int:
    root = _repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    p = argparse.ArgumentParser(description="GT-depth oracle collision ceiling (B′-4)")
    p.add_argument(
        "--dataset",
        default="experiments/aerial/rl/artifacts/dataset_v0_p45_merged_20260821",
    )
    p.add_argument("--config", default="configs/aerial_rl.yaml")
    p.add_argument("--horizon", type=int, default=15)
    p.add_argument("--max-samples", type=int, default=32)
    p.add_argument("--max-center-depth-m", type=float, default=12.0)
    p.add_argument("--stride", type=int, default=2)
    p.add_argument("--d-thresh-m", type=float, default=3.0)
    p.add_argument("--center-frac", type=float, default=0.5)
    p.add_argument("--high-ceiling-gap", type=float, default=0.3)
    p.add_argument("--out", default="artifacts/wam_coll_oracle_gtdepth.json")
    args = p.parse_args()

    from experiments.aerial.rl import dataset as ds
    from experiments.aerial.rl.coll_oracle_rank import (
        oracle_pairwise_gaps,
        score_oracle_arms_at_t,
        verdict_from_oracle_gaps,
    )
    from experiments.aerial.rl.imagination import MAX_IMAGINATION_HORIZON
    from experiments.aerial.rl.latent_encode_probe import center_depth_m

    cfg_path = Path(args.config)
    if not cfg_path.is_absolute():
        cfg_path = root / cfg_path
    with cfg_path.open() as f:
        config: Dict[str, Any] = yaml.safe_load(f) or {}

    dataset = Path(args.dataset).expanduser()
    if not dataset.is_absolute():
        dataset = root / dataset
    out_path = Path(args.out).expanduser()
    if not out_path.is_absolute():
        out_path = root / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    horizon = min(int(args.horizon), int(MAX_IMAGINATION_HORIZON))
    center_frac = float(args.center_frac)
    dh_cfg = (config.get("world_model") or {}).get("depth_head") or {}
    if "center_frac" in dh_cfg:
        center_frac = float(dh_cfg["center_frac"])

    episodes = ds.load_dataset(dataset, skip_quarantined=True)
    rows: List[Dict[str, Any]] = []
    gaps: List[Dict[str, Any]] = []
    n_skip_depth = 0
    n_skip_no_gt = 0
    stride = max(1, int(args.stride))

    for ep_i, ep in enumerate(episodes):
        if len(rows) >= int(args.max_samples):
            break
        if not ep:
            continue
        for t_i in range(0, len(ep), stride):
            if len(rows) >= int(args.max_samples):
                break
            tr = ep[t_i]
            d0 = center_depth_m(tr.obs)
            if d0 is not None and d0 > float(args.max_center_depth_m):
                n_skip_depth += 1
                continue
            if getattr(tr.obs, "depth", None) is None:
                n_skip_no_gt += 1
                continue

            arm_scores = score_oracle_arms_at_t(
                ep,
                t_i,
                horizon=horizon,
                d_thresh_m=float(args.d_thresh_m),
                center_frac=center_frac,
            )
            g = oracle_pairwise_gaps(arm_scores)
            gaps.append(g)
            rows.append({
                "episode_idx": int(ep_i),
                "t_idx": int(t_i),
                "center_depth_m": round(float(d0), 3) if d0 is not None else None,
                "oracle_horizon": horizon,
                "arms": arm_scores,
                "gaps": {
                    kk: (vv if isinstance(vv, str) else round(float(vv), 6))
                    for kk, vv in g.items()
                },
            })

    verdict = verdict_from_oracle_gaps(
        gaps, high_ceiling_gap=float(args.high_ceiling_gap),
    )
    payload = {
        "step": "B_prime_4",
        "dataset": str(dataset),
        "config": str(cfg_path),
        "horizon": horizon,
        "d_thresh_m": float(args.d_thresh_m),
        "center_frac": center_frac,
        "n_scored": len(rows),
        "n_skip_depth": n_skip_depth,
        "n_skip_no_gt": n_skip_no_gt,
        "max_center_depth_m": float(args.max_center_depth_m),
        "stride": stride,
        "method_note": (
            "GT depth on recorded path over H steps; per-arm cone forward/left/right "
            "min < d_thresh. Not counterfactual lateral motion GT."
        ),
        "verdict": verdict,
        "per_z0": rows,
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"out": str(out_path), "verdict": verdict}, ensure_ascii=False, indent=2))
    return 0 if rows else 2


if __name__ == "__main__":
    raise SystemExit(main())
