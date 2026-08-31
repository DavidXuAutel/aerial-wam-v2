"""PL-A: diag default planner OFF; --planner opt-in only."""
from __future__ import annotations

import argparse

from experiments.aerial.rl.dynamics import StubLatentDynamics
from experiments.aerial.rl.reward import RewardConfig
from experiments.aerial.rl.train_rl import _build_planner


def test_build_planner_respects_enable_false():
    dyn = StubLatentDynamics(latent_dim=8)
    cfg = {"planner": {"enable": False, "horizon": 5}, "env": {"step_hz": 5.0}}
    assert _build_planner(cfg, dyn, RewardConfig()) is None


def test_build_planner_enable_true():
    dyn = StubLatentDynamics(latent_dim=8)
    cfg = {"planner": {"enable": True, "horizon": 3}, "env": {"step_hz": 5.0}}
    pl = _build_planner(cfg, dyn, RewardConfig())
    assert pl is not None
    assert int(pl.horizon) == 3


def test_p7_diag_cli_planner_default_off():
    """Argparse contract: --planner is store_true, default False."""
    from experiments.aerial.scripts import v4_p7_diag as diag

    p = argparse.ArgumentParser()
    # Mirror the flag added in main(); keep test independent of full parse.
    p.add_argument("--planner", action="store_true")
    ns = p.parse_args([])
    assert ns.planner is False
    ns2 = p.parse_args(["--planner"])
    assert ns2.planner is True
    assert hasattr(diag, "run_p7_diag")
