"""AirSim renderer host resolution + single-consumer client lock.

Why this module exists (2026-09-03 shared-renderer incident):
``configs/aerial_rl.yaml`` shipped ``env.host: 10.229.20.110`` **in git**, while
``train_rl._build_env`` read only that yaml value and never consulted
``AIRSIM_HOST``. So every box that pulled the repo drove *.110*'s renderer, and
the "two boxes, one route each" parallel scheme had both halves fighting over one
drone: the phase-2 E1 forensics trace teleports 580.5 m mid-episode onto another
route's spawn point. ``_connect`` also logged no host at all, so nothing in any
log said which renderer a run had actually driven. See
``docs/handover/WAM_RENDERER_SHARING_INCIDENT_20260903.md``.

Policy enforced here (so "connected to the wrong renderer" stops being possible
rather than merely discouraged):

* resolution order — ``AIRSIM_HOST`` env var > explicit config ``host`` >
  auto-detect a *local* listener;
* a **non-local** host is refused unless ``AIRSIM_ALLOW_REMOTE_HOST`` is set.
  Cross-net is not just a collision risk: ``configs/aerial_rl.yaml`` already
  documents cross-net DepthPlanar at ~0.7 Hz vs ~6 Hz on loopback;
* **one client per ``host:port`` on this box**, enforced with a ``mkdir`` lock
  (the ``orch_eval_worker.sh:43-47`` idiom); opt out with
  ``AIRSIM_ALLOW_SHARED_RENDERER``.

Both escape hatches are **presence-based**, matching the repo's existing
``AERIAL_ALLOW_LEGACY_RESUME`` convention (``run_b0_v2_from_scratch.sh:53``):
setting the variable to anything non-empty opts in.

The lock is per-box, so it cannot see a client on the *other* machine — that case
is excluded structurally by the local-host guard instead.
"""
from __future__ import annotations

import atexit
import logging
import os
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Callable, Dict, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

AUTO = "auto"
LOOPBACK_NAMES = ("127.0.0.1", "localhost", "::1")
ALLOW_REMOTE_ENV = "AIRSIM_ALLOW_REMOTE_HOST"
ALLOW_SHARED_ENV = "AIRSIM_ALLOW_SHARED_RENDERER"
LOCK_DIR_ENV = "AIRSIM_CLIENT_LOCK_DIR"
DEFAULT_LOCK_DIR = "/tmp/airsim_client_locks"
INCIDENT_DOC = "docs/handover/WAM_RENDERER_SHARING_INCIDENT_20260903.md"
RECOVER_HINT = "~/aerial_airsim_persistent/recover_renderer.sh"


# -- host resolution ------------------------------------------------------
def local_ipv4s() -> frozenset[str]:
    """Addresses that reach a renderer on *this* box: loopback + own IPv4s."""
    addrs = set(LOOPBACK_NAMES)
    try:
        out = subprocess.run(
            ["hostname", "-I"], capture_output=True, text=True, timeout=2.0, check=False
        ).stdout
    except Exception:  # noqa: BLE001 - no `hostname`, or it hung; loopback still works
        out = ""
    addrs.update(tok for tok in out.split() if tok)
    return frozenset(addrs)


def is_local_host(host: str, *, local: Optional[frozenset[str]] = None) -> bool:
    return str(host).strip() in (local if local is not None else local_ipv4s())


def listener_alive(host: str, port: int, timeout: float = 0.5) -> bool:
    """True when something accepts TCP on ``host:port`` right now."""
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except OSError:
        return False


def detect_local_renderer(
    port: int,
    *,
    probe: Callable[[str, int], bool] = listener_alive,
    local: Optional[frozenset[str]] = None,
) -> Optional[str]:
    """First local address with a live renderer — loopback preferred."""
    addrs = local if local is not None else local_ipv4s()
    ordered = ["127.0.0.1"] + sorted(a for a in addrs if a not in LOOPBACK_NAMES)
    for host in ordered:
        if probe(host, int(port)):
            return host
    return None


