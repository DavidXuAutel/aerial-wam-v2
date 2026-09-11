"""Tests for vgoal area search helpers (M3)."""
from __future__ import annotations

import math
import unittest

import numpy as np

from experiments.aerial.scripts.vgoal_area_search import (
    make_area_search_planner,
    search_area_bounds,
)


class TestVgoalAreaSearch(unittest.TestCase):
    def test_search_area_bounds_default(self):
        spawn = np.array([-100.0, 50.0, 20.0])
        min_x, max_x, min_y, max_y = search_area_bounds(spawn, half_m=30.0)
        self.assertEqual((min_x, max_x, min_y, max_y), (-130.0, -70.0, 20.0, 80.0))

    def test_search_area_bounds_route_override(self):
        spawn = np.array([0.0, 0.0, 10.0])
        route = {"search_area": {"min_x": -5.0, "max_x": 5.0, "min_y": -2.0, "max_y": 8.0}}
        bounds = search_area_bounds(spawn, half_m=99.0, route_info=route)
        self.assertEqual(bounds, (-5.0, 5.0, -2.0, 8.0))

    def test_make_planner_scan_returns_none(self):
        self.assertIsNone(
            make_area_search_planner(
                np.array([0.0, 0.0, 20.0]),
                pattern="scan",
                altitude_z=20.0,
            )
        )

    def test_make_planner_lawnmower(self):
        planner = make_area_search_planner(
            np.array([10.0, 20.0, 25.0]),
            pattern="lawnmower",
            altitude_z=25.0,
            half_m=10.0,
            sweep_spacing_m=10.0,
        )
        self.assertIsNotNone(planner)
        self.assertGreater(len(planner.waypoints), 0)
        gr = planner.update([10.0, 10.0, 25.0], 0.0)
        self.assertEqual(len(gr), 4)
        self.assertGreater(float(gr[3]), 0.0)

    def test_make_planner_spiral(self):
        planner = make_area_search_planner(
            np.array([0.0, 0.0, 18.0]),
            pattern="spiral",
            altitude_z=18.0,
            spiral_max_radius_m=20.0,
        )
        self.assertIsNotNone(planner)
        self.assertEqual(len(planner.waypoints), 16)
        self.assertTrue(np.allclose(planner.waypoints[0], [0.0, 0.0, 18.0]))


if __name__ == "__main__":
    unittest.main()
