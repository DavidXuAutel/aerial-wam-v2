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
from experiments.aerial.rl.imagination import MAX_IMAGINATION_HORIZON, imagine
from experiments.aerial.rl.reward import RewardConfig


class ConstantLatentPolicy:
    """Imagination policy that repeats one body delta every step."""

    def __init__(self, action: np.ndarray) -> None:
        self._action = np.asarray(action, dtype=np.float64).reshape(4)

    def act_latent(self, z: np.ndarray) -> np.ndarray:
        return self._action.copy()


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

    def __post_init__(self) -> None:
        self.horizon = int(self.horizon)
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

    def plan(self, obs: Observation, base_action: np.ndarray) -> np.ndarray:
        """Return the candidate first action with highest imagined return."""
        z0 = np.asarray(self.dynamics.encode(obs), dtype=np.float64)
        candidates = list(self.candidate_fn(np.asarray(base_action, dtype=np.float64)))
        if not candidates:
            return np.asarray(base_action, dtype=np.float64).reshape(4)

        best_a = candidates[0]
        best_score = -np.inf
        for cand in candidates:
            roll = imagine(
                self.dynamics,
                ConstantLatentPolicy(cand),
                z0[None, :],
                self.horizon,
                reward_cfg=self.reward_cfg,
            )
            score = float(roll.returns[0])
            if score > best_score:
                best_score = score
                best_a = cand
        return np.asarray(best_a, dtype=np.float64).reshape(4)
