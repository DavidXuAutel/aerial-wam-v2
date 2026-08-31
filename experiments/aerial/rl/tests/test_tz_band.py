"""Unit tests for TZ in-band predicate (V4_TZ_CRITERIA_REFREEZE_20260826)."""
from __future__ import annotations

from experiments.aerial.rl.tz_band import (
    annotate_trace_in_band,
    band_frac,
    band_frac_buckets,
    step_in_band,
)
import numpy as np


def test_speed_cap_only_can_be_in_band():
    assert step_in_band(
        clearance_m=4.0,
        channels=["three_zone"],
        hard_coll=False,
        emergency_latched=False,
    )


def test_emergency_tau_excludes():
    assert not step_in_band(
        clearance_m=4.0,
        channels=["tau"],
        hard_coll=False,
        emergency_latched=False,
    )


def test_l3_brake_channel_excludes():
    assert not step_in_band(
        clearance_m=4.0,
        channels=["three_zone_brake"],
        hard_coll=False,
        emergency_latched=False,
    )


def test_l3_3d_channel_excludes():
    assert not step_in_band(
        clearance_m=4.0,
        channels=["three_zone_3d"],
        hard_coll=False,
        emergency_latched=False,
    )


def test_emergency_latch_excludes_later_steps():
    assert not step_in_band(
        clearance_m=4.0,
        channels=["three_zone"],
        hard_coll=False,
        emergency_latched=True,
    )


def test_outside_band_excluded():
    assert not step_in_band(clearance_m=1.5, channels=[])  # on L3 boundary
    assert not step_in_band(clearance_m=1.2, channels=[])
    assert not step_in_band(clearance_m=8.01, channels=[])
    assert step_in_band(clearance_m=8.0, channels=[])


def test_hard_coll_excludes():
    assert not step_in_band(clearance_m=4.0, channels=[], hard_coll=True)


def test_hard_coll_episode_excluded_from_band_frac():
    """E1: whole episode with any hard_coll is NaN (not counted toward θ)."""
    rows = [
        {"clearance_fov": 4.0, "shield_channels": ["three_zone"], "collided": False},
        {"clearance_fov": 4.0, "shield_channels": ["three_zone"], "collided": True},
    ]
    out = annotate_trace_in_band(rows)
    assert np.isnan(band_frac(out))
    assert np.isnan(band_frac(out, exclude_hard_coll_episode=True))
    # Legacy step-only mode still returns a finite ratio.
    assert band_frac(out, exclude_hard_coll_episode=False) == 0.5


def test_band_frac_buckets_split():
    rows = [
        {"clearance_fov": 3.0, "shield_channels": ["three_zone"], "collided": False},
        {"clearance_fov": 6.0, "shield_channels": ["three_zone"], "collided": False},
        {"clearance_fov": 10.0, "shield_channels": [], "collided": False},
    ]
    out = annotate_trace_in_band(rows)
    b = band_frac_buckets(out)
    assert abs(b["inner_l3_to_l2"] - 1.0 / 3.0) < 1e-9
    assert abs(b["outer_l2_to_l1"] - 1.0 / 3.0) < 1e-9


def test_annotate_latch_propagates():
    rows = [
        {"clearance_fov": 4.0, "shield_channels": ["three_zone"], "collided": False},
        {"clearance_fov": 4.0, "shield_channels": ["tau"], "collided": False},
        {"clearance_fov": 4.0, "shield_channels": ["three_zone"], "collided": False},
    ]
    out = annotate_trace_in_band(rows)
    assert out[0]["in_band"] is True
    assert out[1]["in_band"] is False
    assert out[1]["emergency_latched"] is True
    assert out[2]["in_band"] is False
    assert out[2]["emergency_latched"] is True
    assert band_frac(out) == 1.0 / 3.0
