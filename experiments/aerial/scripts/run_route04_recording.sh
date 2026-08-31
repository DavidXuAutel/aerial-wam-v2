#!/usr/bin/env bash
set -e
source /home/yao/aerial-wam-v2/experiments/aerial/scripts/env_4090.sh

echo "[Fri Aug 28 14:32:36 CST 2026] Waiting for any existing evaluations to finish..."
while pgrep -f "wam_step_g_accept_eval" > /dev/null; do
    sleep 3
done

echo "[Fri Aug 28 14:32:36 CST 2026] Starting Route 04 Video Generation..."
$AERIAL_PY /home/yao/aerial-wam-v2/experiments/aerial/scripts/v4_record_route04_videos.py     --route-idx 3     --max-steps 250     --fps 10.0     --step-hz 5.0     --out-dir artifacts/videos/route04

echo "[Fri Aug 28 14:32:36 CST 2026] Route 04 videos successfully generated!"
