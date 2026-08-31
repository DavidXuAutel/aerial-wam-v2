#!/usr/bin/env bash
# PathExpert densify: OpenFly polylines → dense 5 Hz RGB+Δa NPZ on 125.
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/aerial-wam-v2")"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
export PYTHONUNBUFFERED=1
STAMP="${STAMP:-20260827}"
N="${N:-32}"
ANN="${ANN:-artifacts/seen_airsim16_m1a20.json}"
OUT="experiments/aerial/rl/artifacts/dataset_v0_path_expert_openfly_${STAMP}"
LOG="logs/v4_path_expert_collect_${STAMP}.log"
mkdir -p logs

exec > >(tee -a "$LOG") 2>&1
echo "[path-expert] $(date -Is) start N=${N} ann=${ANN} out=${OUT}"

"$AERIAL_PY" -m experiments.aerial.rl.collect_path_expert_dataset \
  --backend airsim \
  --host 127.0.0.1 \
  --step-hz 5.0 \
  --grab-depth \
  --episodes "$N" \
  --max-steps 400 \
  --annotation "$ANN" \
  --out "$OUT"

echo "[path-expert] $(date -Is) DONE"
echo "AGENT_CHAIN_DONE_PATH_EXPERT {\"out\":\"${OUT}\",\"stamp\":\"${STAMP}\"}"
