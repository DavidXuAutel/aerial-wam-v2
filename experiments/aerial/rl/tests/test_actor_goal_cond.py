"""Goal-conditioned actor: action depends on goal_rel, not only z."""
from __future__ import annotations

import numpy as np

from experiments.aerial.rl.actor_critic import ActorCriticConfig, LatentActorCritic
from experiments.aerial.rl.goal_features import GOAL_REL_DIM


def test_deterministic_action_flips_with_goal_ahead_vs_behind():
    ac = LatentActorCritic(
        config=ActorCriticConfig(
            latent_dim=8,
            condition_on_goal=True,
            step_hz=5.0,
            device="cpu",
        )
    )
    z = np.zeros(8, dtype=np.float32)
    ahead = np.array([10.0, 0.0, 0.0, 10.0], dtype=np.float32)
    behind = np.array([-10.0, 0.0, 0.0, 10.0], dtype=np.float32)
    a_fwd = ac.act_latent(z, goal_rel=ahead, deterministic=True)
    a_back = ac.act_latent(z, goal_rel=behind, deterministic=True)
    # Untrained net may be weak; still must *depend* on goal (not identical).
    assert a_fwd.shape == (4,)
    assert not np.allclose(a_fwd, a_back, atol=1e-5)


def test_update_accepts_rollout_with_goal_rel():
    from experiments.aerial.rl.dynamics import StubLatentDynamics
    from experiments.aerial.rl.imagination import imagine
    from experiments.aerial.rl.actor_critic import ImaginationActorPolicy

    ac = LatentActorCritic(
        config=ActorCriticConfig(latent_dim=8, condition_on_goal=True, step_hz=5.0)
    )
    dyn = StubLatentDynamics(latent_dim=8, goal=np.array([5.0, 0.0, 0.0]))
    z0 = np.zeros((2, 8), dtype=np.float64)
    g0 = np.tile(np.array([5.0, 0.0, 0.0, 5.0], dtype=np.float32), (2, 1))
    roll = imagine(
        dyn,
        ImaginationActorPolicy(ac, deterministic=True),
        z0,
        horizon=3,
        goal_rel0=g0,
        action_limits=ac.action_limits,
    )
    assert roll.goal_rel is not None
    assert roll.goal_rel.shape == (2, 4, 4)  # B, H+1, 4
    out = ac.update(roll)
    assert out.get("status") != "error"
