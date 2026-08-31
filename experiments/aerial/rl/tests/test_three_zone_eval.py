"""Unit tests for three-zone kinematic depth budget."""
from __future__ import annotations

from experiments.aerial.rl.v4_three_zone_eval import (
    ThreeZoneSpec,
    check_0i,
    depth_precision_vs_budget,
    kinematic_budget,
    max_engage_delay_m,
    need,
    simulate_three_zone,
)
import numpy as np


def test_need_braking_distance():
    assert abs(need(5.0, 2.0, 2.5) - 4.2) < 0.05


def test_default_spec_kinematically_feasible():
    spec = ThreeZoneSpec()
    ok, _, viol = simulate_three_zone(spec)
    assert ok, viol
    assert max_engage_delay_m(spec) > 0.1


def test_user_7_5_1_5_strict_infeasible_with_delay():
    spec = ThreeZoneSpec(l1_m=7.0, l2_m=5.0, v1_m_s=2.0, v2_m_s=1.0)
    ok, _, _ = simulate_three_zone(spec)
    assert not ok


def test_depth_budget_passes_tight_errors():
    spec = ThreeZoneSpec()
    kin = kinematic_budget(spec)
    budget = kin["max_underread_at_engage_m"]
    assert 0.0 < budget < 2.0
    assert kin["underread_budget_saturated"] is False
    gt = np.array([kin["engage_outer_m"], spec.l1_m, spec.l2_m, spec.l3_m])
    dhat = gt - 0.05  # slight over-read (safe)
    v = np.full_like(gt, 5.0)
    out = depth_precision_vs_budget(gt, dhat, v, kin, spec)
    assert out["all_bands_ok"]


def test_check_0i_b_star_and_a_strict():
    kin = {
        "sim_diagnostics": {"violations": ["z1", "z2"]},
    }
    # Thin support + zero under-read ⇒ ok but not authoritative.
    depth = {"all_bands_ok": True, "bands": {
        "engage_outer": {"n": 4, "ok": True, "p95_underread_m": 0.0},
        "cap_l1": {"n": 9, "ok": True, "p95_underread_m": 0.0},
    }}
    r_b = check_0i(depth_vs_budget=depth, kinematic=kin, acceptance_mode="b_star")
    r_a = check_0i(depth_vs_budget=depth, kinematic=kin, acceptance_mode="a_strict")
    assert r_b["ok"] is True
    assert r_b["authoritative"] is False
    assert r_b["ok_authoritative"] is False
    assert r_b["stop_before_l3"] is True
    assert r_b["stop_before_l3_nominal"] is True
    assert r_a["stop_probe_ok"] is True

    depth_full = {"all_bands_ok": True, "bands": {
        "engage_outer": {"n": 24, "ok": True, "p95_underread_m": 0.0},
        "cap_l1": {"n": 23, "ok": True, "p95_underread_m": 0.0},
    }}
    r_full = check_0i(depth_vs_budget=depth_full, kinematic=kin, acceptance_mode="b_star")
    assert r_full["authoritative"] is True
    assert r_full["ok_authoritative"] is True


