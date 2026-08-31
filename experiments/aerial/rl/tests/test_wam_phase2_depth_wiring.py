"""F5 wiring: Phase-2 eval must use DepthMinPredictor.predict_min(obs)."""
from __future__ import annotations

import numpy as np

from experiments.aerial.rl.depth_predictor import DepthMinPredictor
from experiments.aerial.rl.env.obs import Observation


def test_depth_min_predictor_api_for_eval_loop():
    pred = DepthMinPredictor(n_frames=1, device="cpu")
    obs = Observation(
        rgb=np.zeros((16, 16, 3), dtype=np.uint8),
        state=np.zeros(7, dtype=np.float32),
    )
    assert pred.predict_min(obs) is None
    assert not hasattr(pred, "predict")
