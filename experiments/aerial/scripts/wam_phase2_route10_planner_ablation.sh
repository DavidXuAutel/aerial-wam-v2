#!/usr/bin/env bash
# Route 10 planner on/off × subgoal 2×2 ablation (isolate WM imagination planner).
#
# Arms:
#   tg_planner_on    toward_g r=100 + planner H=5
#   tg_planner_off   toward_g r=100, π only
#   pl_planner_on    polyline + RG + HA + tti=2.5 + planner H=5
#   pl_planner_off   polyline + RG + HA + tti=2.5, π only
#   tg_planner_pass  toward_g + planner --planner-mock pass (no WM imagination)
#   tg_planner_h1    toward_g + planner H=1
#   pl_planner_pass  polyline stack + planner --planner-mock pass
#   pl_planner_h1    polyline stack + planner H=1
#
# Usage: bash experiments/aerial/scripts/wam_phase2_route10_planner_ablation.sh [all|wm_isolation|summary|ARM]
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
OUT_ROOT="artifacts/wam_phase2_route10_planner_ablation_20260915"
CS=10.0
MAX_STEPS=600

POLYLINE_BASE=(
  --subgoal-source polyline
  --rolling-global
  --heading-assist
  --global-horizon-m 60
  --global-replan-period-s 1.0
  --heading-assist-cte-max-m 8.0
  --heading-assist-cos-thr 0.7
  --tti-coeff 2.5
)

run_one() {
  local tag="$1"
  local planner_mode="$2"
  shift 2
  local out_json="${OUT_ROOT}/${tag}.json"
  local traj_dir="${OUT_ROOT}/${tag}_traj"
  mkdir -p "$OUT_ROOT" "$traj_dir"
  echo "=== ${tag} planner_mode=${planner_mode} ==="
  local planner_args=()
  case "$planner_mode" in
    on)   planner_args=(--planner --planner-horizon 5) ;;
    off)  planner_args=() ;;
    pass) planner_args=(--planner --planner-mock pass) ;;
    h1)   planner_args=(--planner --planner-horizon 1) ;;
    *)    echo "unknown planner_mode=${planner_mode}"; return 1 ;;
  esac
  if ! "$PY" -m experiments.aerial.scripts.wam_phase2_long_eval \
    --annotation "$ANNO" \
    --routes "$ROUTE_IDX" \
    --wm-ckpt "$WM" \
    --actor-ckpt "$ACTOR" \
    --depth-ckpt "$DEPTH" \
    --tau-ckpt "$TAU" \
    --goal-feat-mode meter \
    --cruise-speed "$CS" \
    --max-steps "$MAX_STEPS" \
    --traj-out "${traj_dir}/route09.jsonl" \
    --out "$out_json" \
    "${planner_args[@]}" \
    "$@"; then
    echo "WARN: ${tag} non-zero exit"
  fi
}

arm_tg_planner_on() {
  run_one "tg_planner_on" on \
    --subgoal-source toward_g --r-m-intent 100
}

arm_tg_planner_off() {
  run_one "tg_planner_off" off \
    --subgoal-source toward_g --r-m-intent 100
}

arm_pl_planner_on() {
  run_one "pl_planner_on" on "${POLYLINE_BASE[@]}"
}

arm_pl_planner_off() {
  run_one "pl_planner_off" off "${POLYLINE_BASE[@]}"
}

arm_tg_planner_pass() {
  run_one "tg_planner_pass" pass \
    --subgoal-source toward_g --r-m-intent 100
}

arm_tg_planner_h1() {
  run_one "tg_planner_h1" h1 \
    --subgoal-source toward_g --r-m-intent 100
}

arm_pl_planner_pass() {
  run_one "pl_planner_pass" pass "${POLYLINE_BASE[@]}"
}

arm_pl_planner_h1() {
  run_one "pl_planner_h1" h1 "${POLYLINE_BASE[@]}"
}

