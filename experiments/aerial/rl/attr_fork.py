"""5ai′ ATTR fork helpers (V4_5AIP_ATTR_20260826).

Outcome labels + percept-vs-plan fork on hard_coll windows.
GT clearance is expected as ``clearance_fov`` (AirSim depth-cam min at
control Hz, or offline pose-replay min). Do not slow the closed loop for GT.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

ATTR_ID = "V4_5AIP_ATTR_20260826"
PRE_COLL_N = 5
PERCEPT_OVERREAD = 0.25
PLAN_ABSREL = 0.15
MISS_GT_M = 1.5
MISS_FRAC = 0.50
N_HARD_MIN = 8
LABEL_MARGIN = 4


def classify_outcome(ep: Dict[str, Any]) -> str:
    """Mutually exclusive outcome with priority hard_coll > tau_latch > arrived > stuck_l3 > timeout."""
    steps = list(ep.get("steps") or [])
    hard = bool(ep.get("hard_coll")) or any(bool(s.get("collided")) for s in steps)
    if hard:
        return "hard_coll"
    tau_latch = any(bool(s.get("emergency_latched")) for s in steps) or any(
        "tau" in (s.get("shield_channels") or []) for s in steps
    )
    if tau_latch and not bool(ep.get("arrived")):
        return "tau_latch"
    if bool(ep.get("arrived")):
        return "arrived"
    if steps:
        n = len(steps)
        tail = steps[max(0, n - max(1, n // 5)) :]
        clears = [
            float(s["clearance_fov"])
            for s in tail
            if s.get("clearance_fov") is not None and np.isfinite(float(s["clearance_fov"]))
        ]
        if clears and float(np.median(clears)) <= MISS_GT_M:
            return "stuck_l3"
    return "timeout"


def _collision_index(steps: Sequence[Dict[str, Any]]) -> Optional[int]:
    for i, s in enumerate(steps):
        if bool(s.get("collided")):
            return i
    return None


def hard_coll_window(
    steps: Sequence[Dict[str, Any]], *, n: int = PRE_COLL_N
) -> List[Dict[str, Any]]:
    idx = _collision_index(steps)
    if idx is None:
        return []
    lo = max(0, idx - int(n))
    return list(steps[lo:idx]) if idx > lo else list(steps[max(0, idx - 1) : idx])


def window_rel_errors(window: Sequence[Dict[str, Any]]) -> List[float]:
    """(d̂ − GT) / GT for steps with finite d̂ and GT>0."""
    out: List[float] = []
    for s in window:
        d_hat = s.get("d_hat_fovmin")
        gt = s.get("clearance_fov")
        if d_hat is None or gt is None:
            continue
        d = float(d_hat)
        g = float(gt)
        if not (np.isfinite(d) and np.isfinite(g) and g > 0):
            continue
        out.append((d - g) / g)
    return out


def label_hard_coll_ep(ep: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """Return (percept|plan|unclear, stats) for one hard_coll episode."""
    steps = list(ep.get("steps") or [])
    win = hard_coll_window(steps)
    rels = window_rel_errors(win)
    miss_n = 0
    miss_den = 0
    for s in win:
        gt = s.get("clearance_fov")
        if gt is None or not np.isfinite(float(gt)):
            continue
        miss_den += 1
        if float(gt) <= MISS_GT_M and not bool(s.get("emergency_latched")):
            miss_n += 1
    miss_frac = float(miss_n / miss_den) if miss_den else float("nan")
    med = float(np.median(rels)) if rels else float("nan")
    abs_med = float(np.median(np.abs(rels))) if rels else float("nan")
    stats = {
        "n_window": len(win),
        "n_rel": len(rels),
        "median_rel": round(med, 4) if np.isfinite(med) else None,
        "median_abs_rel": round(abs_med, 4) if np.isfinite(abs_med) else None,
        "miss_frac": round(miss_frac, 4) if np.isfinite(miss_frac) else None,
    }
    percept = (np.isfinite(med) and med >= PERCEPT_OVERREAD) or (
        np.isfinite(miss_frac) and miss_frac >= MISS_FRAC
    )
    plan = np.isfinite(abs_med) and abs_med <= PLAN_ABSREL
    if percept and not plan:
        return "percept", stats
    if plan and not percept:
        return "plan", stats
    if percept and plan:
        # Both predicates true → unclear (do not force a train path).
        return "unclear", stats
    return "unclear", stats


def decide_fork(episodes: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Apply ATTR-3/4 majority fork over hard_coll episodes."""
    outcomes = {c: 0 for c in ("hard_coll", "tau_latch", "arrived", "stuck_l3", "timeout")}
    n_percept = n_plan = n_unclear_hc = 0
    hc_detail: List[Dict[str, Any]] = []
    annotated: List[Dict[str, Any]] = []
    for ep in episodes:
        out = classify_outcome(ep)
        outcomes[out] = outcomes.get(out, 0) + 1
        row = {"idx": ep.get("idx"), "outcome": out}
        if out == "hard_coll":
            lab, stats = label_hard_coll_ep(ep)
            row["hard_coll_label"] = lab
            row["hard_coll_stats"] = stats
            if lab == "percept":
                n_percept += 1
            elif lab == "plan":
                n_plan += 1
            else:
                n_unclear_hc += 1
            hc_detail.append(row)
        annotated.append(row)

    n_hard = int(outcomes.get("hard_coll", 0))
    if n_hard < N_HARD_MIN:
        label = "unclear"
        reason = f"n_hard_coll={n_hard} < {N_HARD_MIN}"
    elif abs(n_percept - n_plan) < LABEL_MARGIN:
        label = "unclear"
        reason = f"|n_percept-n_plan|={abs(n_percept - n_plan)} < {LABEL_MARGIN}"
    elif n_percept > n_plan:
        label = "percept"
        reason = "majority_percept"
    else:
        label = "plan"
        reason = "majority_plan"

    next_action = {
        "percept": "sign_depth_ft_declare",
        "plan": "sign_wm_corpus_declare",
        "unclear": "stop_no_train",
    }[label]

    return {
        "attr_id": ATTR_ID,
        "label": label,
        "reason": reason,
        "next_action": next_action,
        "n_percept": n_percept,
        "n_plan": n_plan,
        "n_unclear_hard_coll": n_unclear_hc,
        "n_hard_coll": n_hard,
        "outcomes": outcomes,
        "episodes": annotated,
        "hc_detail": hc_detail,
        "gt_source_note": (
            "clearance_fov = AirSim depth-camera min at control Hz "
            "(same-rate GT; not a separate slow GT query). "
            "Offline pose-replay may attach under gt_replay if available."
        ),
    }
