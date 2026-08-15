"""V1 three-signal gate entrypoint (frozen spec §V1).

Mirrors ``_v0_gate`` split/merge workflow:

    # metric self-check (no GPU):
    python -m experiments.aerial.rl._v1_gate --self-check

    # merge partials from H100 (②, ③) + 4090 (①):
    python -m experiments.aerial.rl._v1_gate --merge \\
        v1_partial_coll.json v1_partial_wm.json v1_partial_tau_depth.json

Does **not** flip yaml — human action only after authoritative merge exits 0.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from experiments.aerial.rl import v1_metrics as metrics

_ALL_SIGNALS = ("1", "2", "3")


def _parse_signals(spec: Optional[str]) -> set[str]:
    if not spec:
        return set(_ALL_SIGNALS)
    req = {s.strip() for s in spec.split(",") if s.strip()}
    bad = req - set(_ALL_SIGNALS)
    if bad:
        raise SystemExit(f"[v1-gate] --signals: unknown {sorted(bad)}; pick from 1,2,3")
    if not req:
        raise SystemExit("[v1-gate] --signals: empty selection")
    return req


def _merge_partials(paths: List[Path]) -> Dict[str, Any]:
    signals: Dict[str, Any] = {}
    for pth in paths:
        blob = json.loads(pth.read_text())
        part = blob.get("signals") or blob.get("details") or {}
        for k, v in part.items():
            if k in signals:
                print(f"[v1-gate] WARN: signal {k} in multiple partials; {pth} wins",
                      file=sys.stderr)
            signals[k] = v
    return signals


def assemble_verdict(s1: Dict[str, Any], s2: Dict[str, Any], s3: Dict[str, Any]) -> Dict[str, Any]:
    return metrics.aggregate_v1_verdict({"1": s1, "2": s2, "3": s3})


def _emit(obj: Dict[str, Any], path: Optional[str]) -> None:
    text = json.dumps(obj, indent=2, default=str)
    print(text)
    if path:
        Path(path).write_text(text + "\n")
        print(f"[v1-gate] wrote {path}", file=sys.stderr)


def _self_check() -> int:
    s1 = metrics.check_collision_reduction(0.10, 0.07, delta=0.20)
    s2 = metrics.check_wm_fidelity({"ok": True, "reward_ok": True})
    s3 = metrics.check_dual_channel_independence(
        np.array([True, False, True, False]),
        np.array([False, True, False, False]),
    )
    verdict = assemble_verdict(s1, s2, s3)
    if not verdict["ok"]:
        print("[v1-gate] self-check FAIL", file=sys.stderr)
        _emit(verdict, None)
        return 1
    print("[v1-gate] self-check PASS")
    return 0


def _signal3_from_dataset(
    dataset_root: Path,
    *,
    min_depth_m: float,
    min_tau_s: float,
    max_frames: int = 5000,
) -> Dict[str, Any]:
    from experiments.aerial.rl import dataset as ds
    from experiments.aerial.rl.tau_predictor import gt_tau_from_depth_velocity

    root = dataset_root.expanduser().resolve()
    episodes = ds.load_dataset(root)
    depth_breach: List[bool] = []
    tau_breach: List[bool] = []
    for ep in episodes:
        for tr in ep:
            obs = tr.obs
            if obs.depth is None:
                continue
            d_hat = obs.info.get("depth_min_pred")
            if d_hat is None:
                from experiments.aerial.rl.depth_geometry import forward_min_depth
                d_hat = forward_min_depth(obs.depth, center_frac=0.5)
            tau = obs.info.get("tau_pred")
            if tau is None:
                tau = gt_tau_from_depth_velocity(obs.depth, obs)
            if d_hat is None or tau is None:
                continue
            depth_breach.append(float(d_hat) < min_depth_m)
            tau_breach.append(float(tau) < min_tau_s)
            if len(depth_breach) >= max_frames:
                break
        if len(depth_breach) >= max_frames:
            break
    if not depth_breach:
        return {"ok": False, "reason": "no depth frames with τ/D̂ fields"}
    return metrics.check_dual_channel_independence(
        np.asarray(depth_breach, dtype=bool),
        np.asarray(tau_breach, dtype=bool),
        phase="proxy",
    )


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="V1 three-signal gate (frozen spec §V1)")
    p.add_argument("--self-check", action="store_true")
    p.add_argument("--merge", nargs="+", default=None, metavar="JSON")
    p.add_argument("--emit", default=None, help="write verdict JSON")
    p.add_argument("--signals", default=None, help="subset: 1,2,3")
    p.add_argument("--dataset", default=None, help="for offline signal 3")
    p.add_argument("--v0-coll-rate", type=float, default=None, help="V0 baseline for signal 1")
    p.add_argument("--v1-coll-rate", type=float, default=None, help="V1 measured coll rate")
    p.add_argument("--fidelity-json", default=None, help="wm_eval fidelity verdict blob")
    p.add_argument("--min-depth-m", type=float, default=1.5)
    p.add_argument("--min-tau-s", type=float, default=1.0)
    args = p.parse_args(argv)

    if args.self_check:
        return _self_check()

    if args.merge:
        signals = _merge_partials([Path(x) for x in args.merge])
        missing = [k for k in _ALL_SIGNALS if k not in signals]
        if missing:
            print(f"[v1-gate] merge missing signals {missing}", file=sys.stderr)
            return 2
        verdict = metrics.aggregate_v1_verdict({k: signals[k] for k in _ALL_SIGNALS})
        verdict["merged_from"] = [str(x) for x in args.merge]
        _emit(verdict, args.emit)
        return 0 if verdict["ok"] else 1

    wanted = _parse_signals(args.signals)
    signals: Dict[str, Any] = {}

    if "1" in wanted:
        if args.v0_coll_rate is None or args.v1_coll_rate is None:
            signals["1"] = {"ok": False, "reason": "need --v0-coll-rate and --v1-coll-rate"}
        else:
            signals["1"] = metrics.check_collision_reduction(args.v0_coll_rate, args.v1_coll_rate)

    if "2" in wanted:
        if not args.fidelity_json:
            signals["2"] = {"ok": False, "reason": "need --fidelity-json from _wm_fidelity_eval"}
        else:
            blob = json.loads(Path(args.fidelity_json).read_text())
            signals["2"] = metrics.check_wm_fidelity(
                blob.get("verdict") or blob,
                agg=blob.get("agg"),
                recon_growth_ok=(blob.get("verdict") or blob).get("recon_growth_ok"),
            )

    if "3" in wanted:
        if not args.dataset:
            signals["3"] = {"ok": False, "reason": "need --dataset for dual-channel eval"}
        else:
            signals["3"] = _signal3_from_dataset(
                Path(args.dataset),
                min_depth_m=float(args.min_depth_m),
                min_tau_s=float(args.min_tau_s),
            )

    partial_ok = all(signals[k].get("ok") is True for k in wanted)
    out = {
        "partial": True,
        "signals_requested": sorted(wanted),
        "ok": partial_ok,
        "signals": signals,
    }
    _emit(out, args.emit)
    return 0 if partial_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
