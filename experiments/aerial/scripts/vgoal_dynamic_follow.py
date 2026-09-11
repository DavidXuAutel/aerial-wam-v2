"""Dynamic standoff follow helpers for Phase-2 vgoal M4."""
from __future__ import annotations

from typing import Any, Optional, Tuple

import numpy as np


def make_dynamic_tracker(
    *,
    standoff_dist_m: float = 6.0,
    standoff_height_m: float = 3.0,
    intercept_dist_m: float = 12.0,
    max_occlusion_s: float = 3.0,
) -> Any:
    from vgoal.dynamic_tracker import DynamicTargetTracker, DynamicTrackerConfig

    cfg = DynamicTrackerConfig(
        standoff_dist_m=float(standoff_dist_m),
        standoff_height_m=float(standoff_height_m),
        intercept_dist_thresh_m=float(intercept_dist_m),
        max_occlusion_s=float(max_occlusion_s),
    )
    return DynamicTargetTracker(cfg)


def dynamic_tracker_step(
    tracker: Any,
    measured_gr: Optional[np.ndarray],
    det_conf: float,
    pos: np.ndarray,
    yaw: float,
    dt: float,
    *,
    min_meas_conf: float = 0.12,
) -> Tuple[Any, Optional[np.ndarray]]:
    """Run one ``DynamicTargetTracker`` step; boost conf so open-vocab hits register."""
    from vgoal.dynamic_tracker import TrackingMode

    meas = None
    conf = float(det_conf)
    if measured_gr is not None:
        g = np.asarray(measured_gr, dtype=np.float64).reshape(-1)
        meas = [float(g[0]), float(g[1]), float(g[2]), float(g[3] if g.size > 3 else np.linalg.norm(g[:3]))]
        # DynamicTargetTracker gates updates at conf>=0.4
        conf = max(conf, float(min_meas_conf), 0.4)
    mode, goal_rel = tracker.step(meas, pos, yaw, float(dt), confidence=conf)
    if mode in (TrackingMode.SEARCHING, TrackingMode.LOST):
        return mode, None
    return mode, goal_rel
