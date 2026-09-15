#!/usr/bin/env bash
# ARM3 parameter sweep on Route 10 (route_idx=9).
# Base: polyline + rolling-global + heading-assist (arm3 winner).
#
# Usage on 125:
#   bash experiments/aerial/scripts/wam_phase2_route10_arm3_sweep.sh [arm|all|summary]
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
OUT_ROOT="artifacts/wam_phase2_route10_arm3_sweep_$(date +%Y%m%d)"
CS=10.0
MAX_STEPS=600

# arm3 defaults
BASE_FLAGS=(
  --subgoal-source polyline
  --rolling-global
  --heading-assist
  --global-horizon-m 60
  --global-replan-period-s 1.0
  --heading-assist-cte-max-m 8.0
  --heading-assist-cos-thr 0.7
)

run_arm() {
  local tag="$1"
  shift
  local out_json="${OUT_ROOT}/${tag}.json"
  local traj_dir="${OUT_ROOT}/${tag}_traj"
  mkdir -p "$OUT_ROOT" "$traj_dir"
  echo "=== SWEEP ${tag} -> ${out_json} ==="
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
    "${BASE_FLAGS[@]}" \
    "$@"; then
    echo "WARN: ${tag} eval exited non-zero (continuing sweep)"
  fi
}

arm_s0_baseline() {
  run_arm "s0_arm3_baseline"
}

arm_s1_tti25() {
  run_arm "s1_tti_coeff_2p5" --tti-coeff 2.5
}

arm_s2_cte_tight() {
  run_arm "s2_cte_reentry_1p5" \
    --cte-reentry-m 1.5 --cte-lock-freeze-m 4.0 --heading-reentry-cos 0.8
}

arm_s3_ha_soft() {
  run_arm "s3_ha_soft" \
    --heading-assist-cte-max-m 12.0 --heading-assist-cos-thr 0.5
}

arm_s4_rg_fast() {
  run_arm "s4_rg_fast" \
    --global-replan-period-s 0.5 --global-horizon-m 40
}

arm_s5_combo() {
  run_arm "s5_combo" \
    --tti-coeff 2.5 \
    --cte-reentry-m 1.5 --cte-lock-freeze-m 4.0 --heading-reentry-cos 0.8 \
    --heading-assist-cte-max-m 12.0 --heading-assist-cos-thr 0.5 \
    --global-replan-period-s 0.5 --global-horizon-m 40
}

print_summary() {
  "$PY" << PY
import json, glob
from pathlib import Path
out = Path("${OUT_ROOT}")
rows = []
for p in sorted(out.glob("s*.json")):
    try:
        e = json.load(open(p))["episodes"][0]
    except Exception:
        continue
    rows.append({
        "tag": p.stem,
        "arrived": e["arrived"],
        "spl": e["spl"],
        "L_act": e["actual_length_m"],
        "steps": e["steps"],
        "IR": e["intervention_rate"],
        "d_final": e["d_final_m"],
    })
rows.sort(key=lambda r: (-r["spl"], r["L_act"], r["IR"]))
print(f"{'tag':28s} {'arr':5s} {'SPL':>6s} {'L_act':>7s} {'steps':>5s} {'IR':>6s} {'d_fin':>6s}")
for r in rows:
    print(f"{r['tag']:28s} {str(r['arrived']):5s} {r['spl']:6.3f} {r['L_act']:7.1f} {r['steps']:5d} {r['IR']:6.3f} {r['d_final']:6.2f}")
PY
}

CMD="${1:-all}"
case "$CMD" in
  s0|baseline)     arm_s0_baseline ;;
  s1|tti)          arm_s1_tti25 ;;
  s2|cte)          arm_s2_cte_tight ;;
  s3|ha)           arm_s3_ha_soft ;;
  s4|rg)           arm_s4_rg_fast ;;
  s5|combo)        arm_s5_combo ;;
  summary)         print_summary ;;
  all)
    arm_s0_baseline || true
    arm_s1_tti25 || true
    arm_s2_cte_tight || true
    arm_s3_ha_soft || true
    arm_s4_rg_fast || true
    arm_s5_combo || true
    echo ""
    print_summary
    ;;
  *)
    echo "Usage: $0 [s0|s1|s2|s3|s4|s5|all|summary]"
    exit 1
    ;;
esac
