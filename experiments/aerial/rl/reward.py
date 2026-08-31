"""Composite navigation reward (spec §4.5).

The spec gives the *shape*, not a scalar:

    reward = w_prog * progress
           - w_coll * collision_risk
           - w_man  * maneuver_cost

  * ``progress``       = decrease in distance-to-goal since the last step (m).
  * ``collision_risk`` = 1.0 on real contact (``obs.collided``); otherwise the
    world-model's predicted ``p_coll`` in ∈[0,1] (imagined rollouts).
  * ``maneuver_cost``  = L2 norm of the executed body delta (aggressive-maneuver
    penalty; keeps motions smooth).

``NavigationReward`` is stateful: it remembers the previous distance so the
collector can call ``.step(obs, action)`` once per env step. ``reward_terms``
is a pure function for the imagination side (given explicit distances / p_coll).

Arrival radius: ``RewardConfig.success_dist_m`` is the *online* arrival /
termination gate. It defaults to ``DEFAULT_ONLINE_SUCCESS_DIST_M`` (the tight 3 m
online radius) so that even a bare ``NavigationReward()`` — one built without going
through the YAML / ``build_from_config`` path — uses the correct threshold. The
20 m ``OPENFLY_SUCCESS_DIST_M`` (re-exported as ``EVAL_SUCCESS_DIST_M``) is the
loose *eval SR metric* radius and is intentionally NOT the per-step termination gate.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np

from experiments.aerial.eval.metrics import OPENFLY_SUCCESS_DIST_M
from experiments.aerial.rl.env.obs import Observation

# Online arrival / termination radius (m). Tighter than the eval SR metric so a
# bare NavigationReward()/RewardConfig() defaults to THIS, not the loose eval
# radius — code paths that skip the YAML must not silently terminate at 20 m.
DEFAULT_ONLINE_SUCCESS_DIST_M = 3.0
# The loose eval success-rate radius (metrics.OPENFLY_SUCCESS_DIST_M = 20 m),
# re-exported for reference. Intentionally NOT the per-step termination gate.
EVAL_SUCCESS_DIST_M = float(OPENFLY_SUCCESS_DIST_M)


@dataclass
class RewardConfig:
    w_progress: float = 1.0
    w_collision: float = 10.0
    w_maneuver: float = 0.01               # curriculum START weight
    w_curiosity: float = 0.0              # Near-obstacle lateral clearance curiosity
    curiosity_fwd_thresh_m: float = 3.5   # Trigger exploration when forward depth <= thresh
    curiosity_max_bonus: float = 2.0      # Max curiosity bonus per step
    success_dist_m: float = DEFAULT_ONLINE_SUCCESS_DIST_M
    success_bonus: float = 10.0
    # Maneuver-penalty curriculum (design doc §2.4): keep the aggressive-maneuver
    # penalty small early (exploration matters more than smoothness), then ramp it
    # up as competence rises. ``w_maneuver`` is the start; the effective weight
    # ramps linearly toward ``w_maneuver_final`` over the competence band
    # ``[threshold, threshold + ramp]``. Defaults make the curriculum a NO-OP
    # (final == start), so unconfigured runs behave exactly as before.
    # NOTE (§1.5): the threshold is a project-tuned placeholder for OUR 4-D
    # kinematic SEARCH regime — it is deliberately NOT DreamerV3's reward-50.0.
    w_maneuver_final: float = 0.01
    maneuver_curriculum_threshold: float = 0.0
    maneuver_curriculum_ramp: float = 1.0


def maneuver_weight_at(metric: float, cfg: RewardConfig, w_start: Optional[float] = None) -> float:
    """Effective ``w_maneuver`` for a competence ``metric`` (e.g. mean episode return).

    Linearly ramps from the START weight (``w_start`` if given, else
    ``cfg.w_maneuver``) toward ``cfg.w_maneuver_final`` across the band
    ``[threshold, threshold + ramp]``; flat before the threshold. Pass ``w_start``
    explicitly (a snapshot of the base weight) when the caller mutates
    ``cfg.w_maneuver`` between iterations, so the schedule never feeds its own
    output back in as the start. Pure function of scalars — no side effects.
    """
    start = float(cfg.w_maneuver if w_start is None else w_start)
    final = float(cfg.w_maneuver_final)
    threshold = float(cfg.maneuver_curriculum_threshold)
    ramp = float(cfg.maneuver_curriculum_ramp)
    if final == start or metric < threshold:
        return start
    if ramp <= 0.0:
        return final                       # step at the threshold
    frac = min(1.0, max(0.0, (float(metric) - threshold) / ramp))
    return start + frac * (final - start)


def reward_terms(
    progress: float,
    collision_risk: float,
    maneuver_cost: float,
    cfg: RewardConfig = RewardConfig(),
    curiosity_gain: float = 0.0,
) -> Dict[str, float]:
    """Pure term breakdown + scalar reward. Used by both real and imagined paths."""
    r = (
        cfg.w_progress * float(progress)
        - cfg.w_collision * float(collision_risk)
        - cfg.w_maneuver * float(maneuver_cost)
        + cfg.w_curiosity * float(np.clip(curiosity_gain, 0.0, cfg.curiosity_max_bonus))
    )
    return {
        "reward": float(r),
        "progress": float(progress),
        "collision_risk": float(collision_risk),
        "maneuver_cost": float(maneuver_cost),
        "curiosity_gain": float(curiosity_gain),
    }


class NavigationReward:
    """Stateful per-episode reward: progress toward ``goal`` − risk − maneuver + curiosity."""

    def __init__(self, goal: Optional[np.ndarray], cfg: Optional[RewardConfig] = None) -> None:
        self.cfg = cfg or RewardConfig()
        self._goal = None if goal is None else np.asarray(goal, dtype=np.float64).reshape(3)
        self._prev_dist: Optional[float] = None
        self._cum_curiosity: float = 0.0

    def reset(self, goal: Optional[np.ndarray], start_pos: np.ndarray) -> None:
        self._goal = None if goal is None else np.asarray(goal, dtype=np.float64).reshape(3)
        self._prev_dist = self._dist(np.asarray(start_pos, dtype=np.float64).reshape(3))
        self._cum_curiosity = 0.0

    def _dist(self, pos: np.ndarray) -> Optional[float]:
        if self._goal is None:
            return None
        return float(np.linalg.norm(pos - self._goal))

    def step(
        self,
        obs: Observation,
        action: np.ndarray,
        p_coll: Optional[float] = None,
    ) -> tuple[float, bool, Dict[str, float]]:
        """Return ``(reward, done, terms)`` for one real env transition."""
        pos = obs.position
        dist = self._dist(pos)
        progress = 0.0
        if dist is not None and self._prev_dist is not None:
            progress = self._prev_dist - dist
        self._prev_dist = dist

        # Near-obstacle lateral clearance curiosity (spec 20260828):
        curiosity_gain = 0.0
        if self.cfg.w_curiosity > 0:
            cones = obs.info.get("depth_cones_pred") if isinstance(obs.info, dict) else None
            fwd_d = None
            left_d = None
            right_d = None
            if isinstance(cones, dict):
                fwd_d = cones.get("forward")
                left_d = cones.get("left")
                right_d = cones.get("right")
            if fwd_d is None and isinstance(obs.info, dict):
                fwd_d = obs.info.get("depth_min_pred")

            if fwd_d is not None and np.isfinite(float(fwd_d)):
                if float(fwd_d) <= float(self.cfg.curiosity_fwd_thresh_m) and progress <= 0.1:
                    l_val = float(left_d) if (left_d is not None and np.isfinite(float(left_d))) else 5.0
                    r_val = float(right_d) if (right_d is not None and np.isfinite(float(right_d))) else 5.0
                    lat_adv = max(0.0, max(l_val, r_val) - float(fwd_d))
                    dyaw = abs(float(action[3])) if len(action) > 3 else 0.0
                    raw_gain = lat_adv * dyaw
                    avail = max(0.0, 3.0 - self._cum_curiosity)
                    curiosity_gain = min(raw_gain, avail)
                    self._cum_curiosity += curiosity_gain

        collision_risk = 1.0 if obs.collided else float(p_coll or 0.0)
        maneuver_cost = float(np.linalg.norm(np.asarray(action, dtype=np.float64)))
        terms = reward_terms(
            progress, collision_risk, maneuver_cost, self.cfg, curiosity_gain=curiosity_gain
        )

        arrived = dist is not None and dist < self.cfg.success_dist_m
        if arrived:
            terms["reward"] += self.cfg.success_bonus
        done = bool(obs.collided or arrived)
        terms["arrived"] = float(arrived)
        return terms["reward"], done, terms
