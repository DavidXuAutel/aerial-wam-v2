"""Unit tests for path-tangent heading assist."""
from __future__ import annotations

import math

import numpy as np

from experiments.aerial.rl.env.action import body_delta_limits
from experiments.aerial.rl.path_heading_assist import (
    apply_path_heading_assist,
    path_tangent_yaw,
)


def test_path_tangent_yaw_straight():
    path = np.array([[0.0, 0.0, 10.0], [0.0, -10.0, 10.0]], dtype=np.float64)  # -Y
    assert path_tangent_yaw(path, 0) == math.atan2(-10.0, 0.0)


def test_assist_noop_when_aligned():
    path = np.array([[0.0, 0.0, 10.0], [10.0, 0.0, 10.0]], dtype=np.float64)
    lim = body_delta_limits(0.2)
    act = np.array([1.0, 0.5, 0.0, 0.0], dtype=np.float64)
    out, hit, info = apply_path_heading_assist(
        act, yaw=0.0, path=path, seg_idx=0, cte_m=1.0, limits=lim
    )
    assert hit is False
    assert info["heading_assist"] is False
    np.testing.assert_allclose(out, act)


def test_assist_injects_yaw_when_orthogonal():
    path = np.array([[0.0, 0.0, 10.0], [10.0, 0.0, 10.0]], dtype=np.float64)  # +X
    lim = body_delta_limits(0.2)
    act = np.array([0.5, 0.8, 0.0, 0.0], dtype=np.float64)
    # body yaw = +90° (facing +Y), path wants +X → large yaw error
    out, hit, info = apply_path_heading_assist(
        act, yaw=math.pi / 2, path=path, seg_idx=0, cte_m=2.0, limits=lim, cos_thr=0.7
    )
    assert hit is True
    assert abs(out[3]) > 0.1
    assert abs(out[3]) <= lim[3] + 1e-9
    # cos < 0 → lateral attenuated
    assert abs(out[1]) < abs(act[1])


def test_assist_skips_when_cte_large():
    path = np.array([[0.0, 0.0, 10.0], [10.0, 0.0, 10.0]], dtype=np.float64)
    lim = body_delta_limits(0.2)
    act = np.array([0.5, 0.8, 0.0, 0.0], dtype=np.float64)
    out, hit, _ = apply_path_heading_assist(
        act, yaw=math.pi / 2, path=path, seg_idx=0, cte_m=20.0, limits=lim
    )
    assert hit is False
    np.testing.assert_allclose(out, act)
