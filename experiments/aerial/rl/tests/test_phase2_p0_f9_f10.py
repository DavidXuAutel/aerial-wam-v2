"""P0 F9 (g_norm) + F10 (planner streaming z) unit tests."""
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("torch")

from experiments.aerial.rl.actor_critic import ActorCriticConfig, LatentActorCritic, LatentActorDeployPolicy
from experiments.aerial.rl.dynamics import StubLatentDynamics
from experiments.aerial.rl.env.obs import Observation
from experiments.aerial.rl.goal_features import (
    GOAL_NORM_DIM,
    g_norm_from_goal_rel,
    goal_rel_body,
    reward_aux_features,
)
from experiments.aerial.rl.planner import ImaginationPlanner
from experiments.aerial.rl.reward import RewardConfig
from experiments.aerial.rl.tests.test_v1b_planner_shield import _obs


def test_g_norm_stable_for_metre_scale_carrots():
    """20–55 m subgoals must not produce O(10–50) feature magnitudes."""
    for dist in (20.0, 35.0, 55.0):
        g = goal_rel_body(np.zeros(3), 0.0, np.array([dist, 0.0, 0.0]))
        gn = g_norm_from_goal_rel(g)
        assert gn.shape == (GOAL_NORM_DIM,)
        assert np.all(np.abs(gn[:3]) <= 1.0 + 1e-5)
        assert gn[3] == pytest.approx(np.log1p(dist), rel=1e-5)
        assert float(np.max(np.abs(gn))) < 5.0
        aux = reward_aux_features(g, np.zeros(3), np.zeros(4))
        np.testing.assert_allclose(gn, aux[:GOAL_NORM_DIM], rtol=1e-5, atol=1e-5)


def test_feat_tensor_meter_mode_keeps_raw_metres():
    """Re-anchor default: Step E weights expect metre goal_rel tail."""
    ac = LatentActorCritic(
        config=ActorCriticConfig(
            latent_dim=8, condition_on_goal=True, goal_feat_mode="meter", device="cpu"
        )
    )
    z = np.zeros(8, dtype=np.float32)
    g_raw = goal_rel_body(np.zeros(3), 0.0, np.array([50.0, 0.0, 0.0]))
    feat = ac._feat_tensor(z, g_raw).cpu().numpy().reshape(-1)
    np.testing.assert_allclose(feat[8:], g_raw, rtol=1e-5, atol=1e-5)


def test_feat_tensor_g_norm_mode_not_raw_metres():
    ac = LatentActorCritic(
        config=ActorCriticConfig(
            latent_dim=8, condition_on_goal=True, goal_feat_mode="g_norm", device="cpu"
        )
    )
    z = np.zeros(8, dtype=np.float32)
    g_raw = goal_rel_body(np.zeros(3), 0.0, np.array([50.0, 0.0, 0.0]))
    feat = ac._feat_tensor(z, g_raw).cpu().numpy().reshape(-1)
    assert 49.0 not in feat
    assert 50.0 not in feat
    expected_tail = g_norm_from_goal_rel(g_raw)
    np.testing.assert_allclose(feat[8:], expected_tail, rtol=1e-5, atol=1e-5)


def test_planner_skips_encode_when_latent_injected():
    dyn = StubLatentDynamics(goal=np.array([20.0, 0.0, 0.0]), latent_dim=8)
    planner = ImaginationPlanner(dyn, horizon=2, reward_cfg=RewardConfig())
    obs = _obs([0.0, 0.0, 0.0])
    z_stream = dyn.encode(obs) + 3.0

    def _bad_encode(_obs):
        raise AssertionError("encode must not run when latent= is passed")

    dyn.encode = _bad_encode  # type: ignore[method-assign]
    out = planner.plan(obs, np.zeros(4), latent=z_stream)
    assert out.shape == (4,)


def test_deploy_and_planner_share_streaming_latent():
    dyn = StubLatentDynamics(goal=np.array([30.0, 0.0, 0.0]), latent_dim=8)
    ac = LatentActorCritic(
        config=ActorCriticConfig(latent_dim=8, condition_on_goal=True, device="cpu")
    )
    policy = LatentActorDeployPolicy(dyn, ac, deterministic=True, stream_latent=True)
    planner = ImaginationPlanner(dyn, horizon=2, reward_cfg=RewardConfig())

    obs0 = _obs([0.0, 0.0, 0.0], info={"goal": [30.0, 0.0, 0.0]})
    policy.act(obs0)
    z_after_first = policy._latent.copy()

    obs1 = _obs([1.0, 0.0, 0.0], info={"goal": [29.0, 0.0, 0.0]})
    policy.act(obs1)
    z_after_second = policy._latent.copy()

    assert not np.allclose(z_after_first, dyn.encode(obs1))
    np.testing.assert_allclose(
        planner.plan(obs1, np.zeros(4), latent=z_after_second)[:1],
        planner.plan(obs1, np.zeros(4), latent=z_after_second)[:1],
    )
