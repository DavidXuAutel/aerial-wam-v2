"""Pre-run link-rate gate (no torch, no airsim).

Guards the second half of the 2026-09-03 incident: the host can be right and the
link still too slow to judge anything. A 0.33 Hz closed loop produced arrival
0/16 and mean_progress -1.9 for the same ckpt that scores 75% arrival on
loopback, and nothing in the run refused to start or recorded the link speed.
See ``experiments/aerial/rl/env/rate_gate.py``.
"""
from __future__ import annotations

import pytest

from experiments.aerial.rl.env.rate_gate import (
    ALLOW_SLOW_ENV,
    DEFAULT_DEPTH_BUDGET_S,
    assert_link_rate,
    probe_depth_latency,
)


class _Cfg:
    def __init__(self, host: str = "127.0.0.1", port: int = 41451) -> None:
        self.host = host
        self.port = port


class _FakeEnv:
    """Stands in for AirSimDroneEnv: only the probe surface the gate touches."""

    def __init__(self, samples, host: str = "127.0.0.1") -> None:
        self._samples = list(samples)
        self.config = _Cfg(host)
        self.calls: list[tuple[int, int]] = []

    def probe_depth_latency(self, *, n: int = 5, warmup: int = 1) -> list[float]:
        self.calls.append((n, warmup))
        return list(self._samples)


class _MockEnv:
    """The mock backend: no renderer link exists to measure."""


# -- budget is the per-step observe reservation ----------------------------
def test_default_budget_matches_observe_budget():
    # airsim_env.step reserves exactly this for a depth grab; above it the
    # commanded rate is unreachable, so the two must not drift apart.
    assert DEFAULT_DEPTH_BUDGET_S == 0.15


# -- pass / fail ----------------------------------------------------------
def test_loopback_latency_passes_and_reports():
    env = _FakeEnv([0.098, 0.101, 0.104])
    rep = assert_link_rate(env, env_vars={})
    assert rep["verdict"] == "ok"
    assert rep["median_s"] == 0.101
    assert rep["depth_hz_ceiling"] == pytest.approx(9.9, abs=0.05)
    assert rep["host"] == "127.0.0.1"
    assert rep["gate"] == "depth_frame_latency"


def test_cross_net_latency_refuses_to_start():
    env = _FakeEnv([0.68, 0.71, 0.75], host="10.229.20.110")
    with pytest.raises(RuntimeError) as ei:
        assert_link_rate(env, env_vars={})
    msg = str(ei.value)
    assert "10.229.20.110" in msg
    assert ALLOW_SLOW_ENV in msg  # the message must say how to override
    assert "0.150" in msg  # and what the budget was


def test_median_not_mean_decides():
    # One slow frame (GPU hiccup) must not fail an otherwise healthy link.
    env = _FakeEnv([0.10, 0.10, 0.11, 0.12, 2.0])
    assert assert_link_rate(env, env_vars={})["verdict"] == "ok"


def test_boundary_is_inclusive():
    env = _FakeEnv([DEFAULT_DEPTH_BUDGET_S] * 3)
    assert assert_link_rate(env, env_vars={})["verdict"] == "ok"


# -- escape hatch is presence-based, and never silent ---------------------
def test_waiver_proceeds_but_records_the_slow_link():
    env = _FakeEnv([0.7, 0.7, 0.7])
    rep = assert_link_rate(env, env_vars={ALLOW_SLOW_ENV: "1"})
    assert rep["verdict"] == "waived"
    assert rep["median_s"] == 0.7  # the number a reader needs is still on record


def test_empty_waiver_does_not_opt_in():
    env = _FakeEnv([0.7])
    with pytest.raises(RuntimeError):
        assert_link_rate(env, env_vars={ALLOW_SLOW_ENV: "  "})


# -- degenerate renderers -------------------------------------------------
def test_depthless_renderer_fails_closed_even_with_waiver():
    # No depth at all is a broken renderer, not a slow one: the eval scores
    # clearance from depth, so there is nothing to waive.
    env = _FakeEnv([])
    with pytest.raises(RuntimeError, match="no depth frame"):
        assert_link_rate(env, env_vars={ALLOW_SLOW_ENV: "1"})


def test_mock_env_skips_the_gate():
    assert probe_depth_latency(_MockEnv()) is None
    assert assert_link_rate(_MockEnv(), env_vars={}) is None


# -- plumbing -------------------------------------------------------------
def test_probe_args_forwarded():
    env = _FakeEnv([0.1] * 3)
    assert_link_rate(env, n=7, warmup=2, env_vars={})
    assert env.calls == [(7, 2)]


def test_commanded_hz_recorded_when_given():
    env = _FakeEnv([0.1] * 3)
    rep = assert_link_rate(env, step_hz=5.0, env_vars={})
    assert rep["commanded_hz"] == 5.0
    assert "commanded_hz" not in assert_link_rate(_FakeEnv([0.1] * 3), env_vars={})
