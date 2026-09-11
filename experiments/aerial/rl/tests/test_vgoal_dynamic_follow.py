"""Tests for M4 dynamic follow helpers."""
from __future__ import annotations

import unittest

import numpy as np

from experiments.aerial.scripts.vgoal_dynamic_follow import (
    dynamic_tracker_step,
    make_dynamic_tracker,
)


class TestVgoalDynamicFollow(unittest.TestCase):
    def test_make_and_step_intercepting(self):
        tracker = make_dynamic_tracker(standoff_dist_m=5.0, standoff_height_m=2.0)
        mode, gr = dynamic_tracker_step(
            tracker,
            np.array([20.0, 0.0, 0.0, 20.0], dtype=np.float64),
            0.15,
            np.array([0.0, 0.0, 10.0]),
            0.0,
            0.2,
            min_meas_conf=0.12,
        )
        self.assertEqual(str(mode.value), "intercepting")
        self.assertIsNotNone(gr)
        self.assertGreater(float(gr[3]), 0.0)

    def test_searching_without_measurement(self):
        tracker = make_dynamic_tracker()
        mode, gr = dynamic_tracker_step(
            tracker,
            None,
            0.0,
            np.array([0.0, 0.0, 10.0]),
            0.0,
            0.2,
        )
        self.assertEqual(str(mode.value), "searching")
        self.assertIsNone(gr)


if __name__ == "__main__":
    unittest.main()
