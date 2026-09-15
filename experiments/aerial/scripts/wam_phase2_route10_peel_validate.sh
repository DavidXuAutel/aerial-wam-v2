#!/usr/bin/env bash
# Repeat-validation for winning Route-10 stack (opt sweep 2026-09-15).
# polyline+RG+HA, planner H=1, tti=2.5, peel_early subgoal tuning.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source "$ROOT/experiments/aerial/scripts/env_4090.sh"
PY="${AERIAL_PY:-${PYTHON_BIN:-python3}}"

ROUTE_IDX=9
OUT_ROOT="artifacts/wam_phase2_route10_peel_validate_20260915"
ANNO="experiments/aerial/phase3_unified/annotations/outdoor_long_only.json"
ACTOR="experiments/aerial/rl/artifacts/v4_ac_ckpt_phase2_toward_g_20260905_112006/v4_ac_latest.pt"
WM="experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt"
DEPTH="experiments/aerial/rl/artifacts/depth_ckpt_p45mid_s8j_20260825/depth_best_holdout_da3_ft_head.pt"
TAU="experiments/aerial/rl/artifacts/tau_ckpt_foe_r60_20260815/tau_foe_calibrator.pt"

WINNER=(
  --subgoal-source polyline
  --rolling-global
  --heading-assist
  --global-horizon-m 60
  --global-replan-period-s 1.0
  --heading-assist-cte-max-m 8.0
  --heading-assist-cos-thr 0.7
  --planner --planner-horizon 1
  --tti-coeff 2.5
  --heading-reentry-cos 0.5
  --cte-reentry-m 1.5
  --cruise-speed 10.0
  --max-steps 600
)

run_rep() {
  local tag="$1"
  local out="${OUT_ROOT}/${tag}.json"
  local traj="${OUT_ROOT}/${tag}_traj"
  mkdir -p "$OUT_ROOT" "$traj"
  echo "=== ${tag} ==="
  "$PY" -m experiments.aerial.scripts.wam_phase2_long_eval \
    --annotation "$ANNO" --routes "$ROUTE_IDX" \
    --wm-ckpt "$WM" --actor-ckpt "$ACTOR" \
    --depth-ckpt "$DEPTH" --tau-ckpt "$TAU" \
    --goal-feat-mode meter \
    --traj-out "${traj}/route09.jsonl" --out "$out" \
    "${WINNER[@]}" || true
}

summary() {
  "$PY" << 'PY'
import json, statistics as st
from pathlib import Path
out = Path("artifacts/wam_phase2_route10_peel_validate_20260915")
rows = []
for p in sorted(out.glob("peel*.json")):
    e = json.load(open(p))["episodes"][0]
    rows.append(e)
    print(p.stem, "arr", e["arrived"], "SPL", round(e["spl"],3), "L", round(e["actual_length_m"],1))
arr = [e for e in rows if e["arrived"]]
ge07 = [e for e in arr if e["spl"] >= 0.70]
print(f"\n{len(arr)}/{len(rows)} arrived, {len(ge07)}/{len(rows)} SPL>=0.7")
if arr:
    print(f"SPL mean={st.fmean(e['spl'] for e in arr):.3f}  L mean={st.fmean(e['actual_length_m'] for e in arr):.1f}")
PY
}

case "${1:-all}" in
  all)
    run_rep peel_r1; run_rep peel_r2; run_rep peel_r3; summary ;;
  summary) summary ;;
  peel_r1) run_rep peel_r1 ;;
  peel_r2) run_rep peel_r2 ;;
  peel_r3) run_rep peel_r3 ;;
  *) echo "Usage: $0 [all|summary|peel_r1|peel_r2|peel_r3]"; exit 1 ;;
esac
