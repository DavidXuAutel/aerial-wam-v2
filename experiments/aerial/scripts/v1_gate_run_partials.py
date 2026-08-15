#!/usr/bin/env python3
"""Run V1 gate partials and emit JSON (H100 offline + 4090 rollout).

Usage (H100, from repo root with venv + cuda):
  python experiments/aerial/scripts/v1_gate_run_partials.py h100 \\
    --repo ~/aerial-wam-v2 \\
    --dataset ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_local_depth_r60_20260814 \\
    --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_v1a_20260815/wm_step_500.pt \\
    --out-dir experiments/aerial/rl/artifacts/v1_gate_r60_20260815

Usage (4090, renderer @ 127.0.0.1:41451):
  python experiments/aerial/scripts/v1_gate_run_partials.py rollout4090 \\
    --repo ~/aerial-wam-v2 \\
    --config configs/aerial_rl.yaml \\
    --rollout-dataset experiments/aerial/rl/artifacts/dataset_v0_local_depth_r60_20260814 \\
    --depth-ckpt experiments/aerial/rl/artifacts/depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt \\
    --v0-coll-rate 0.125 \\
    --out-dir experiments/aerial/rl/artifacts/v1_gate_r60_20260815
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def _repo_root(explicit: Optional[str]) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    return Path(__file__).resolve().parents[3]


def _emit(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")
    print(f"[v1-run] wrote {path}")


def run_h100(args: argparse.Namespace) -> int:
    root = _repo_root(args.repo)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    out_dir = Path(args.out_dir).expanduser()
    if not out_dir.is_absolute():
        out_dir = root / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    dataset = Path(args.dataset).expanduser()
    results: Dict[str, Any] = {"host": "h100", "dataset": str(dataset)}

    # --- Signal 3: dual-channel independence (offline) ---
    from experiments.aerial.rl._v1_gate import _signal3_from_dataset

    s3 = _signal3_from_dataset(
        dataset,
        min_depth_m=float(args.min_depth_m),
        min_tau_s=float(args.min_tau_s),
    )
    partial3 = {"partial": True, "signals_requested": ["3"], "ok": bool(s3.get("ok")), "signals": {"3": s3}}
    _emit(out_dir / "v1_partial_3_r60_20260815.json", partial3)
    results["signal3"] = s3

    # --- Signal 2: WM fidelity (held-out) ---
    s2: Dict[str, Any]
    try:
        import torch  # noqa: F401
        from experiments.aerial.rl import dataset as ds
        from experiments.aerial.rl import wm_eval
        from experiments.aerial.rl._wm_fidelity_eval import (
            _heldout_split,
            _make_windows,
            _recon_curve,
        )
        from experiments.aerial.rl._wm_train_validate import _load_world_model_cfg, _refuse_v0
        from experiments.aerial.rl.dynamics_torch import TorchRSSMDynamics

        ckpt = Path(args.wm_ckpt).expanduser()
        if not ckpt.is_absolute():
            ckpt = root / ckpt
        cfg_path = root / args.config
        wm_cfg = _load_world_model_cfg(cfg_path)
        wm_cfg.setdefault("device", args.device)
        _refuse_v0(dataset, False)
        episodes = ds.load_dataset(dataset, skip_quarantined=True)
        held = _heldout_split(episodes, float(args.heldout_frac))
        windows = _make_windows(held, int(args.horizon), int(args.n_starts))
        sample_obs = held[0][0].obs
        wm_cfg["image_size"] = int(__import__("numpy").asarray(sample_obs.rgb).shape[0])
        model = TorchRSSMDynamics.from_config(wm_cfg)
        payload = model.load_checkpoint(ckpt)
        out = wm_eval.evaluate(model, windows, horizon=int(args.horizon))
        agg, verdict = out["agg"], out["verdict"]
        recon = _recon_curve(model, windows, int(args.horizon))
        passed = bool(verdict["passed"] and recon["recon_growth_ok"])
        fidelity_blob = {
            "verdict": {**verdict, "passed": passed, "recon_growth_ok": recon["recon_growth_ok"]},
            "agg": agg,
            "recon": recon,
            "ckpt": str(ckpt),
            "ckpt_step": payload.get("step"),
            "heldout_frac": float(args.heldout_frac),
        }
        _emit(out_dir / "v1_fidelity_r60_20260815.json", fidelity_blob)
        from experiments.aerial.rl import v1_metrics

        s2 = v1_metrics.check_wm_fidelity(fidelity_blob["verdict"])
        s2["fidelity_json"] = str(out_dir / "v1_fidelity_r60_20260815.json")
    except Exception as exc:
        s2 = {"ok": False, "reason": f"fidelity eval failed: {exc}"}

    partial2 = {"partial": True, "signals_requested": ["2"], "ok": bool(s2.get("ok")), "signals": {"2": s2}}
    _emit(out_dir / "v1_partial_2_r60_20260815.json", partial2)
    results["signal2"] = s2

    _emit(out_dir / "v1_h100_run_summary.json", results)
    ok = bool(s3.get("ok")) and bool(s2.get("ok"))
    print(f"[v1-run] H100 partials ok={ok} sig3={s3.get('ok')} sig2={s2.get('ok')}")
    return 0 if ok else 1


def _episode_collision_rate(collided: List[List[bool]]) -> float:
    if not collided:
        return float("nan")
    hits = sum(1 for ep in collided if any(ep))
    return float(hits / len(collided))


def run_rollout4090(args: argparse.Namespace) -> int:
    root = _repo_root(args.repo)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    import yaml

    from experiments.aerial.rl import v0_metrics as v0m
    from experiments.aerial.rl import v0_rollout_eval as rollout
    from experiments.aerial.rl import v1_metrics
    from experiments.aerial.rl.depth_predictor import DepthMinPredictor
    from experiments.aerial.rl.reward import RewardConfig
    from experiments.aerial.rl.safety import DepthTauShield, ThresholdSafetyShield
    from experiments.aerial.rl.tau_predictor import TauPredictor
    from experiments.aerial.rl.train_rl import HeuristicPolicy, _build_env

    out_dir = Path(args.out_dir).expanduser()
    if not out_dir.is_absolute():
        out_dir = root / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    cfg_path = root / args.config
    cfg = yaml.safe_load(cfg_path.read_text()) or {}
    env = _build_env(cfg.get("env", {}) or {})
    reward_cfg = RewardConfig(**(cfg.get("reward", {}) or {})) if cfg.get("reward") else None
    thr = v0m.DEFAULT_THRESHOLDS

    rollout_ds = Path(args.rollout_dataset).expanduser()
    if not rollout_ds.is_absolute():
        rollout_ds = root / rollout_ds
    depth_ckpt = Path(args.depth_ckpt).expanduser()
    if not depth_ckpt.is_absolute():
        depth_ckpt = root / depth_ckpt

    policy = HeuristicPolicy(goal_getter=lambda: getattr(env, "goal", None))
    from experiments.aerial.rl._v0_gate import _obstacle_candidate_positions

    cand, cand_yaw = _obstacle_candidate_positions(rollout_ds)
    starts, scan_diag = rollout.make_obstacle_facing_episodes(
        env, int(args.n_episodes), cand, seed=int(args.seed),
        candidate_yaws=cand_yaw,
        obstacle_max_m=25.0, center_frac=0.3,
        probe_policy=policy, probe_near_m=float(thr.near_collision_depth_m),
        probe_steps=40, reward_cfg=reward_cfg,
        preserve_order=True, max_scans=1000, log_every=20,
    )
    if not starts:
        s1 = {"ok": False, "reason": "no obstacle-facing starts", "scan": scan_diag}
        partial1 = {"partial": True, "signals_requested": ["1"], "ok": False, "signals": {"1": s1}}
        _emit(out_dir / "v1_partial_1_r60_20260815.json", partial1)
        return 1

    predictor = DepthMinPredictor.from_checkpoint(depth_ckpt, device=args.device)
    tau_pred = TauPredictor()

    def _run_v1_shield(shield_kind: str) -> Dict[str, Any]:
        collided_on: List[List[bool]] = []
        drop_stats: Dict[str, int] = {}
        for epi in starts:
            if hasattr(policy, "reset"):
                policy.reset()
            if shield_kind == "depth_tau":
                shield = DepthTauShield(
                    min_depth_m=float(cfg.get("safety", {}).get("min_depth_m", 1.5)),
                    min_tau_s=float(cfg.get("safety", {}).get("min_tau_s", 1.0)),
                )
            else:
                shield = ThresholdSafetyShield(
                    min_depth_m=float(cfg.get("safety", {}).get("min_depth_m", 1.5)),
                    min_tau_s=float(cfg.get("safety", {}).get("min_tau_s", 1.0)),
                )
            ep = rollout._run_one_resilient(
                env, policy, epi, max_steps=int(args.max_steps), reward_cfg=reward_cfg,
                shield=shield, depth_predictor=predictor, tau_predictor=tau_pred,
                drop_stats=drop_stats,
            )
            if ep is None:
                continue
            m = rollout._episode_masks(ep, near_collision_depth_m=float(thr.near_collision_depth_m))
            collided_on.append(m["collided"])
        rate = _episode_collision_rate(collided_on)
        return {
            "collision_rate": rate,
            "n_episodes": len(collided_on),
            "drop_stats": drop_stats,
            "shield_kind": shield_kind,
        }

    v0_stats = _run_v1_shield("threshold")
    v1_stats = _run_v1_shield("depth_tau")
    v0_rate = float(v0_stats["collision_rate"])
    v1_rate = float(v1_stats["collision_rate"])
    if args.v0_coll_rate is not None:
        v0_rate = float(args.v0_coll_rate)
    s1 = v1_metrics.check_collision_reduction(v0_rate, v1_rate)
    s1["v0_measured"] = v0_stats
    s1["v1_measured"] = v1_stats
    s1["scan"] = scan_diag

    partial1 = {"partial": True, "signals_requested": ["1"], "ok": bool(s1.get("ok")), "signals": {"1": s1}}
    _emit(out_dir / "v1_partial_1_r60_20260815.json", partial1)
    print(f"[v1-run] 4090 signal1 ok={s1.get('ok')} v0={v0_rate:.4f} v1={v1_rate:.4f}")
    return 0 if s1.get("ok") else 1


def run_merge(args: argparse.Namespace) -> int:
    root = _repo_root(args.repo)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from experiments.aerial.rl._v1_gate import _merge_partials, assemble_verdict

    out_dir = Path(args.out_dir).expanduser()
    if not out_dir.is_absolute():
        out_dir = root / out_dir
    paths = [
        out_dir / "v1_partial_1_r60_20260815.json",
        out_dir / "v1_partial_2_r60_20260815.json",
        out_dir / "v1_partial_3_r60_20260815.json",
    ]
    for p in paths:
        if not p.exists():
            print(f"[v1-run] missing {p}", file=sys.stderr)
            return 2
    signals = _merge_partials(paths)
    verdict = assemble_verdict(signals["1"], signals["2"], signals["3"])
    verdict["merged_from"] = [str(p) for p in paths]
    out = out_dir / "v1_gate_r60_20260815.json"
    _emit(out, verdict)
    return 0 if verdict.get("ok") else 1


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("h100", "rollout4090", "merge"))
    p.add_argument("--repo", default=None)
    p.add_argument("--out-dir", default="experiments/aerial/rl/artifacts/v1_gate_r60_20260815")
    p.add_argument("--dataset", default="~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_local_depth_r60_20260814")
    p.add_argument("--wm-ckpt", default="experiments/aerial/rl/artifacts/wm_ckpt_v1a_20260815/wm_step_500.pt")
    p.add_argument("--config", default="configs/aerial_rl.yaml")
    p.add_argument("--device", default="cuda")
    p.add_argument("--heldout-frac", type=float, default=0.25)
    p.add_argument("--horizon", type=int, default=15)
    p.add_argument("--n-starts", type=int, default=1)
    p.add_argument("--min-depth-m", type=float, default=1.5)
    p.add_argument("--min-tau-s", type=float, default=1.0)
    p.add_argument("--rollout-dataset", default="experiments/aerial/rl/artifacts/dataset_v0_local_depth_r60_20260814")
    p.add_argument("--depth-ckpt", default="experiments/aerial/rl/artifacts/depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt")
    p.add_argument("--n-episodes", type=int, default=8)
    p.add_argument("--max-steps", type=int, default=200)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--v0-coll-rate", type=float, default=None)
    args = p.parse_args()
    if args.mode == "h100":
        return run_h100(args)
    if args.mode == "rollout4090":
        return run_rollout4090(args)
    return run_merge(args)


if __name__ == "__main__":
    raise SystemExit(main())
