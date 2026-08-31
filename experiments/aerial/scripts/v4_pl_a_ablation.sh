#!/usr/bin/env bash
# PL-A ablation: A0 no-planner → A1 --planner, same seed 6800.
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/aerial-wam-v2")"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
export PYTHONUNBUFFERED=1
STAMP=20260827
SEED=6800
ACCEPT=7800
LOG=logs/v4_pl_a_ablation_${STAMP}.log
mkdir -p logs artifacts

exec > >(tee -a "$LOG") 2>&1
say() { echo "[pl-a] $(date '+%Y-%m-%dT%H:%M:%S%z') $*"; }

DEPTH=experiments/aerial/rl/artifacts/depth_ckpt_p45mid_s8j_20260825/depth_best_holdout_da3_ft_head.pt
WM=experiments/aerial/rl/artifacts/wm_ckpt_p45_merged_20260821/wm_step_500.pt

say "=== A0 no-planner seed=${SEED} ==="
"$AERIAL_PY" experiments/aerial/scripts/v4_p7_diag.py \
  --env-host 127.0.0.1 \
  --target-n 16 --spare-count 16 --reset-retries 2 \
  --seed 0 --diag-seed "$SEED" --accept-seed "$ACCEPT" \
  --stamp "${STAMP}_nopl" \
  --depth-ckpt "$DEPTH" --wm-ckpt "$WM" \
  --out "artifacts/v4_p7_diag_nopl_n16_${STAMP}.json"

say "=== A1 with --planner seed=${SEED} ==="
"$AERIAL_PY" experiments/aerial/scripts/v4_p7_diag.py \
  --env-host 127.0.0.1 \
  --planner \
  --target-n 16 --spare-count 16 --reset-retries 2 \
  --seed 0 --diag-seed "$SEED" --accept-seed "$ACCEPT" \
  --stamp "${STAMP}_withpl" \
  --depth-ckpt "$DEPTH" --wm-ckpt "$WM" \
  --out "artifacts/v4_p7_diag_withpl_n16_${STAMP}.json"

say "=== SUMMARY ==="
"$AERIAL_PY" - <<'PY'
import json
from pathlib import Path
for name in [
    "v4_p7_diag_nopl_n16_20260827.json",
    "v4_p7_diag_withpl_n16_20260827.json",
]:
    d = json.loads((Path("artifacts") / name).read_text())
    print(
        name,
        "planner=", d.get("planner_enabled"),
        "arrival=", d.get("arrival_rate"),
        "hard_coll=", d.get("hard_coll_rate"),
        "n=", d.get("n_scored"),
        "auth=", d.get("authoritative"),
    )
PY
say "=== PL_A_ABLATION_DONE ==="
echo 'AGENT_CHAIN_DONE_PL_A {"stamp":"20260827"}'
