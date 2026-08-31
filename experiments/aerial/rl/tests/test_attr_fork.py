"""Unit tests for ATTR outcome / fork (V4_5AIP_ATTR_20260826)."""
from __future__ import annotations

from experiments.aerial.rl.attr_fork import classify_outcome, decide_fork, label_hard_coll_ep


def _ep(steps, **kw):
    d = {"idx": kw.get("idx", 0), "arrived": False, "hard_coll": False, "steps": steps}
    d.update(kw)
    return d


def test_classify_priority_hard_coll():
    steps = [
        {"clearance_fov": 4.0, "collided": False, "shield_channels": ["tau"], "emergency_latched": True},
        {"clearance_fov": 1.0, "collided": True, "shield_channels": [], "emergency_latched": True},
    ]
    assert classify_outcome(_ep(steps, hard_coll=True)) == "hard_coll"


def test_label_percept_overread():
    # d̂ systematically over-reads GT by 30%+
    steps = []
    for _ in range(6):
        steps.append(
            {
                "clearance_fov": 2.0,
                "d_hat_fovmin": 2.8,
                "collided": False,
                "emergency_latched": False,
                "shield_channels": ["three_zone"],
            }
        )
    steps.append({"clearance_fov": 0.5, "d_hat_fovmin": 2.0, "collided": True})
    lab, st = label_hard_coll_ep(_ep(steps, hard_coll=True))
    assert lab == "percept"
    assert st["median_rel"] is not None and st["median_rel"] >= 0.25


def test_label_plan_calibrated():
    steps = []
    for _ in range(6):
        steps.append(
            {
                "clearance_fov": 2.0,
                "d_hat_fovmin": 2.05,
                "collided": False,
                "emergency_latched": False,
                "shield_channels": ["three_zone"],
            }
        )
    steps.append({"clearance_fov": 0.4, "d_hat_fovmin": 0.42, "collided": True})
    lab, st = label_hard_coll_ep(_ep(steps, hard_coll=True))
    assert lab == "plan"
    assert st["median_abs_rel"] is not None and st["median_abs_rel"] <= 0.15


def test_fork_unclear_when_few_hard_coll():
    eps = [_ep([{"clearance_fov": 10.0, "collided": False}], arrived=True, idx=i) for i in range(32)]
    fork = decide_fork(eps)
    assert fork["label"] == "unclear"
    assert fork["next_action"] == "stop_no_train"
