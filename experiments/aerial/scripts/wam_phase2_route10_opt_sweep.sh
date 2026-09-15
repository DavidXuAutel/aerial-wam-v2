#!/usr/bin/env bash
# Route 10 optimization sweep: combine H=1 planner + tti + heading-assist tuning.
# Goal: stable SPL >= 0.70 (gate) on arm3 stack before 16-route promotion.
#
# Usage: bash experiments/aerial/scripts/wam_phase2_route10_opt_sweep.sh [all|summary|TAG]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source "$ROOT/experiments/aerial/scripts/env_4090.sh"
PY="${AERIAL_PY:-${PYTHON_BIN:-python3}}"

ROUTE_IDX=9
ANNO="experiments/aerial/phase3_unified/annotations/outdoor_long_only.json"
ACTOR="experiments/aerial/rl/artifacts/v4_ac_ckpt_phase2_toward_g_20260905_112006/v4_ac_latest.pt"
WM="experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt"
DEPTH="experiments/aerial/rl/artifacts/depth_ckpt_p45mid_s8j_20260825/depth_best_holdout_da3_ft_head.pt"
TAU="experiments/aerial/rl/artifacts/tau_ckpt_foe_r60_20260815/tau_foe_calibrator.pt"
OUT_ROOT="artifacts/wam_phase2_route10_opt_sweep_20260915"
CS=10.0
MAX_STEPS=600
PH=1

BASE=(
  --subgoal-source polyline
  --rolling-global
  --heading-assist
  --global-horizon-m 60
  --global-replan-period-s 1.0
  --heading-assist-cte-max-m 8.0
  --heading-assist-cos-thr 0.7
)

run_opt() {
  local tag="$1"
  local horizon="$2"
  local tti="$3"
  shift 3
  local out_json="${OUT_ROOT}/${tag}.json"
  local traj_dir="${OUT_ROOT}/${tag}_traj"
  mkdir -p "$OUT_ROOT" "$traj_dir"
  echo "=== ${tag} H=${horizon} tti=${tti} ==="
  if ! "$PY" -m experiments.aerial.scripts.wam_phase2_long_eval \
    --annotation "$ANNO" \
    --routes "$ROUTE_IDX" \
    --wm-ckpt "$WM" \
    --actor-ckpt "$ACTOR" \
    --depth-ckpt "$DEPTH" \
    --tau-ckpt "$TAU" \
    --goal-feat-mode meter \
    --cruise-speed "$CS" \
    --planner --planner-horizon "$horizon" \
    --max-steps "$MAX_STEPS" \
    --traj-out "${traj_dir}/route09.jsonl" \
    --out "$out_json" \
    --tti-coeff "$tti" \
    "${BASE[@]}" \
    "$@"; then
    echo "WARN: ${tag} non-zero exit"
  fi
}

# --- Phase 1: H=1 × tti grid ---
h1_tti20()      { run_opt "h1_tti20"      "$PH" 2.0; }
h1_tti25_r1()   { run_opt "h1_tti25_r1"   "$PH" 2.5; }
h1_tti25_r2()   { run_opt "h1_tti25_r2"   "$PH" 2.5; }
h1_tti25_r3()   { run_opt "h1_tti25_r3"   "$PH" 2.5; }
h1_tti30()      { run_opt "h1_tti30"      "$PH" 3.0; }
h1_tti40()      { run_opt "h1_tti40"      "$PH" 4.0; }

# --- Phase 2: HA / subgoal tuning at tti=2.5 ---
h1_tti25_ha_soft() {
  run_opt "h1_tti25_ha_soft" "$PH" 2.5 \
    --heading-assist-cte-max-m 12.0 --heading-assist-cos-thr 0.5
}
h1_tti25_ha_lat01() {
  run_opt "h1_tti25_ha_lat01" "$PH" 2.5 \
    --heading-assist-cos-thr 0.5 --heading-assist-lateral-scale 0.1
}
h1_tti25_peel_early() {
  run_opt "h1_tti25_peel_early" "$PH" 2.5 \
    --heading-reentry-cos 0.5 --cte-reentry-m 1.5
}
h1_tti25_cs8() {
  run_opt "h1_tti25_cs8" "$PH" 2.5 --cruise-speed 8.0
}

# --- Baseline: prior best (H=5 tti=2.5) same day ---
h5_tti25_ref() { run_opt "h5_tti25_ref" 5 2.5; }

summary() {
  "$PY" << 'PY'
import json, statistics as st
from pathlib import Path

out = Path("artifacts/wam_phase2_route10_opt_sweep_20260915")
rows = []
for p in sorted(out.glob("*.json")):
    e = json.load(open(p))["episodes"][0]
    rows.append((p.stem, e))
rows.sort(key=lambda x: (-x[1]["spl"], x[1]["actual_length_m"]))
print(f"{'tag':22s} {'arr':5s} {'SPL':>6s} {'L_act':>7s} {'steps':>5s} {'IR':>6s} {'d_fin':>6s}")
for tag, e in rows:
    gate = "PASS" if e["arrived"] and e["spl"] >= 0.70 else ""
    print(f"{tag:22s} {str(e['arrived']):5s} {e['spl']:6.3f} {e['actual_length_m']:7.1f} {e['steps']:5d} {e['intervention_rate']:6.3f} {e['d_final_m']:6.2f} {gate}")
arr = [e for _, e in rows if e["arrived"]]
ge07 = [e for e in arr if e["spl"] >= 0.70]
print(f"\narrived {len(arr)}/{len(rows)}  SPL>=0.7: {len(ge07)}/{len(rows)}")
if ge07:
    print(f"gate hits: SPL mean={st.fmean(x['spl'] for x in ge07):.3f}  L mean={st.fmean(x['actual_length_m'] for x in ge07):.1f}")
tti25 = [e for t, e in rows if "tti25" in t and e["arrived"]]
if len(tti25) >= 2:
    print(f"tti25 stability: {len(tti25)}/{sum(1 for t,_ in rows if 'tti25' in t)} arrived, SPL mean={st.fmean(x['spl'] for x in tti25):.3f}")
PY
}

phase1() {
  h1_tti20
  h1_tti25_r1
  h1_tti25_r2
  h1_tti25_r3
  h1_tti30
  h1_tti40
}

phase2() {
  h1_tti25_ha_soft
  h1_tti25_ha_lat01
  h1_tti25_peel_early
  h1_tti25_cs8
  h5_tti25_ref
}

CMD="${1:-all}"
case "$CMD" in
  all)               phase1; phase2; summary ;;
  phase1)            phase1; summary ;;
  phase2)            phase2; summary ;;
  summary)           summary ;;
  h1_tti20)          h1_tti20 ;;
  h1_tti25_r1)       h1_tti25_r1 ;;
  h1_tti25_r2)       h1_tti25_r2 ;;
  h1_tti25_r3)       h1_tti25_r3 ;;
  h1_tti30)          h1_tti30 ;;
  h1_tti40)          h1_tti40 ;;
  h1_tti25_ha_soft)  h1_tti25_ha_soft ;;
  h1_tti25_ha_lat01) h1_tti25_ha_lat01 ;;
  h1_tti25_peel_early) h1_tti25_peel_early ;;
  h1_tti25_cs8)      h1_tti25_cs8 ;;
  h5_tti25_ref)      h5_tti25_ref ;;
  *)
    echo "Usage: $0 [all|phase1|phase2|summary|h1_tti25_r1|...]"
    exit 1
    ;;
esac
