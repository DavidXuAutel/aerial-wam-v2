"""Tests for V1b planner + DepthTauShield."""
from __future__ import annotations

import numpy as np

from experiments.aerial.rl.buffer import ReplayBuffer
from experiments.aerial.rl.collector import RolloutCollector
from experiments.aerial.rl.dynamics import StubLatentDynamics
from experiments.aerial.rl.env.obs import Observation
from experiments.aerial.rl.planner import (
    ImaginationPlanner,
    default_candidates,
    drop_backward_if_subgoal_ahead,
)
from experiments.aerial.rl.reward import RewardConfig
from experiments.aerial.rl.safety import DepthTauShield
from experiments.aerial.rl import v1_metrics


def _obs(pos, depth_val=10.0, info=None):
    state = np.array([pos[0], pos[1], pos[2], 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
    depth = np.full((16, 16), depth_val, dtype=np.float32)
    rgb = np.zeros((16, 16, 3), dtype=np.uint8)
    return Observation(rgb=rgb, state=state, depth=depth, info=info or {})


def test_planner_prefers_forward_toward_goal():
    dyn = StubLatentDynamics(goal=np.array([50.0, 0.0, 0.0]), latent_dim=8)
    planner = ImaginationPlanner(dyn, horizon=3, reward_cfg=RewardConfig())
    obs = _obs([0.0, 0.0, 0.0], info={"goal": np.array([50.0, 0.0, 0.0])})
    hover = np.zeros(4)
    planned = planner.plan(obs, hover)
    assert planned[0] > 0.0


def test_drop_backward_when_subgoal_ahead():
    cands = default_candidates(np.zeros(4))
    assert any(c[0] < -0.01 for c in cands)
    gr = np.array([15.0, 0.0, 0.0, 15.0], dtype=np.float32)
    filtered = drop_backward_if_subgoal_ahead(cands, gr)
    assert not any(c[0] < -0.01 and np.all(np.abs(c[1:]) < 1e-6) for c in filtered)


def test_planner_passes_goal_rel_into_imagine(monkeypatch):
    captured: dict = {}

    def _spy_imagine(*args, **kwargs):
        captured.update(kwargs)
        from experiments.aerial.rl.imagination import imagine as real_imagine

        return real_imagine(*args, **kwargs)

    monkeypatch.setattr("experiments.aerial.rl.planner.imagine", _spy_imagine)
    dyn = StubLatentDynamics(goal=np.array([20.0, 0.0, 0.0]), latent_dim=8)
    planner = ImaginationPlanner(dyn, horizon=2, reward_cfg=RewardConfig())
    obs = _obs([0.0, 0.0, 0.0], info={"goal": np.array([20.0, 0.0, 0.0])})
    planner.plan(obs, np.zeros(4))
    assert captured.get("goal_rel0") is not None
    assert float(captured["goal_rel0"][0, 0]) > 0.0
    assert captured.get("body_vel0") is not None
    assert captured.get("propagate_goal_rel") is True


def test_depth_tau_shield_records_independent_channel():
    shield = DepthTauShield(min_depth_m=3.0, min_tau_s=2.0)
    obs = _obs([0.0, 0.0, 0.0], info={"tau_pred": 0.5})
    assert shield.should_override(obs)
    assert shield.last_channels == ("tau",)
    assert obs.info["shield_channels"] == ["tau"]


def test_dual_channel_independence_metric():
    d = np.array([True, False, True, False, False])
    t = np.array([False, True, False, False, True])
    out = v1_metrics.check_dual_channel_independence(d, t, max_both_fail_frac=0.5)
    assert out["ok"] is True
    assert out["both_fail_frac"] == 0.0


def test_collector_runs_with_planner():
    class _Env:
        def __init__(self):
            self.config = type("C", (), {"step_hz": 5.0})()
            self.goal = np.array([20.0, 0.0, 0.0])

        def reset(self, episode=None):
            return _obs([0.0, 0.0, 0.0])

        def step(self, action):
            return _obs([1.0, 0.0, 0.0]), {}

    class _Policy:
        def act(self, view):
            return np.zeros(4, dtype=np.float64)

    dyn = StubLatentDynamics(goal=np.array([20.0, 0.0, 0.0]), latent_dim=8)
    planner = ImaginationPlanner(dyn, horizon=2)
    buf = ReplayBuffer(capacity_episodes=1, seed=0)
    col = RolloutCollector(
        _Env(), _Policy(), buf,
        max_steps=2, target_hz=0.0, planner=planner,
        skip_reset_collision=False,
    )
    ep, stats = col.collect_episode()
    assert stats.steps == 2
    assert len(ep) == 2
