"""Renderer host resolution + single-consumer lock (no torch, no airsim).

Guards the 2026-09-03 shared-renderer incident: 125's eval drove 110's renderer
because the host came from a git-committed yaml value and nothing logged it. See
``experiments/aerial/rl/env/renderer_host.py``.

``test_airsim_env_real.py::_make_env`` injects ``_client`` directly and therefore
never reaches ``_connect``, so the guard needs these direct tests.
"""
from __future__ import annotations

import os

import pytest

from experiments.aerial.rl.env.renderer_host import (
    ALLOW_REMOTE_ENV,
    ALLOW_SHARED_ENV,
    AUTO,
    RendererClientLock,
    detect_local_renderer,
    is_local_host,
    resolve_airsim_host,
)

LOCAL = frozenset({"127.0.0.1", "localhost", "::1", "10.229.20.125"})
REMOTE = "10.229.20.110"


def _up(*hosts: str):
    """Probe stub: only ``hosts`` have a listener."""
    return lambda h, p: h in hosts


# -- resolution order -----------------------------------------------------
def test_env_var_beats_config():
    host, prov = resolve_airsim_host(
        "127.0.0.1", 41451, env={"AIRSIM_HOST": "10.229.20.125"}, local=LOCAL
    )
    assert (host, prov) == ("10.229.20.125", "AIRSIM_HOST")


def test_config_beats_auto_detect():
    host, prov = resolve_airsim_host(
        "10.229.20.125", 41451, env={}, probe=_up("127.0.0.1"), local=LOCAL
    )
    assert (host, prov) == ("10.229.20.125", "config")


def test_auto_prefers_loopback():
    host, prov = resolve_airsim_host(
        AUTO, 41451, env={}, probe=_up("127.0.0.1", "10.229.20.125"), local=LOCAL
    )
    assert (host, prov) == ("127.0.0.1", "auto")


def test_auto_falls_back_to_own_lan_ip():
    """110's renderer binds its LAN IP, not loopback — auto must still find it."""
    host, prov = resolve_airsim_host(
        AUTO, 41451, env={}, probe=_up("10.229.20.125"), local=LOCAL
    )
    assert (host, prov) == ("10.229.20.125", "auto")


@pytest.mark.parametrize("cfg", [AUTO, "auto", "AUTO", "", None])
def test_auto_without_any_listener_raises(cfg):
    with pytest.raises(RuntimeError, match="no AirSim renderer listening"):
        resolve_airsim_host(cfg, 41451, env={}, probe=_up(), local=LOCAL)


def test_detect_local_renderer_returns_none_when_nothing_listens():
    assert detect_local_renderer(41451, probe=_up(), local=LOCAL) is None


# -- the guard ------------------------------------------------------------
def test_remote_host_refused_by_default():
    with pytest.raises(RuntimeError, match="NON-LOCAL"):
        resolve_airsim_host(REMOTE, 41451, env={}, local=LOCAL)


def test_remote_host_refused_when_it_came_from_env_var():
    with pytest.raises(RuntimeError, match="NON-LOCAL"):
        resolve_airsim_host(AUTO, 41451, env={"AIRSIM_HOST": REMOTE}, local=LOCAL)


def test_remote_host_allowed_with_opt_in():
    host, prov = resolve_airsim_host(
        REMOTE, 41451, env={ALLOW_REMOTE_ENV: "1"}, local=LOCAL
    )
    assert (host, prov) == (REMOTE, "config")


def test_refusal_message_names_the_escape_hatch_and_incident():
    with pytest.raises(RuntimeError) as err:
        resolve_airsim_host(REMOTE, 41451, env={}, local=LOCAL)
    msg = str(err.value)
    assert ALLOW_REMOTE_ENV in msg
    assert "WAM_RENDERER_SHARING_INCIDENT_20260903" in msg


def test_is_local_host():
    assert is_local_host("127.0.0.1", local=LOCAL)
    assert is_local_host("10.229.20.125", local=LOCAL)
    assert not is_local_host(REMOTE, local=LOCAL)


# -- single-consumer lock -------------------------------------------------
def _lock(tmp_path, env=None):
    return RendererClientLock("127.0.0.1", 41451, env=env or {}, lock_dir=str(tmp_path))


def test_lock_is_exclusive_while_held(tmp_path):
    first = _lock(tmp_path)
    assert first.acquire() is True
    with pytest.raises(RuntimeError, match="already holds"):
        _lock(tmp_path).acquire()
    first.release()
    assert _lock(tmp_path).acquire() is True


def test_lock_records_holder_pid(tmp_path):
    held = _lock(tmp_path)
    held.acquire()
    assert held.holder_pid() == os.getpid()
    held.release()
    assert not held.path.exists()


def test_stale_lock_from_dead_holder_is_stolen(tmp_path):
    stale = _lock(tmp_path)
    stale.path.parent.mkdir(parents=True, exist_ok=True)
    stale.path.mkdir()
    (stale.path / "pid").write_text("2147483646\n")  # PID that cannot be running
    assert _lock(tmp_path).acquire() is True


def test_lock_dir_without_pid_file_is_treated_as_stale(tmp_path):
    orphan = _lock(tmp_path)
    orphan.path.parent.mkdir(parents=True, exist_ok=True)
    orphan.path.mkdir()
    assert _lock(tmp_path).acquire() is True


def test_opt_out_skips_locking(tmp_path):
    held = _lock(tmp_path)
    held.acquire()
    shared = _lock(tmp_path, env={ALLOW_SHARED_ENV: "1"})
    assert shared.acquire() is False  # no raise: caller declared the override
    held.release()


def test_release_is_idempotent(tmp_path):
    held = _lock(tmp_path)
    held.acquire()
    held.release()
    held.release()


def test_lock_dir_comes_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("AIRSIM_CLIENT_LOCK_DIR", str(tmp_path / "viaenv"))
    lock = RendererClientLock("127.0.0.1", 41451)
    assert lock.path.parent == tmp_path / "viaenv"
    lock.acquire()
    lock.release()
