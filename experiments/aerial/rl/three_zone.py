"""Three-zone speed governor — shared kinematics for shield + offline eval.

Default profile (2026-08-29): **8 / 5 / 1.5 m @ 2 / 1 / 0.2 m/s** with cruise
**25 m/s**, ``a_max=2.5 m/s²``, plus discrete schedule margins so bang-bang at
``dt=0.2`` still meets zone caps (legacy 5 m/s declare used the same L/v lines
with cruise 5 → engage ≈ 12.2 m; see ``V4_THREE_ZONE_DECLARE_20260823.md``).
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace
from typing import Any, Dict, List, Optional, Tuple

# Geometric lines + speed caps (unchanged L/v from 20260823).
DEFAULT_L1 = 8.0
DEFAULT_L2 = 5.0
DEFAULT_L3 = 1.5
DEFAULT_V1 = 2.0
DEFAULT_V2 = 1.0
DEFAULT_V_STOP = 0.2
DEFAULT_V_CRUISE = 25.0
DEFAULT_A_MAX = 2.5
DEFAULT_DT = 0.2
DEFAULT_DELAY_S = 0.2
# Discrete lag steps at 25 m/s (control periods) absorbed before each geometric line.
DEFAULT_DISC_LAG_STEPS_AT_25 = 4
# G1″: ⓪i stop probe only — not deploy control-loop dt.
STOP_PROBE_DT_S = 0.01


def need(v0: float, v1: float, a: float) -> float:
    if v0 <= v1:
        return 0.0
    return (v0 * v0 - v1 * v1) / (2.0 * max(a, 1e-9))


def disc_lag_steps_for_cruise(v_cruise_m_s: float) -> int:
    """Scale lag pad with cruise: 5 m/s → 1 step, 25 m/s → 4 steps."""
    return int(max(1, min(DEFAULT_DISC_LAG_STEPS_AT_25, round(float(v_cruise_m_s) / 6.25))))


def disc_schedule_margin_m(
    v_tgt: float,
    *,
    a_max_m_s2: float = DEFAULT_A_MAX,
    dt_s: float = DEFAULT_DT,
    lag_steps: int = DEFAULT_DISC_LAG_STEPS_AT_25,
) -> float:
    """Extra metres so bang-bang reaches ``v_tgt`` before a geometric line.

    Models up to ``lag_steps`` of one-step accel lag at constant ``a_max``.
    """
    n = max(0, int(lag_steps))
    return float(
        need(
            float(v_tgt) + n * float(a_max_m_s2) * float(dt_s),
            float(v_tgt),
            float(a_max_m_s2),
        )
    )


_DEFAULT_LAG = disc_lag_steps_for_cruise(DEFAULT_V_CRUISE)
DEFAULT_SCHEDULE_MARGIN_L1_M = disc_schedule_margin_m(DEFAULT_V1, lag_steps=_DEFAULT_LAG)
DEFAULT_SCHEDULE_MARGIN_L2_M = disc_schedule_margin_m(DEFAULT_V2, lag_steps=_DEFAULT_LAG)


@dataclass(frozen=True)
class ThreeZoneSpec:
    l1_m: float = DEFAULT_L1
    l2_m: float = DEFAULT_L2
    l3_m: float = DEFAULT_L3
    v1_m_s: float = DEFAULT_V1
    v2_m_s: float = DEFAULT_V2
    v_stop_m_s: float = DEFAULT_V_STOP
    v_cruise_m_s: float = DEFAULT_V_CRUISE
    a_max_m_s2: float = DEFAULT_A_MAX
    dt_s: float = DEFAULT_DT
    delay_s: float = DEFAULT_DELAY_S
    #: Reach ``v1`` by ``l1_m + schedule_margin_l1_m`` (not only at ``l1_m``).
    schedule_margin_l1_m: float = DEFAULT_SCHEDULE_MARGIN_L1_M
    #: Reach ``v2`` by ``l2_m + schedule_margin_l2_m``.
    schedule_margin_l2_m: float = DEFAULT_SCHEDULE_MARGIN_L2_M

    @property
    def l1_sched_m(self) -> float:
        return float(self.l1_m) + float(self.schedule_margin_l1_m)

    @property
    def l2_sched_m(self) -> float:
        return float(self.l2_m) + float(self.schedule_margin_l2_m)

    @property
    def engage_outer_m(self) -> float:
        return self.l1_sched_m + need(self.v_cruise_m_s, self.v1_m_s, self.a_max_m_s2)

    @classmethod
    def for_cruise(cls, v_cruise_m_s: float, **overrides: Any) -> "ThreeZoneSpec":
        """Build a spec with lag margins matched to ``v_cruise_m_s``."""
        cfg: Dict[str, Any] = {"v_cruise_m_s": float(v_cruise_m_s)}
        cfg.update(overrides)
        return cls.from_mapping(cfg)

    @classmethod
    def from_mapping(cls, cfg: Any) -> "ThreeZoneSpec":
        g = cfg if isinstance(cfg, dict) else {}
        a = float(g.get("a_max_m_s2", DEFAULT_A_MAX))
        dt = float(g.get("dt_s", DEFAULT_DT))
        v1 = float(g.get("v1_m_s", DEFAULT_V1))
        v2 = float(g.get("v2_m_s", DEFAULT_V2))
        vc = float(g.get("v_cruise_m_s", DEFAULT_V_CRUISE))
        if "disc_lag_steps" in g:
            lag = int(g["disc_lag_steps"])
        else:
            lag = disc_lag_steps_for_cruise(vc)
        m1 = g.get("schedule_margin_l1_m")
        m2 = g.get("schedule_margin_l2_m")
        if m1 is None:
            m1 = disc_schedule_margin_m(v1, a_max_m_s2=a, dt_s=dt, lag_steps=lag)
        if m2 is None:
            m2 = disc_schedule_margin_m(v2, a_max_m_s2=a, dt_s=dt, lag_steps=lag)
        return cls(
            l1_m=float(g.get("l1_m", DEFAULT_L1)),
            l2_m=float(g.get("l2_m", DEFAULT_L2)),
            l3_m=float(g.get("l3_m", DEFAULT_L3)),
            v1_m_s=v1,
            v2_m_s=v2,
            v_stop_m_s=float(g.get("v_stop_m_s", DEFAULT_V_STOP)),
            v_cruise_m_s=vc,
            a_max_m_s2=a,
            dt_s=dt,
            delay_s=float(g.get("delay_s", DEFAULT_DELAY_S)),
            schedule_margin_l1_m=float(m1),
            schedule_margin_l2_m=float(m2),
        )


def stop_probe_spec(spec: Optional[ThreeZoneSpec] = None) -> ThreeZoneSpec:
    """ThreeZoneSpec for ⓪i stop probe with de-aliased ``dt_s=0.01`` (G1″)."""
    base = spec if spec is not None else ThreeZoneSpec()
    return replace(base, dt_s=float(STOP_PROBE_DT_S))


def default_sim_d0(spec: ThreeZoneSpec) -> float:
    """Start beyond engage so cruise→v1 has a full outer band."""
    return float(max(spec.engage_outer_m + 40.0, 60.0))


def resolve_v_ref_m_s(
    spec: ThreeZoneSpec,
    *,
    v_now_m_s: Optional[float] = None,
    v_cmd_m_s: Optional[float] = None,
) -> float:
    """Reference speed for engage / outer schedule (≤ configured cruise).

    Uses ``max(v_now, v_cmd)`` so commanding accel expands the outer band
    immediately; never exceeds ``spec.v_cruise_m_s``.
    """
    vc = float(spec.v_cruise_m_s)
    parts = [float(spec.v1_m_s)]
    if v_now_m_s is not None and math.isfinite(float(v_now_m_s)):
        parts.append(max(0.0, float(v_now_m_s)))
    if v_cmd_m_s is not None and math.isfinite(float(v_cmd_m_s)):
        parts.append(max(0.0, float(v_cmd_m_s)))
    if v_now_m_s is None and v_cmd_m_s is None:
        return vc
    return float(min(vc, max(parts)))


def engage_outer_for_speed(spec: ThreeZoneSpec, v_ref_m_s: float) -> float:
    """Engage distance if braking from ``v_ref`` (dynamic outer band)."""
    v_ref = float(min(float(spec.v_cruise_m_s), max(float(v_ref_m_s), 0.0)))
    lag = disc_lag_steps_for_cruise(max(v_ref, float(spec.v1_m_s)))
    m1 = disc_schedule_margin_m(
        float(spec.v1_m_s),
        a_max_m_s2=float(spec.a_max_m_s2),
        dt_s=float(spec.dt_s),
        lag_steps=lag,
    )
    l1e = float(spec.l1_m) + float(m1)
    return l1e + need(v_ref, float(spec.v1_m_s), float(spec.a_max_m_s2))


def planned_speed_m_s(
    d_hat: float,
    spec: ThreeZoneSpec,
    *,
    v_ref_m_s: Optional[float] = None,
) -> float:
    """Instantaneous speed cap from predicted forward depth.

    When ``v_ref_m_s`` is set (deploy dynamic mode), the outer engage band is
    sized for that speed (capped by ``v_cruise``). Open-air ceiling stays
    ``v_cruise`` so the vehicle may still accelerate; commanding a higher
    ``v_cmd`` must be folded into ``v_ref`` by the caller.
    """
    d = float(d_hat)
    v_ref = (
        float(spec.v_cruise_m_s)
        if v_ref_m_s is None
        else float(min(float(spec.v_cruise_m_s), max(float(v_ref_m_s), 0.0)))
    )
    lag = disc_lag_steps_for_cruise(max(v_ref, float(spec.v1_m_s)))
    m1 = (
        float(spec.schedule_margin_l1_m)
        if v_ref_m_s is None
        else disc_schedule_margin_m(
            float(spec.v1_m_s),
            a_max_m_s2=float(spec.a_max_m_s2),
            dt_s=float(spec.dt_s),
            lag_steps=lag,
        )
    )
    m2 = (
        float(spec.schedule_margin_l2_m)
        if v_ref_m_s is None
        else disc_schedule_margin_m(
            float(spec.v2_m_s),
            a_max_m_s2=float(spec.a_max_m_s2),
            dt_s=float(spec.dt_s),
            lag_steps=lag,
        )
    )
    l1e = float(spec.l1_m) + m1
    l2e = float(spec.l2_m) + m2
    engage = l1e + need(v_ref, float(spec.v1_m_s), float(spec.a_max_m_s2))
    if d > engage:
        return float(spec.v_cruise_m_s)
    if d > l1e:
        return math.sqrt(
            max(0.0, spec.v1_m_s ** 2 + 2.0 * spec.a_max_m_s2 * (d - l1e))
        )
    if d > spec.l1_m:
        return float(spec.v1_m_s)
    if d > l2e:
        return min(
            spec.v1_m_s,
            math.sqrt(max(0.0, spec.v2_m_s ** 2 + 2.0 * spec.a_max_m_s2 * (d - l2e))),
        )
    if d > spec.l2_m:
        return float(spec.v2_m_s)
    if d > spec.l3_m:
        return min(
            spec.v2_m_s,
            math.sqrt(
                max(0.0, spec.v_stop_m_s ** 2 + 2.0 * spec.a_max_m_s2 * (d - spec.l3_m))
            ),
        )
    return float(spec.v_stop_m_s)


def simulate_three_zone(
    spec: ThreeZoneSpec,
    *,
    d0: Optional[float] = None,
    v0: Optional[float] = None,
    engage_delay_m: float = 0.0,
) -> Tuple[bool, List[Tuple[float, float, float]], List[str]]:
    """Bang-bang decel profile; optional constant engage delay (m) after true engage."""
    v0 = float(spec.v_cruise_m_s if v0 is None else v0)
    d0_use = float(default_sim_d0(spec) if d0 is None else d0)
    d, v, t = float(d0_use), v0, 0.0
    traj: List[Tuple[float, float, float]] = []
    violations: List[str] = []
    engaged = False
    true_eng = spec.engage_outer_m
    t_lim = max(40.0, 3.0 * true_eng / max(spec.v_stop_m_s, 0.2))

    if spec.delay_s > 0:
        d -= v * spec.delay_s
        t += spec.delay_s

    while t < t_lim:
        if not engaged and d <= true_eng + engage_delay_m:
            engaged = True
        if engaged:
            v_plan = planned_speed_m_s(d, spec)
            if v > v_plan + 1e-3:
                v = max(v_plan, v - spec.a_max_m_s2 * spec.dt_s)
        traj.append((t, d, v))
        if d <= spec.l1_m and d > spec.l2_m and v > spec.v1_m_s + 0.05:
            violations.append("z1")
        if d <= spec.l2_m and d > spec.l3_m and v > spec.v2_m_s + 0.05:
            violations.append("z2")
        if d <= spec.l3_m and v > spec.v_stop_m_s + 0.05:
            violations.append("z3")
        t += spec.dt_s
        d -= v * spec.dt_s
        if d <= spec.l3_m and v <= spec.v_stop_m_s + 0.05:
            return len(violations) == 0, traj, violations
        if d <= 0:
            return False, traj, violations + ["collision"]
    return False, traj, violations + ["timeout"]


def max_engage_delay_m(spec: ThreeZoneSpec, *, d0: Optional[float] = None) -> float:
    """Legacy helper: max *early-engage* advance (m) still passing caps.

    Positive ``engage_delay_m`` in ``simulate_three_zone`` advances engage
    (`d <= true_eng + engage_delay_m`), i.e. it is *not* under-read.
    """
    d0_use = float(default_sim_d0(spec) if d0 is None else d0)
    lo, hi = 0.0, 0.5
    hi_cap = 64.0
    while hi < hi_cap:
        ok, _, _ = simulate_three_zone(spec, d0=d0_use, engage_delay_m=hi)
        if not ok:
            break
        lo = hi
        hi *= 2.0
    if hi >= hi_cap:
        return lo
    for _ in range(24):
        mid = 0.5 * (lo + hi)
        ok, _, _ = simulate_three_zone(spec, d0=d0_use, engage_delay_m=mid)
        if ok:
            lo = mid
        else:
            hi = mid
    return lo


def max_underread_budget_m(
    spec: ThreeZoneSpec, *, d0: Optional[float] = None
) -> Tuple[float, bool]:
    """Max late-engage budget (m) under which zone caps still pass.

    Under-read ``(D̂ − GT > 0)`` maps to *later* engage, which in
    ``simulate_three_zone`` is modeled by ``engage_delay_m < 0``.

    Returns ``(budget_m, saturated)`` where ``saturated=True`` means no failure
    was found up to the search ceiling.
    """
    d0_use = float(default_sim_d0(spec) if d0 is None else d0)
    lo, hi = 0.0, 0.5
    hi_cap = 64.0
    while hi < hi_cap:
        ok, _, _ = simulate_three_zone(spec, d0=d0_use, engage_delay_m=-hi)
        if not ok:
            break
        lo = hi
        hi *= 2.0
    if hi >= hi_cap:
        return lo, True
    for _ in range(28):
        mid = 0.5 * (lo + hi)
        ok, _, _ = simulate_three_zone(spec, d0=d0_use, engage_delay_m=-mid)
        if ok:
            lo = mid
        else:
            hi = mid
    return lo, False


def kinematic_budget(spec: ThreeZoneSpec) -> Dict[str, Any]:
    """Per-boundary depth under-read budget (D̂ − GT > 0 ⇒ late engage)."""
    d0 = default_sim_d0(spec)
    ok, _, viol = simulate_three_zone(spec, d0=d0)
    eng = spec.engage_outer_m
    underread_budget, sat = max_underread_budget_m(spec, d0=d0)
    engage_advance_budget = max_engage_delay_m(spec, d0=d0)
    m_outer = eng - need(spec.v_cruise_m_s, spec.v1_m_s, spec.a_max_m_s2) - spec.l1_sched_m
    m_mid = (spec.l1_m - spec.l2_m) - need(spec.v1_m_s, spec.v2_m_s, spec.a_max_m_s2)
    m_inner = (spec.l2_m - spec.l3_m) - need(spec.v2_m_s, spec.v_stop_m_s, spec.a_max_m_s2)
    b_l1 = max(0.0, underread_budget)
    b_l2 = max(0.0, min(m_mid, underread_budget))
    b_l3 = max(0.0, min(m_inner, underread_budget))
    return {
        "spec": asdict(spec),
        "feasible_nominal": ok,
        "sim_diagnostics": {"violations": list(viol) if not ok else []},
        "engage_outer_m": round(eng, 3),
        # Legacy key kept for compatibility with existing consumers.
        "max_engage_delay_m": round(engage_advance_budget, 3),
        "max_underread_at_engage_m": round(underread_budget, 3),
        "underread_budget_saturated": bool(sat),
        "segment_margin_m": {
            "outer_to_l1": round(m_outer, 3),
            "l1_to_l2": round(m_mid, 3),
            "l2_to_l3": round(m_inner, 3),
        },
        "required_sigma_rel_at_l1": round(b_l1 / max(spec.l1_m, 1e-6), 4),
        "required_sigma_rel_at_l2": round(b_l2 / max(spec.l2_m, 1e-6), 4),
        "required_sigma_rel_at_l3": round(b_l3 / max(spec.l3_m, 1e-6), 4),
    }
