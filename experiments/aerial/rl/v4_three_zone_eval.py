"""Three-zone speed shield: kinematic feasibility + depth-precision budget (offline).

Runs on 4090/H100 like ``v4_zero_eval`` — one forward pass over a GT-depth corpus,
scores whether the **old-head** ``D̂_fwd`` errors fit the margins implied by an
optimal three-line speed profile.

    python -m experiments.aerial.rl.v4_three_zone_eval \\
        --dataset .../dataset_v0_p45_merged_20260821 \\
        --depth-ckpt .../depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt \\
        --tau-ckpt .../tau_foe_calibrator.pt \\
        --heldout-frac 0.35 --split-seed 0 \\
        --emit artifacts/v4_three_zone_oldhead_hold035_20260822.json

S-5 (2026-08-24): adds functional gate candidate ``0i`` over three-zone depth
budget + stop-before-L3 semantics, with explicit acceptance mode.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from experiments.aerial.rl.depth_geometry import forward_min_depth
from experiments.aerial.rl.three_zone import (
    DEFAULT_A_MAX,
    DEFAULT_DELAY_S,
    DEFAULT_L1,
    DEFAULT_L2,
    DEFAULT_L3,
    DEFAULT_V1,
    DEFAULT_V2,
    STOP_PROBE_DT_S,
    ThreeZoneSpec,
    kinematic_budget,
    max_engage_delay_m,
    need,
    simulate_three_zone,
    stop_probe_spec,
)
from experiments.aerial.rl.tau_predictor import closing_speed_m_s, make_tau_predictor
from experiments.aerial.rl.v4_zero_eval import ZeroThresholds, _heldout_episodes, check_0d, check_0h

DEFAULT_CENTER_FRAC = 0.5

# Re-export for tests / callers.
__all__ = [
    "ThreeZoneSpec",
    "need",
    "simulate_three_zone",
    "max_engage_delay_m",
    "kinematic_budget",
    "depth_precision_vs_budget",
    "run_eval",
]


def _band_stats(
    gt: np.ndarray,
    dhat: np.ndarray,
    v: np.ndarray,
    *,
    lo: float,
    hi: float,
    budget_m: float,
) -> Dict[str, Any]:
    m = (
        np.isfinite(gt)
        & np.isfinite(dhat)
        & (gt > lo)
        & (gt <= hi)
    )
    n = int(np.count_nonzero(m))
    if n == 0:
        return {
            "gt_lo": lo,
            "gt_hi": hi,
            "n": 0,
            "budget_m": budget_m,
            "ok": False,
            "reason": "no_support",
        }
    err = dhat[m] - gt[m]  # >0 under-read (late)
    under = err[err > 0]
    p90_under = float(np.percentile(under, 90)) if under.size else 0.0
    p95_under = float(np.percentile(under, 95)) if under.size else 0.0
    frac_late = float(np.mean(err > 0))
    frac_exceed = float(np.mean(err > budget_m)) if budget_m > 0 else float(np.mean(err > 0))
    med_v = float(np.median(v[m])) if v is not None else float("nan")
    return {
        "gt_lo": lo,
        "gt_hi": hi,
        "n": n,
        "budget_m": round(budget_m, 3),
        "median_signed_err_m": round(float(np.median(err)), 4),
        "p90_underread_m": round(p90_under, 4),
        "p95_underread_m": round(p95_under, 4),
        "frac_underread": round(frac_late, 4),
        "frac_exceed_budget": round(frac_exceed, 4),
        "ok": p95_under <= budget_m and frac_exceed <= 0.05,
        "median_v_fwd_m_s": round(med_v, 3),
    }


_PRIMARY_0I_BANDS = ("engage_outer", "cap_l1")
_DEFAULT_MIN_BAND_SUPPORT = 20


def depth_precision_vs_budget(
    gt_fwd: np.ndarray,
    dhat_fwd: np.ndarray,
    v_fwd: np.ndarray,
    budget: Dict[str, Any],
    spec: ThreeZoneSpec,
) -> Dict[str, Any]:
    eng = float(budget["engage_outer_m"])
    delay_b = float(budget["max_underread_at_engage_m"])
    half = 0.5
    bands = {
        "engage_outer": (eng - 1.0, eng + 0.5, delay_b),
        "cap_l1": (spec.l1_m - half, spec.l1_m + half, delay_b),
        "cap_l2": (spec.l2_m - half, spec.l2_m + half, float(budget["segment_margin_m"]["l1_to_l2"])),
        "cap_l3": (spec.l3_m - 0.25, spec.l3_m + 0.25, float(budget["segment_margin_m"]["l2_to_l3"])),
    }
    rows = {
        name: _band_stats(gt_fwd, dhat_fwd, v_fwd, lo=lo, hi=hi, budget_m=b)
        for name, (lo, hi, b) in bands.items()
    }
    # Primary ⓪i bands only; cap_l2/cap_l3 are report-only (E0 / Errata §0.5).
    primary_ok = True
    for name in _PRIMARY_0I_BANDS:
        row = rows[name]
        if int(row.get("n", 0)) <= 0 or not row.get("ok"):
            primary_ok = False
            break
    return {"bands": rows, "all_bands_ok": bool(primary_ok)}


def _stop_probe_from_depth_p95(
    depth_vs_budget: Dict[str, Any],
    *,
    spec: Optional[ThreeZoneSpec] = None,
) -> Dict[str, Any]:
    """S5F-2: probe stop-before-L3 with observed primary-band p95 under-read.

    Late engage is modeled as ``engage_delay_m = -p95_underread`` on the
    worst primary band (``engage_outer`` / ``cap_l1``).
    """
    bands = depth_vs_budget.get("bands") or {}
    p95s: List[float] = []
    for name in _PRIMARY_0I_BANDS:
        row = bands.get(name) or {}
        if int(row.get("n", 0)) > 0:
            p95s.append(float(row.get("p95_underread_m", 0.0) or 0.0))
    probe_m = float(max(p95s)) if p95s else 0.0
    # G1″: stop probe uses dt=0.01 (de-aliased); deploy control loop keeps dt=0.2.
    zone = stop_probe_spec(spec)
    _, _, viol = simulate_three_zone(zone, engage_delay_m=-probe_m)
    viol_s = [str(v) for v in viol]
    return {
        "underread_probe_m": round(probe_m, 4),
        "probe_dt_s": float(STOP_PROBE_DT_S),
        "probe_violations": viol_s,
        "probe_violation_counts": {
            "z1": int(viol_s.count("z1")),
            "z2": int(viol_s.count("z2")),
            "z3": int(viol_s.count("z3")),
            "collision": int(viol_s.count("collision")),
        },
    }


def check_0i(
    *,
    depth_vs_budget: Dict[str, Any],
    kinematic: Dict[str, Any],
    acceptance_mode: str = "b_star",
    min_band_support: int = _DEFAULT_MIN_BAND_SUPPORT,
    spec: Optional[ThreeZoneSpec] = None,
) -> Dict[str, Any]:
    """S-5 / G1″ functional gate for three-zone safety.

    Modes:
    - ``a_strict``: ``stop_probe_ok`` requires zero ``z1/z2/z3/collision``.
    - ``b_star`` (default): ``stop_probe_ok`` requires zero ``z3`` and ``collision``
      (G1″); ``z1/z2`` report-only.

    G1″ (2026-08-26): primary ``ok`` = ``all_bands_ok AND stop_before_l3``
    (z3 HARD ∧ collision HARD) on de-aliased stop probe ``dt_s=0.01``.
    """
    mode = str(acceptance_mode).strip().lower()
    if mode not in {"a_strict", "b_star"}:
        raise ValueError(f"unknown acceptance_mode={acceptance_mode}")
    all_bands_ok = bool(depth_vs_budget.get("all_bands_ok", False))
    sim_diag = kinematic.get("sim_diagnostics") or {}
    viol_nom = [str(v) for v in (sim_diag.get("violations") or [])]
    cnt_nom = {
        "z1": int(viol_nom.count("z1")),
        "z2": int(viol_nom.count("z2")),
        "z3": int(viol_nom.count("z3")),
        "collision": int(viol_nom.count("collision")),
    }
    stop_before_l3_nominal = cnt_nom["z3"] == 0 and cnt_nom["collision"] == 0
    no_collision_nominal = cnt_nom["collision"] == 0
    probe = _stop_probe_from_depth_p95(depth_vs_budget, spec=spec)
    cnt = probe["probe_violation_counts"]
    stop_before_l3 = cnt["z3"] == 0 and cnt["collision"] == 0
    no_collision_probe = cnt["collision"] == 0
    no_z3_probe = cnt["z3"] == 0
    if mode == "a_strict":
        stop_probe_ok = (
            stop_before_l3 and cnt["z1"] == 0 and cnt["z2"] == 0
        )
    else:
        # G1″ B*: z3 HARD + collision HARD on dt=0.01 probe; z1/z2 report-only.
        stop_probe_ok = bool(stop_before_l3)
    bands = depth_vs_budget.get("bands") or {}
    band_support: Dict[str, Any] = {}
    support_ok = True
    for name in _PRIMARY_0I_BANDS:
        row = bands.get(name) or {}
        n = int(row.get("n", 0))
        ok_n = n >= int(min_band_support)
        band_support[name] = {
            "n": n,
            "min_required": int(min_band_support),
            "ok": bool(ok_n),
        }
        if not ok_n:
            support_ok = False
    # Report-only secondary bands (E0): always emit cap_l2/cap_l3 rows if present.
    secondary_band_report = {
        name: dict(bands.get(name) or {})
        for name in ("cap_l2", "cap_l3")
    }
    # G1″: primary = budget AND (no z3) AND (no collision) on stop probe.
    functional_ok = bool(all_bands_ok and stop_before_l3)
    return {
        "ok": functional_ok,
        "ok_authoritative": bool(functional_ok and support_ok),
        "authoritative": bool(support_ok),
        "acceptance_mode": mode,
        "gate_id": "G1_double_prime",
        "all_bands_ok": all_bands_ok,
        "support_ok": support_ok,
        "band_support": band_support,
        "secondary_band_report": secondary_band_report,
        "min_band_support": int(min_band_support),
        "no_collision_probe": bool(no_collision_probe),
        "no_z3_probe": bool(no_z3_probe),
        "no_collision_nominal": bool(no_collision_nominal),
        "stop_before_l3": bool(stop_before_l3),
        "stop_before_l3_nominal": bool(stop_before_l3_nominal),
        "stop_probe_ok": bool(stop_probe_ok),
        "underread_probe_m": probe["underread_probe_m"],
        "probe_dt_s": probe.get("probe_dt_s", STOP_PROBE_DT_S),
        "sim_violation_counts": cnt,
        "sim_violation_counts_nominal": cnt_nom,
        "note": (
            "G1_double_prime: primary ok = all_bands_ok AND stop_before_l3 "
            "(z3 HARD ∧ collision HARD) on stop probe dt_s=0.01; "
            "z1/z2 report-only; cap_l2/cap_l3 report-only (E0). "
            "Deploy control-loop dt unchanged (0.2)."
        ),
    }


# G1 signed default: operational budget 1.0 m (overrides kinematic 0.2).
_DEFAULT_0I_BUDGET_M = 1.0


def run_eval(
    *,
    dataset: Path,
    depth_ckpt: Path,
    tau_ckpt: Path,
    device: str,
    config: Dict[str, Any],
    spec: ThreeZoneSpec,
    heldout_frac: float = 0.0,
    split_seed: int = 0,
    max_episodes: int = 0,
    acceptance_mode: str = "b_star",
    budget_m: Optional[float] = None,
    emit: Optional[Path] = None,
) -> Dict[str, Any]:
    import torch

    from experiments.aerial.rl import dataset as ds
    from experiments.aerial.rl.depth_predictor import DepthMinPredictor

    tau_cfg = config.get("tau") or {}
    safety_cfg = config.get("safety") or {}
    zone_cfg = ThreeZoneSpec.from_mapping(safety_cfg)
    thr = ZeroThresholds(
        trigger_m=float(zone_cfg.l3_m),
        center_frac=DEFAULT_CENTER_FRAC,
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
    episodes, split_meta = _heldout_episodes(
        episodes, float(heldout_frac), seed=int(split_seed), dataset_dir=dataset
    )

    gt_fwd_list: List[float] = []
    dhat_fwd_list: List[float] = []
    v_fwd_list: List[float] = []
    ep_id_list: List[int] = []

    for ep_i, ep in enumerate(episodes):
        hist: List[np.ndarray] = []
        tau_pred.reset()
        for t in ep:
            rgb = np.asarray(t.obs.rgb, dtype=np.uint8)
            hist.append(rgb)
            depth_gt = getattr(t.obs, "depth", None)
            if depth_gt is None:
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
            g_fwd = forward_min_depth(gmap, center_frac=thr.center_frac)
            d_fwd = forward_min_depth(dmap, center_frac=thr.center_frac)
            if np.isfinite(g_fwd) and np.isfinite(d_fwd):
                gt_fwd_list.append(float(g_fwd))
                dhat_fwd_list.append(float(d_fwd))
                v_fwd_list.append(float(closing_speed_m_s(t.obs)))
                ep_id_list.append(int(ep_i))

    gt_arr = np.asarray(gt_fwd_list, dtype=np.float64)
    dhat_arr = np.asarray(dhat_fwd_list, dtype=np.float64)
    v_arr = np.asarray(v_fwd_list, dtype=np.float64)
    ep_ids_arr = np.asarray(ep_id_list, dtype=np.int64)

    kin = kinematic_budget(spec)
    kin_ok, kin_traj, kin_viol = simulate_three_zone(spec)
    kin = {
        **kin,
        "sim_diagnostics": {
            "ok": bool(kin_ok),
            "n_steps": int(len(kin_traj)),
            "violations": kin_viol,
        },
    }
    kinematic_underread = float(kin["max_underread_at_engage_m"])
    if budget_m is None:
        op_budget = float(_DEFAULT_0I_BUDGET_M)
        budget_source = "operational_1m"
    else:
        op_budget = float(budget_m)
        if abs(op_budget - _DEFAULT_0I_BUDGET_M) < 1e-12:
            budget_source = "operational_1m"
        else:
            budget_source = f"override:{op_budget}"
    kin["kinematic_max_underread_at_engage_m"] = round(kinematic_underread, 4)
    kin["max_underread_at_engage_m"] = round(op_budget, 4)
    kin["budget_source"] = budget_source
    depth = depth_precision_vs_budget(gt_arr, dhat_arr, v_arr, kin, spec)
    sub_0i = check_0i(
        depth_vs_budget=depth,
        kinematic=kin,
        acceptance_mode=str(acceptance_mode),
        spec=spec,
    )
    sub_0h = check_0h(
        gt_arr,
        dhat_arr,
        engage_outer_m=float(kin["engage_outer_m"]),
        thr=thr,
        episode_ids=ep_ids_arr,
    )
    sub_0d_legacy = check_0d(gt_arr, dhat_arr, thr=thr, episode_ids=ep_ids_arr)

    payload: Dict[str, Any] = {
        "authoritative": bool(sub_0i.get("authoritative", False)),
        "label": "three_zone_kinematic_depth_budget",
        "dataset": str(dataset),
        "depth_ckpt": str(depth_ckpt),
        "split": split_meta,
        "budget_source": budget_source,
        "operational_budget_m": round(op_budget, 4),
        "kinematic_max_underread_at_engage_m": round(kinematic_underread, 4),
        "kinematic": kin,
        "depth_vs_budget": depth,
        "0i_three_zone_functional": sub_0i,
        "0h_engage_miss": sub_0h,
        "0d_legacy": sub_0d_legacy,
        "verdict": {
            "kinematic_feasible": kin["feasible_nominal"],
            "depth_meets_budget": depth["all_bands_ok"],
            "functional_0i_ok": sub_0i.get("ok", False),
            "functional_0i_ok_authoritative": sub_0i.get("ok_authoritative", False),
            "engage_miss_ok": sub_0h.get("ok", False),
            "ok": (
                kin["feasible_nominal"]
                and depth["all_bands_ok"]
                and sub_0h.get("ok", False)
                and sub_0i.get("ok_authoritative", False)
            ),
        },
    }
    if emit is not None:
        emit.parent.mkdir(parents=True, exist_ok=True)
        emit.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--depth-ckpt", required=True)
    ap.add_argument("--tau-ckpt", required=True)
    ap.add_argument("--config", default="configs/aerial_rl.yaml")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--max-episodes", type=int, default=0)
    ap.add_argument("--heldout-frac", type=float, default=0.35)
    ap.add_argument("--split-seed", type=int, default=0)
    ap.add_argument("--emit", default=None)
    ap.add_argument("--l1", type=float, default=DEFAULT_L1)
    ap.add_argument("--l2", type=float, default=DEFAULT_L2)
    ap.add_argument("--l3", type=float, default=DEFAULT_L3)
    ap.add_argument("--v1", type=float, default=DEFAULT_V1)
    ap.add_argument("--v2", type=float, default=DEFAULT_V2)
    ap.add_argument("--a-max", type=float, default=DEFAULT_A_MAX)
    ap.add_argument("--delay-s", type=float, default=DEFAULT_DELAY_S)
    ap.add_argument(
        "--acceptance-mode",
        choices=("a_strict", "b_star"),
        default="b_star",
        help="S-5 mode: a_strict or b_star (recommended)",
    )
    ap.add_argument(
        "--0i-budget-m",
        type=float,
        default=_DEFAULT_0I_BUDGET_M,
        dest="budget_m",
        help=(
            "G1 operational under-read budget (m) applied to engage/cap_l1 bands; "
            f"default {_DEFAULT_0I_BUDGET_M} (operational_1m). "
            "Kinematic search value kept as kinematic_max_underread_at_engage_m."
        ),
    )
    args = ap.parse_args(argv)

    import yaml

    cfg = yaml.safe_load(Path(args.config).read_text()) or {}
    spec = ThreeZoneSpec(
        l1_m=float(args.l1),
        l2_m=float(args.l2),
        l3_m=float(args.l3),
        v1_m_s=float(args.v1),
        v2_m_s=float(args.v2),
        a_max_m_s2=float(args.a_max),
        delay_s=float(args.delay_s),
    )
    payload = run_eval(
        dataset=Path(args.dataset).expanduser(),
        depth_ckpt=Path(args.depth_ckpt).expanduser(),
        tau_ckpt=Path(args.tau_ckpt).expanduser(),
        device=str(args.device),
        config=cfg,
        spec=spec,
        heldout_frac=float(args.heldout_frac),
        split_seed=int(args.split_seed),
        max_episodes=int(args.max_episodes),
        acceptance_mode=str(args.acceptance_mode),
        budget_m=float(args.budget_m),
        emit=Path(args.emit).expanduser() if args.emit else None,
    )
    kin = payload["kinematic"]
    print(
        f"[three-zone] kinematic feasible={kin['feasible_nominal']} "
        f"engage≥{kin['engage_outer_m']}m budget={kin['max_underread_at_engage_m']}m "
        f"source={kin.get('budget_source')} "
        f"(kinematic={kin.get('kinematic_max_underread_at_engage_m')})"
    )
    for name, row in payload["depth_vs_budget"]["bands"].items():
        if row.get("n", 0) == 0:
            print(f"  {name}: no support")
            continue
        mark = "OK" if row.get("ok") else "FAIL"
        print(
            f"  {name}: {mark} n={row['n']} p95_under={row['p95_underread_m']}m "
            f"budget={row['budget_m']}m exceed_frac={row['frac_exceed_budget']}"
        )
    h = payload.get("0h_engage_miss", {})
    if h.get("n_cond", 0):
        mark = "OK" if h.get("ok") else "FAIL"
        print(
            f"  0h engage_miss: {mark} n={h.get('n_cond')} "
            f"p={h.get('p_engage_miss')} consec={h.get('max_consecutive_miss')} "
            f"@ {h.get('engage_outer_m')}m"
        )
    else:
        print("  0h engage_miss: no support")
    i = payload.get("0i_three_zone_functional", {})
    if i:
        mark = "OK" if i.get("ok") else "FAIL"
        auth = "auth" if i.get("authoritative") else "insufficient_support"
        print(
            f"  0i functional ({i.get('acceptance_mode')}/{i.get('gate_id')}): {mark} "
            f"[{auth}] no_collision={i.get('no_collision_probe')} "
            f"stop_before_l3={i.get('stop_before_l3')} "
            f"(nominal={i.get('stop_before_l3_nominal')}) "
            f"probe_m={i.get('underread_probe_m')} "
            f"viol={i.get('sim_violation_counts')}"
        )
        for bname, brow in (i.get("band_support") or {}).items():
            print(
                f"    support {bname}: n={brow.get('n')} "
                f"min={brow.get('min_required')} ok={brow.get('ok')}"
            )
    print(f"[three-zone] verdict ok={payload['verdict']['ok']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