def resolve_airsim_host(
    cfg_host: Optional[str],
    port: int,
    *,
    env: Optional[Dict[str, str]] = None,
    probe: Callable[[str, int], bool] = listener_alive,
    local: Optional[frozenset[str]] = None,
) -> Tuple[str, str]:
    """Resolve the renderer host; refuse a remote one unless opted in.

    Returns ``(host, provenance)`` where provenance is ``"AIRSIM_HOST"``,
    ``"config"`` or ``"auto"`` — the caller logs it so a run's own log says which
    renderer it drove and why.

    Raises ``RuntimeError`` when no local renderer is listening (auto mode) or
    when a non-local host was requested without ``AIRSIM_ALLOW_REMOTE_HOST``.
    """
    env = os.environ if env is None else env
    addrs = local if local is not None else local_ipv4s()
    port = int(port)

    env_host = (env.get("AIRSIM_HOST") or "").strip()
    cfg = (cfg_host or "").strip()
    if env_host:
        host, provenance = env_host, "AIRSIM_HOST"
    elif cfg and cfg.lower() != AUTO:
        host, provenance = cfg, "config"
    else:
        found = detect_local_renderer(port, probe=probe, local=addrs)
        if found is None:
            raise RuntimeError(
                f"no AirSim renderer listening on any local address:{port} "
                f"(tried 127.0.0.1 and {sorted(a for a in addrs if a not in LOOPBACK_NAMES)}). "
                f"Start it with {RECOVER_HINT}, or point AIRSIM_HOST at a renderer "
                f"explicitly (a non-local one also needs {ALLOW_REMOTE_ENV}=1)."
            )
        host, provenance = found, "auto"

    if not is_local_host(host, local=addrs) and not (env.get(ALLOW_REMOTE_ENV) or "").strip():
        raise RuntimeError(
            f"refusing to drive a NON-LOCAL AirSim renderer {host}:{port} "
            f"(from {provenance}). The renderer is single-consumer: on 2026-09-03 two "
            f"boxes' eval processes shared one drone this way and silently corrupted a "
            f"whole phase-2 arm (580 m mid-episode teleport; see {INCIDENT_DOC}). "
            f"Cross-net is also ~0.7 Hz on depth vs ~6 Hz on loopback. "
            f"Use this box's own renderer (unset AIRSIM_HOST / set host: auto), or, if "
            f"the cross-box connection is deliberate, set {ALLOW_REMOTE_ENV}=1."
        )
    return host, provenance


# -- single-consumer lock -------------------------------------------------
class RendererClientLock:
    """``mkdir``-based advisory lock: one client per ``host:port`` per box.

    Mirrors ``experiments/aerial/scripts/orch_eval_worker.sh:43-47`` (atomic
    ``mkdir``, env-overridable path, release on exit) and the ``/proc/<pid>``
    liveness check from ``~/aerial_airsim_persistent/recover_renderer.sh`` so a
    crashed run's lock does not wedge the next one.
    """

    def __init__(
        self,
        host: str,
        port: int,
        *,
        env: Optional[Dict[str, str]] = None,
        lock_dir: Optional[str] = None,
    ) -> None:
        env = os.environ if env is None else env
        base = lock_dir or env.get(LOCK_DIR_ENV) or DEFAULT_LOCK_DIR
        safe = str(host).replace(":", "-").replace("/", "-")
        self.path = Path(base) / f"{safe}_{int(port)}.lock"
        self.host = str(host)
        self.port = int(port)
        self._env = env
        self._held = False

    # -- introspection ----------------------------------------------------
    def holder_pid(self) -> Optional[int]:
        try:
            return int((self.path / "pid").read_text().strip())
        except (OSError, ValueError):
            return None

    @staticmethod
    def _pid_alive(pid: Optional[int]) -> bool:
        return pid is not None and Path(f"/proc/{pid}").exists()

    # -- lifecycle --------------------------------------------------------
    def acquire(self) -> bool:
        """Take the lock. Returns False when the caller opted out of locking.

        Raises ``RuntimeError`` when a live process already holds it.
        """
        if (self._env.get(ALLOW_SHARED_ENV) or "").strip():
            logger.warning(
                "%s set — skipping the single-consumer lock for %s:%d",
                ALLOW_SHARED_ENV,
                self.host,
                self.port,
            )
            return False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for attempt in (0, 1):
            try:
                self.path.mkdir()  # atomic
            except FileExistsError:
                pid = self.holder_pid()
                if self._pid_alive(pid):
                    raise RuntimeError(
                        f"another AirSim client (pid {pid}) already holds "
                        f"{self.host}:{self.port} — the renderer is single-consumer, a "
                        f"second client silently corrupts both runs (see {INCIDENT_DOC}). "
                        f"Wait for it, or set {ALLOW_SHARED_ENV}=1 to override. "
                        f"Lock: {self.path}"
                    ) from None
                if attempt == 0:  # stale: holder is gone
                    logger.warning(
                        "stealing stale renderer lock %s (pid %s is gone)", self.path, pid
                    )
                    shutil.rmtree(self.path, ignore_errors=True)
                    continue
                raise RuntimeError(f"could not take renderer lock {self.path}") from None
            else:
                break
        (self.path / "pid").write_text(f"{os.getpid()}\n")
        self._held = True
        atexit.register(self.release)
        logger.info("renderer lock held: %s (pid %d)", self.path, os.getpid())
        return True

    def release(self) -> None:
        if not self._held:
            return
        self._held = False
        shutil.rmtree(self.path, ignore_errors=True)


# -- CLI: shared by env_4090.sh so bash and Python agree ------------------
def _main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="print this box's local AirSim renderer host")
    ap.add_argument("--port", type=int, default=int(os.environ.get("AIRSIM_PORT", 41451)))
    args = ap.parse_args(argv)
    host = detect_local_renderer(args.port)
    if host is None:
        return 1
    print(host)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI shim
    raise SystemExit(_main())
