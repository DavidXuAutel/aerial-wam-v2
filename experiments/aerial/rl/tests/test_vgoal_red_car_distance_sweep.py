"""Unit tests for red-car distance ring pose generation."""
from __future__ import annotations

import math

import numpy as np

from experiments.aerial.scripts.vgoal_red_car_distance_sweep import anchor_perturb_poses, ring_poses


def test_ring_poses_count_and_geometry():
    car = np.array([0.0, 0.0, 20.0])
    poses = ring_poses(
        car,
        standoffs_m=[10.0, 20.0],
        bearings_deg=[0.0, 90.0],
        heights_m=[18.0, 22.0],
        yaw_offsets_deg=[0.0],
    )
    assert len(poses) == 8
    p = poses[0]
    assert p["standoff_m"] == 10.0
    assert p["bearing_deg"] == 0.0
    assert p["height_z"] == 18.0
    pos = np.array(p["pos"], dtype=np.float64)
    assert math.isclose(float(np.linalg.norm(pos[:2] - car[:2])), 10.0, rel_tol=1e-3)
    assert math.isclose(pos[2], 18.0, rel_tol=1e-3)


def test_anchor_perturb_poses_count():
    poses = anchor_perturb_poses(
        [0.0, 0.0, 20.0],
        0.0,
        fwd_jitter_m=[0.0, 1.0],
        lat_jitter_m=[0.0],
        z_jitter_m=[0.0],
        yaw_jitter_deg=[0.0, 5.0],
    )
    assert len(poses) == 4
    assert poses[0]["anchor_fwd_m"] == 0.0
    assert poses[0]["sweep_mode"] == "anchor"


def test_ring_poses_face_target():
    car = np.array([100.0, 50.0, 20.0])
    poses = ring_poses(
        car,
        standoffs_m=[15.0],
        bearings_deg=[0.0],
        heights_m=[20.0],
        yaw_offsets_deg=[0.0],
    )
    yaw = float(poses[0]["yaw_rad"])
    pos = np.array(poses[0]["pos"], dtype=np.float64)
    expected = math.atan2(car[1] - pos[1], car[0] - pos[0])
    assert math.isclose(yaw, expected, rel_tol=1e-4, abs_tol=1e-4)
