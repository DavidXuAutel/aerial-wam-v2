"""L0 honest Euclidean goal metrics for Phase-2 long_eval."""

from experiments.aerial.scripts.wam_phase2_long_eval import (
    _goal_closure,
    _monotone_inflate,
)


def test_goal_closure_full_and_none():
    assert _goal_closure(100.0, 0.0) == 1.0
    assert _goal_closure(100.0, 100.0) == 0.0
    assert abs(_goal_closure(153.42, 64.68) - (1.0 - 64.68 / 153.42)) < 1e-6


def test_monotone_inflate_flags_prog_without_euclidean():
    assert _monotone_inflate(0.98, 64.0) is True
    assert _monotone_inflate(0.98, 10.0) is False
    assert _monotone_inflate(0.5, 64.0) is False