wm_isolation() {
  arm_tg_planner_pass
  arm_tg_planner_h1
  arm_pl_planner_pass
  arm_pl_planner_h1
  summary
}

summary() {
  "$PY" << PY
import json, statistics as st
from pathlib import Path

out = Path("${OUT_ROOT}")
tags = [
    "tg_planner_on", "tg_planner_off", "tg_planner_pass", "tg_planner_h1",
    "pl_planner_on", "pl_planner_off", "pl_planner_pass", "pl_planner_h1",
]
print(f"{'tag':18s} {'arr':5s} {'SPL':>6s} {'L_act':>7s} {'steps':>5s} {'IR':>6s} {'d_fin':>6s}")
rows = []
for tag in tags:
    p = out / f"{tag}.json"
    if not p.exists():
        print(f"{tag:18s} MISSING")
        continue
    e = json.load(open(p))["episodes"][0]
    rows.append((tag, e))
    print(f"{tag:18s} {str(e['arrived']):5s} {e['spl']:6.3f} {e['actual_length_m']:7.1f} {e['steps']:5d} {e['intervention_rate']:6.3f} {e['d_final_m']:6.2f}")

def delta(a, b, key):
    va = next((x[1][key] for x in rows if x[0] == a), None)
    vb = next((x[1][key] for x in rows if x[0] == b), None)
    if va is None or vb is None:
        return
    print(f"  Δ({a} - {b}) {key}: {va - vb:+.3f}")

print("\n--- Planner effect (H=5 on - off), same subgoal ---")
for pair in [("tg_planner_on", "tg_planner_off"), ("pl_planner_on", "pl_planner_off")]:
    if any(x[0] == pair[0] for x in rows) and any(x[0] == pair[1] for x in rows):
        print(pair[0].split("_")[0] + ":")
        delta(pair[0], pair[1], "spl")
        delta(pair[0], pair[1], "actual_length_m")

print("\n--- WM imagination depth (H=5 on - pass / H=1), same subgoal ---")
for base, variants in [
    ("tg", [("tg_planner_on", "H=5"), ("tg_planner_pass", "pass"), ("tg_planner_h1", "H=1")]),
    ("pl", [("pl_planner_on", "H=5"), ("pl_planner_pass", "pass"), ("pl_planner_h1", "H=1")]),
]:
    have = [(t, lab) for t, lab in variants if any(x[0] == t for x in rows)]
    if len(have) < 2:
        continue
    print(base + ":")
    for t, lab in have:
        e = next(x[1] for x in rows if x[0] == t)
        print(f"  {lab:5s} arr={e['arrived']} SPL={e['spl']:.3f} L={e['actual_length_m']:.1f} IR={e['intervention_rate']:.3f}")

print("\n--- Subgoal effect (polyline - toward_g), planner H=5 ---")
delta("pl_planner_on", "tg_planner_on", "spl")
delta("pl_planner_on", "tg_planner_on", "actual_length_m")
PY
}

CMD="${1:-all}"
case "$CMD" in
  all)
    arm_tg_planner_on
    arm_tg_planner_off
    arm_pl_planner_on
    arm_pl_planner_off
    wm_isolation
    ;;
  wm_isolation) wm_isolation ;;
  summary) summary ;;
  tg_planner_on)   arm_tg_planner_on ;;
  tg_planner_off)  arm_tg_planner_off ;;
  pl_planner_on)   arm_pl_planner_on ;;
  pl_planner_off)  arm_pl_planner_off ;;
  tg_planner_pass) arm_tg_planner_pass ;;
  tg_planner_h1)   arm_tg_planner_h1 ;;
  pl_planner_pass) arm_pl_planner_pass ;;
  pl_planner_h1)   arm_pl_planner_h1 ;;
  *)
    echo "Usage: $0 [all|wm_isolation|summary|tg_planner_on|...|pl_planner_h1]"
    exit 1
    ;;
esac
