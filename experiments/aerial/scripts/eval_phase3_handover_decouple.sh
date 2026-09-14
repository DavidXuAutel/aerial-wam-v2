#!/usr/bin/env bash
# Phase-3 decouple handover eval: oracle router + dual ckpt.
#
# Usage (125 with AirSim):
#   bash experiments/aerial/scripts/eval_phase3_handover_decouple.sh
#   bash experiments/aerial/scripts/eval_phase3_handover_decouple.sh <outdoor_ckpt> [indoor_ckpt]
#
# Dry-run (manifest only, no sim):
#   DRY_RUN=1 bash experiments/aerial/scripts/eval_phase3_handover_decouple.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh 2>/dev/null || true

OUTDOOR_CKPT="${1:-experiments/aerial/rl/artifacts/v4_ac_ckpt_phase2_toward_g_20260905_112006/v4_ac_latest.pt}"
INDOOR_CKPT="${2:-}"
WM_CKPT="${WM_CKPT:-experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt}"
OUT_DIR="${OUT_DIR:-artifacts/phase3_unified_eval_decouple_$(date +%Y%m%d)}"
SEGMENTS="${SEGMENTS:-outdoor_approach,indoor_micro}"
RUN_OUTDOOR_GATE="${RUN_OUTDOOR_GATE:-0}"

EXTRA=()
if [[ "${DRY_RUN:-0}" == "1" ]]; then
  EXTRA+=(--dry-run)
fi
if [[ "$RUN_OUTDOOR_GATE" == "1" ]]; then
  EXTRA+=(--run-outdoor-long-gate)
fi

INDOOR_ARG=()
if [[ -n "$INDOOR_CKPT" ]]; then
  INDOOR_ARG=(--indoor-ckpt "$INDOOR_CKPT")
fi

echo "=== Phase-3 decouple handover eval ==="
echo "outdoor_ckpt=$OUTDOOR_CKPT"
echo "indoor_ckpt=${INDOOR_CKPT:-<same as outdoor>}"
echo "out_dir=$OUT_DIR"
echo "segments=$SEGMENTS"

"${PYTHON_BIN:-python3}" experiments/aerial/scripts/eval_phase3_handover_decouple.py \
  --outdoor-ckpt "$OUTDOOR_CKPT" \
  "${INDOOR_ARG[@]}" \
  --wm-ckpt "$WM_CKPT" \
  --out-dir "$OUT_DIR" \
  --segments "$SEGMENTS" \
  "${EXTRA[@]}"
