"""Non-polyline intent / subgoal outer loop (Phase-2 goal+scene nav).

Modes:
  * toward_g  — clip toward G at Phase-1 scale (E0 main)
  * direct_g  — raw far G into goal_rel (ablation A)
  * scene     — yaw-fan candidates + depth-aware score (E1)

No GT polyline. Stop / rem_dist semantics are Euclidean to G.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from experiments.aerial.rl.goal_features import goal_rel_body


def clip_toward_goal(
    curr_pos: np.ndarray,
    goal: np.ndarray,
    r_m: float,
) -> np.ndarray:
    """World-frame c*: at most ``r_m`` along the vector to G (or G if closer)."""
    p = np.asarray(curr_pos, dtype=np.float64).reshape(3)
    g = np.asarray(goal, dtype=np.float64).reshape(3)
    delta = g - p
    dist = float(np.linalg.norm(delta))
    r = float(max(1e-3, r_m))
    if dist <= r or dist < 1e-9:
        return g.copy()
    return p + delta * (r / dist)


def _safe_speed_from_depth(
    *,
    cruise_speed: float,
    min_creep_speed: float,
    d_danger: float,
    d_clear: float,
    d_fwd_hat: Optional[float],
    d_to_g: float,
    terminal_creep_rem_m: float = 8.0,
) -> float:
    v_safe = float(cruise_speed)
    if d_fwd_hat is not None and np.isfinite(float(d_fwd_hat)):
        d_fwd = float(d_fwd_hat)
        if d_fwd <= d_danger:
            v_safe = float(min_creep_speed)
        elif d_fwd < d_clear:
            t = (d_fwd - d_danger) / max(1e-6, d_clear - d_danger)
            v_safe = min_creep_speed + t * (cruise_speed - min_creep_speed)
    if d_to_g <= float(terminal_creep_rem_m):
        t_term = float(np.clip(d_to_g / max(1e-6, terminal_creep_rem_m), 0.0, 1.0))
        v_term = min_creep_speed + t_term * (cruise_speed - min_creep_speed)
        v_safe = float(min(v_safe, v_term))
    return float(v_safe)


@dataclass
class TowardGoalIntent:
    """E0 outer stub: no GT polyline; modes ``toward_g`` | ``direct_g``."""

    r_m: float = 25.0
    mode: str = "toward_g"
    cruise_speed: float = 10.0
    d_danger: float = 3.0
    d_clear: float = 22.0
    min_creep_speed: float = 1.0

    def reset(self) -> None:
        return None

    def compute(
        self,
        curr_pos: np.ndarray,
        curr_yaw: float,
        goal: np.ndarray,
        d_fwd_hat: Optional[float] = None,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        mode = str(self.mode)
        if mode not in ("toward_g", "direct_g"):
            raise ValueError(f"unknown TowardGoalIntent.mode={mode!r}")
        p = np.asarray(curr_pos, dtype=np.float64).reshape(3)
        g = np.asarray(goal, dtype=np.float64).reshape(3)
        if mode == "direct_g":
            target = g.copy()
        else:
            r = float(self.r_m)
            if d_fwd_hat is not None and np.isfinite(float(d_fwd_hat)):
                alpha = float(
                    np.clip(
                        (float(d_fwd_hat) - self.d_danger)
                        / max(1e-6, self.d_clear - self.d_danger),
                        0.4,
                        1.0,
                    )
                )
                r = max(12.0, r * alpha)
            target = clip_toward_goal(p, g, r_m=r)

        g_rel = goal_rel_body(p, float(curr_yaw), target)
        d_to_g = float(np.linalg.norm(g - p))
        v_safe = _safe_speed_from_depth(
            cruise_speed=self.cruise_speed,
            min_creep_speed=self.min_creep_speed,
            d_danger=self.d_danger,
            d_clear=self.d_clear,
            d_fwd_hat=d_fwd_hat,
            d_to_g=d_to_g,
        )
        info: Dict[str, Any] = {
            "subgoal_source": mode,
            "target_world": target.tolist(),
            "rem_dist": d_to_g,
            "s_progress": 0.0,
            "safe_speed_limit": v_safe,
            "cte_m": None,
            "r_lookahead": float(np.linalg.norm(target - p)),
            "seg_idx": 0,
        }
        return g_rel, info


@dataclass
class SceneIntentPlanner:
    """E1 outer loop: yaw-fan candidates + depth-aware hold/replan."""

    r_m: float = 25.0
    cruise_speed: float = 10.0
    yaw_offsets_deg: Sequence[float] = field(
        default_factory=lambda: (0.0, -15.0, 15.0, -30.0, 30.0)
    )
    replan_period_s: float = 2.0
    step_hz: float = 5.0
    w_g: float = 1.0
    w_jump: float = 0.05
    d_danger: float = 3.0
    d_clear: float = 22.0
    min_creep_speed: float = 1.0
    stall_eps_m: float = 0.05

    _c_prev: Optional[np.ndarray] = field(default=None, init=False, repr=False)
    _steps_since_replan: int = field(default=10**9, init=False, repr=False)
    _last_d_to_g: Optional[float] = field(default=None, init=False, repr=False)
    _stall_steps: int = field(default=0, init=False, repr=False)

    def reset(self) -> None:
        self._c_prev = None
        self._steps_since_replan = 10**9
        self._last_d_to_g = None
        self._stall_steps = 0

    def _candidates(
        self, p: np.ndarray, yaw: float, goal: np.ndarray
    ) -> List[np.ndarray]:
        out: List[np.ndarray] = [clip_toward_goal(p, goal, self.r_m)]
        r = float(self.r_m)
        for deg in self.yaw_offsets_deg:
            psi = float(yaw) + np.deg2rad(float(deg))
            c = p + np.array(
                [r * np.cos(psi), r * np.sin(psi), 0.0], dtype=np.float64
            )
            c[2] = p[2] + 0.3 * (goal[2] - p[2])
            out.append(c)
        return out

    def _should_replan(self, d_to_g: float, d_fwd_hat: Optional[float]) -> bool:
        period_steps = max(1, int(round(float(self.replan_period_s) * float(self.step_hz))))
        if self._c_prev is None:
            return True
        if self._steps_since_replan >= period_steps:
            return True
        if d_fwd_hat is not None and np.isfinite(float(d_fwd_hat)):
            if float(d_fwd_hat) < float(self.d_clear):
                return True
        if self._last_d_to_g is not None:
            progressed = float(self._last_d_to_g) - float(d_to_g)
            if progressed < float(self.stall_eps_m):
                self._stall_steps += 1
            else:
                self._stall_steps = 0
            if self._stall_steps >= period_steps:
                return True
        return False

    def _score(
        self,
        p: np.ndarray,
        goal: np.ndarray,
        cand: np.ndarray,
        d_fwd_hat: Optional[float],
        yaw: float,
    ) -> float:
        d_before = float(np.linalg.norm(goal - p))
        d_after = float(np.linalg.norm(goal - cand))
        progress = d_before - d_after
        jump = 0.0
        if self._c_prev is not None:
            jump = float(np.linalg.norm(cand - self._c_prev))
        j = -float(self.w_g) * progress + float(self.w_jump) * jump
        # Penalize nearly-forward candidates when depth is tight.
        if d_fwd_hat is not None and np.isfinite(float(d_fwd_hat)):
            if float(d_fwd_hat) < float(self.d_clear):
                delta = cand - p
                cos_y, sin_y = np.cos(yaw), np.sin(yaw)
                fwd = float(cos_y * delta[0] + sin_y * delta[1])
                left = float(-sin_y * delta[0] + cos_y * delta[1])
                horiz = max(1e-6, float(np.hypot(fwd, left)))
                if fwd / horiz > 0.85 and float(d_fwd_hat) < float(self.d_danger) * 2.0:
                    j += 5.0
        return float(j)

    def compute(
        self,
        curr_pos: np.ndarray,
        curr_yaw: float,
        goal: np.ndarray,
        d_fwd_hat: Optional[float] = None,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        p = np.asarray(curr_pos, dtype=np.float64).reshape(3)
        g = np.asarray(goal, dtype=np.float64).reshape(3)
        yaw = float(curr_yaw)
        d_to_g = float(np.linalg.norm(g - p))

        replan = self._should_replan(d_to_g, d_fwd_hat)
        cands = self._candidates(p, yaw, g)
        n_cands = len(cands)

        if replan:
            best = cands[0]
            best_j = self._score(p, g, best, d_fwd_hat, yaw)
            for c in cands[1:]:
                j = self._score(p, g, c, d_fwd_hat, yaw)
                if j < best_j:
                    best_j = j
                    best = c
            target = best.copy()
            self._c_prev = target.copy()
            self._steps_since_replan = 0
            self._stall_steps = 0
        else:
            assert self._c_prev is not None
            target = self._c_prev.copy()
            self._steps_since_replan += 1

        self._last_d_to_g = d_to_g
        g_rel = goal_rel_body(p, yaw, target)
        v_safe = _safe_speed_from_depth(
            cruise_speed=self.cruise_speed,
            min_creep_speed=self.min_creep_speed,
            d_danger=self.d_danger,
            d_clear=self.d_clear,
            d_fwd_hat=d_fwd_hat,
            d_to_g=d_to_g,
        )
        info: Dict[str, Any] = {
            "subgoal_source": "scene",
            "target_world": target.tolist(),
            "rem_dist": d_to_g,
            "s_progress": 0.0,
            "safe_speed_limit": v_safe,
            "cte_m": None,
            "r_lookahead": float(np.linalg.norm(target - p)),
            "seg_idx": 0,
            "n_candidates": int(n_cands),
            "replan": bool(replan),
        }
        return g_rel, info
