#!/usr/bin/env bash
# P3-indoor collect — Building_99 renderer only; all episodes indoor_micro.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh 2>/dev/null || true

CONFIG="${CONFIG:-configs/aerial_rl_phase3_indoor.yaml}"
# Do not inherit env_4090 ANNOTATION (outdoor routes) — indoor collect is fixed corpus.
INDOOR_ANNOTATION="experiments/aerial/phase3_unified/annotations/phase3_indoor_seen.json"
ANNOTATION="${INDOOR_ANNOTATION}"
OUT="${OUT:-experiments/aerial/rl/artifacts/dataset_phase3_indoor_seen}"
EPISODES="${EPISODES:-0}"
MAX_STEPS="${MAX_STEPS:-60}"
STEP_HZ="${STEP_HZ:-5.0}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-41451}"

if [[ ! -f "$ANNOTATION" ]]; then
  echo "[p3-indoor] building indoor annotation -> $ANNOTATION"
  "${PYTHON_BIN:-python3}" -m experiments.aerial.scripts.build_phase3_indoor_annotation --out "$ANNOTATION"
fi

echo "=== P3-indoor collect (building99 only) ==="
echo "config=$CONFIG"
echo "annotation=$ANNOTATION"
echo "out=$OUT episodes=${EPISODES:-all}"

"${PYTHON_BIN:-python3}" experiments/aerial/scripts/collect_phase3_indoor.py \
  --config "$CONFIG" \
  --annotation "$ANNOTATION" \
  --out "$OUT" \
  --episodes "$EPISODES" \
  --max-steps "$MAX_STEPS" \
  --step-hz "$STEP_HZ" \
  --host "$HOST" \
  --port "$PORT"
