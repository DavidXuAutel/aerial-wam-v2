"""Pre-run link-rate gate: measure one depth frame before an eval is allowed to start.

Why this module exists (2026-09-03/04). ``env.host`` was hardcoded to the .110
renderer in git, so evals launched on .125 drove .110 across the net. DepthPlanar
off-box costs ~0.7 s/frame vs ~0.1 s on loopback, which dropped the closed loop
from a commanded 5 Hz to **0.33 Hz achieved**. At that rate the drone advances
~3 m per control step: two phase-1 arms were judged FAIL (arrival 0/16,
mean_progress −1.9) and one phase-2 arm was scored, on numbers that said nothing
about the policy under test. ``renderer_host`` now makes the *wrong host* hard;
this module makes a *slow link* hard, because the host can be right and the link
still be too slow to judge anything (loaded GPU, renderer thrashing, a second
consumer).

The gate is deliberately at the acceptance-eval entry points rather than inside
``step()``: a mid-episode raise would waste the episodes already flown, and a
per-step warning is exactly what the incident proved nobody reads. Fail *before*
the first route.

Budget: ``DEFAULT_DEPTH_BUDGET_S`` = 0.15 s = the per-step observe budget
``airsim_env.step`` already reserves for a depth grab (``airsim_env.py:260``).
Above it, ``step()`` cannot hold the commanded rate no matter what it does, so
the number a run would produce is not comparable to any threshold. Measured
separation is wide — loopback ~0.10 s, cross-net ~0.7 s — so this is not a
knife-edge.

Escape hatch: ``AERIAL_ALLOW_SLOW_RENDERER`` (presence-based, like
``AIRSIM_ALLOW_REMOTE_HOST`` / ``AERIAL_ALLOW_LEGACY_RESUME``). Set it and the
run proceeds with the probe recorded as ``waived`` — the stats still land in the
result JSON, so a slow-link number can never again be *silently* declared.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_DEPTH_BUDGET_S = 0.15
ALLOW_SLOW_ENV = "AERIAL_ALLOW_SLOW_RENDERER"
INCIDENT_DOC = "docs/handover/WAM_RENDERER_SHARING_INCIDENT_20260903.md"


def probe_depth_latency(env: Any, *, n: int = 5, warmup: int = 1) -> Optional[List[float]]:
    """Time ``n`` depth grabs on ``env``, or None when it cannot be probed.

    ``None`` means "not an AirSim env" (mock/smoke paths have no renderer link to
    measure) — the caller skips the gate rather than failing closed, because the
    mock backend is already excluded from authoritative verdicts elsewhere.
    """
    probe = getattr(env, "probe_depth_latency", None)
    if probe is None:
        return None
    return list(probe(n=int(n), warmup=int(warmup)))


def _stats(samples: List[float]) -> Dict[str, float]:
    ordered = sorted(samples)
    mid = len(ordered) // 2
    median = ordered[mid] if len(ordered) % 2 else 0.5 * (ordered[mid - 1] + ordered[mid])
    return {
        "median_s": round(float(median), 4),
        "mean_s": round(float(sum(ordered) / len(ordered)), 4),
        "min_s": round(float(ordered[0]), 4),
        "max_s": round(float(ordered[-1]), 4),
    }


def assert_link_rate(
    env: Any,
    *,
    budget_s: float = DEFAULT_DEPTH_BUDGET_S,
    n: int = 5,
    warmup: int = 1,
    step_hz: Optional[float] = None,
    env_vars: Optional[Dict[str, str]] = None,
) -> Optional[Dict[str, Any]]:
    """Refuse to start when a depth frame costs more than ``budget_s``.

    Returns a stats dict for the caller to stamp into its result JSON (or None
    when the env has no renderer link, e.g. the mock backend). Raises
    ``RuntimeError`` when the median grab exceeds the budget and
    ``AERIAL_ALLOW_SLOW_RENDERER`` is unset.
    """
    env_vars = os.environ if env_vars is None else env_vars
    samples = probe_depth_latency(env, n=n, warmup=warmup)
    if samples is None:
        logger.info("link-rate gate skipped: %s exposes no depth probe", type(env).__name__)
        return None
    if not samples:
        raise RuntimeError(
            "link-rate gate: the renderer returned no depth frame at all. A depth-less "
            "renderer (CV-only build, dead bridge) cannot produce the clearance signal "
            f"this eval scores. Start a full renderer, or check {INCIDENT_DOC}."
        )

    cfg = getattr(env, "config", None)
    report: Dict[str, Any] = {
        "gate": "depth_frame_latency",
        "host": str(getattr(cfg, "host", "?")),
        "port": int(getattr(cfg, "port", 0) or 0),
        "n": len(samples),
        "warmup": int(warmup),
        "budget_s": float(budget_s),
        "samples_s": [round(float(s), 4) for s in samples],
        **_stats(samples),
    }
    report["depth_hz_ceiling"] = round(1.0 / report["median_s"], 2) if report["median_s"] > 0 else None
    if step_hz:
        report["commanded_hz"] = float(step_hz)

    if report["median_s"] <= float(budget_s):
        report["verdict"] = "ok"
        logger.info(
            "link-rate gate PASS: depth %.3f s/frame median on %s:%d (budget %.3f s, "
            "ceiling %.2f Hz)",
            report["median_s"], report["host"], report["port"], budget_s,
            report["depth_hz_ceiling"],
        )
        return report

    waived = bool((env_vars.get(ALLOW_SLOW_ENV) or "").strip())
    report["verdict"] = "waived" if waived else "fail"
    msg = (
        f"link-rate gate FAILED: one depth frame from {report['host']}:{report['port']} "
        f"costs {report['median_s']:.3f} s (median of {len(samples)}; samples "
        f"{report['samples_s']}), over the {budget_s:.3f} s budget — that caps the closed "
        f"loop at ~{report['depth_hz_ceiling']} Hz"
        + (f" against a commanded {step_hz:g} Hz" if step_hz else "")
        + ". Metrics measured on such a link are not comparable to the acceptance "
        f"thresholds: on 2026-09-03 a 0.33 Hz cross-net link produced arrival 0/16 and "
        f"mean_progress -1.9 for a policy that scores 75% arrival on loopback "
        f"({INCIDENT_DOC}). Use this box's own renderer (unset AIRSIM_HOST / host: auto), "
        f"check nothing else is loading the GPU, then re-run. To measure anyway, set "
        f"{ALLOW_SLOW_ENV}=1 — the probe is recorded either way."
    )
    if not waived:
        raise RuntimeError(msg)
    logger.warning("%s set — proceeding on a slow link. %s", ALLOW_SLOW_ENV, msg)
    return report
