#!/usr/bin/env bash
# P2b outdoor regression gate — run on 125 after H100 FT.
#
# Compares candidate ckpt outdoor long eval vs Phase-2 baseline JSON.
# PASS if arrivals >= min_arrivals (default 11/16 = baseline 81.2% - 10pp).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh

ACTOR_CKPT="${1:?usage: $0 <actor_ckpt> [baseline_json]}"
BASELINE_JSON="${2:-artifacts/phase3_unified_eval_20260911/outdoor_long_eval_phase2_baseline.json}"
WM_CKPT="${WM_CKPT:-experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt}"
OUT_DIR="${OUT_DIR:-artifacts/phase3_unified_eval_$(date +%Y%m%d)}"
CANDIDATE_JSON="${OUT_DIR}/outdoor_long_eval_p2b_candidate.json"
MIN_ARRIVALS="${MIN_ARRIVALS:-11}"
MIN_RATE="${MIN_RATE:-0.7125}"

mkdir -p "$OUT_DIR"

if [[ ! -f "$BASELINE_JSON" ]]; then
  echo "[gate] ERROR missing baseline: $BASELINE_JSON" >&2
  exit 1
fi

echo "=== P2b outdoor regression gate ==="
echo "candidate=$ACTOR_CKPT"
echo "baseline=$BASELINE_JSON"
echo "out=$CANDIDATE_JSON"

"${PYTHON_BIN:-python3}" experiments/aerial/scripts/wam_phase2_long_eval.py \
  --actor-ckpt "$ACTOR_CKPT" \
  --wm-ckpt "$WM_CKPT" \
  --subgoal-source toward_g \
  --cruise-speed 10 \
  --planner \
  --success-dist 3.0 \
  --out "$CANDIDATE_JSON"

python3 - <<PY
import json, sys
from pathlib import Path

baseline = json.loads(Path("$BASELINE_JSON").read_text())
candidate = json.loads(Path("$CANDIDATE_JSON").read_text())
b_eps = baseline["episodes"]
c_eps = candidate["episodes"]
b_arr = sum(1 for e in b_eps if e.get("arrived"))
c_arr = sum(1 for e in c_eps if e.get("arrived"))
n = len(c_eps)
b_rate = b_arr / max(len(b_eps), 1)
c_rate = c_arr / max(n, 1)
min_arr = int("$MIN_ARRIVALS")
min_rate = float("$MIN_RATE")
delta = b_rate - c_rate

print("=== regression gate ===")
print(f"baseline:  {b_arr}/{len(b_eps)} ({b_rate:.1%})")
print(f"candidate: {c_arr}/{n} ({c_rate:.1%})")
print(f"delta:     {delta:+.1%} (positive = regression)")
print(f"threshold: >={min_arr}/{n} arrivals ({min_rate:.1%})")

ok = c_arr >= min_arr and c_rate >= min_rate
verdict = "PASS" if ok else "FAIL"
print(f"verdict:   {verdict}")
Path("$OUT_DIR/regression_gate_p2b.json").write_text(
    json.dumps(
        {
            "verdict": verdict,
            "baseline_json": "$BASELINE_JSON",
            "candidate_json": "$CANDIDATE_JSON",
            "baseline_arrivals": b_arr,
            "candidate_arrivals": c_arr,
            "n_routes": n,
            "baseline_rate": round(b_rate, 4),
            "candidate_rate": round(c_rate, 4),
            "delta_rate": round(delta, 4),
            "min_arrivals": min_arr,
            "min_rate": min_rate,
        },
        indent=2,
    ),
    encoding="utf-8",
)
sys.exit(0 if ok else 2)
PY
