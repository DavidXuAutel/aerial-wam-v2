"""V1 three-signal gate metrics (frozen spec §V1)."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Mapping, Optional

import numpy as np


@dataclass(frozen=True)
class V1GateThresholds:
    """Draft thresholds — re-freeze before declaring authoritative V1 PASS."""

    collision_reduction_delta: float = 0.20
    dual_channel_max_both_fail_frac: float = 0.35
    tau_mae_max_s: float = 2.0


DEFAULT_V1_THRESHOLDS = V1GateThresholds()


def check_collision_reduction(
    v0_coll_rate: float,
    v1_coll_rate: float,
    *,
    delta: float = DEFAULT_V1_THRESHOLDS.collision_reduction_delta,
) -> Dict[str, Any]:
    """V1-①: collision rate must drop relative to the frozen V0 baseline."""
    if not np.isfinite(v0_coll_rate) or v0_coll_rate <= 0:
        return {
            "ok": False,
            "reason": "invalid v0_coll_rate baseline",
            "v0_coll_rate": v0_coll_rate,
            "v1_coll_rate": v1_coll_rate,
        }
    target = float(v0_coll_rate * (1.0 - delta))
    ok = bool(np.isfinite(v1_coll_rate) and v1_coll_rate <= target)
    return {
        "ok": ok,
        "v0_coll_rate": float(v0_coll_rate),
        "v1_coll_rate": float(v1_coll_rate),
        "target_max": target,
        "delta": float(delta),
    }


def check_wm_fidelity(signal: Mapping[str, Any]) -> Dict[str, Any]:
    """V1-②: wrap ``wm_eval.fidelity_verdict`` output."""
    ok = signal.get("ok") is True
    return {"ok": ok, **dict(signal)}


def check_dual_channel_independence(
    depth_breach: np.ndarray,
    tau_breach: np.ndarray,
    *,
    max_both_fail_frac: float = DEFAULT_V1_THRESHOLDS.dual_channel_max_both_fail_frac,
) -> Dict[str, Any]:
    """V1-③: τ and D̂ triggers must not collapse to the same failure set."""
    d = np.asarray(depth_breach, dtype=bool).reshape(-1)
    t = np.asarray(tau_breach, dtype=bool).reshape(-1)
    if d.shape != t.shape:
        return {"ok": False, "reason": "depth/tau breach arrays differ in length"}
    n = int(d.size)
    if n == 0:
        return {"ok": False, "reason": "empty breach arrays"}

    both = d & t
    depth_only = d & ~t
    tau_only = t & ~d
    neither = ~d & ~t
    both_frac = float(np.mean(both))
    ok = bool(both_frac <= max_both_fail_frac and (depth_only.any() or tau_only.any()))
    return {
        "ok": ok,
        "n": n,
        "both_fail_frac": both_frac,
        "both_fail_max": float(max_both_fail_frac),
        "depth_only_frac": float(np.mean(depth_only)),
        "tau_only_frac": float(np.mean(tau_only)),
        "neither_frac": float(np.mean(neither)),
        "both_fail_indices": np.flatnonzero(both).tolist()[:32],
    }


def aggregate_v1_verdict(results: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    keys = ("1", "2", "3")
    missing = [k for k in keys if k not in results]
    if missing:
        return {"ok": False, "passed": {}, "reason": f"missing signals {missing}"}
    bad_type = [k for k in keys if not isinstance(results[k].get("ok"), bool)]
    if bad_type:
        return {
            "ok": False,
            "passed": {},
            "details": dict(results),
            "reason": f"signals {bad_type} have a non-bool 'ok'",
        }
    passed = {k: results[k].get("ok") is True for k in keys}
    return {
        "ok": all(passed.values()),
        "passed": passed,
        "thresholds": asdict(DEFAULT_V1_THRESHOLDS),
        "details": dict(results),
    }
