import numpy as np

from experiments.aerial.rl.env.mavlink_bridge import (
    ARDUCOPTER_MODE_GUIDED,
    ned_to_wam_state,
)


def test_ned_to_wam_state_z_sign():
    st = ned_to_wam_state(1.0, 2.0, 3.0, 0.5, -0.5, 0.1, 0.25)
    assert np.allclose(st, [1.0, 2.0, -3.0, 0.5, -0.5, -0.1, 0.25])


def test_arducopter_guided_mode_constant():
    assert ARDUCOPTER_MODE_GUIDED == 4


def test_global_position_fallback_logic():
    rel_m = 2.5
    st = ned_to_wam_state(0.0, 0.0, -rel_m, 0.1, -0.2, 0.05, 1.0)
    assert np.allclose(st[:4], [0.0, 0.0, rel_m, 0.1])
