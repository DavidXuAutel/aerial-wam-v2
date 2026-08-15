"""Tests for V1 gate metrics (re-freeze §1.2)."""
from __future__ import annotations

import numpy as np

from experiments.aerial.rl import v1_metrics


def test_collision_reduction_pass():
    out = v1_metrics.check_collision_reduction(0.10, 0.07, delta=0.20)
    assert out["ok"] is True
    assert abs(out["target_max"] - 0.08) < 1e-9


def test_wm_fidelity_coll_na_when_no_collision_trajs():
    verdict = {
        "reward_ok": True,
        "done_ok": True,
        "recon_growth_ok": True,
        "passed": False,
        "coll_ok": False,
    }
    agg = {"coll_traj_pos": 0, "coll_auroc": float("nan"), "latent_norm_max": 19.0}
    out = v1_metrics.check_wm_fidelity(verdict, agg=agg, recon_growth_ok=True)
    assert out["coll_ok"] is None
    assert out["coll_insufficient"] is True
    assert out["ok"] is True


def test_wm_fidelity_fails_on_reward():
    verdict = {"reward_ok": False, "done_ok": True, "recon_growth_ok": True}
    agg = {"coll_traj_pos": 0, "latent_norm_max": 19.0}
    out = v1_metrics.check_wm_fidelity(verdict, agg=agg, recon_growth_ok=True)
    assert out["ok"] is False


def test_aggregate_rejects_proxy_signal3_for_merge():
    s1 = {"ok": True}
    s2 = {"ok": True}
    s3 = {"ok": True, "authoritative": False, "phase": "proxy"}
    out = v1_metrics.aggregate_v1_verdict({"1": s1, "2": s2, "3": s3})
    assert out["ok"] is False
    assert "Phase 2" in out["reason"]


def test_dual_channel_proxy_marks_phase():
    d = np.array([True, False, False])
    t = np.array([False, True, False])
    out = v1_metrics.check_dual_channel_independence(d, t, phase="proxy")
    assert out["phase"] == "proxy"
    assert out["authoritative"] is False
