"""Collector behavior: the reset-collision entry guard (spawn-artifact skip).

An episode whose reset spawns the vehicle already in collision (inside geometry)
is not a learnable trajectory — the collector must skip it before any step so it
never reaches the buffer/dataset as a 1-step instant crash.
"""
import numpy as np

from experiments.aerial.rl.buffer import ReplayBuffer
from experiments.aerial.rl.collector import RolloutCollector
from experiments.aerial.rl.env.mock_env import MockAirSimDroneEnv, MockEnvConfig


class _FwdPolicy:
    """Minimal RL-style policy: always commands a forward body delta."""

    def act(self, _policy_view) -> np.ndarray:
        return np.array([3.0, 0.0, 0.0, 0.0])


def _collector(env, **kw) -> RolloutCollector:
    return RolloutCollector(env, _FwdPolicy(), ReplayBuffer(), max_steps=5, **kw)


# a tight box so an off-origin start pose spawns out of bounds == in collision
_TIGHT = MockEnvConfig(bounds_m=1.0)
_INSIDE = {"pos": [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]], "yaw": [0.0, 0.0]}
_SPAWN_COLLISION = {"pos": [[50.0, 0.0, 0.0], [60.0, 0.0, 0.0]], "yaw": [0.0, 0.0]}


def test_reset_collision_is_skipped():
    env = MockAirSimDroneEnv(_TIGHT)
    col = _collector(env)
    trans, stats = col.collect_episode(_SPAWN_COLLISION)
    assert trans == []                 # no steps taken
    assert stats.skipped == 1
    assert stats.episodes == 0
    assert len(col.buffer) == 0        # never reached the buffer


def test_healthy_reset_is_collected():
    env = MockAirSimDroneEnv(_TIGHT)
    col = _collector(env)
    trans, stats = col.collect_episode(_INSIDE)
    assert len(trans) > 0
    assert stats.skipped == 0
    assert stats.episodes == 1


def test_collect_aggregates_skips():
    env = MockAirSimDroneEnv(_TIGHT)
    col = _collector(env)
    # alternate a good start and a spawn-collision start across 4 episodes
    total = col.collect(4, episodes=[_INSIDE, _SPAWN_COLLISION])
    assert total.skipped == 2          # the two _SPAWN_COLLISION rounds
    assert total.episodes == 2         # only the healthy ones counted


def test_guard_can_be_disabled():
    env = MockAirSimDroneEnv(_TIGHT)
    col = _collector(env, skip_reset_collision=False)
    trans, stats = col.collect_episode(_SPAWN_COLLISION)
    assert len(trans) > 0              # collected despite reset collision
    assert stats.skipped == 0


def test_takeoff_scan_steps_executes_in_place_yaw():
    env = MockAirSimDroneEnv(MockEnvConfig(bounds_m=100.0))
    far_goal_ep = {"pos": [[0.0, 0.0, 0.0], [50.0, 0.0, 0.0]], "yaw": [0.0, 0.0]}
    col = RolloutCollector(env, _FwdPolicy(), ReplayBuffer(), max_steps=10, takeoff_scan_steps=4)
    trans, stats = col.collect_episode(far_goal_ep)
    assert len(trans) == 10
    # First 4 steps should be pure yaw rotation (dx=dy=dz=0, dyaw > 0)
    for i in range(4):
        a = trans[i].action
        assert a[0] == 0.0
        assert a[1] == 0.0
        assert a[2] == 0.0
        assert a[3] > 0.0
    # Step 4 onward should follow policy (forward > 0)
    assert trans[4].action[0] > 0.0

