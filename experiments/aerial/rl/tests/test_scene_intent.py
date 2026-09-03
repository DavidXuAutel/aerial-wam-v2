"""Unit tests for non-polyline scene intent (Phase-2 E0/E1)."""
from __future__ import annotations

import numpy as np
import pytest

from experiments.aerial.rl.scene_intent import (
    SceneIntentPlanner,
    TowardGoalIntent,
    clip_toward_goal,
)


def test_clip_toward_goal_far():
    p = np.array([0.0, 0.0, 10.0])
    g = np.array([100.0, 0.0, 10.0])
    c = clip_toward_goal(p, g, r_m=25.0)
    np.testing.assert_allclose(c, [25.0, 0.0, 10.0], atol=1e-5)


def test_clip_toward_goal_near_returns_g():
    p = np.array([0.0, 0.0, 10.0])
    g = np.array([10.0, 0.0, 10.0])
    c = clip_toward_goal(p, g, r_m=25.0)
    np.testing.assert_allclose(c, g, atol=1e-5)


def test_toward_g_never_uses_polyline_keys():
    intent = TowardGoalIntent(r_m=25.0, mode="toward_g")
    intent.reset()
    g_rel, info = intent.compute(
        curr_pos=np.zeros(3),
        curr_yaw=0.0,
        goal=np.array([80.0, 0.0, 0.0]),
    )
    assert "target_world" in info
    assert info.get("subgoal_source") == "toward_g"
    assert abs(float(g_rel[3]) - 25.0) < 1.0
    assert "cte_m" not in info or info["cte_m"] is None


def test_direct_g_keeps_full_distance():
    intent = TowardGoalIntent(r_m=25.0, mode="direct_g")
    intent.reset()
    g_rel, info = intent.compute(
        curr_pos=np.zeros(3),
        curr_yaw=0.0,
        goal=np.array([80.0, 0.0, 0.0]),
    )
    assert info["subgoal_source"] == "direct_g"
    assert float(g_rel[3]) == pytest.approx(80.0, abs=1e-3)


def test_scene_planner_picks_forward_when_clear():
    pl = SceneIntentPlanner(r_m=25.0)
    pl.reset()
    _g_rel, info = pl.compute(
        curr_pos=np.zeros(3),
        curr_yaw=0.0,
        goal=np.array([100.0, 0.0, 0.0]),
        d_fwd_hat=40.0,
    )
    assert info["subgoal_source"] == "scene"
    assert info["n_candidates"] >= 2
    tw = np.array(info["target_world"])
    assert tw[0] > 0.0


def test_scene_planner_holds_between_replans():
    pl = SceneIntentPlanner(r_m=25.0, replan_period_s=2.0, step_hz=5.0)
    pl.reset()
    _, info0 = pl.compute(
        np.zeros(3), 0.0, np.array([100.0, 0.0, 0.0]), 40.0
    )
    t0 = info0["target_world"]
    _, info1 = pl.compute(
        np.array([1.0, 0.0, 0.0]), 0.0, np.array([100.0, 0.0, 0.0]), 40.0
    )
    assert info1.get("replan") is False
    np.testing.assert_allclose(info1["target_world"], t0, atol=1e-6)


def test_scene_clear_path_stays_on_goal_ray():
    """E1 observability: clear forward depth ⇒ candidate 0 ⇒ dev 0 ⇒ ≡ toward_g."""
    pl = SceneIntentPlanner(r_m=25.0)
    pl.reset()
    _, info = pl.compute(np.zeros(3), 0.0, np.array([100.0, 0.0, 0.0]), 40.0)
    assert info["chosen_idx"] == 0
    assert info["dev_deg"] == pytest.approx(0.0, abs=1e-6)
    assert info["replan_count"] == 1
    assert info["offaxis_count"] == 0


def test_scene_tight_depth_toward_g_still_wins_in_soft_zone():
    """In the soft-penalty zone (d_danger < d_fwd < d_clear), toward_g progress
    dominates the soft forward penalty → candidate 0 should still win.
    Hard-block only fires when d_fwd < d_danger (< 3 m)."""
    pl = SceneIntentPlanner(r_m=25.0, d_danger=3.0, d_clear=22.0)
    pl.reset()
    _, info = pl.compute(np.zeros(3), 0.0, np.array([100.0, 0.0, 0.0]), 4.0)
    assert info["chosen_idx"] == 0, "toward_g progress should dominate at d_fwd=4m"
    assert info["offaxis_count"] == 0


def test_scene_imminent_danger_hard_blocks_forward():
    """When d_fwd < d_danger (< 3 m), forward candidates are hard-blocked
    → fan must pick a lateral candidate → offaxis counted."""
    pl = SceneIntentPlanner(r_m=25.0, d_danger=3.0, d_clear=22.0)
    pl.reset()
    # d_fwd=2.0 < d_danger=3.0 → hard block nose-aligned candidates
    _, info = pl.compute(np.zeros(3), 0.0, np.array([100.0, 0.0, 0.0]), 2.0)
    assert info["chosen_idx"] != 0, "forward candidate must be hard-blocked at d_fwd=2m"
    assert info["dev_deg"] > 1.0
    assert info["offaxis_count"] == 1


def test_scene_fan_reaches_past_danger_cone():
    """Regression: a fan narrower than the ±60° cone leaves nothing feasible,
    so every candidate is discarded and `scene` degenerates into `toward_g`."""
    pl = SceneIntentPlanner()
    assert max(abs(float(d)) for d in pl.yaw_offsets_deg) >= 60.0
    _, info = pl.compute(np.zeros(3), 0.0, np.array([100.0, 0.0, 0.0]), 3.0)
    assert info["n_feasible"] > 0
    assert info["n_fan_starved"] == 0


def test_scene_fan_starved_still_returns_target():
    pl = SceneIntentPlanner(r_m=25.0, yaw_offsets_deg=(0.0,))
    pl.reset()
    _, info = pl.compute(np.zeros(3), 0.0, np.array([100.0, 0.0, 0.0]), 1.0)
    assert info["n_feasible"] == 0
    assert info["n_fan_starved"] == 1
    assert np.all(np.isfinite(np.array(info["target_world"])))


def test_scene_counters_reset_per_route():
    pl = SceneIntentPlanner(r_m=25.0)
    pl.reset()
    pl.compute(np.zeros(3), 0.0, np.array([100.0, 0.0, 0.0]), 4.0)
    assert pl.replan_count == 1
    pl.reset()
    assert pl.replan_count == 0
    assert pl.offaxis_count == 0
