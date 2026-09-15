#!/usr/bin/env bash
# 16-route eval — V11 stack (2026-09-15).
# Code: cap_r (CTE>3m) + ha_fix (HA seg on full corridor, RG period skip, terminal_smooth).
# CLI: polyline+RG+HA, planner H=1, tti=2.5, peel_early params.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source "$ROOT/experiments/aerial/scripts/env_4090.sh"
PY="${AERIAL_PY:-${PYTHON_BIN:-python3}}"

OUT_ROOT="${OUT_ROOT:-artifacts/wam_phase2_v11_full16_20260915}"
ANNO="${ANNO:-experiments/aerial/phase3_unified/annotations/outdoor_long_only.json}"
ACTOR="${ACTOR:-experiments/aerial/rl/artifacts/v4_ac_ckpt_phase2_toward_g_20260905_112006/v4_ac_latest.pt}"
WM="${WM:-experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt}"
DEPTH="${DEPTH:-experiments/aerial/rl/artifacts/depth_ckpt_p45mid_s8j_20260825/depth_best_holdout_da3_ft_head.pt}"
TAU="${TAU:-experiments/aerial/rl/artifacts/tau_ckpt_foe_r60_20260815/tau_foe_calibrator.pt}"

mkdir -p "$OUT_ROOT"
OUT_JSON="${OUT_ROOT}/full16.json"
LOG="${OUT_ROOT}/run.log"

echo "=== Phase-2 best stack 16-route eval -> ${OUT_JSON} ===" | tee "$LOG"

"$PY" -m experiments.aerial.scripts.wam_phase2_long_eval \
  --annotation "$ANNO" \
  --wm-ckpt "$WM" \
  --actor-ckpt "$ACTOR" \
  --depth-ckpt "$DEPTH" \
  --tau-ckpt "$TAU" \
  --goal-feat-mode meter \
  --cruise-speed 10.0 \
  --max-steps 600 \
  --planner --planner-horizon 1 \
  --tti-coeff 2.5 \
  --subgoal-source polyline \
  --rolling-global \
  --heading-assist \
  --global-horizon-m 60 \
  --global-replan-period-s 1.0 \
  --heading-assist-cte-max-m 8.0 \
  --heading-assist-cos-thr 0.7 \
  --heading-reentry-cos 0.5 \
  --cte-reentry-m 1.5 \
  --traj-out "${OUT_ROOT}/traj" \
  --out "$OUT_JSON" 2>&1 | tee -a "$LOG"

"$PY" << PY
import json, statistics as st
d = json.load(open("${OUT_JSON}"))
eps = d["episodes"]
arr = [e for e in eps if e["arrived"]]
spls = [e["spl"] for e in arr if e["spl"]]
ge07 = sum(1 for s in spls if s >= 0.70)
print(f"\nSR={len(arr)}/{len(eps)} ({100*len(arr)/len(eps):.1f}%)")
if spls:
    print(f"SPL mean={st.fmean(spls):.3f} med={st.median(spls):.3f}  SPL>=0.7: {ge07}/{len(arr)}")
    for e in sorted(arr, key=lambda x: -x["spl"])[:5]:
        print(f"  R{e['route_idx']+1:02d} SPL={e['spl']:.3f} L={e['actual_length_m']:.0f}m")
PY
