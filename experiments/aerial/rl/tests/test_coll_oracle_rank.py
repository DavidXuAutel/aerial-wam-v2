"""Unit tests for GT-depth oracle ranking (B′-4)."""
from __future__ import annotations

import numpy as np

from experiments.aerial.rl.coll_oracle_rank import (
    oracle_pairwise_gaps,
    step_oracle_risks,
    verdict_from_oracle_gaps,
)


def test_step_oracle_wall_ahead_forward_riskier():
    depth = np.full((64, 64), 20.0, dtype=np.float64)
    # Obstacle in forward center; right half still clear → lateral gap > 0.
    depth[28:36, 32:36] = 1.5
    row = step_oracle_risks(depth, d_thresh_m=3.0, center_frac=0.5)
    assert row["forward_risk"] == 1.0
    best_lat = min(row["left_risk"], row["right_risk"])
    assert row["forward_risk"] > best_lat


def test_oracle_pairwise_gaps_positive_when_forward_worse():
    arms = {
        "forward": {"mean_oracle_risk": 0.8},
        "left": {"mean_oracle_risk": 0.1},
        "right": {"mean_oracle_risk": 0.2},
    }
    g = oracle_pairwise_gaps(arms)
    assert g["best_lateral"] == "left"
    assert abs(g["p_coll_gap_forward_minus_lateral"] - 0.7) < 1e-9


def test_verdict_high_ceiling():
    gaps = [{"p_coll_gap_forward_minus_lateral": 0.35} for _ in range(8)]
    v = verdict_from_oracle_gaps(gaps, high_ceiling_gap=0.3)
    assert v["high_ceiling"] is True
    assert v["label"] == "high_ceiling"
