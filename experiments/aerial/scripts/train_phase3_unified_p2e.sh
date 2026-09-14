#!/usr/bin/env bash
# Phase-3 P2e — Phase-2 expert close-tail micro-FT (125 collect → H100 train).
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
CONFIG_REL="configs/aerial_rl_phase3_unified_p2e.yaml"
EXPERT_REL="experiments/aerial/rl/artifacts/dataset_phase3_p2e_phase2_expert"
DATASET_REL="experiments/aerial/rl/artifacts/dataset_phase3_p2e_close_tail"
WM_REL="experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828"
INIT_REL="${INIT_REL:-experiments/aerial/rl/artifacts/v4_ac_ckpt_phase2_toward_g_20260905_112006/v4_ac_latest.pt}"
CKPT_REL="experiments/aerial/rl/artifacts/v4_ac_ckpt_phase3_unified_p2e_${STAMP}"
LOG_REL="artifacts/train_phase3_unified_p2e_${STAMP}.log"
ITERS="${ITERS:-80}"
TAIL_REPEAT="${TAIL_REPEAT:-4}"
SKIP_COLLECT="${SKIP_COLLECT:-0}"

ssh_h100() {
  ssh -i "$H100_SSH_KEY" -o IdentitiesOnly=yes -o BatchMode=yes \
    -o StrictHostKeyChecking=accept-new -p "$H100_PORT" \
    "${H100_USER}@${H100_HOST}" "$@"
}

tar_push_h100() {
  local rel="$1"
  tar czf - -C "$ROOT" "$rel" | ssh_h100 "mkdir -p ${H100_REPO}/$(dirname "$rel") && tar xzf - -C ${H100_REPO}"
}

say() { echo "[phase3-p2e] $*"; }

if [[ ! -f "$INIT_REL" ]]; then
  say "ERROR missing warm-start ckpt: $INIT_REL"
  exit 1
fi

if [[ "$SKIP_COLLECT" != "1" ]]; then
  say "=== step 1: collect Phase-2 expert rollouts (125) ==="
  "${PYTHON_BIN:-python3}" -m experiments.aerial.scripts.build_phase3_outdoor_long_only_annotation
  "${PYTHON_BIN:-python3}" -m experiments.aerial.scripts.collect_phase3_p2e_phase2_expert \
    --actor-ckpt "$INIT_REL" \
    --out "$EXPERT_REL"
fi

say "=== step 2: build close-tail replay (3–18m, repeat×${TAIL_REPEAT}) ==="
python3 -m experiments.aerial.scripts.build_phase3_p2e_close_tail_dataset \
  --src "$EXPERT_REL" \
  --out "$DATASET_REL" \
  --repeat "$TAIL_REPEAT"

N_P2E=$(find "$ROOT/$DATASET_REL" -maxdepth 1 -name 'episode_*.npz' 2>/dev/null | wc -l | tr -d ' ')
say "p2e close-tail episodes=$N_P2E"
test "$N_P2E" -ge 16

say "=== sync close-tail dataset -> H100 ==="
tar_push_h100 "$DATASET_REL"

say "=== sync Phase-2 warm-start ckpt -> H100 ==="
tar_push_h100 "$(dirname "$INIT_REL")"

say "=== sync WM ckpt -> H100 (if needed) ==="
if ! ssh_h100 "test -f ${H100_REPO}/${WM_REL}/wm_step_3500.pt"; then
  tar_push_h100 "$WM_REL"
fi

say "=== sync p2e config + code ==="
tar_push_h100 "$CONFIG_REL"
tar_push_h100 experiments/aerial/phase3_unified
tar_push_h100 experiments/aerial/rl/scene_profile.py
tar_push_h100 experiments/aerial/rl/train_v4_ac.py
tar_push_h100 experiments/aerial/rl/train_rl.py
tar_push_h100 experiments/aerial/rl/corrector.py
tar_push_h100 experiments/aerial/rl/collector.py
tar_push_h100 experiments/aerial/rl/dynamics_torch.py
tar_push_h100 experiments/aerial/rl/actor_critic.py
tar_push_h100 experiments/aerial/eval/run_closed_loop.py
tar_push_h100 experiments/aerial/scripts/build_phase3_p2e_close_tail_dataset.py
tar_push_h100 experiments/aerial/scripts/collect_phase3_p2e_phase2_expert.py
tar_push_h100 experiments/aerial/scripts/wam_phase2_long_eval.py
tar_push_h100 experiments/aerial/scripts/train_phase3_unified_p2e.sh
tar_push_h100 experiments/aerial/scripts/eval_phase3_outdoor_regression_gate.sh

say "=== H100 micro-FT (offline, warm-start Phase-2, iters=$ITERS) ==="
ssh_h100 "cd ${H100_REPO} && source experiments/aerial/scripts/env_h100.sh && \
  mkdir -p $(dirname ${CKPT_REL}) artifacts && \
  nohup \$AERIAL_PY -m experiments.aerial.rl.train_v4_ac \
    --config ${CONFIG_REL} \
    --iters ${ITERS} --episodes-per-iter 0 --skip-collect \
    --imagine-batch 8 --imagine-horizon 8 \
    --device cuda --dynamics torch --backend mock \
    --wm-ckpt ${WM_REL}/wm_step_3500.pt \
    --dataset ${DATASET_REL} \
    --annotation experiments/aerial/phase3_unified/annotations/outdoor_long_only.json \
    --init-actor-ckpt ${INIT_REL} \
    --w-collision 1.0 \
    --ckpt-dir ${CKPT_REL} \
    > ${LOG_REL} 2>&1 & echo TRAIN_PID=\$!"

say "log: ${H100_REPO}/${LOG_REL}"
say "ckpt: ${H100_REPO}/${CKPT_REL}/v4_ac_latest.pt"
say "post-train gate (125): OUT_DIR=artifacts/phase3_unified_eval_${STAMP} bash experiments/aerial/scripts/eval_phase3_outdoor_regression_gate.sh ${CKPT_REL}/v4_ac_latest.pt"
