#!/usr/bin/env bash
# Route 10 (route_idx=9) trajectory-efficiency ablation plan.
#
# Context: V6 toward_g baseline flew 287.5 m for a 111 m task (SPL=0.43, 452 steps).
# This script runs the planned arms on .110 (AirSim); merge JSONs before DECLARE.
#
# Usage (on eval box):
#   source experiments/aerial/scripts/env_4090.sh   # or your .110 env
#   bash experiments/aerial/scripts/wam_phase2_route10_efficiency_plan.sh [arm]
#
# Arms: baseline | polyline | polyline_ha | polyline_rg | toward_g_r25 | toward_g_r50 | all
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
OUT_ROOT="artifacts/wam_phase2_route10_efficiency_$(date +%Y%m%d)"
CS=10.0
MAX_STEPS=600

run_eval() {
  local tag="$1"
  shift
  local out_json="${OUT_ROOT}/${tag}.json"
  local traj_jsonl="${OUT_ROOT}/${tag}_traj.jsonl"
  mkdir -p "$OUT_ROOT"
  echo "=== ARM: ${tag} -> ${out_json} ==="
  "$PY" -m experiments.aerial.scripts.wam_phase2_long_eval \
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
    --traj-out "$traj_jsonl" \
    --out "$out_json" \
    "$@"
}

arm_baseline() {
  run_eval "arm0_baseline_toward_g_r100" \
    --subgoal-source toward_g --r-m-intent 100
}

arm_polyline() {
  run_eval "arm1_polyline" \
    --subgoal-source polyline
}

arm_polyline_ha() {
  run_eval "arm2_polyline_heading_assist" \
    --subgoal-source polyline --heading-assist
}

arm_polyline_rg() {
  run_eval "arm3_polyline_rolling_global_ha" \
    --subgoal-source polyline --heading-assist --rolling-global \
    --global-horizon-m 60 --global-replan-period-s 1.0
}

arm_toward_g_r25() {
  run_eval "arm4_toward_g_r25" \
    --subgoal-source toward_g --r-m-intent 25
}

arm_toward_g_r50() {
  run_eval "arm5_toward_g_r50" \
    --subgoal-source toward_g --r-m-intent 50
}

run_forensics() {
  local tag="$1"
  local traj_jsonl="${OUT_ROOT}/${tag}_traj.jsonl"
  if [[ ! -f "$traj_jsonl" ]]; then
    echo "skip forensics: missing $traj_jsonl"
    return 0
  fi
  "$PY" -m experiments.aerial.scripts.wam_phase2_traj_forensics \
    --annotation "$ANNO" \
    --route-indices "$ROUTE_IDX" \
    --actor-ckpt "$ACTOR" \
    --wm-ckpt "$WM" \
    --depth-ckpt "$DEPTH" \
    --cruise-speed "$CS" \
    --max-steps "$MAX_STEPS" \
    --out-dir "${OUT_ROOT}/forensics_${tag}"
}

render_dual_view() {
  local tag="$1"
  local traj_jsonl="${OUT_ROOT}/${tag}_traj.jsonl"
  if [[ ! -f "$traj_jsonl" ]]; then
    echo "skip render: missing $traj_jsonl"
    return 0
  fi
  "$PY" -m experiments.aerial.scripts.wam_phase2_dual_view_from_traj \
    --traj-jsonl "$traj_jsonl" \
    --ref-polyline-json "$ANNO" \
    --route-label "PHASE-2 ROUTE 10 (${tag})" \
    --out-dir "${OUT_ROOT}/videos_${tag}" \
    --out-prefix "route10_${tag}" \
    --fps 5 --source-hz 5
}

ARM="${1:-all}"

case "$ARM" in
  baseline)       arm_baseline ;;
  polyline)       arm_polyline ;;
  polyline_ha)    arm_polyline_ha ;;
  polyline_rg)    arm_polyline_rg ;;
  toward_g_r25)   arm_toward_g_r25 ;;
  toward_g_r50)   arm_toward_g_r50 ;;
  forensics)
    for t in arm0_baseline_toward_g_r100 arm1_polyline arm2_polyline_heading_assist \
             arm3_polyline_rolling_global_ha arm4_toward_g_r25 arm5_toward_g_r50; do
      run_forensics "$t"
    done
    ;;
  render)
    for t in arm0_baseline_toward_g_r100 arm2_polyline_heading_assist arm3_polyline_rolling_global_ha; do
      render_dual_view "$t"
    done
    ;;
  all)
    arm_baseline
    arm_polyline
    arm_polyline_ha
    arm_polyline_rg
    arm_toward_g_r25
    arm_toward_g_r50
    ;;
  *)
    echo "Unknown arm: $ARM"
    echo "Usage: $0 [baseline|polyline|polyline_ha|polyline_rg|toward_g_r25|toward_g_r50|forensics|render|all]"
    exit 1
    ;;
esac

echo ""
echo "Done. Results under: ${OUT_ROOT}"
echo "Compare: python - <<'PY'"
echo "import json, glob"
echo "for p in sorted(glob.glob('${OUT_ROOT}/arm*.json')):"
echo "  d=json.load(open(p)); e=d['episodes'][0]"
echo "  print(p.split('/')[-1], 'SPL', e['spl'], 'L_act', e['actual_length_m'], 'steps', e['steps'], 'IR', e['intervention_rate'])"
echo "PY"
