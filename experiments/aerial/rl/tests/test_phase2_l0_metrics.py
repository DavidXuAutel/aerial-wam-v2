"""L0 honest Euclidean goal metrics for Phase-2 long_eval."""

import pytest

from experiments.aerial.scripts.merge_phase2_split_eval import merge_summaries
from experiments.aerial.scripts.wam_phase2_long_eval import (
    _goal_closure,
    _monotone_inflate,
    aggregate_metrics,
    select_route_indices,
)


def _ep(route_idx, *, closure, arrived=False, ir=0.0, replans=0, offaxis=0, maxdev=0.0):
    return {
        "route_idx": route_idx,
        "base_route_idx": 100 + route_idx,
        "goal_closure": closure,
        "arrived": arrived,
        "severe_collision": False,
        "collided": False,
        "progress_ratio": 0.0,
        "spl": 1.0 if arrived else 0.0,
        "intervention_rate": ir,
        "monotone_inflate": False,
        "n_intent_replans": replans,
        "n_intent_offaxis": offaxis,
        "max_intent_dev_deg": maxdev,
    }


def _summary(episodes, *, source="scene"):
    scored, spawn_fails, metrics, verdict = aggregate_metrics(episodes)
    return {
        "protocol_version": "wam_phase2_goal_scene_e0_20260903",
        "subgoal_source": source,
        "goal_feat_mode": "metre",
        "actor_ckpt": "ckpt_step_e",
        "cruise_speed_m_s": 10.0,
        "rolling_global": False,
        "route_indices": [e["route_idx"] for e in episodes],
        "n_scored": len(scored),
        "n_spawn_fail_f1": len(spawn_fails),
        "metrics": metrics,
        "verdict": verdict,
        "episodes": episodes,
    }


def test_goal_closure_full_and_none():
    assert _goal_closure(100.0, 0.0) == 1.0
    assert _goal_closure(100.0, 100.0) == 0.0
    assert abs(_goal_closure(153.42, 64.68) - (1.0 - 64.68 / 153.42)) < 1e-6


def test_monotone_inflate_flags_prog_without_euclidean():
    assert _monotone_inflate(0.98, 64.0) is True
    assert _monotone_inflate(0.98, 10.0) is False
    assert _monotone_inflate(0.5, 64.0) is False


def test_aggregate_excludes_spawn_fails_from_scored():
    eps = [_ep(0, closure=0.5), {"route_idx": 1, "spawn_fail": True}]
    scored, spawn_fails, metrics, _ = aggregate_metrics(eps)
    assert len(scored) == 1 and len(spawn_fails) == 1
    assert metrics["mean_goal_closure"] == 0.5


def test_split_merge_matches_single_box_run():
    """A merged two-box row must equal the same routes run on one box."""
    e0 = _ep(0, closure=0.66, ir=0.0, replans=40, offaxis=6, maxdev=45.0)
    e1 = _ep(1, closure=0.31, ir=0.013, replans=60, offaxis=0, maxdev=0.0)

    one_box = _summary([e0, e1])
    merged = merge_summaries(
        [_summary([e0]), _summary([e1])], ["box_110.json", "box_125.json"]
    )

    assert merged["metrics"] == one_box["metrics"]
    assert merged["n_scored"] == 2
    assert merged["route_indices"] == [0, 1]
    # max, not mean — the trap that hand-merging falls into
    assert merged["metrics"]["max_intent_dev_deg"] == 45.0
    assert merged["metrics"]["n_intent_replans"] == 100
    assert merged["metrics"]["intent_offaxis_frac"] == 0.06
    assert merged["verdict"] == "FAIL"  # SR=0


def test_routes_flag_overrides_episodes_and_is_0_based():
    """The whole point of the split: box A gets route 0, box B gets route 1."""
    assert select_route_indices(16, 2, None) == [0, 1]
    assert select_route_indices(16, 2, "0") == [0]
    assert select_route_indices(16, 2, "1") == [1]
    # --routes wins over --episodes, and does not have to be a prefix
    assert select_route_indices(16, 1, "1,3") == [1, 3]
    assert select_route_indices(2, 99, None) == [0, 1]  # clipped to annotation


def test_routes_flag_refuses_bad_input():
    with pytest.raises(SystemExit, match="out of range"):
        select_route_indices(2, 2, "2")  # 0-based: index 2 of a 2-route anno
    with pytest.raises(SystemExit, match="out of range"):
        select_route_indices(16, 2, "-1")
    with pytest.raises(SystemExit, match="duplicates"):
        select_route_indices(16, 2, "0,0")


def test_merge_refuses_different_arms():
    with pytest.raises(SystemExit, match="not the same arm"):
        merge_summaries(
            [
                _summary([_ep(0, closure=0.5)], source="scene"),
                _summary([_ep(1, closure=0.4)], source="toward_g"),
            ],
            ["a.json", "b.json"],
        )


def test_merge_refuses_overlapping_routes():
    with pytest.raises(SystemExit, match="appears in both"):
        merge_summaries(
            [_summary([_ep(0, closure=0.5)]), _summary([_ep(0, closure=0.5)])],
            ["a.json", "b.json"],
        )
