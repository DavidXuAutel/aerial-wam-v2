"""GT-depth oracle collision ranking (runbook B′-4).

Diagnostic only: measures whether **recorded GT depth** along the flown path
separates forward vs lateral danger at the same sampling points as step B.

Uses the next ``H`` GT depth frames from each ``(episode, t)`` (not counterfactual
lateral motion — ceiling on *observable* geometry in the corpus).
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

import numpy as np

from experiments.aerial.rl.depth_geometry import cone_clearances, forward_min_depth

# Runbook B′-4: oracle_gap >= 0.3 ⇒ geometry separable in data.
ORACLE_HIGH_CEILING_GAP = 0.3


def _depth_from_obs(obs: Any) -> Optional[np.ndarray]:
    depth = getattr(obs, "depth", None)
    if depth is None:
        return None
    arr = np.asarray(depth, dtype=np.float64)
    if arr.ndim != 2 or arr.size == 0:
        return None
    return arr


def step_oracle_risks(
    depth: np.ndarray,
    *,
    d_thresh_m: float,
    center_frac: float,
) -> Dict[str, float]:
    """Per-frame forward / left / right binary risks from one GT depth map."""
    fwd_d = forward_min_depth(depth, center_frac=center_frac)
    cones = cone_clearances(depth, center_frac=center_frac)
    left_d = float(cones["left"])
    right_d = float(cones["right"])

    def _risk(d_m: float) -> float:
        return 1.0 if np.isfinite(d_m) and d_m < float(d_thresh_m) else 0.0

    fwd_risk = _risk(fwd_d)
    left_risk = _risk(left_d)
    right_risk = _risk(right_d)
    best_lat_name = "left" if left_risk <= right_risk else "right"
    return {
        "forward_risk": fwd_risk,
        "left_risk": left_risk,
        "right_risk": right_risk,
        "best_lateral": best_lat_name,
        "forward_min_m": float(fwd_d) if np.isfinite(fwd_d) else float("nan"),
        "left_min_m": float(left_d) if np.isfinite(left_d) else float("nan"),
        "right_min_m": float(right_d) if np.isfinite(right_d) else float("nan"),
    }


def score_oracle_arms_at_t(
    episode: Sequence[Any],
    t_idx: int,
    *,
    horizon: int,
    d_thresh_m: float,
    center_frac: float,
) -> Dict[str, Dict[str, float]]:
    """Mean oracle risk per arm over ``H`` recorded GT depth frames."""
    sums = {"forward": 0.0, "left": 0.0, "right": 0.0}
    n_valid = 0
    for dt in range(max(1, int(horizon))):
        j = int(t_idx) + dt
        if j >= len(episode):
            break
        depth = _depth_from_obs(episode[j].obs)
        if depth is None:
            continue
        row = step_oracle_risks(
            depth, d_thresh_m=float(d_thresh_m), center_frac=float(center_frac),
        )
        sums["forward"] += float(row["forward_risk"])
        sums["left"] += float(row["left_risk"])
        sums["right"] += float(row["right_risk"])
        n_valid += 1
    if n_valid == 0:
        nan = float("nan")
        return {
            k: {"mean_oracle_risk": nan, "n_steps": 0}
            for k in ("forward", "left", "right")
        }
    return {
        k: {"mean_oracle_risk": float(sums[k] / n_valid), "n_steps": n_valid}
        for k in ("forward", "left", "right")
    }


def oracle_risk_over_horizon(
    episode: Sequence[Any],
    t_idx: int,
    *,
    horizon: int,
    d_thresh_m: float,
    center_frac: float,
) -> Dict[str, Any]:
    """Legacy summary + per-step rows (forward vs best-lateral on each frame)."""
    per_step: List[Dict[str, Any]] = []
    risks_fwd: List[float] = []
    risks_lat: List[float] = []
    gaps: List[float] = []

    for dt in range(max(1, int(horizon))):
        j = int(t_idx) + dt
        if j >= len(episode):
            break
        depth = _depth_from_obs(episode[j].obs)
        if depth is None:
            continue
        row = step_oracle_risks(
            depth, d_thresh_m=float(d_thresh_m), center_frac=float(center_frac),
        )
        best_lat_risk = min(float(row["left_risk"]), float(row["right_risk"]))
        gap = float(row["forward_risk"]) - best_lat_risk
        risks_fwd.append(float(row["forward_risk"]))
        risks_lat.append(best_lat_risk)
        gaps.append(gap)
        per_step.append({"t_offset": dt, **row, "lateral_risk": best_lat_risk, "gap": gap})

    if not per_step:
        return {
            "n_steps": 0,
            "forward_oracle_risk": float("nan"),
            "lateral_oracle_risk": float("nan"),
            "p_coll_gap_forward_minus_lateral": float("nan"),
            "per_step": per_step,
        }

    return {
        "n_steps": len(per_step),
        "forward_oracle_risk": float(np.mean(risks_fwd)),
        "lateral_oracle_risk": float(np.mean(risks_lat)),
        "p_coll_gap_forward_minus_lateral": float(np.mean(gaps)),
        "per_step": per_step,
    }


def oracle_pairwise_gaps(arm_scores: Mapping[str, Mapping[str, float]]) -> Dict[str, Any]:
    """Same schema as :func:`imagine_coll_rank.pairwise_gaps` for oracle arms."""
    fwd = arm_scores["forward"]
    left = arm_scores["left"]
    right = arm_scores["right"]
    best_lat_name = "left" if left["mean_oracle_risk"] <= right["mean_oracle_risk"] else "right"
    best = arm_scores[best_lat_name]
    return {
        "best_lateral": best_lat_name,
        "p_coll_gap_forward_minus_lateral": float(
            fwd["mean_oracle_risk"] - best["mean_oracle_risk"]
        ),
        "forward_mean_oracle_risk": float(fwd["mean_oracle_risk"]),
        "lateral_mean_oracle_risk": float(best["mean_oracle_risk"]),
        "return_gap_lateral_minus_forward": 0.0,
    }


def verdict_from_oracle_gaps(
    gaps: Sequence[Mapping[str, float]],
    *,
    high_ceiling_gap: float = ORACLE_HIGH_CEILING_GAP,
) -> Dict[str, Any]:
    """Oracle ceiling verdict (not step-B pass/fail)."""
    if not gaps:
        return {
            "high_ceiling": False,
            "label": "insufficient_empty",
            "n_z0": 0,
            "median_oracle_gap": None,
            "note": "no z0 scored",
        }
    pc = np.asarray(
        [g["p_coll_gap_forward_minus_lateral"] for g in gaps], dtype=np.float64,
    )
    med = float(np.median(pc))
    high = med >= float(high_ceiling_gap)
    return {
        "high_ceiling": bool(high),
        "label": "high_ceiling" if high else "low_ceiling",
        "n_z0": int(len(gaps)),
        "median_oracle_gap": round(med, 6),
        "mean_oracle_gap": round(float(pc.mean()), 6),
        "threshold_high_ceiling": float(high_ceiling_gap),
        "note": (
            "GT 几何在采样上可分（WM coll 路径未学到）"
            if high
            else "采样/GT 上界也低 — 优先调 B 采样或更近障帧"
        ),
    }
