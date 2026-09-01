"""Phase-2 scripts must feed shield both depth_min and depth_cones (F5+/P0b).

Without ``obs.info['depth_cones_pred']``, ``ThreeZoneSpeedShield._forward_d_hat``
falls back to full-frame ``depth_min_pred`` and L3-brakes in open air — the
2026-09-01 offtrack probe root cause (frac_intervened≈1, v_after≈0.25).
"""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[4]
_SCRIPTS = _ROOT / "experiments" / "aerial" / "scripts"


def _assert_cones_wired(name: str) -> None:
    src = (_SCRIPTS / name).read_text(encoding="utf-8")
    assert "depth_cones_pred" in src, f"{name} must set obs.info['depth_cones_pred']"
    assert "predict_min_and_cones" in src, f"{name} must call predict_min_and_cones"


def test_long_eval_wires_cones():
    _assert_cones_wired("wam_phase2_long_eval.py")


def test_forensics_wires_cones():
    _assert_cones_wired("wam_phase2_traj_forensics.py")


def test_offtrack_probes_wires_cones():
    _assert_cones_wired("wam_phase2_offtrack_probes.py")


def test_record_route_wires_cones():
    _assert_cones_wired("wam_phase2_record_route.py")
