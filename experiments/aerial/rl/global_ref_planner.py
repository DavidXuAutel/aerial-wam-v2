"""Receding global reference planner (Phase-2 P0).

Builds a short forward polyline ``P_ref`` on a known corridor and refreshes it
on a period / stall / CTE / force schedule. Local Phase-1 WAM still tracks a
lookahead carrot on ``P_ref``; this module does not emit body actions.

Naming: receding global reference — not a claim of full nonlinear MPC.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from experiments.aerial.rl.subgoal_generator import (
    compute_polyline_cum_lengths,
    nearest_on_polyline,
    point_at_arc_length,
)


@dataclass
class GlobalRefConfig:
    horizon_m: float = 60.0
    replan_period_s: float = 1.0
    step_hz: float = 5.0
    max_point_spacing_m: float = 8.0
    min_progress_m: float = 0.5
    stall_steps_to_replan: int = 25
    max_cte_m_to_replan: float = 12.0
    blend_prev: float = 0.3
    max_anchor_jump_m: float = 8.0


class GlobalRefPlanner:
    def __init__(self, cfg: Optional[GlobalRefConfig] = None) -> None:
        self.cfg = cfg or GlobalRefConfig()
        self.replan_count = 0
        self.last_replan_reason = "init"
        self.last_anchor_jump_m = 0.0
        self._corridor: Optional[np.ndarray] = None
        self._cum: Optional[np.ndarray] = None
        self._total_len = 0.0
        self._goal: Optional[np.ndarray] = None
        self._pref: Optional[np.ndarray] = None
        self._steps_since_replan = 0
        self._stall_steps = 0
        self._last_s: Optional[float] = None

    def reset(
        self, corridor: np.ndarray, goal: Optional[np.ndarray] = None
    ) -> None:
        pts = np.asarray(corridor, dtype=np.float64).reshape(-1, 3)
        if pts.shape[0] < 2:
            raise ValueError("corridor must have at least 2 points")
        self._corridor = pts
        self._cum, self._total_len = compute_polyline_cum_lengths(pts)
        if goal is None:
            self._goal = pts[-1].copy()
        else:
            self._goal = np.asarray(goal, dtype=np.float64).reshape(3).copy()
        self._pref = None
        self.replan_count = 0
        self.last_replan_reason = "init"
        self.last_anchor_jump_m = 0.0
        self._steps_since_replan = 0
        self._stall_steps = 0
        self._last_s = None

    @property
    def last_Pref(self) -> Optional[np.ndarray]:
        return None if self._pref is None else self._pref.copy()

    def step(
        self,
        p: np.ndarray,
        yaw: float,
        *,
        cte_m: Optional[float] = None,
        progressed_m: Optional[float] = None,
        force: bool = False,
    ) -> np.ndarray:
        if self._corridor is None or self._cum is None or self._goal is None:
            raise RuntimeError("GlobalRefPlanner.reset() must be called first")

        p_arr = np.asarray(p, dtype=np.float64).reshape(3)
        _ = float(yaw)  # reserved for future heading-aware sampling

        true_proj, _seg, true_s, _rem = nearest_on_polyline(p_arr, self._corridor)
        if cte_m is None:
            cte_m = float(np.linalg.norm(p_arr - true_proj))
        else:
            cte_m = float(cte_m)

        if progressed_m is None:
            if self._last_s is None:
                ds = float("inf")  # first observation: not a stall
            else:
                ds = float(true_s) - float(self._last_s)
            progressed_m = ds
        else:
            progressed_m = float(progressed_m)
        self._last_s = float(true_s)

        if abs(progressed_m) < float(self.cfg.min_progress_m):
            self._stall_steps += 1
        else:
            self._stall_steps = 0

        reason = self._should_replan(force=force, cte_m=cte_m)
        if reason is not None:
            self._pref = self._build_pref(float(true_s))
            self.replan_count += 1
            self.last_replan_reason = reason
            self._steps_since_replan = 0
            self._stall_steps = 0
        else:
            self._steps_since_replan += 1

        assert self._pref is not None
        return self._pref.copy()

    def _should_replan(self, *, force: bool, cte_m: float) -> Optional[str]:
        if self._pref is None:
            return "init"
        if force:
            return "force"
        period_steps = max(
            1, int(round(float(self.cfg.replan_period_s) * float(self.cfg.step_hz)))
        )
        # replan_period_s <= 0 ⇒ every step
        if float(self.cfg.replan_period_s) <= 0.0:
            return "period"
        if self._steps_since_replan + 1 >= period_steps:
            return "period"
        if self._stall_steps >= int(self.cfg.stall_steps_to_replan):
            return "stall"
        if cte_m > float(self.cfg.max_cte_m_to_replan):
            return "cte"
        return None

    def _build_pref(self, s_true: float) -> np.ndarray:
        assert self._corridor is not None and self._cum is not None and self._goal is not None
        horizon = float(self.cfg.horizon_m)
        spacing = max(1e-3, float(self.cfg.max_point_spacing_m))
        s0 = float(np.clip(s_true, 0.0, self._total_len))
        s1 = float(min(self._total_len, s0 + horizon))

        samples = [s0]
        s = s0 + spacing
        while s < s1 - 1e-9:
            samples.append(s)
            s += spacing
        if not samples or samples[-1] < s1 - 1e-6:
            samples.append(s1)

        pts = [
            point_at_arc_length(self._corridor, ss, cum_lengths=self._cum)
            for ss in samples
        ]
        # Append final G only when the forward window reaches corridor end.
        if s1 >= self._total_len - 1e-6:
            if float(np.linalg.norm(pts[-1] - self._goal)) > 1e-3:
                pts.append(self._goal.copy())

        pref = np.asarray(pts, dtype=np.float64).reshape(-1, 3)
        if pref.shape[0] < 2:
            # Degenerate near goal: duplicate goal with tiny offset along corridor.
            pref = np.vstack([pref[0], self._goal.copy()])

        pref = self._blend_and_clamp_anchor(pref)
        return pref

    def _blend_and_clamp_anchor(self, pref: np.ndarray) -> np.ndarray:
        out = pref.copy()
        if self._pref is None:
            self.last_anchor_jump_m = 0.0
            return out

        old_anchor = self._pref[0].copy()
        new_anchor = out[0].copy()
        blend = float(np.clip(self.cfg.blend_prev, 0.0, 1.0))
        blended = (1.0 - blend) * new_anchor + blend * old_anchor
        jump = float(np.linalg.norm(blended - old_anchor))
        max_jump = float(self.cfg.max_anchor_jump_m)
        if jump > max_jump + 1e-12 and jump > 1e-12:
            scale = max_jump / jump
            blended = old_anchor + scale * (blended - old_anchor)
            jump = float(np.linalg.norm(blended - old_anchor))
        # Also clamp raw new_anchor path if blend=0 but jump huge
        raw_jump = float(np.linalg.norm(new_anchor - old_anchor))
        if blend <= 1e-12 and raw_jump > max_jump + 1e-12:
            scale = max_jump / raw_jump
            blended = old_anchor + scale * (new_anchor - old_anchor)
            jump = float(np.linalg.norm(blended - old_anchor))

        out[0] = blended
        self.last_anchor_jump_m = jump
        # Ensure still ≥2 distinct-ish points
        if float(np.linalg.norm(out[-1] - out[0])) < 1e-6:
            out[-1] = self._goal.copy() if self._goal is not None else out[-1]
        return out
