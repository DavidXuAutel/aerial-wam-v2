"""Tests for V4 gate metrics."""
import numpy as np

from experiments.aerial.rl import v4_metrics as m


def test_progress_vs_heuristic_pass():
    r = m.check_progress_vs_heuristic([12.0, 11.0], [10.0, 9.0], delta_p=0.10)
    assert r["ok"]
    assert r["mean_progress_actor"] >= r["target_min"]


def test_progress_vs_heuristic_fail():
    r = m.check_progress_vs_heuristic([10.0], [10.0], delta_p=0.10)
    assert not r["ok"]


def test_safety_no_regression_pass():
    r = m.check_safety_no_regression(0.05, 0.10, near_coll_rate_ratio=0.75)
    assert r["ok"]


def test_safety_no_regression_coll_fail():
    r = m.check_safety_no_regression(0.15, 0.10)
    assert not r["ok"]


def test_aggregate_v4_verdict():
    s1 = m.check_progress_vs_heuristic([12.0], [10.0])
    s4 = m.check_safety_no_regression(0.05, 0.10)
    v = m.aggregate_v4_verdict({"1": s1, "4": s4})
    assert v["ok"]


def test_v4_gate_self_check():
    from experiments.aerial.rl._v4_gate import main

    assert main(["--self-check"]) == 0
