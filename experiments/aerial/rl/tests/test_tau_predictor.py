"""Tests for τ predictor (V1b scaffold)."""
from __future__ import annotations

import numpy as np

from experiments.aerial.rl.env.obs import Observation
from experiments.aerial.rl.tau_predictor import TauPredictor, gt_tau_from_depth_velocity


def _obs(depth_val: float, vx: float, yaw: float = 0.0) -> Observation:
    depth = np.full((224, 224), depth_val, dtype=np.float32)
    state = np.array([0.0, 0.0, 5.0, vx, 0.0, 0.0, yaw], dtype=np.float32)
    return Observation(rgb=np.zeros((224, 224, 3), dtype=np.uint8), state=state, depth=depth)


def test_gt_tau_approaching():
    obs = _obs(3.0, vx=1.0)
    tau = gt_tau_from_depth_velocity(obs.depth, obs)
    assert tau is not None
    assert abs(tau - 3.0) < 0.01


def test_gt_tau_not_closing_returns_max():
    obs = _obs(2.0, vx=0.0)
    tau = gt_tau_from_depth_velocity(obs.depth, obs, max_tau_s=60.0)
    assert tau == 60.0


def test_predictor_fills_interface():
    pred = TauPredictor()
    obs = _obs(5.0, vx=2.5)
    tau = pred.predict_tau(obs)
    assert tau is not None and abs(tau - 2.0) < 0.01
