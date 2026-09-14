#!/usr/bin/env bash
# Phase-3 P2 — offline fusion FT on H100 (run ON 125, syncs to H100 then trains).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_h100_from_125.sh 2>/dev/null || {
  H100_USER="${H100_USER:-a25689}"
  H100_HOST="${H100_HOST:-10.239.121.23}"
  H100_PORT="${H100_PORT:-31126}"
  H100_SSH_KEY="${H100_SSH_KEY:-$HOME/.ssh/id_ed25519_h100}"
  H100_REPO="${H100_REPO:-/home/a25689/aerial-wam-v2}"
}

STAMP="${STAMP:-$(date +%Y%m%d)}"
DATASET_REL="experiments/aerial/rl/artifacts/dataset_phase3_handover_seen"
WM_REL="experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828"
INIT_REL="experiments/aerial/rl/artifacts/v4_ac_ckpt_phase2_toward_g_20260905_112006/v4_ac_latest.pt"
CKPT_REL="experiments/aerial/rl/artifacts/v4_ac_ckpt_phase3_unified_${STAMP}"
LOG_REL="artifacts/train_phase3_unified_${STAMP}.log"
ITERS="${ITERS:-500}"

ssh_h100() {
  ssh -i "$H100_SSH_KEY" -o IdentitiesOnly=yes -o BatchMode=yes \
    -o StrictHostKeyChecking=accept-new -p "$H100_PORT" \
    "${H100_USER}@${H100_HOST}" "$@"
}

tar_push_h100() {
  local rel="$1"
  tar czf - -C "$ROOT" "$rel" | ssh_h100 "mkdir -p ${H100_REPO}/$(dirname "$rel") && tar xzf - -C ${H100_REPO}"
}

say() { echo "[phase3-train] $*"; }

say "=== verify 125 dataset ==="
N125=$(ls "$ROOT/$DATASET_REL"/episode_*.npz 2>/dev/null | wc -l | tr -d ' ')
say "125 npz=$N125 (expect 44)"
test "$N125" -ge 28

say "=== sync dataset -> H100 (if needed) ==="
N100=$(ssh_h100 "ls ${H100_REPO}/${DATASET_REL}/episode_*.npz 2>/dev/null | wc -l" | tr -d ' ')
if [ "${N100:-0}" -lt "$N125" ]; then
  say "H100 has $N100/$N125 — tar push"
  tar_push_h100 "$DATASET_REL"
else
  say "H100 already has $N100 npz"
fi

say "=== sync WM ckpt -> H100 (if needed) ==="
if ! ssh_h100 "test -f ${H100_REPO}/${WM_REL}/wm_step_3500.pt"; then
  tar_push_h100 "$WM_REL"
fi

say "=== sync phase3 config + code ==="
tar_push_h100 configs/aerial_rl_phase3_unified.yaml
tar_push_h100 experiments/aerial/phase3_unified
tar_push_h100 experiments/aerial/rl/scene_profile.py
tar_push_h100 experiments/aerial/rl/train_v4_ac.py
tar_push_h100 experiments/aerial/rl/train_rl.py
tar_push_h100 experiments/aerial/eval/run_closed_loop.py
tar_push_h100 experiments/aerial/scripts/train_phase3_unified.sh

say "=== H100 train (offline replay, warm-start phase2 toward_g) ==="
ssh_h100 "cd ${H100_REPO} && source experiments/aerial/scripts/env_h100.sh && \
  mkdir -p $(dirname ${CKPT_REL}) artifacts && \
  nohup \$AERIAL_PY -m experiments.aerial.rl.train_v4_ac \
    --config configs/aerial_rl_phase3_unified.yaml \
    --iters ${ITERS} --episodes-per-iter 0 --skip-collect \
    --imagine-batch 16 --imagine-horizon 15 \
    --device cuda --dynamics torch --backend mock \
    --wm-ckpt ${WM_REL}/wm_step_3500.pt \
    --dataset ${DATASET_REL} \
    --annotation experiments/aerial/phase3_unified/annotations/handover_seen_filtered.json \
    --init-actor-ckpt ${INIT_REL} \
    --w-collision 1.0 \
    --ckpt-dir ${CKPT_REL} \
    > ${LOG_REL} 2>&1 & echo TRAIN_PID=\$!"

say "log: ${H100_REPO}/${LOG_REL}"
say "ckpt: ${H100_REPO}/${CKPT_REL}/v4_ac_latest.pt"
say "monitor: ssh h100-23 'tail -f ${H100_REPO}/${LOG_REL}'"
