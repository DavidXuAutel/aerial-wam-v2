#!/usr/bin/env bash
# Dual-gate acceptance for Phase-3 unified navigation (outdoor + indoor, same ckpt).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"

ACTOR_CKPT="${1:-experiments/aerial/rl/artifacts/v4_ac_ckpt_phase2_toward_g_20260905_112006/v4_ac_latest.pt}"
WM_CKPT="${WM_CKPT:-experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt}"
OUT_DIR="${OUT_DIR:-artifacts/phase3_unified_eval_$(date +%Y%m%d)}"
mkdir -p "$OUT_DIR"

echo "=== Phase-3 unified eval ==="
echo "actor=$ACTOR_CKPT"
echo "out=$OUT_DIR"

echo "=== Outdoor gate (Phase-2 long eval) ==="
python experiments/aerial/scripts/wam_phase2_long_eval.py \
  --actor-ckpt "$ACTOR_CKPT" \
  --wm-ckpt "$WM_CKPT" \
  --subgoal-source toward_g \
  --cruise-speed 10 \
  --planner \
  --success-dist 3.0 \
  --out "$OUT_DIR/outdoor_long_eval.json"

echo "=== Indoor gate (mainline baseline · outdoor-route stub) ==="
python experiments/aerial/scripts/indoor_mainline_baseline_eval.py \
  --actor-ckpt "$ACTOR_CKPT" \
  --wm-ckpt "$WM_CKPT" \
  --success-dist 0.20 \
  --pose-source odom_from_imu_rgb \
  --assist none \
  --out "$OUT_DIR/indoor_mainline_eval.json"

echo "=== Indoor gate (Building_99 · gt_proxy) ==="
python experiments/aerial/scripts/eval_phase3_building99_indoor.py \
  --actor-ckpt "$ACTOR_CKPT" \
  --wm-ckpt "$WM_CKPT" \
  --pose-source gt_proxy \
  --scene-script "${SCENE_SCRIPT:-$HOME/aerial-indoor-wam/experiments/aerial/scripts/recover_renderer_scene.sh}" \
  --out "$OUT_DIR/building99_indoor_eval.json"

echo "=== Done ==="
echo "Outdoor:   $OUT_DIR/outdoor_long_eval.json"
echo "Indoor:    $OUT_DIR/indoor_mainline_eval.json"
echo "Building99: $OUT_DIR/building99_indoor_eval.json"
