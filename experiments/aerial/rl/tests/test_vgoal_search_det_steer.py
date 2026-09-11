"""Tests for det-driven SEARCHING steer helpers."""
from __future__ import annotations

import math
import unittest
from types import SimpleNamespace

from experiments.aerial.scripts.wam_vgoal_eval import bbox_det_steer_yaw_rate


class TestVgoalSearchDetSteer(unittest.TestCase):
    def test_bbox_center_no_turn(self):
        det = SimpleNamespace(bbox=[460.0, 100.0, 500.0, 140.0])
        rate = bbox_det_steer_yaw_rate(det, 960, gain=1.0, max_yaw_rate=0.3)
        self.assertAlmostEqual(rate, 0.0, places=5)

    def test_bbox_right_turns_left(self):
        det = SimpleNamespace(bbox=[800.0, 100.0, 840.0, 140.0])
        rate = bbox_det_steer_yaw_rate(det, 960, gain=1.0, max_yaw_rate=0.3)
        self.assertLess(rate, 0.0)

    def test_bbox_left_turns_right(self):
        det = SimpleNamespace(bbox=[120.0, 100.0, 160.0, 140.0])
        rate = bbox_det_steer_yaw_rate(det, 960, gain=1.0, max_yaw_rate=0.3)
        self.assertGreater(rate, 0.0)

    def test_clamped_to_max_yaw(self):
        det = SimpleNamespace(bbox=[900.0, 0.0, 950.0, 50.0])
        rate = bbox_det_steer_yaw_rate(det, 960, gain=5.0, max_yaw_rate=0.2)
        self.assertLessEqual(abs(rate), 0.2 + 1e-9)
        self.assertAlmostEqual(abs(rate), 0.2, places=5)


if __name__ == "__main__":
    unittest.main()
