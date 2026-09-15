#!/usr/bin/env bash
# Resume P2c online FT from iter 20 (125 background entry).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh

export START_ITER="${START_ITER:-20}"
export RESUME_CKPT="${RESUME_CKPT:-experiments/aerial/rl/artifacts/v4_ac_ckpt_phase3_unified_p2c_20260913/v4_ac_latest.pt}"
export STAMP="${STAMP:-20260913}"
LOG="artifacts/train_phase3_unified_p2c_${STAMP}_resume.log"

exec >>"$LOG" 2>&1
echo "[$(date -Iseconds)] === p2c resume start iter=$START_ITER ==="
bash experiments/aerial/scripts/train_phase3_unified_p2c.sh
echo "[$(date -Iseconds)] === p2c resume done ==="
