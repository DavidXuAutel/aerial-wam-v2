# experiments/aerial/rl/tests/test_subgoal_generator.py
import numpy as np
import pytest
from experiments.aerial.rl.subgoal_generator import (
    project_to_polyline,
    sample_point_along_polyline,
    AdaptiveSubgoalGenerator,
)


def test_project_to_polyline_straight_line():
    path = np.array(
        [
            [0.0, 0.0, 10.0],
            [100.0, 0.0, 10.0],
            [200.0, 0.0, 10.0],
        ],
        dtype=np.float64,
    )
    pos = np.array([50.0, 5.0, 10.0], dtype=np.float64)
    proj, seg_idx, s_curr, rem_dist = project_to_polyline(pos, path, prev_s_max=0.0)
    np.testing.assert_allclose(proj, [50.0, 0.0, 10.0], atol=1e-5)
    assert seg_idx == 0
    assert pytest.approx(s_curr, abs=1e-3) == 50.0
    assert pytest.approx(rem_dist, abs=1e-3) == 150.0


def test_anti_backtracking_lock():
    path = np.array(
        [
            [0.0, 0.0, 10.0],
            [100.0, 0.0, 10.0],
            [200.0, 0.0, 10.0],
        ],
        dtype=np.float64,
    )
    pos_back = np.array([70.0, 0.0, 10.0], dtype=np.float64)
    proj, seg_idx, s_curr, rem_dist = project_to_polyline(pos_back, path, prev_s_max=80.0)
    assert s_curr >= 80.0
    assert pytest.approx(rem_dist, abs=1e-3) == 120.0


def test_sample_point_along_polyline():
    path = np.array(
        [
            [0.0, 0.0, 10.0],
            [100.0, 0.0, 10.0],
            [100.0, 100.0, 10.0],
        ],
        dtype=np.float64,
    )
    proj_point = np.array([80.0, 0.0, 10.0], dtype=np.float64)
    target = sample_point_along_polyline(
        path, segment_idx=0, proj_point=proj_point, r_lookahead=40.0
    )
    np.testing.assert_allclose(target, [100.0, 20.0, 10.0], atol=1e-5)


def test_adaptive_subgoal_generator_straight_clear():
    generator = AdaptiveSubgoalGenerator(r_base=55.0, r_min=20.0, cruise_speed=10.0)
    path = np.array([[0.0, 0.0, 10.0], [200.0, 0.0, 10.0]], dtype=np.float64)
    g_rel, info = generator.compute_subgoal(
        np.array([0.0, 0.0, 10.0]), 0.0, path, d_fwd_hat=30.0
    )
    assert g_rel.shape == (4,)
    assert pytest.approx(g_rel[0], abs=1.0) == 55.0
    assert pytest.approx(g_rel[1], abs=0.1) == 0.0
    assert pytest.approx(g_rel[3], abs=1.0) == 55.0
    assert info["alpha_clearance"] == 1.0
    assert info["safe_speed_limit"] >= 8.0


def test_adaptive_subgoal_generator_tight_turn_and_obstacle():
    generator = AdaptiveSubgoalGenerator(r_base=55.0, r_min=20.0, cruise_speed=10.0)
    path = np.array(
        [[0.0, 0.0, 10.0], [20.0, 0.0, 10.0], [20.0, 100.0, 10.0]],
        dtype=np.float64,
    )
    g_rel, info = generator.compute_subgoal(
        np.array([10.0, 0.0, 10.0]), 0.0, path, d_fwd_hat=3.0
    )
    assert info["r_lookahead"] <= 25.0
    assert info["alpha_clearance"] == pytest.approx(0.4, abs=1e-3)
    # Near danger: creep floor, not 4 m/s hard floor
    assert info["safe_speed_limit"] <= 1.0


def test_cte_recovery_shrinks_lookahead():
    generator = AdaptiveSubgoalGenerator(r_base=55.0, r_min=20.0, cruise_speed=10.0)
    path = np.array([[0.0, 0.0, 10.0], [200.0, 0.0, 10.0]], dtype=np.float64)
    # Large cross-track error
    g_rel, info = generator.compute_subgoal(
        np.array([50.0, 12.0, 10.0]), 0.0, path, d_fwd_hat=30.0
    )
    assert info["cte_m"] > 5.0
    assert info["r_lookahead"] < 55.0


