# experiments/aerial/rl/tests/test_global_ref_planner.py
"""Unit tests for receding GlobalRefPlanner (Phase-2 P0)."""

import numpy as np
import pytest

from experiments.aerial.rl.global_ref_planner import GlobalRefConfig, GlobalRefPlanner


def _straight_corridor(length: float = 200.0, z: float = 10.0) -> np.ndarray:
    return np.array([[0.0, 0.0, z], [length, 0.0, z]], dtype=np.float64)


def test_reset_and_first_step_returns_forward_polyline():
    cfg = GlobalRefConfig(
        horizon_m=40.0, max_point_spacing_m=10.0, replan_period_s=1.0, step_hz=5.0
    )
    gp = GlobalRefPlanner(cfg)
    F = _straight_corridor()
    gp.reset(F, goal=F[-1])
    Pref = gp.step(np.array([0.0, 0.0, 10.0]), 0.0, force=True)
    assert Pref.ndim == 2 and Pref.shape[1] == 3 and Pref.shape[0] >= 2
    assert Pref[0, 0] == pytest.approx(0.0, abs=1.0)
    assert Pref[-1, 0] <= 40.0 + 1e-6


def test_no_replan_within_period_returns_equal_path():
    cfg = GlobalRefConfig(horizon_m=40.0, replan_period_s=1.0, step_hz=5.0)
    gp = GlobalRefPlanner(cfg)
    F = _straight_corridor()
    gp.reset(F)
    p = np.array([5.0, 0.0, 10.0])
    a = gp.step(p, 0.0, force=True)
    b = gp.step(p, 0.0)
    np.testing.assert_allclose(a, b)
    assert gp.replan_count == 1


def test_stall_forces_replan_event():
    cfg = GlobalRefConfig(
        horizon_m=40.0,
        replan_period_s=100.0,
        step_hz=5.0,
        min_progress_m=0.5,
        stall_steps_to_replan=3,
    )
    gp = GlobalRefPlanner(cfg)
    gp.reset(_straight_corridor())
    p = np.array([10.0, 0.0, 10.0])
    gp.step(p, 0.0, force=True, progressed_m=0.0)
    for _ in range(3):
        gp.step(p, 0.0, progressed_m=0.0)
    assert gp.replan_count >= 2
    assert gp.last_replan_reason == "stall"


def test_anchor_jump_bounded_when_blending():
    cfg = GlobalRefConfig(
        horizon_m=50.0,
        blend_prev=0.5,
        max_anchor_jump_m=8.0,
        replan_period_s=0.0,
        step_hz=5.0,
        max_point_spacing_m=10.0,
    )
    gp = GlobalRefPlanner(cfg)
    gp.reset(_straight_corridor())
    p0 = np.array([0.0, 0.0, 10.0])
    gp.step(p0, 0.0, force=True)
    # Large along-track jump in reported position would move natural anchor;
    # blend + clamp must keep first-waypoint jump within bound.
    p1 = np.array([30.0, 0.0, 10.0])
    gp.step(p1, 0.0, force=True)
    assert gp.last_anchor_jump_m <= 8.0 + 1e-6


def test_includes_goal_when_within_horizon():
    cfg = GlobalRefConfig(horizon_m=80.0, max_point_spacing_m=20.0, step_hz=5.0)
    gp = GlobalRefPlanner(cfg)
    F = _straight_corridor(length=50.0)
    gp.reset(F, goal=F[-1])
    Pref = gp.step(np.array([0.0, 0.0, 10.0]), 0.0, force=True)
    np.testing.assert_allclose(Pref[-1], F[-1], atol=1e-5)
