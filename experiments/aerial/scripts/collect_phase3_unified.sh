#!/usr/bin/env bash
# P1 — collect mixed outdoor+indoor rollouts on 125 (RGB, scene-tagged).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"

CONFIG="${CONFIG:-configs/aerial_rl_phase3_unified.yaml}"
ANNOTATION="${ANNOTATION:-experiments/aerial/phase3_unified/annotations/mixed_seen.json}"
OUT="${OUT:-experiments/aerial/rl/artifacts/dataset_phase3_unified_seen}"
EPISODES="${EPISODES:-20}"
MAX_STEPS="${MAX_STEPS:-200}"
STEP_HZ="${STEP_HZ:-5.0}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-41451}"

if [[ ! -f "$ANNOTATION" ]]; then
  echo "annotation missing — building $ANNOTATION"
  python -m experiments.aerial.scripts.build_phase3_mixed_annotation --out "$ANNOTATION"
fi

echo "=== Phase-3 P1 collect ==="
echo "config=$CONFIG annotation=$ANNOTATION out=$OUT episodes=$EPISODES"

python -m experiments.aerial.rl.collect_dataset \
  --config "$CONFIG" \
  --annotation "$ANNOTATION" \
  --backend airsim \
  --host "$HOST" \
  --port "$PORT" \
  --episodes "$EPISODES" \
  --max-steps "$MAX_STEPS" \
  --step-hz "$STEP_HZ" \
  --out "$OUT"
