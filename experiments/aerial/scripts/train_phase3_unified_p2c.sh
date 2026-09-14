#!/usr/bin/env bash
# Phase-3 P2c — outdoor online close-loop FT on 125 (AirSim + 4090).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh

STAMP="${STAMP:-$(date +%Y%m%d)}"
CONFIG_REL="configs/aerial_rl_phase3_unified_p2c.yaml"
ANNO_REL="experiments/aerial/phase3_unified/annotations/outdoor_long_only.json"
WM_REL="experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828"
INIT_REL="experiments/aerial/rl/artifacts/v4_ac_ckpt_phase2_toward_g_20260905_112006/v4_ac_latest.pt"
CKPT_REL="experiments/aerial/rl/artifacts/v4_ac_ckpt_phase3_unified_p2c_${STAMP}"
LOG_REL="artifacts/train_phase3_unified_p2c_${STAMP}.log"
SCENE_SH="${SCENE_SCRIPT:-$HOME/aerial-indoor-wam/experiments/aerial/scripts/recover_renderer_scene.sh}"

ITERS="${ITERS:-48}"
START_ITER="${START_ITER:-0}"
EP_PER_ITER="${EP_PER_ITER:-1}"
NEAR_FRAC="${NEAR_FRAC:-0.5}"
NEAR_MIN="${NEAR_MIN:-5.0}"
NEAR_MAX="${NEAR_MAX:-20.0}"
RESUME_CKPT="${RESUME_CKPT:-}"
RENDERER_RESTART_EVERY="${RENDERER_RESTART_EVERY:-10}"

say() { echo "[phase3-p2c] $*"; }

if [[ -n "$RESUME_CKPT" ]]; then
  INIT_REL="$RESUME_CKPT"
  say "resume warm-start: $INIT_REL (start_iter=$START_ITER)"
elif [[ -f "${CKPT_REL}/v4_ac_latest.pt" && "${START_ITER:-0}" -gt 0 ]]; then
  INIT_REL="${CKPT_REL}/v4_ac_latest.pt"
  say "resume from existing ckpt: $INIT_REL (start_iter=$START_ITER)"
fi

say "=== build outdoor_long_only annotation ==="
python3 -m experiments.aerial.scripts.build_phase3_outdoor_long_only_annotation \
  --out "$ANNO_REL"

say "=== switch renderer -> outdoor ==="
if [[ -x "$SCENE_SH" ]]; then
  bash "$SCENE_SH" outdoor
  sleep 30
else
  say "WARN: missing $SCENE_SH — assuming outdoor already up"
fi

for i in $(seq 1 36); do
  if python3 -c "import socket;socket.create_connection(('127.0.0.1',41451),3).close()" 2>/dev/null; then
    say "airsim port open (try $i)"
    break
  fi
  sleep 5
done

if ! python3 -c "import socket;socket.create_connection(('127.0.0.1',41451),3).close()" 2>/dev/null; then
  say "ERROR: AirSim :41451 not reachable"
  exit 1
fi

pkill -f "train_v4_ac.*phase3_unified_p2c" 2>/dev/null || true
sleep 2

say "=== online train (phase2 loop, near-goal frac=$NEAR_FRAC, iters=$ITERS start=$START_ITER restart_every=$RENDERER_RESTART_EVERY) ==="
mkdir -p "$(dirname "$CKPT_REL")" artifacts

nohup env PYTHONUNBUFFERED=1 "$PYTHON_BIN" -m experiments.aerial.rl.train_v4_ac \
  --config "$CONFIG_REL" \
  --backend airsim \
  --device cuda \
  --dynamics torch \
  --phase2 \
  --wm-ckpt "${WM_REL}/wm_step_3500.pt" \
  --annotation "$ANNO_REL" \
  --init-actor-ckpt "$INIT_REL" \
  --iters "$ITERS" \
  --start-iter "$START_ITER" \
  --save-every-iter \
  --episodes-per-iter "$EP_PER_ITER" \
  --imagine-batch 16 \
  --imagine-horizon 15 \
  --near-goal-frac "$NEAR_FRAC" \
  --near-goal-dist-min "$NEAR_MIN" \
  --near-goal-dist-max "$NEAR_MAX" \
  --renderer-restart-every "$RENDERER_RESTART_EVERY" \
  --renderer-restart-script "$SCENE_SH" \
  --renderer-restart-scene outdoor \
  --w-collision 1.0 \
  --ckpt-dir "$CKPT_REL" \
  > "$LOG_REL" 2>&1 &

echo "TRAIN_PID=$!"
say "log: $ROOT/$LOG_REL"
say "ckpt: $ROOT/$CKPT_REL/v4_ac_latest.pt"
say "post-train: bash experiments/aerial/scripts/eval_phase3_outdoor_regression_gate.sh $CKPT_REL/v4_ac_latest.pt"
