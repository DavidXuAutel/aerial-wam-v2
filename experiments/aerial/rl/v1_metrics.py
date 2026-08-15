"""V1 three-signal gate metrics (frozen spec §V1)."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Mapping, Optional

import numpy as np


@dataclass(frozen=True)
class V1GateThresholds:
    """Re-freeze draft (design doc §1.2, 2026-08-15)."""

    collision_reduction_delta: float = 0.20
    dual_channel_max_both_fail_frac_proxy: float = 0.35
    dual_channel_max_both_fail_frac_auth: float = 0.20
    tau_mae_max_s: float = 2.0
    tau_only_min_frac: float = 0.005
    latent_norm_max: float = 25.0
    coll_auroc_min: float = 0.65
    coll_traj_min_for_auroc: int = 3
    n_eval_episodes: int = 8


DEFAULT_V1_THRESHOLDS = V1GateThresholds()


def check_wm_fidelity(
    signal: Mapping[str, Any],
    *,
    agg: Optional[Mapping[str, Any]] = None,
    recon_growth_ok: Optional[bool] = None,
    thr: V1GateThresholds = DEFAULT_V1_THRESHOLDS,
) -> Dict[str, Any]:
    """V1-②: wrap ``wm_eval.fidelity_verdict`` with coll N/A + latent cap (§1.2.2)."""
    reward_ok = signal.get("reward_ok") is True
    done_ok = signal.get("done_ok") is True
    recon_ok = (
        bool(recon_growth_ok)
        if recon_growth_ok is not None
        else signal.get("recon_growth_ok") is True
    )

    coll_ok: Optional[bool]
    coll_insufficient = False
    coll_traj_pos = None
    if agg is not None:
        coll_traj_pos = int(agg.get("coll_traj_pos", 0) or 0)
        au = agg.get("coll_auroc")
        if coll_traj_pos >= thr.coll_traj_min_for_auroc:
            coll_ok = bool(np.isfinite(au) and float(au) >= thr.coll_auroc_min)
        else:
            coll_ok = None
            coll_insufficient = coll_traj_pos < thr.coll_traj_min_for_auroc
    else:
        # Back-compat: raw verdict without agg — trust coll_ok if finite.
        raw = signal.get("coll_ok")
        coll_ok = bool(raw) if raw is not None else None

    latent_ok = True
    latent_norm_max = None
    if agg is not None and "latent_norm_max" in agg:
        latent_norm_max = float(agg["latent_norm_max"])
        latent_ok = bool(latent_norm_max <= thr.latent_norm_max)

    overall = bool(
        reward_ok
        and done_ok
        and recon_ok
        and latent_ok
        and coll_ok is not False
    )
    out: Dict[str, Any] = {
        **dict(signal),
        "ok": overall,
        "reward_ok": reward_ok,
        "done_ok": done_ok,
        "recon_growth_ok": recon_ok,
        "latent_ok": latent_ok,
        "coll_ok": coll_ok,
        "coll_insufficient": coll_insufficient,
    }
    if latent_norm_max is not None:
        out["latent_norm_max"] = latent_norm_max
    if coll_traj_pos is not None:
        out["coll_traj_pos"] = coll_traj_pos
    return out


def check_collision_reduction(
    v0_coll_rate: float,
    v1_coll_rate: float,
    *,
    delta: float = DEFAULT_V1_THRESHOLDS.collision_reduction_delta,
    shield_off_coll_rate: float | None = None,
) -> Dict[str, Any]:
    """V1-①: collision rate must drop relative to the frozen V0 baseline.

    When V0 shield-on rate is already at the zero floor on *collision-bearing*
    starts (``shield_off_coll_rate > 0``) and V1 is also zero, treat as PASS —
    there is no headroom for a δ reduction, and equality at the floor is not a
    vacuous open-air result (V0 partial_24 also had ``n_contact=0`` with
    shield-off collisions).
    """
    off = float(shield_off_coll_rate) if shield_off_coll_rate is not None else float("nan")
    if (not np.isfinite(v0_coll_rate) or v0_coll_rate <= 0) and np.isfinite(off) and off > 0:
        v1_ok = bool(np.isfinite(v1_coll_rate) and v1_coll_rate <= 0.0)
        return {
            "ok": v1_ok,
            "reason": "tied_zero_collision_bearing" if v1_ok else "v1_above_zero_floor",
            "v0_coll_rate": float(v0_coll_rate) if np.isfinite(v0_coll_rate) else 0.0,
            "v1_coll_rate": float(v1_coll_rate) if np.isfinite(v1_coll_rate) else v1_coll_rate,
            "target_max": 0.0,
            "delta": float(delta),
            "shield_off_coll_rate": off,
            "baseline_kind": "tied_zero_collision_bearing",
        }
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


def check_dual_channel_independence(
    depth_breach: np.ndarray,
    tau_breach: np.ndarray,
    *,
    max_both_fail_frac: float = DEFAULT_V1_THRESHOLDS.dual_channel_max_both_fail_frac_proxy,
    phase: str = "proxy",
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
        "phase": phase,
        "authoritative": phase == "auth",
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
    s3 = results.get("3", {})
    proxy_blocks_merge = (
        s3.get("ok") is True
        and s3.get("authoritative") is False
    )
    overall_ok = all(passed.values()) and not proxy_blocks_merge
    out: Dict[str, Any] = {
        "ok": overall_ok,
        "passed": passed,
        "thresholds": asdict(DEFAULT_V1_THRESHOLDS),
        "details": dict(results),
    }
    if proxy_blocks_merge:
        out["reason"] = "signal 3 proxy PASS is not merge-eligible (Phase 2 required)"
    return out