def test_check_0i_g1_double_prime_z3_hard():
    """G1″: ok = all_bands_ok AND stop_before_l3 (z3 HARD ∧ collision HARD); probe dt=0.01."""
    kin = {"sim_diagnostics": {"violations": []}}
    # Budget FAIL: all_bands_ok False ⇒ ok False (even if stop probe passes).
    # p95=3.0 triggers z1 only — stop_before_l3 stays True; no collision.
    depth_budget_fail = {"all_bands_ok": False, "bands": {
        "engage_outer": {"n": 24, "ok": False, "p95_underread_m": 3.0},
        "cap_l1": {"n": 23, "ok": False, "p95_underread_m": 2.1},
    }}
    r = check_0i(depth_vs_budget=depth_budget_fail, kinematic=kin, acceptance_mode="b_star")
    assert r["gate_id"] == "G1_double_prime"
    assert r["probe_dt_s"] == 0.01
    assert r["stop_before_l3_nominal"] is True
    assert r["stop_before_l3"] is True  # z3/collision absent at 3 m
    assert r["no_collision_probe"] is True
    assert r["no_z3_probe"] is True
    assert r["sim_violation_counts"]["z1"] > 0
    assert r["underread_probe_m"] == 3.0
    assert r["ok"] is False
    assert r["authoritative"] is True
    # a_strict probe fails on z1; primary still False (budget)
    r_a = check_0i(depth_vs_budget=depth_budget_fail, kinematic=kin, acceptance_mode="a_strict")
    assert r_a["stop_probe_ok"] is False
    assert r_a["ok"] is False

    # z3 only (~5.8 m under-read at dt=0.01): G1″ primary FAIL (z3 HARD); no collision yet.
    depth_z3_only = {"all_bands_ok": True, "bands": {
        "engage_outer": {"n": 24, "ok": True, "p95_underread_m": 5.8},
        "cap_l1": {"n": 23, "ok": True, "p95_underread_m": 0.5},
    }}
    r_z3 = check_0i(depth_vs_budget=depth_z3_only, kinematic=kin, acceptance_mode="b_star")
    assert r_z3["all_bands_ok"] is True
    assert r_z3["stop_before_l3"] is False
    assert r_z3["sim_violation_counts"]["z3"] > 0
    assert r_z3["no_collision_probe"] is True
    assert r_z3["no_z3_probe"] is False
    assert r_z3["ok"] is False
    assert r_z3["ok_authoritative"] is False
    assert r_z3["stop_probe_ok"] is False  # B*: z3 HARD ∧ collision HARD

    # Collision HARD: ≥7.21 m under-read at dt=0.01 ⇒ collision ⇒ ok False.
    depth_coll = {"all_bands_ok": True, "bands": {
        "engage_outer": {"n": 24, "ok": True, "p95_underread_m": 7.25},
        "cap_l1": {"n": 23, "ok": True, "p95_underread_m": 0.5},
    }}
    r_coll = check_0i(depth_vs_budget=depth_coll, kinematic=kin, acceptance_mode="b_star")
    assert r_coll["no_collision_probe"] is False
    assert r_coll["sim_violation_counts"]["collision"] > 0
    assert r_coll["ok"] is False
    assert r_coll["ok_authoritative"] is False
    assert r_coll["stop_probe_ok"] is False


def test_z3_first_offender_probe_dt_authority():
    """G1″ §1.1: dt=0.01 is authoritative; z3∨coll first offender ≥5.0 m; coll≈7.21."""
    from experiments.aerial.rl.three_zone import ThreeZoneSpec, simulate_three_zone

    def first_offender(dt: float, *, want_z3_or_coll: bool) -> float:
        spec = ThreeZoneSpec(dt_s=dt)
        for i in range(0, 900):
            d = i * 0.01
            _, _, viol = simulate_three_zone(spec, engage_delay_m=-d)
            vs = {str(v) for v in viol}
            if want_z3_or_coll:
                if "z3" in vs or "collision" in vs:
                    return d
            elif "collision" in vs:
                return d
        raise AssertionError(f"no offender found dt={dt}")

    z3coll_01 = first_offender(0.01, want_z3_or_coll=True)
    z3coll_20 = first_offender(0.20, want_z3_or_coll=True)
    coll_01 = first_offender(0.01, want_z3_or_coll=False)
    coll_05 = first_offender(0.05, want_z3_or_coll=False)
    coll_20 = first_offender(0.20, want_z3_or_coll=False)
    # Alias lock: coarse dt falsely reports ~0.21 m; fine dt is the authority.
    assert z3coll_20 < 0.5
    assert z3coll_01 >= 5.0
    assert abs(coll_01 - 7.21) < 0.05
    assert abs(coll_05 - coll_01) < 0.05
    assert abs(coll_20 - coll_01) < 0.05
