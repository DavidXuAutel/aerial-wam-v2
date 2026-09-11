"""Tests for red-car spawn export from anchor report."""
from __future__ import annotations

from experiments.aerial.scripts.vgoal_red_car_spawn_export import export_routes


def test_export_routes_dedup_and_sort():
    poses = [
        {"pos": [1.0, 2.0, 20.0], "yaw_rad": 0.1, "yolo_conf": 0.5, "hit_raw": True},
        {"pos": [1.0, 2.0, 20.0], "yaw_rad": 0.1, "yolo_conf": 0.3, "hit_raw": True},
        {"pos": [3.0, 4.0, 20.0], "yaw_rad": -0.2, "yolo_conf": 0.4, "hit_raw": True},
    ]
    routes = export_routes(poses, min_conf=0.25, require_hit_raw=True, max_routes=10, pos_round_m=0.5, visual_prompt="red car")
    assert len(routes) == 2
    assert max(r["probe_conf"] for r in routes) == 0.5
    assert routes[0]["detector"] == "open_vocab"