def test_monotone_lock_updates_seg_idx():
    path = np.array(
        [[0.0, 0.0, 10.0], [100.0, 0.0, 10.0], [200.0, 0.0, 10.0]],
        dtype=np.float64,
    )
    # Orthogonal nearest is still on seg0, but lock forces s>=150 → seg1
    pos = np.array([40.0, 0.0, 10.0], dtype=np.float64)
    proj, seg_idx, s_curr, rem = project_to_polyline(pos, path, prev_s_max=150.0)
    assert s_curr >= 150.0
    assert seg_idx == 1
    np.testing.assert_allclose(proj[0], 150.0, atol=1e-5)


def test_terminal_creep_caps_v_safe():
    gen = AdaptiveSubgoalGenerator(
        r_base=55.0, r_min=20.0, cruise_speed=10.0, terminal_creep_rem_m=8.0
    )
    path = np.array([[0.0, 0.0, 10.0], [100.0, 0.0, 10.0]], dtype=np.float64)
    # Near end of path with clear depth
    _, info = gen.compute_subgoal(
        np.array([96.0, 0.0, 10.0]), 0.0, path, d_fwd_hat=40.0
    )
    assert info["rem_dist"] < 8.0
    assert info["safe_speed_limit"] < 10.0
    assert info["safe_speed_limit"] <= gen.min_creep_speed + 1e-6 + (
        info["rem_dist"] / 8.0
    ) * (10.0 - gen.min_creep_speed)


def test_cte_uses_true_projection_not_locked_point():
    """Off-track + high s-lock must not report CTE to the locked arc point."""
    gen = AdaptiveSubgoalGenerator(r_base=55.0, r_min=20.0, cruise_speed=10.0)
    path = np.array(
        [[0.0, 0.0, 10.0], [100.0, 0.0, 10.0], [200.0, 0.0, 10.0]],
        dtype=np.float64,
    )
    gen._prev_s_max = 150.0
    # True nearest is ~(40,0); lateral CTE=30. Locked point would be ~(150,0).
    _, info = gen.compute_subgoal(
        np.array([40.0, 30.0, 10.0]), 0.0, path, d_fwd_hat=40.0
    )
    assert info["cte_m"] == pytest.approx(30.0, abs=0.5)
    # Carrot must pull from true projection, not from locked s=150.
    target = np.asarray(info["target_world"], dtype=np.float64)
    assert target[0] < 100.0


def test_offtrack_freezes_monotone_progress():
    """CTE above freeze threshold must not inflate s_progress via monotone lock."""
    gen = AdaptiveSubgoalGenerator(
        r_base=55.0, r_min=20.0, cruise_speed=10.0, cte_lock_freeze_m=5.0
    )
    path = np.array(
        [[0.0, 0.0, 10.0], [100.0, 0.0, 10.0], [200.0, 0.0, 10.0]],
        dtype=np.float64,
    )
    gen._prev_s_max = 150.0
    _, info = gen.compute_subgoal(
        np.array([40.0, 30.0, 10.0]), 0.0, path, d_fwd_hat=40.0
    )
    assert info["cte_m"] > 5.0
    assert info["s_progress"] == pytest.approx(40.0, abs=1.0)
    assert info.get("s_lock_frozen") is True
    # Next on-track step should not re-jump to 150.
    assert gen._prev_s_max == pytest.approx(info["s_progress"], abs=1e-3)


def test_ontrack_monotone_lock_still_advances():
    gen = AdaptiveSubgoalGenerator(
        r_base=55.0, r_min=20.0, cruise_speed=10.0, cte_lock_freeze_m=5.0
    )
    path = np.array(
        [[0.0, 0.0, 10.0], [100.0, 0.0, 10.0], [200.0, 0.0, 10.0]],
        dtype=np.float64,
    )
    gen._prev_s_max = 80.0
    _, info = gen.compute_subgoal(
        np.array([70.0, 1.0, 10.0]), 0.0, path, d_fwd_hat=40.0
    )
    assert info["cte_m"] < 5.0
    assert info["s_progress"] >= 80.0
    assert not info.get("s_lock_frozen")

