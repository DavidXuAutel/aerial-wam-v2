"""Short-horizon imagination planner (V1b, frozen spec §7).

Scores a small set of candidate body deltas by rolling them forward through a
``LatentDynamics`` model for ``horizon`` steps (≤ ``MAX_IMAGINATION_HORIZON``),
then returns the first action of the highest-return sequence. This is the
test-time imagination scoring path — distinct from V4 actor-critic training.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Sequence

import numpy as np

from experiments.aerial.rl.dynamics import LatentDynamics
from experiments.aerial.rl.env.obs import Observation
from experiments.aerial.rl.goal_features import body_vel_from_obs, goal_rel_from_obs
from experiments.aerial.rl.imagination import MAX_IMAGINATION_HORIZON, imagine
from experiments.aerial.rl.reward import RewardConfig

# Body-frame fwd above this → subgoal is ahead; drop pure-backward planner atom.
_SUBGOAL_AHEAD_FWD_M = 0.05


class ConstantLatentPolicy:
    """Imagination policy that repeats one body delta every step."""

    def __init__(self, action: np.ndarray) -> None:
        self._action = np.asarray(action, dtype=np.float64).reshape(4)

    def act_latent(self, z: np.ndarray) -> np.ndarray:
        return self._action.copy()


def drop_backward_if_subgoal_ahead(
    candidates: Sequence[np.ndarray],
    goal_rel: np.ndarray,
) -> List[np.ndarray]:
    """Remove the hardcoded pure-backward candidate when carrot is ahead in body frame."""
    if float(goal_rel[0]) <= _SUBGOAL_AHEAD_FWD_M:
        return list(candidates)
    kept: List[np.ndarray] = []
    for cand in candidates:
        c = np.asarray(cand, dtype=np.float64).reshape(4)
        pure_back = c[0] < -0.01 and np.all(np.abs(c[1:]) < 1e-6)
        if pure_back:
            continue
        kept.append(c)
    return kept if kept else list(candidates)


def default_candidates(base_action: np.ndarray) -> List[np.ndarray]:
    """Small discrete set around the policy proposal."""
    base = np.asarray(base_action, dtype=np.float64).reshape(4)
    dx, dy, dz, dyaw = base
    return [
        base,
        np.array([dx * 0.5, dy, dz, dyaw], dtype=np.float64),
        np.zeros(4, dtype=np.float64),
        np.array([-max(abs(dx), 0.5), 0.0, 0.0, 0.0], dtype=np.float64),
        np.array([dx, dy * 0.5, dz, dyaw], dtype=np.float64),
        np.array([max(abs(dx), 1.0), 0.0, 0.0, 0.0], dtype=np.float64),
    ]


@dataclass
class ImaginationPlanner:
    """Pick the best first action via batched short imagined rollouts."""

    dynamics: LatentDynamics
    horizon: int = 5
    reward_cfg: Optional[RewardConfig] = None
    candidate_fn: Any = field(default=default_candidates)
    #: Optional deployed action box. ``None`` (default) keeps the V1-merged
    #: behaviour: candidates are scored in the UNCLIPPED space and only clipped
    #: later at ``collector.py:167`` — a same-origin inconsistency with §A.4,
    #: logged 2026-08-18 but deliberately NOT changed by default, since flipping
    #: it would alter the V1 deployed path and require a V1 re-gate.
    action_limits: Optional[np.ndarray] = None

    def __post_init__(self) -> None:
        self.horizon = int(self.horizon)
        if self.action_limits is not None:
            lim = np.abs(np.asarray(self.action_limits, dtype=np.float64).reshape(-1))
            if lim.shape != (4,) or not np.all(lim > 0):
                raise ValueError(
                    f"action_limits must be 4 positive values, got {self.action_limits!r}"
                )
            self.action_limits = lim
        if self.horizon < 1:
            raise ValueError("horizon must be >= 1")
        if self.horizon > MAX_IMAGINATION_HORIZON:
            raise ValueError(
                f"planner horizon {self.horizon} exceeds cap {MAX_IMAGINATION_HORIZON}"
            )

    def set_goal(self, goal: Optional[np.ndarray]) -> None:
        set_goal = getattr(self.dynamics, "set_goal", None)
        if callable(set_goal):
            set_goal(goal)

    def plan(
        self,
        obs: Observation,
        base_action: np.ndarray,
        *,
        latent: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """Return the candidate first action with highest imagined return.

        When ``latent`` is provided (deploy streaming posterior), imagination
        scores from that state instead of resetting via ``encode(obs)``.
        """
        if latent is not None:
            z0 = np.asarray(latent, dtype=np.float64).reshape(-1)
        else:
            z0 = np.asarray(self.dynamics.encode(obs), dtype=np.float64)
        goal_rel = goal_rel_from_obs(obs)
        body_vel = body_vel_from_obs(obs)
        candidates = list(self.candidate_fn(np.asarray(base_action, dtype=np.float64)))
        candidates = drop_backward_if_subgoal_ahead(candidates, goal_rel)
        if not candidates:
            return np.asarray(base_action, dtype=np.float64).reshape(4)
        if self.action_limits is not None:
            lim = self.action_limits
            candidates = [np.clip(c, -lim, lim) for c in candidates]

        best_a = candidates[0]
        best_score = -np.inf
        gr0 = np.asarray(goal_rel, dtype=np.float32).reshape(1, -1)
        bv0 = np.asarray(body_vel, dtype=np.float32).reshape(1, -1)
        for cand in candidates:
            roll = imagine(
                self.dynamics,
                ConstantLatentPolicy(cand),
                z0[None, :],
                self.horizon,
                reward_cfg=self.reward_cfg,
                goal_rel0=gr0,
                body_vel0=bv0,
                propagate_goal_rel=True,
                action_limits=self.action_limits,
            )
            score = float(roll.returns[0])
            if score > best_score:
                best_score = score
                best_a = cand
        return np.asarray(best_a, dtype=np.float64).reshape(4)
