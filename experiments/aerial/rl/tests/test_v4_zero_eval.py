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
    pixel_absrel_stats,
    suggest_delta,
)


def test_pixel_absrel_near_domain():
    gt = np.array([1.0, 2.0, 4.0, 5.0])
    pred = np.array([1.1, 2.2, 4.4, 5.5])
    stats = pixel_absrel_stats(pred, gt, gt_lo=0.0, gt_hi=3.0)
    assert stats["n"] == 2
    assert abs(stats["median_absrel"] - 0.1) < 1e-6


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
