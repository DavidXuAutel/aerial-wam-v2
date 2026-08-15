"""Time-to-contact (τ) predictor — V1b [1d] scaffold.

Phase 1 (this module): **depth + closing-velocity proxy** on the forward cone.
Independent of ``depth_min_pred`` / ``D̂`` trigger path: uses τ = d_fwd / v_close
with v_close from proprio velocity projected onto body-forward.

Phase 2 (future): optical-flow FOE + divergence per pure-vision design §4.1d.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from experiments.aerial.rl.depth_geometry import forward_min_depth
from experiments.aerial.rl.env.obs import Observation

DEFAULT_MIN_CLOSING_M_S = 0.05
DEFAULT_MAX_TAU_S = 60.0


def closing_speed_m_s(obs: Observation) -> float:
    """Body-forward closing speed (m/s) from world velocity and yaw."""
    st = np.asarray(obs.state, dtype=np.float64).reshape(-1)
    vx, vy, yaw = float(st[3]), float(st[4]), float(st[6])
    fx, fy = float(np.cos(yaw)), float(np.sin(yaw))
    v_fwd = vx * fx + vy * fy
    return max(v_fwd, 0.0)


def gt_tau_from_depth_velocity(
    depth: np.ndarray,
    obs: Observation,
    *,
    center_frac: float = 0.5,
    min_closing_m_s: float = DEFAULT_MIN_CLOSING_M_S,
    max_tau_s: float = DEFAULT_MAX_TAU_S,
) -> Optional[float]:
    """Supervision / sim-only τ from GT depth + proprio (m/s → s)."""
    d_fwd = forward_min_depth(depth, center_frac=center_frac)
    if not np.isfinite(d_fwd) or d_fwd <= 0:
        return None
    v = closing_speed_m_s(obs)
    if v < min_closing_m_s:
        return max_tau_s
    return float(min(d_fwd / v, max_tau_s))


@dataclass
class TauPredictor:
    """Populate ``obs.info['tau_pred']`` for the τ leg of ``ThresholdSafetyShield``."""

    center_frac: float = 0.5
    min_closing_m_s: float = DEFAULT_MIN_CLOSING_M_S
    max_tau_s: float = DEFAULT_MAX_TAU_S
    use_gt_depth: bool = True

    def predict_tau(self, obs: Observation) -> Optional[float]:
        if not self.use_gt_depth or obs.depth is None:
            return None
        return gt_tau_from_depth_velocity(
            obs.depth,
            obs,
            center_frac=self.center_frac,
            min_closing_m_s=self.min_closing_m_s,
            max_tau_s=self.max_tau_s,
        )
