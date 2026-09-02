"""Path-tangent heading assist for Phase-2 deploy (R05 knife, 2026-09-01).

When cross-track error is still small but body heading has peeled away from the
polyline tangent, step_e π often translates on lateral ``g_rel`` instead of
yawing back — R05: cos(heading, tang) collapses 1→0 within ~10 steps while
``s_true`` stays 0; privileged rejoin (explicit yaw) still flies the corridor.

This assist only injects ``dyaw`` (and optionally attenuates body-lateral) when
``cte <= cte_max`` and ``cos(heading, tang) < cos_thr``. It does not replace π.
"""
from __future__ import annotations

import math
from typing import Optional, Tuple

import numpy as np


def _wrap_pi(a: float) -> float:
    return float((a + math.pi) % (2.0 * math.pi) - math.pi)


def path_tangent_yaw(path: np.ndarray, seg_idx: int) -> float:
    path = np.asarray(path, dtype=np.float64)
    i = int(np.clip(seg_idx, 0, max(0, len(path) - 2)))
    d = path[i + 1, :2] - path[i, :2]
    return float(math.atan2(float(d[1]), float(d[0])))


def apply_path_heading_assist(
    action: np.ndarray,
    *,
    yaw: float,
    path: np.ndarray,
    seg_idx: int,
    cte_m: float,
    limits: np.ndarray,
    cte_max_m: float = 8.0,
    cos_thr: float = 0.7,
    lateral_scale_when_misaligned: float = 0.25,
) -> Tuple[np.ndarray, bool, dict]:
    """Return (action', intervened, info)."""
    action = np.asarray(action, dtype=np.float64).reshape(4).copy()
    limits = np.asarray(limits, dtype=np.float64).reshape(4)
    info = {
        "heading_assist": False,
        "cos_heading_tang": float("nan"),
        "yaw_err_rad": float("nan"),
    }
    if not np.isfinite(cte_m) or float(cte_m) > float(cte_max_m):
        return action, False, info

    tang_yaw = path_tangent_yaw(path, seg_idx)
    err = _wrap_pi(tang_yaw - float(yaw))
    cos_h = float(math.cos(err))
    info["cos_heading_tang"] = cos_h
    info["yaw_err_rad"] = err
    if cos_h >= float(cos_thr):
        return action, False, info

    # Yaw toward tangent; clip to deploy box.
    dyaw_lim = float(limits[3])
    action[3] = float(np.clip(err, -dyaw_lim, dyaw_lim))
    # While badly misaligned (near-orthogonal+), don't translate sideways off-line.
    if cos_h < 0.3:
        action[1] *= float(lateral_scale_when_misaligned)
    info["heading_assist"] = True
    return action, True, info
