"""TZ in-band predicate (V4_TZ_CRITERIA_REFREEZE_20260826 + Errata E0/E1).

Band is the deploy three-zone working interval ``(L3, L1] = (1.5, 8.0]``.
Speed-cap steps (``three_zone`` channel) **may** count; τ / p_coll emergency
latch, L3 active brake (``three_zone_brake``), and hard collision **exclude**
the step. Once an emergency channel is seen, the remainder of the episode is
also excluded.

E1 (Errata TE-4a): hard-collision **episodes** are excluded entirely from
``band_frac`` / θ statistics (not only the collided step).
E0: optional half-band buckets ``(1.5,5]`` / ``(5,8]`` (report-only).
"""
from __future__ import annotations

from typing import Any, Iterable, Optional, Sequence

import numpy as np

REFREEZE_ID = "V4_TZ_CRITERIA_REFREEZE_20260826"
ERRATA_ID = "tz-errata-p0b-20260826"
TZ_BAND_LO_M = 1.5
TZ_BAND_MID_M = 5.0  # L2; E0 half-band split
TZ_BAND_HI_M = 8.0
EMERGENCY_CHANNELS = frozenset({"tau", "p_coll", "three_zone_brake", "three_zone_3d"})


def is_emergency_channels(channels: Optional[Iterable[str]]) -> bool:
    if not channels:
        return False
    return bool(EMERGENCY_CHANNELS.intersection({str(c) for c in channels}))


def step_in_band(
    *,
    clearance_m: Optional[float],
    channels: Optional[Sequence[str]] = None,
    hard_coll: bool = False,
    emergency_latched: bool = False,
    lo_m: float = TZ_BAND_LO_M,
    hi_m: float = TZ_BAND_HI_M,
) -> bool:
    """Return True iff this step counts toward ``band_frac`` under TZ-3."""
    if hard_coll or emergency_latched:
        return False
    if is_emergency_channels(channels):
        return False
    if clearance_m is None:
        return False
    c = float(clearance_m)
    if not np.isfinite(c):
        return False
    return float(lo_m) < c <= float(hi_m)


def annotate_trace_in_band(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return rows with ``in_band`` / ``emergency_latched`` under TZ-3."""
    latched = False
    out: list[dict[str, Any]] = []
    for row in rows:
        ch = list(row.get("shield_channels") or row.get("channels") or [])
        hard = bool(row.get("collided") or row.get("hard_coll"))
        clearance = row.get("clearance_fov")
        if is_emergency_channels(ch):
            latched = True
        in_b = step_in_band(
            clearance_m=clearance,
            channels=ch,
            hard_coll=hard,
            emergency_latched=latched,
        )
        r = dict(row)
        r["shield_channels"] = ch
        r["emergency_latched"] = bool(latched)
        r["in_band"] = bool(in_b)
        out.append(r)
    return out


def episode_has_hard_coll(rows: Sequence[dict[str, Any]]) -> bool:
    return any(bool(r.get("collided") or r.get("hard_coll")) for r in rows)


def band_frac(
    rows: Sequence[dict[str, Any]],
    *,
    exclude_hard_coll_episode: bool = True,
) -> float:
    """Fraction of steps in-band.

    E1 default: if any step in the episode hard-collided, return NaN so the
    episode is dropped from θ / median statistics (整局剔除).
    """
    if not rows:
        return float("nan")
    if exclude_hard_coll_episode and episode_has_hard_coll(rows):
        return float("nan")
    n = sum(1 for r in rows if r.get("in_band"))
    return float(n) / float(len(rows))


def band_frac_buckets(
    rows: Sequence[dict[str, Any]],
    *,
    exclude_hard_coll_episode: bool = True,
) -> dict[str, float]:
    """E0 report-only half-band occupancy: ``(1.5,5]`` and ``(5,8]``."""
    if not rows:
        return {
            "inner_l3_to_l2": float("nan"),
            "outer_l2_to_l1": float("nan"),
        }
    if exclude_hard_coll_episode and episode_has_hard_coll(rows):
        return {
            "inner_l3_to_l2": float("nan"),
            "outer_l2_to_l1": float("nan"),
        }
    n = float(len(rows))
    latched = False
    n_inner = 0
    n_outer = 0
    for row in rows:
        ch = list(row.get("shield_channels") or row.get("channels") or [])
        hard = bool(row.get("collided") or row.get("hard_coll"))
        if is_emergency_channels(ch):
            latched = True
        c = row.get("clearance_fov")
        if step_in_band(
            clearance_m=c,
            channels=ch,
            hard_coll=hard,
            emergency_latched=latched,
            lo_m=TZ_BAND_LO_M,
            hi_m=TZ_BAND_MID_M,
        ):
            n_inner += 1
        if step_in_band(
            clearance_m=c,
            channels=ch,
            hard_coll=hard,
            emergency_latched=latched,
            lo_m=TZ_BAND_MID_M,
            hi_m=TZ_BAND_HI_M,
        ):
            n_outer += 1
    return {
        "inner_l3_to_l2": float(n_inner) / n,
        "outer_l2_to_l1": float(n_outer) / n,
    }
