"""Adaptive Subgoal Generator — Phase 2 mainline (design v1.0 / plan Task 1–2).

Mainline only:
1. True orthogonal polyline projection (CTE / carrot); monotone lock for progress only
2. Clearance / curvature adaptive lookahead (10 m/s cruise envelope)
3. CTE recovery: when cross-track error > 5 m, shrink lookahead to re-enter
4. CTE lock freeze: when CTE > cte_lock_freeze_m, roll s_progress back to true arc-s
5. Curvature+clearance speed governor aligned with ThreeZone creep floor
6. SE(3) body-relative g_rel = [dx_b, dy_b, dz_b, dist]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

import numpy as np


def compute_polyline_cum_lengths(points: np.ndarray) -> Tuple[np.ndarray, float]:
    pts = np.asarray(points, dtype=np.float64)
    if len(pts) < 2:
        return np.array([0.0], dtype=np.float64), 0.0
    seg_lens = np.linalg.norm(pts[1:] - pts[:-1], axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg_lens)])
    return cum, float(cum[-1])


def point_at_arc_length(
    points: np.ndarray,
    s: float,
    cum_lengths: Optional[np.ndarray] = None,
) -> np.ndarray:
    pts = np.asarray(points, dtype=np.float64)
    if len(pts) == 0:
        return np.zeros(3, dtype=np.float64)
    if len(pts) == 1:
        return pts[0].copy()
    if cum_lengths is None:
        cum_lengths, total = compute_polyline_cum_lengths(pts)
    else:
        total = float(cum_lengths[-1])
    s = float(np.clip(s, 0.0, total))
    if s <= 0.0:
        return pts[0].copy()
    if s >= total:
        return pts[-1].copy()
    idx = int(np.searchsorted(cum_lengths, s, side="right") - 1)
    idx = max(0, min(idx, len(pts) - 2))
    s0, s1 = float(cum_lengths[idx]), float(cum_lengths[idx + 1])
    seg = s1 - s0
    if seg < 1e-6:
        return pts[idx].copy()
    t = (s - s0) / seg
    return pts[idx] + t * (pts[idx + 1] - pts[idx])


def nearest_on_polyline(
    pos: np.ndarray,
    path_points: np.ndarray,
) -> Tuple[np.ndarray, int, float, float]:
    """True orthogonal projection onto the polyline (no monotone lock)."""
    points = np.asarray(path_points, dtype=np.float64)
    pos = np.asarray(pos, dtype=np.float64)
    n_pts = len(points)
    assert n_pts >= 2, "Path must have at least 2 points"

    cum_lengths, total_length = compute_polyline_cum_lengths(points)
    seg_vectors = points[1:] - points[:-1]
    seg_lengths = cum_lengths[1:] - cum_lengths[:-1]

    best_dist_sq = float("inf")
    best_proj = points[0].copy()
    best_seg = 0
    best_s = 0.0

    for i in range(n_pts - 1):
        p0 = points[i]
        v = seg_vectors[i]
        l = float(seg_lengths[i])
        if l < 1e-6:
            continue
        v_norm = v / l
        t = float(np.clip(np.dot(pos - p0, v_norm) / l, 0.0, 1.0))
        proj_pt = p0 + t * v
        dist_sq = float(np.sum((pos - proj_pt) ** 2))
        s_candidate = float(cum_lengths[i] + t * l)
        if dist_sq < best_dist_sq:
            best_dist_sq = dist_sq
            best_proj = proj_pt
            best_seg = i
            best_s = s_candidate

    rem_dist = max(0.0, total_length - float(best_s))
    return best_proj, best_seg, float(best_s), rem_dist


def project_to_polyline(
    pos: np.ndarray,
    path_points: np.ndarray,
    prev_s_max: float = 0.0,
) -> Tuple[np.ndarray, int, float, float]:
    """Project onto polyline with monotonic arc-length lock (legacy helper).

    For control / CTE, prefer :func:`nearest_on_polyline` +
    :class:`AdaptiveSubgoalGenerator` freeze logic — locked arc points must not
    redefine cross-track error.
    """
    points = np.asarray(path_points, dtype=np.float64)
    true_proj, true_seg, true_s, _rem = nearest_on_polyline(pos, points)
    cum_lengths, total_length = compute_polyline_cum_lengths(points)
    s_monotone = max(float(prev_s_max), float(true_s))
    rem_dist = max(0.0, total_length - s_monotone)
    if s_monotone > true_s + 1e-6:
        locked_proj = point_at_arc_length(points, s_monotone, cum_lengths=cum_lengths)
        locked_seg = int(np.searchsorted(cum_lengths, s_monotone, side="right") - 1)
        locked_seg = max(0, min(locked_seg, len(points) - 2))
        return locked_proj, locked_seg, s_monotone, rem_dist
    return true_proj, true_seg, s_monotone, rem_dist


def sample_point_along_polyline(
    path_points: np.ndarray,
    segment_idx: int,
    proj_point: np.ndarray,
    r_lookahead: float,
) -> np.ndarray:
    """Walk forward along polyline by r_lookahead from proj_point (mainline)."""
    points = np.asarray(path_points, dtype=np.float64)
    n_pts = len(points)
    rem_r = float(r_lookahead)
    curr_pt = np.asarray(proj_point, dtype=np.float64).copy()
    for i in range(max(0, segment_idx), n_pts - 1):
        p_next = points[i + 1]
        v = p_next - curr_pt
        d = float(np.linalg.norm(v))
        if d >= rem_r:
            if d < 1e-6:
                return p_next.copy()
            return curr_pt + (rem_r / d) * v
        rem_r -= d
        curr_pt = p_next.copy()
    return points[-1].copy()


@dataclass
class AdaptiveSubgoalGenerator:
    """Mainline adaptive carrot + clearance/curvature governor (design defaults)."""

    r_base: float = 55.0
    r_min: float = 20.0
    d_clear: float = 22.0
    d_danger: float = 3.0
    cruise_speed: float = 10.0
    cte_reentry_m: float = 5.0  # design §3.3.2
    #: When CTE exceeds this, roll progress lock back to true arc-s (anti Prog inflate).
    cte_lock_freeze_m: float = 5.0
    a_lat_max: float = 2.5  # lateral accel budget for curvature speed limit
    min_creep_speed: float = 0.2  # align with ThreeZone v_stop (not a 4 m/s floor)
    #: When rem_dist falls below this, force terminal creep (F12; ~2 steps @ 5 Hz × 10 m/s)
    terminal_creep_rem_m: float = 8.0
    _prev_s_max: float = field(default=0.0, init=False, repr=False)

    def reset(self) -> None:
        self._prev_s_max = 0.0

    def compute_subgoal(
        self,
        curr_pos: np.ndarray,
        curr_yaw: float,
        global_path: np.ndarray,
        d_fwd_hat: Optional[float] = None,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        curr_pos = np.asarray(curr_pos, dtype=np.float64)
        global_path = np.asarray(global_path, dtype=np.float64)

        true_proj, true_seg, true_s, rem_true = nearest_on_polyline(curr_pos, global_path)
        cte = float(np.linalg.norm(curr_pos - true_proj))

        freeze = float(cte) > float(self.cte_lock_freeze_m)
        if freeze:
            # Honest progress: do not keep a stale forward lock while off the corridor.
            s_progress = float(true_s)
            self._prev_s_max = s_progress
        else:
            s_progress = max(float(self._prev_s_max), float(true_s))
            self._prev_s_max = s_progress

        # Control geometry always from true projection (carrot + CTE).
        proj_pt = true_proj
        seg_idx = int(true_seg)
        rem_dist = float(rem_true)

        # 1. Clearance α ∈ [0.4, 1] (design); near danger still shrinks R
        if d_fwd_hat is not None and np.isfinite(d_fwd_hat):
            alpha = float(
                np.clip(
                    (float(d_fwd_hat) - self.d_danger) / (self.d_clear - self.d_danger),
                    0.4,
                    1.0,
                )
            )
            d_fwd = float(d_fwd_hat)
        else:
            alpha = 1.0
            d_fwd = float("inf")

        # 2. Curvature β from upcoming segment turn
        beta = 1.0
        theta_turn = 0.0
        if seg_idx < len(global_path) - 2:
            v1 = global_path[seg_idx + 1] - global_path[seg_idx]
            v2 = global_path[seg_idx + 2] - global_path[seg_idx + 1]
            n1 = float(np.linalg.norm(v1[:2]))
            n2 = float(np.linalg.norm(v2[:2]))
            if n1 > 1e-3 and n2 > 1e-3:
                cos_theta = float(np.clip(np.dot(v1[:2], v2[:2]) / (n1 * n2), -1.0, 1.0))
                theta_turn = float(np.arccos(cos_theta))
                beta = float(np.cos(np.clip(theta_turn, 0.0, np.pi / 2.0) / 2.0))

        # 3. Lookahead R (design); CTE recovery shrinks R when off-track
        r_nominal = max(self.r_min, self.r_base * alpha * beta)
        if cte > self.cte_reentry_m:
            # Pull carrot closer for ~30–45° re-entry (design §3.3.2)
            r_nominal = min(r_nominal, max(self.r_min, cte / np.tan(np.deg2rad(35.0))))
        r_lookahead = min(rem_dist, r_nominal)

        target_world = sample_point_along_polyline(
            global_path, segment_idx=seg_idx, proj_point=proj_pt, r_lookahead=r_lookahead
        )

        # 4. Speed governor: clearance × curvature; κ from turn over chord ~R
        # v_lat = sqrt(a_lat / κ), κ ≈ θ / ds with ds ≈ max(r_lookahead, 1)
        ds = max(r_lookahead, 1.0)
        kappa = float(theta_turn) / ds
        v_curv = (
            float(np.sqrt(self.a_lat_max / max(kappa, 1e-6)))
            if kappa > 1e-4
            else self.cruise_speed
        )
        v_clear = self.cruise_speed * alpha * (beta ** 1.5)
        if d_fwd <= self.d_danger:
            v_clear = min(v_clear, self.min_creep_speed)
        elif d_fwd < self.d_clear:
            # Linear bleed toward creep between danger and clear
            t = (d_fwd - self.d_danger) / max(1e-6, self.d_clear - self.d_danger)
            v_clear = self.min_creep_speed + t * (self.cruise_speed - self.min_creep_speed)
            v_clear *= beta ** 1.5
        v_safe = float(
            np.clip(min(self.cruise_speed, v_clear, v_curv), self.min_creep_speed, self.cruise_speed)
        )
        # F12: bleed to creep as remaining arc length approaches the arrival ball
        # so 10 m/s @ 5 Hz (~2 m/step) cannot skip the 3 m∧3 m contract.
        if rem_dist <= float(self.terminal_creep_rem_m):
            t_term = float(
                np.clip(
                    rem_dist / max(1e-6, float(self.terminal_creep_rem_m)),
                    0.0,
                    1.0,
                )
            )
            v_term = self.min_creep_speed + t_term * (self.cruise_speed - self.min_creep_speed)
            v_safe = float(min(v_safe, v_term))

        # 5. Body-relative goal
        delta_w = target_world - curr_pos
        cos_y, sin_y = np.cos(curr_yaw), np.sin(curr_yaw)
        dx_b = cos_y * delta_w[0] + sin_y * delta_w[1]
        dy_b = -sin_y * delta_w[0] + cos_y * delta_w[1]
        dz_b = delta_w[2]
        dist = float(np.linalg.norm(delta_w))
        g_rel_body = np.array([dx_b, dy_b, dz_b, dist], dtype=np.float32)

        info = {
            "s_progress": float(s_progress),
            "s_true": float(true_s),
            "rem_dist": rem_dist,
            "r_lookahead": r_lookahead,
            "alpha_clearance": alpha,
            "beta_curvature": beta,
            "cte_m": cte,
            "s_lock_frozen": bool(freeze),
            "safe_speed_limit": v_safe,
            "target_world": target_world.tolist(),
        }
        return g_rel_body, info
