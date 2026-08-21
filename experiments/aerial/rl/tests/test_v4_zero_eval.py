"""Unit tests for V4-⓪ scorers (torch-free)."""
from __future__ import annotations

import numpy as np

from experiments.aerial.rl.v4_zero_eval import (
    ZeroThresholds,
    check_0a,
    check_0c,
    check_0d,
    check_support_b,
    clearance_sweep,
    near_absrel_gt_bins,
    pixel_absrel_stats,
    suggest_delta,
)


def test_pixel_absrel_near_domain():
    gt = np.array([1.0, 2.0, 4.0, 5.0])
    pred = np.array([1.1, 2.2, 4.4, 5.5])
    stats = pixel_absrel_stats(pred, gt, gt_lo=0.0, gt_hi=3.0)
    assert stats["n"] == 2
    assert abs(stats["median_absrel"] - 0.1) < 1e-6


def test_near_absrel_gt_bins_split():
    # (0,1.5]: AbsRel 1.0; (1.5,3]: AbsRel 0.1
    gt = np.array([1.0, 1.0, 2.0, 2.0])
    pred = np.array([2.0, 2.0, 2.2, 2.2])
    bins = near_absrel_gt_bins(pred, gt, edges=(0.0, 1.5, 3.0))
    assert bins[0]["n_px"] == 2
    assert abs(bins[0]["p90_absrel"] - 1.0) < 1e-6
    assert bins[1]["n_px"] == 2
    assert abs(bins[1]["p90_absrel"] - 0.1) < 1e-6


def test_support_b_pass():
    thr = ZeroThresholds()
    ok = check_support_b([200] * 120, thr=thr)
    assert ok["ok"] is True
    assert ok["support_px"] == 24_000


def test_support_b_fail_single_frame_dominates():
    thr = ZeroThresholds()
    frames = [90000] + [500] * 20
    bad = check_support_b(frames, thr=thr)
    assert bad["ok"] is False


def test_0d_miss_rate_and_consecutive():
    thr = ZeroThresholds(trigger_m=3.0)
    gt = np.array([2.0, 2.5, 2.0, 2.0, 4.0])
    dhat = np.array([3.5, 3.5, 3.5, 2.0, 4.0])  # two consecutive misses
    r = check_0d(gt, dhat, thr=thr)
    assert r["ok"] is False
    assert r["max_consecutive_miss"] == 3
    assert r["n_near_forward_frames"] == r["n_cond"] == 4


def test_heldout_episodes_seeded_split():
    from experiments.aerial.rl.holdout_split import split_holdout_indices
    from experiments.aerial.rl.v4_zero_eval import _heldout_episodes

    eps = list(range(10))
    scored, meta = _heldout_episodes(eps, 0.25, seed=0)
    _, hold_idx, meta2 = split_holdout_indices(10, frac=0.25, seed=0)
    assert meta["regime"] == "seeded_holdout"
    assert meta["holdout_indices"] == sorted(hold_idx)
    assert len(scored) == meta["n_holdout"] == 2  # round(0.25*10)=2 (banker)
    all_eps, meta0 = _heldout_episodes(eps, 0.0, seed=0)
    assert all_eps == eps
    assert meta0["regime"] == "all_episodes"


def test_train_eval_holdout_indices_match():
    from experiments.aerial.rl.holdout_split import split_holdout_indices

    t1, h1, m1 = split_holdout_indices(77, frac=0.2, seed=0)
    t2, h2, m2 = split_holdout_indices(77, frac=0.2, seed=0)
    assert sorted(h1) == sorted(h2) == m1["holdout_indices"]
    assert set(t1) | set(h1) == set(range(77))
    assert set(t1).isdisjoint(h1)


def test_clearance_sweep_aligned():
    thr = ZeroThresholds(trigger_m=3.0, min_tau_s=1.0)
    gt_fov = np.array([3.5, 4.0, 5.0, 6.0])
    dhat = np.array([2.5, 3.5, 4.0, 5.0])
    gt_fwd = np.array([3.5, 4.0, 5.0, 6.0])
    tau = np.array([2.0, 2.0, 2.0, 2.0])
    v = np.array([1.0, 1.0, 1.0, 1.0])
    rows = clearance_sweep(gt_fov, dhat, gt_fwd, tau, v, thr=thr, bin_width=1.0)
    assert rows
    assert all("clearance_lo" in r for r in rows)


def test_suggest_delta_finds_first_bin():
    thr = ZeroThresholds()
    rows = [
        {"clearance_lo": 3.0, "n": 10, "p_dhat_false_trigger": 0.2, "p_tau_false_trigger": 0.1},
        {"clearance_lo": 3.5, "n": 10, "p_dhat_false_trigger": 0.03, "p_tau_false_trigger": 0.02},
    ]
    hint = suggest_delta(rows, thr=thr)
    assert hint["suggested_lo_clearance_m"] == 3.5


def test_0f_outer_absrel_not_gated_by_0c_threshold():
    """⓪f(1)(2) are report-only — outer p90>0.50 must not fail primary merge."""
    from experiments.aerial.rl.v4_zero_eval import aggregate_verdict

    sub = {
        "0a": {"ok": True},
        "0b": {"ok": True},
        "0c": {"ok": True},
        "0d": {"ok": True},
        "0e": {"ok": True},
        "0f": {
            "ok": True,  # support-only pre-freeze
            "median_absrel": 0.10,
            "p90_absrel": 0.80,  # would fail if wrongly using ⓪c's 0.50
        },
    }
    v = aggregate_verdict(sub)
    assert v["ok"] is True
    assert v["ok_primary"] is True
    assert v["ok_0f"] is True


def test_aggregate_primary_ignores_0f_fail():
    from experiments.aerial.rl.v4_zero_eval import aggregate_verdict

    sub = {
        "0a": {"ok": True},
        "0b": {"ok": True},
        "0c": {"ok": False},
        "0d": {"ok": True},
        "0e": {"ok": True},
        "0f": {"ok": False},
    }
    v = aggregate_verdict(sub)
    assert v["ok"] is False
    assert v["ok_primary"] is False
    assert v["ok_0f"] is False
