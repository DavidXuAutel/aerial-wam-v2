"""V4-⓪ v2 offline eval (P3) — near-band depth + ⓪f reaction-band diagnostics.

Runs on H100 (torch). Scores deployment ``DepthMinPredictor`` + ``TauPredictor``
against a GT-depth rollout corpus. Authority = RUNBOOK §2.1 / criteria §4.6.2.

    python -m experiments.aerial.rl.v4_zero_eval \\
        --dataset .../dataset_v0_local_depth_r60_20260814 \\
        --depth-ckpt .../depth_step_2000_da3_ft_head.pt \\
        --tau-ckpt .../tau_foe_calibrator.pt \\
        --emit artifacts/v4_zero_p3_20260820.json

Exits 0 when all scored sub-items PASS; 1 otherwise. ``⓪f`` band ``[lo,hi]`` is
never filled — only clearance-sweep diagnostics for later freeze.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from experiments.aerial.rl.depth_geometry import forward_min_depth, full_min_depth
from experiments.aerial.rl.tau_predictor import closing_speed_m_s, make_tau_predictor


# Frozen §4.6.2 thresholds (do not invent).
_NEAR_LO = 0.0
_NEAR_HI = 3.0
_OUTER_LO = 3.0
_OUTER_HI = 8.0
_SUPPORT_MIN = 10_000
_N_FRAMES_MIN = 100
_MAX_FRAME_FRAC = 0.20
_ABSREL_MEDIAN_MAX = 0.30
_ABSREL_P90_MAX = 0.50
_FALSE_TRIGGER_MAX = 0.05
_TAU_MARGIN_FACTOR = 2.0


@dataclass(frozen=True)
class ZeroThresholds:
    trigger_m: float = 3.0
    min_tau_s: float = 1.0
    center_frac: float = 0.5
    absrel_median_max: float = _ABSREL_MEDIAN_MAX
    absrel_p90_max: float = _ABSREL_P90_MAX
    support_min: int = _SUPPORT_MIN
    n_frames_min: int = _N_FRAMES_MIN
    max_frame_frac: float = _MAX_FRAME_FRAC
    false_trigger_max: float = _FALSE_TRIGGER_MAX


def pixel_absrel_stats(
    pred: np.ndarray,
    gt: np.ndarray,
    *,
    gt_lo: float,
    gt_hi: float,
    max_depth_m: float = 200.0,
) -> Dict[str, Any]:
    """AbsRel on pixels with ``gt_lo < GT <= gt_hi`` (upper inclusive hi)."""
    p = np.asarray(pred, dtype=np.float64).reshape(-1)
    g = np.asarray(gt, dtype=np.float64).reshape(-1)
    m = np.isfinite(p) & np.isfinite(g) & (g > gt_lo) & (g <= gt_hi)
    if max_depth_m is not None:
        m &= g <= float(max_depth_m)
    n = int(np.count_nonzero(m))
    if n == 0:
        return {"n": 0, "median_absrel": float("nan"), "p90_absrel": float("nan")}
    rel = np.abs(p[m] - g[m]) / np.clip(g[m], 1e-6, None)
    return {
        "n": n,
        "median_absrel": round(float(np.median(rel)), 4),
        "p90_absrel": round(float(np.percentile(rel, 90)), 4),
    }


def near_absrel_gt_bins(
    pred: np.ndarray,
    gt: np.ndarray,
    *,
    edges: Sequence[float] = (0.0, 1.5, 3.0),
) -> List[Dict[str, Any]]:
    """AbsRel stats on ``(edges[i], edges[i+1]]`` GT bins (near-band diagnostics)."""
    out: List[Dict[str, Any]] = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        st = pixel_absrel_stats(pred, gt, gt_lo=float(lo), gt_hi=float(hi))
        out.append(
            {
                "gt_lo": float(lo),
                "gt_hi": float(hi),
                "domain": f"({lo:g}, {hi:g}]",
                "n_px": st["n"],
                "median_absrel": st["median_absrel"],
                "p90_absrel": st["p90_absrel"],
            }
        )
    return out


def check_support_b(
    per_frame_near_px: Sequence[int],
    *,
    thr: ZeroThresholds,
) -> Dict[str, Any]:
    total = int(sum(per_frame_near_px))
    n_frames = int(sum(1 for x in per_frame_near_px if x > 0))
    max_frac = (
        float(max(per_frame_near_px) / total) if total > 0 else float("nan")
    )
    ok = (
        total >= thr.support_min
        and n_frames >= thr.n_frames_min
        and (total == 0 or max_frac <= thr.max_frame_frac)
    )
    reason = None
    if total < thr.support_min:
        reason = f"support={total} < {thr.support_min}"
    elif n_frames < thr.n_frames_min:
        reason = f"n_frames_with_near_px={n_frames} < {thr.n_frames_min}"
    elif total > 0 and max_frac > thr.max_frame_frac:
        reason = f"max_frame_frac={max_frac:.3f} > {thr.max_frame_frac}"
    return {
        "ok": bool(ok),
        "support_px": total,
        "n_frames_with_near_px": n_frames,
        "max_frame_frac": round(max_frac, 4) if np.isfinite(max_frac) else None,
        "reason": reason,
    }


def check_0a(stats: Dict[str, Any], *, thr: ZeroThresholds) -> Dict[str, Any]:
    med = stats.get("median_absrel", float("nan"))
    ok = stats.get("n", 0) >= thr.support_min and np.isfinite(med) and med <= thr.absrel_median_max
    return {
        "ok": bool(ok),
        "median_absrel": med,
        "threshold": thr.absrel_median_max,
        "n_px": stats.get("n", 0),
        "domain": f"({ _NEAR_LO:g}, {_NEAR_HI:g}]",
    }


def check_0c(stats: Dict[str, Any], *, thr: ZeroThresholds) -> Dict[str, Any]:
    p90 = stats.get("p90_absrel", float("nan"))
    ok = stats.get("n", 0) >= thr.support_min and np.isfinite(p90) and p90 <= thr.absrel_p90_max
    return {
        "ok": bool(ok),
        "p90_absrel": p90,
        "threshold": thr.absrel_p90_max,
        "n_px": stats.get("n", 0),
        "domain": f"({ _NEAR_LO:g}, {_NEAR_HI:g}]",
    }


def check_0d(
    gt_fwd: np.ndarray,
    dhat_fwd: np.ndarray,
    *,
    thr: ZeroThresholds,
    episode_ids: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """Functional miss-trigger rate on forward min (⓪d)."""
    g = np.asarray(gt_fwd, dtype=np.float64)
    d = np.asarray(dhat_fwd, dtype=np.float64)
    m = np.isfinite(g) & np.isfinite(d) & (g <= thr.trigger_m)
    n = int(np.count_nonzero(m))
    if n == 0:
        return {"ok": False, "reason": "no frames with D_gt_fwd <= trigger", "n": 0}
    miss = d[m] > thr.trigger_m
    rate = float(np.mean(miss))
    # Consecutive miss-run check (per episode when ids provided, else global).
    max_run = _max_consecutive_true(miss, episode_ids[m] if episode_ids is not None else None)
    ok = rate <= thr.false_trigger_max and max_run < 2
    return {
        "ok": bool(ok),
        "p_miss_trigger": round(rate, 4),
        "threshold": thr.false_trigger_max,
        "max_consecutive_miss": int(max_run),
        "n_cond": n,
        # Alias — denominator of p_miss_trigger (GT_forward ≤ trigger).
        # Required for rate-leg CI; consec FAIL does not depend on this.
        "n_near_forward_frames": n,
        "trigger_m": thr.trigger_m,
    }


def _max_consecutive_true(flags: np.ndarray, episode_ids: Optional[np.ndarray]) -> int:
    flags = np.asarray(flags, dtype=bool).reshape(-1)
    if episode_ids is None:
        return _max_run_in_segment(flags)
    eids = np.asarray(episode_ids).reshape(-1)
    best = 0
    for e in np.unique(eids):
        best = max(best, _max_run_in_segment(flags[eids == e]))
    return best


def _max_run_in_segment(flags: np.ndarray) -> int:
    best = run = 0
    for f in flags:
        if f:
            run += 1
            best = max(best, run)
        else:
            run = 0
    return best


def clearance_sweep(
    gt_fov: np.ndarray,
    dhat_fov: np.ndarray,
    gt_fwd: np.ndarray,
    tau_hat: np.ndarray,
    v_fwd: np.ndarray,
    *,
    thr: ZeroThresholds,
    bin_width: float = 0.25,
) -> List[Dict[str, Any]]:
    """Per-clearance-bin false-trigger diagnostics for ⓪f (no ``[lo,hi]`` commit).

    All input arrays must be aligned per-frame (same length).
    """
    gt_fov = np.asarray(gt_fov, dtype=np.float64)
    dhat_fov = np.asarray(dhat_fov, dtype=np.float64)
    gt_fwd = np.asarray(gt_fwd, dtype=np.float64)
    tau_hat = np.asarray(tau_hat, dtype=np.float64)
    v_fwd = np.asarray(v_fwd, dtype=np.float64)
    n = gt_fov.size
    if not (dhat_fov.size == gt_fwd.size == tau_hat.size == v_fwd.size == n):
        raise ValueError("clearance_sweep inputs must have equal length")

    rows: List[Dict[str, Any]] = []
    c = _OUTER_LO
    while c < _OUTER_HI:
        hi = min(c + bin_width, _OUTER_HI)
        m = np.isfinite(gt_fov) & (gt_fov >= c) & (gt_fov < hi)
        n_bin = int(np.count_nonzero(m))
        row: Dict[str, Any] = {"clearance_lo": round(c, 3), "clearance_hi": round(hi, 3), "n": n_bin}
        if n_bin > 0:
            row["p_dhat_false_trigger"] = round(
                float(np.mean(dhat_fov[m] < thr.trigger_m)), 4
            )
            margin = gt_fwd / np.clip(v_fwd, 1e-6, None)
            need = _TAU_MARGIN_FACTOR * thr.min_tau_s
            tau_m = (
                m
                & np.isfinite(tau_hat)
                & np.isfinite(gt_fwd)
                & np.isfinite(v_fwd)
                & (v_fwd >= 0.05)
                & (margin >= need)
            )
            if np.any(tau_m):
                row["p_tau_false_trigger"] = round(
                    float(np.mean(tau_hat[tau_m] < thr.min_tau_s)), 4
                )
                row["n_tau_cond"] = int(np.count_nonzero(tau_m))
        rows.append(row)
        c = hi
    return rows


def suggest_delta(rows: Sequence[Dict[str, Any]], *, thr: ZeroThresholds) -> Dict[str, Any]:
    """Smallest clearance bin edge where both channels meet ``<= false_trigger_max``."""
    for row in rows:
        if row.get("n", 0) <= 0:
            continue
        pd = row.get("p_dhat_false_trigger")
        pt = row.get("p_tau_false_trigger")
        if pd is None or pt is None:
            continue
        if pd <= thr.false_trigger_max and pt <= thr.false_trigger_max:
            lo = float(row["clearance_lo"])
            return {
                "suggested_lo_clearance_m": lo,
                "suggested_delta_m": round(lo - thr.trigger_m, 3),
                "note": "diagnostic only — [lo,hi] not frozen in P3",
            }
    return {
        "suggested_lo_clearance_m": None,
        "suggested_delta_m": None,
        "note": "no bin satisfied both false-trigger rates",
    }


def aggregate_verdict(sub: Dict[str, Any]) -> Dict[str, Any]:
    """Primary merge = ⓪a–⓪e. ⓪f is report/diag until ``[lo,hi]`` is frozen.

    Outer AbsRel (⓪f(1)(2)) is **report-only** — §4.6.2 does not give it the
    ⓪a/⓪c thresholds ``0.30`` / ``0.50``. False-trigger bins (3)(4) are scored
    only after a band is frozen; pre-freeze they do not gate ``ok``.
    """
    keys_primary = ("0a", "0b", "0c", "0d", "0e")
    ok_primary = all(sub[k].get("ok") for k in keys_primary if k in sub)
    f = sub.get("0f", {})
    ok_f = bool(f.get("ok", False))
    return {
        "ok": bool(ok_primary),
        "ok_primary": ok_primary,
        "ok_0f": ok_f,
        "sub": {k: sub[k].get("ok") for k in sorted(sub)},
    }


def _heldout_episodes(episodes: List[Any], frac: float) -> Tuple[List[Any], Dict[str, Any]]:
    """Deterministic tail split — last ceil(frac*N) episodes are the scored set.

    Matches ``_wm_fidelity_eval._heldout_split`` / ``_wm_train_validate`` discipline:
    when ``frac>0``, score only the held-out tail (honest gate for a head trained
    on the complementary prefix). ``frac=0`` scores all episodes (in-sample /
    fully OOD control-arm regimes — caller must declare which).
    """
    import math

    n = len(episodes)
    if frac <= 0.0 or n == 0:
        return list(episodes), {
            "heldout_frac": 0.0,
            "n_total": n,
            "n_scored": n,
            "n_train_prefix": n,
            "regime": "all_episodes",
        }
    k = max(1, math.ceil(float(frac) * n))
    scored = list(episodes[n - k :])
    return scored, {
        "heldout_frac": float(frac),
        "n_total": n,
        "n_scored": len(scored),
        "n_train_prefix": n - len(scored),
        "regime": "heldout_tail",
    }


def run_eval(
    *,
    dataset: Path,
    depth_ckpt: Path,
    tau_ckpt: Path,
    device: str,
    config: Dict[str, Any],
    max_episodes: int = 0,
    emit: Optional[Path] = None,
    heldout_frac: float = 0.0,
) -> Dict[str, Any]:
    import torch

    from experiments.aerial.rl import dataset as ds
    from experiments.aerial.rl.depth_predictor import DepthMinPredictor

    safety = config.get("safety", {}) or {}
    tau_cfg = config.get("tau_predictor", {}) or {}
    thr = ZeroThresholds(
        trigger_m=float(safety.get("min_depth_m", 3.0)),
        min_tau_s=float(safety.get("min_tau_s", 1.0)),
        center_frac=float(tau_cfg.get("center_frac", 0.5)),
    )

    pred = DepthMinPredictor.from_checkpoint(depth_ckpt, device=device)
    n_frames = int(pred.n_frames)
    tau_pred = make_tau_predictor(
        kind=str(tau_cfg.get("kind", "foe_calibrated")),
        ckpt=tau_ckpt,
        device=device,
        center_frac=thr.center_frac,
        min_closing_m_s=float(tau_cfg.get("min_closing_m_s", 0.05)),
        max_tau_s=float(tau_cfg.get("max_tau_s", 60.0)),
        dt_s=float(tau_cfg.get("dt_s", 0.1)),
        use_gt_depth=False,
    )

    episodes = ds.load_dataset(dataset, skip_quarantined=True)
    if max_episodes > 0:
        episodes = episodes[: int(max_episodes)]
    episodes, split_meta = _heldout_episodes(episodes, float(heldout_frac))
    if split_meta["regime"] == "heldout_tail":
        print(
            f"[v4-zero] held-out split: score {split_meta['n_scored']}/"
            f"{split_meta['n_total']} (tail); train prefix "
            f"{split_meta['n_train_prefix']} excluded"
        )
    elif float(heldout_frac) <= 0.0:
        print(
            "[v4-zero] WARNING: --heldout-frac=0 → scoring ALL episodes "
            "(in-sample if the depth head trained on this corpus; OK for a "
            "control-arm head that never saw these eps)"
        )
    near_pred: List[float] = []
    near_gt: List[float] = []
    outer_pred: List[float] = []
    outer_gt: List[float] = []
    per_frame_near_px: List[int] = []

    gt_fwd_list: List[float] = []
    dhat_fwd_list: List[float] = []
    ep_ids: List[int] = []
    per_frame_outer_px: List[int] = []
    # Aligned per-frame rows for ⓪f sweep (fov + τ on same timestep).
    fov_gt: List[float] = []
    fov_dhat: List[float] = []
    fov_gt_fwd: List[float] = []
    fov_tau: List[float] = []
    fov_vfwd: List[float] = []

    dt_fallback_count = 0
    dt_samples: List[float] = []
    n_no_depth = 0
    n_frames_total = 0

    for ep_i, ep in enumerate(episodes):
        hist: deque = deque(maxlen=n_frames)
        tau_pred.reset()
        for t in ep:
            rgb = np.asarray(t.obs.rgb, dtype=np.uint8)
            hist.append(rgb)
            depth_gt = getattr(t.obs, "depth", None)
            if depth_gt is None:
                n_no_depth += 1
                continue
            frames = list(hist)
            while len(frames) < n_frames:
                frames.insert(0, frames[0])
            stack = np.stack(frames[-n_frames:], axis=0)
            tensor = torch.from_numpy(stack).unsqueeze(0)
            with torch.no_grad():
                dmap_t, _ = pred._model.predict_from_window(tensor.to(device))  # noqa: SLF001
            dmap = np.squeeze(dmap_t.squeeze(0).detach().float().cpu().numpy())

            gmap = np.asarray(depth_gt, dtype=np.float64)
            near_m = (
                np.isfinite(gmap)
                & (gmap > _NEAR_LO)
                & (gmap <= _NEAR_HI)
                & (gmap <= 200.0)
            )
            outer_m = (
                np.isfinite(gmap)
                & (gmap > _OUTER_LO)
                & (gmap <= _OUTER_HI)
                & (gmap <= 200.0)
            )
            if np.any(near_m):
                near_pred.extend(dmap.reshape(-1)[near_m.reshape(-1)].tolist())
                near_gt.extend(gmap.reshape(-1)[near_m.reshape(-1)].tolist())
                per_frame_near_px.append(int(np.count_nonzero(near_m)))
            else:
                per_frame_near_px.append(0)
            if np.any(outer_m):
                outer_pred.extend(dmap.reshape(-1)[outer_m.reshape(-1)].tolist())
                outer_gt.extend(gmap.reshape(-1)[outer_m.reshape(-1)].tolist())
                per_frame_outer_px.append(int(np.count_nonzero(outer_m)))
            else:
                per_frame_outer_px.append(0)

            g_fov = full_min_depth(gmap)
            d_fov = full_min_depth(dmap)
            g_fwd = forward_min_depth(gmap, center_frac=thr.center_frac)
            d_fwd = forward_min_depth(dmap, center_frac=thr.center_frac)

            obs = t.obs
            prev_t = tau_pred._prev_t  # noqa: SLF001
            tau_v = tau_pred.predict_tau(obs)
            obs_t = float(obs.t)
            if prev_t is not None and np.isfinite(obs_t) and np.isfinite(prev_t) and obs_t > prev_t:
                dt_samples.append(float(obs_t - prev_t))
            elif prev_t is not None:
                dt_fallback_count += 1

            if np.isfinite(g_fwd) and np.isfinite(d_fwd):
                gt_fwd_list.append(g_fwd)
                dhat_fwd_list.append(d_fwd)
                ep_ids.append(ep_i)
            if (
                np.isfinite(g_fov)
                and np.isfinite(d_fov)
                and tau_v is not None
                and np.isfinite(g_fwd)
            ):
                fov_gt.append(g_fov)
                fov_dhat.append(d_fov)
                fov_gt_fwd.append(g_fwd)
                fov_tau.append(float(tau_v))
                fov_vfwd.append(closing_speed_m_s(obs))
            n_frames_total += 1

    near_stats = pixel_absrel_stats(
        np.asarray(near_pred), np.asarray(near_gt), gt_lo=_NEAR_LO, gt_hi=_NEAR_HI
    )
    near_gt_bins = near_absrel_gt_bins(
        np.asarray(near_pred), np.asarray(near_gt), edges=(0.0, 1.5, 3.0)
    )
    outer_stats = pixel_absrel_stats(
        np.asarray(outer_pred), np.asarray(outer_gt), gt_lo=_OUTER_LO, gt_hi=_OUTER_HI
    )
    sup_b = check_support_b(per_frame_near_px, thr=thr)
    sub_0a = check_0a(near_stats, thr=thr)
    sub_0b = {**sup_b, "label": "0b", "near_px_total": sup_b["support_px"]}
    sub_0c = {
        **check_0c(near_stats, thr=thr),
        "gt_bins": near_gt_bins,
        "note": "gt_bins: AbsRel on (0,1.5] vs (1.5,3.0]; not a PASS criterion — attribution only",
    }
    sub_0d = check_0d(
        np.asarray(gt_fwd_list),
        np.asarray(dhat_fwd_list),
        thr=thr,
        episode_ids=np.asarray(ep_ids, dtype=np.int64),
    )
    sub_0e = {
        "ok": True,
        "distribution": "deployment_rollout_corpus",
        "dataset": str(dataset),
        "note": "⓪e: not WM train holdout; rollout frames with GT depth",
    }

    sweep = clearance_sweep(
        np.asarray(fov_gt),
        np.asarray(fov_dhat),
        np.asarray(fov_gt_fwd),
        np.asarray(fov_tau),
        np.asarray(fov_vfwd),
        thr=thr,
    )
    delta_hint = suggest_delta(sweep, thr=thr)
    outer_sup = check_support_b(per_frame_outer_px, thr=thr)
    # ⓪f(1)(2) AbsRel on (3,8] are report-only (§4.6.2 / 5aa) — do NOT apply
    # ⓪a median≤0.30 or ⓪c p90≤0.50 (those thresholds are near-band only).
    # Pre-freeze ok = outer support only; (3)(4) false-trigger rates live in
    # clearance_sweep and become gating only after [lo,hi] is frozen.
    sub_0f = {
        "ok": bool(outer_sup["ok"]),
        "domain": f"({_OUTER_LO:g}, {_OUTER_HI:g}]",
        "median_absrel": outer_stats["median_absrel"],
        "p90_absrel": outer_stats["p90_absrel"],
        "n_px": outer_stats["n"],
        "support": outer_sup,
        "clearance_sweep": sweep,
        "delta_hint": delta_hint,
        "band_lo_hi": None,
        "note": (
            "⓪f(1)(2) report-only AbsRel; (3)(4) false-trigger rates in "
            "clearance_sweep; [lo,hi] intentionally null pre-freeze — do not "
            "apply ⓪a/⓪c AbsRel thresholds to the outer domain"
        ),
    }

    sub = {"0a": sub_0a, "0b": sub_0b, "0c": sub_0c, "0d": sub_0d, "0e": sub_0e, "0f": sub_0f}
    verdict = aggregate_verdict(sub)

    payload: Dict[str, Any] = {
        "step": "P3",
        "signal": "V4-⓪-v2",
        "dataset": str(dataset),
        "depth_ckpt": str(depth_ckpt),
        "tau_ckpt": str(tau_ckpt),
        "device": device,
        "thresholds": {
            "trigger_m": thr.trigger_m,
            "min_tau_s": thr.min_tau_s,
            "center_frac": thr.center_frac,
        },
        "split": split_meta,
        "episodes": len(episodes),
        "frames_scored": n_frames_total,
        "n_no_depth_frames": n_no_depth,
        "near_pixel_stats": {**near_stats, "gt_bins": near_gt_bins},
        "outer_pixel_stats": outer_stats,
        "tau_dt": {
            "n_samples": len(dt_samples),
            "median_dt_s": round(float(np.median(dt_samples)), 4) if dt_samples else None,
            "dt_fallback_count": dt_fallback_count,
            "used_default_dt_s": dt_fallback_count > 0,
        },
        "sub": sub,
        "verdict": verdict,
    }

    if emit:
        emit.parent.mkdir(parents=True, exist_ok=True)
        emit.write_text(json.dumps(payload, indent=2) + "\n")
        print(f"[v4-zero] wrote {emit}")

    _print_summary(payload)
    return payload


def _print_summary(payload: Dict[str, Any]) -> None:
    v = payload["verdict"]
    print(f"[v4-zero] episodes={payload['episodes']} frames={payload['frames_scored']}")
    for k in ("0a", "0b", "0c", "0d", "0e", "0f"):
        s = payload["sub"][k]
        mark = "PASS" if s.get("ok") else "FAIL"
        print(f"  {k}: {mark}  {json.dumps({x: s[x] for x in s if x != 'ok'}, default=str)[:120]}")
    print(f"[v4-zero] merge ok={v['ok']}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--depth-ckpt", required=True)
    ap.add_argument("--tau-ckpt", required=True)
    ap.add_argument("--config", default="configs/aerial_rl.yaml")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--max-episodes", type=int, default=0)
    ap.add_argument(
        "--heldout-frac",
        type=float,
        default=0.0,
        help=(
            "score only the deterministic tail fraction of episodes "
            "(same discipline as _wm_fidelity_eval). Required for authoritative "
            "⓪ after training a head on this corpus; 0 = all eps "
            "(declare control-arm / in-sample regime in the emit note)"
        ),
    )
    ap.add_argument("--emit", default=None)
    ap.add_argument("--trigger-m", type=float, default=None, help="override safety.min_depth_m (default 3.0 for V4 gate)")
    args = ap.parse_args(argv)

    import yaml

    cfg_path = Path(args.config)
    cfg = yaml.safe_load(cfg_path.read_text()) or {}
    if args.trigger_m is not None:
        cfg.setdefault("safety", {})["min_depth_m"] = float(args.trigger_m)
    elif float((cfg.get("safety") or {}).get("min_depth_m", 1.5)) < 2.0:
        # V4 deploy gate uses 3.0 m standoff; yaml training safety.min_depth_m=1.5 is not deploy trigger.
        cfg.setdefault("safety", {})["min_depth_m"] = 3.0

    payload = run_eval(
        dataset=Path(args.dataset).expanduser(),
        depth_ckpt=Path(args.depth_ckpt).expanduser(),
        tau_ckpt=Path(args.tau_ckpt).expanduser(),
        device=str(args.device),
        config=cfg,
        max_episodes=int(args.max_episodes),
        heldout_frac=float(args.heldout_frac),
        emit=Path(args.emit).expanduser() if args.emit else None,
    )
    return 0 if payload["verdict"]["ok"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
