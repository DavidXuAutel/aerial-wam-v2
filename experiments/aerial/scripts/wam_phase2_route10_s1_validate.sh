#!/usr/bin/env bash
# Repeat-validation around s1 (tti_coeff sweep) on Route 10 / arm3 stack.
# Usage: bash experiments/aerial/scripts/wam_phase2_route10_s1_validate.sh [all|summary]
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
OUT_ROOT="artifacts/wam_phase2_route10_s1_validate_$(date +%Y%m%d)"
CS=10.0
MAX_STEPS=600

BASE=(
  --subgoal-source polyline
  --rolling-global
  --heading-assist
  --global-horizon-m 60
  --global-replan-period-s 1.0
  --heading-assist-cte-max-m 8.0
  --heading-assist-cos-thr 0.7
)

run_one() {
  local tag="$1"
  local tti="$2"
  local seed="${3:-42}"
  local out_json="${OUT_ROOT}/${tag}.json"
  local traj_dir="${OUT_ROOT}/${tag}_traj"
  mkdir -p "$OUT_ROOT" "$traj_dir"
  echo "=== ${tag} tti=${tti} seed=${seed} ==="
  if ! "$PY" -m experiments.aerial.scripts.wam_phase2_long_eval \
    --annotation "$ANNO" \
    --routes "$ROUTE_IDX" \
    --wm-ckpt "$WM" \
    --actor-ckpt "$ACTOR" \
    --depth-ckpt "$DEPTH" \
    --tau-ckpt "$TAU" \
    --goal-feat-mode meter \
    --cruise-speed "$CS" \
    --planner --planner-horizon 5 \
    --max-steps "$MAX_STEPS" \
    --traj-out "${traj_dir}/route09.jsonl" \
    --out "$out_json" \
    "${BASE[@]}" \
    --tti-coeff "$tti"; then
    echo "WARN: ${tag} non-zero exit"
  fi
}

summary() {
  "$PY" << PY
import json
from pathlib import Path
out = Path("${OUT_ROOT}")
rows = []
for p in sorted(out.glob("*.json")):
    e = json.load(open(p))["episodes"][0]
    rows.append((p.stem, e))
print(f"{'tag':22s} {'arr':5s} {'SPL':>6s} {'L_act':>7s} {'steps':>5s} {'IR':>6s} {'d_fin':>6s}")
for tag, e in rows:
    print(f"{tag:22s} {str(e['arrived']):5s} {e['spl']:6.3f} {e['actual_length_m']:7.1f} {e['steps']:5d} {e['intervention_rate']:6.3f} {e['d_final_m']:6.2f}")
arr = [e for _, e in rows if e["arrived"]]
if arr:
    import statistics as st
    print(f"\narrived n={len(arr)}/{len(rows)}  SPL mean={st.fmean(x['spl'] for x in arr):.3f}  L mean={st.fmean(x['actual_length_m'] for x in arr):.1f}  IR mean={st.fmean(x['intervention_rate'] for x in arr):.3f}")
PY
}

CMD="${1:-all}"
case "$CMD" in
  all)
    run_one "tti20_run1" 2.0
    run_one "tti25_run1" 2.5
    run_one "tti25_run2" 2.5
    run_one "tti25_run3" 2.5
    run_one "tti30_run1" 3.0
    summary
    ;;
  summary) summary ;;
  *) echo "Usage: $0 [all|summary]"; exit 1 ;;
esac
