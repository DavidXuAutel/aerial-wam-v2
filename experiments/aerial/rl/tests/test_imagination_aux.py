"""Imagination aux pass-through for torch reward head (V4 reward-head fix)."""
import numpy as np
import pytest

torch = pytest.importorskip("torch")

from experiments.aerial.rl.dynamics_torch import TorchRSSMDynamics  # noqa: E402
from experiments.aerial.rl.env.obs import Observation  # noqa: E402
from experiments.aerial.rl.imagination import imagine  # noqa: E402


class _ZeroPolicy:
    def act_latent(self, z):
        return np.zeros(4, dtype=np.float64)


def _obs(pos=(0.0, 0.0, 0.0), goal=(10.0, 0.0, 0.0)):
    state = np.array([pos[0], pos[1], pos[2], 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
    return Observation(
        rgb=np.zeros((16, 16, 3), np.uint8),
        state=state,
        info={"goal": np.asarray(goal, dtype=np.float32)},
    )


def _tiny_torch_wm():
    return TorchRSSMDynamics(
        image_size=16, recurrent_dim=16, stoch_dim=4, stoch_classes=4,
        hidden_dim=16, num_bins=41, device="cpu", torch_dtype=torch.float32,
    )


def test_imagine_nonzero_goal_rel_changes_progress_vs_zeros():
    m = _tiny_torch_wm()
    z = m.encode(_obs())
    z0 = z[None, :]
    g0 = np.zeros((1, 4), dtype=np.float32)
    g1 = np.array([[10.0, 0.0, 0.0, 10.0]], dtype=np.float32)
    v = np.array([[0.0, 0.0, 0.0]], dtype=np.float32)
    roll0 = imagine(m, _ZeroPolicy(), z0, horizon=2, goal_rel0=g0, body_vel0=v)
    roll1 = imagine(m, _ZeroPolicy(), z0, horizon=2, goal_rel0=g1, body_vel0=v)
    assert roll0.progress[0, 0] != roll1.progress[0, 0]
