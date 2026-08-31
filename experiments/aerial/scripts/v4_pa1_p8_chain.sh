#!/usr/bin/env bash
# P-A1 DONE → H100 P8 train → 125 pp8 accept (declare tz-p8-train-20260827).
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/aerial-wam-v2")"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_h100_from_125.sh

STAMP=20260827
LOG="logs/v4_pa1_p8_chain_${STAMP}.log"
BATCH_PID="${BATCH_PID:-1798430}"
declare -a ARTIFACTS=(
  "v4_p7_attr_tz_l3_3d_n32_${STAMP}.json"
  "v4_p7_attr_tz_p0bfix_h1_n32_${STAMP}.json"
  "v4_p7_attr_tz_l3brake_h1_n32_${STAMP}.json"
)

mkdir -p logs artifacts

exec > >(tee -a "$LOG") 2>&1
say() { echo "[pa1-p8] $(date '+%Y-%m-%dT%H:%M:%S%z') $*"; }

ssh_h100() {
  ssh -i "$H100_SSH_KEY" -o IdentitiesOnly=yes -o BatchMode=yes \
    -o StrictHostKeyChecking=accept-new -p "$H100_PORT" \
    "${H100_USER}@${H100_HOST}" "$@"
}

rsync_h100() {
  rsync -az -e "ssh -i $H100_SSH_KEY -o IdentitiesOnly=yes -p $H100_PORT" "$@"
}

scp_h100() {
  scp -i "$H100_SSH_KEY" -o IdentitiesOnly=yes -P "$H100_PORT" "$@"
}

tar_push_h100() {
  local rel="$1"
  tar czf - -C "$ROOT" "$rel" | ssh_h100 "mkdir -p ${H100_REPO}/$(dirname "$rel") && tar xzf - -C ${H100_REPO}"
}

say "=== WAIT P-A1 (batch PID ${BATCH_PID}) ==="
if [[ "${SKIP_PA1_WAIT:-0}" == "1" ]]; then
  say "SKIP_PA1_WAIT=1 — assuming P-A1 artifacts present"
else
while ps -p "$BATCH_PID" >/dev/null 2>&1; do
  ep=$(grep -oE 'ep[0-9]+:' logs/v4_p7_attr_tz_l3_3d_n32_${STAMP}.log 2>/dev/null | tail -1 || true)
  say "batch running ... ${ep:-scanning}"
  sleep 120
done
fi

for a in "${ARTIFACTS[@]}"; do
  if [[ ! -f "artifacts/${a}" ]]; then
    say "ERROR: missing artifacts/${a} after batch exit"
    exit 1
  fi
done
say "P-A1 DONE: 3/3 ATTR JSON on disk"

say "=== P-A1 SUMMARY ==="
"$AERIAL_PY" - <<'PY'
import json
from pathlib import Path
for name in [
    "v4_p7_attr_tz_l3_3d_n32_20260827.json",
    "v4_p7_attr_tz_p0bfix_h1_n32_20260827.json",
    "v4_p7_attr_tz_l3brake_h1_n32_20260827.json",
]:
    p = Path("artifacts") / name
    d = json.loads(p.read_text())
    fork = (d.get("fork") or {})
    print(
        f"{name}: arrival={d.get('arrival_rate')} hard_coll={d.get('hard_coll_rate')} "
        f"fork={fork.get('label')} n_scored={d.get('n_scored')}"
    )
PY

say "=== RSYNC code → H100 (tar+ssh; H100 has no rsync) ==="
tar_push_h100 experiments/aerial/rl
tar_push_h100 configs
ssh_h100 "mkdir -p ${H100_REPO}/experiments/aerial/scripts"
scp_h100 \
  experiments/aerial/scripts/v4_p7_diag.py \
  experiments/aerial/scripts/v4_pp8_pair_gate.py \
  "${H100_USER}@${H100_HOST}:${H100_REPO}/experiments/aerial/scripts/"

WM_REL="experiments/aerial/rl/artifacts/wm_ckpt_p45_merged_20260821/wm_step_500.pt"
if ! ssh_h100 "test -f ${H100_REPO}/${WM_REL}"; then
  say "WM ckpt missing on H100 — scp (~1.1GB)"
  ssh_h100 "mkdir -p ${H100_REPO}/experiments/aerial/rl/artifacts/wm_ckpt_p45_merged_20260821"
  scp_h100 "$WM_REL" "${H100_USER}@${H100_HOST}:${H100_REPO}/${WM_REL}"
fi

say "=== H100 P8 TRAIN (300 iter) ==="
TRAIN_LOG="logs/v4_p8_train_tz_pp8_${STAMP}.log"
ssh_h100 "cd ${H100_REPO} && source experiments/aerial/scripts/env_h100.sh && \
  export PYTHONUNBUFFERED=1 && \
  \$AERIAL_PY -m experiments.aerial.rl.train_v4_ac \
    --iters 300 --episodes-per-iter 0 --skip-collect \
    --imagine-batch 16 --imagine-horizon 15 \
    --device cuda --dynamics torch --backend mock \
    --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_p45_merged_20260821/wm_step_500.pt \
    --dataset experiments/aerial/rl/artifacts/dataset_v0_p45_merged_20260821 \
    --ckpt-dir experiments/aerial/rl/artifacts/v4_ac_ckpt_tz_pp8_20260827 \
  " 2>&1 | tee "$TRAIN_LOG"

CKPT_REL="experiments/aerial/rl/artifacts/v4_ac_ckpt_tz_pp8_20260827/v4_ac_latest.pt"
if ! ssh_h100 "test -f ${H100_REPO}/${CKPT_REL}"; then
  say "ERROR: H100 train did not write ${CKPT_REL}"
  exit 1
fi

say "=== FETCH ckpt → 125 ==="
mkdir -p "$(dirname "$CKPT_REL")"
scp_h100 "${H100_USER}@${H100_HOST}:${H100_REPO}/${CKPT_REL}" "${CKPT_REL}"

say "=== PP8 heuristic baseline (seed 6700) ==="
export PYTHONUNBUFFERED=1
"$AERIAL_PY" experiments/aerial/scripts/v4_p7_diag.py \
  --env-host 127.0.0.1 \
  --target-n 16 --spare-count 16 --reset-retries 2 \
  --seed 0 --diag-seed 6700 --accept-seed 7700 \
  --stamp "${STAMP}_pp8_base" \
  --depth-ckpt experiments/aerial/rl/artifacts/depth_ckpt_p45mid_s8j_20260825/depth_best_holdout_da3_ft_head.pt \
  --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_p45_merged_20260821/wm_step_500.pt \
  --out artifacts/v4_p7_heuristic_baseline_pp8_n16_${STAMP}.json \
  2>&1 | tee logs/v4_p7_heuristic_baseline_pp8_n16_${STAMP}.log

say "=== PP8 actor accept (seed 6700) ==="
"$AERIAL_PY" experiments/aerial/scripts/v4_p7_diag.py \
  --env-host 127.0.0.1 \
  --target-n 16 --spare-count 16 --reset-retries 2 \
  --seed 0 --diag-seed 6700 --accept-seed 7700 \
  --stamp "${STAMP}_pp8_actor" \
  --actor-ckpt "${CKPT_REL}" \
  --depth-ckpt experiments/aerial/rl/artifacts/depth_ckpt_p45mid_s8j_20260825/depth_best_holdout_da3_ft_head.pt \
  --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_p45_merged_20260821/wm_step_500.pt \
  --out artifacts/v4_p7_accept_pp8_n16_${STAMP}.json \
  2>&1 | tee logs/v4_p7_accept_pp8_n16_${STAMP}.log

say "=== Post-P8 pair gate ==="
"$AERIAL_PY" experiments/aerial/scripts/v4_pp8_pair_gate.py \
  --baseline artifacts/v4_p7_heuristic_baseline_pp8_n16_${STAMP}.json \
  --actor artifacts/v4_p7_accept_pp8_n16_${STAMP}.json \
  --out artifacts/v4_pp8_pair_gate_${STAMP}.json \
  | tee logs/v4_pp8_pair_gate_${STAMP}.log

say "=== CHAIN_DONE ==="
echo "AGENT_CHAIN_DONE_PA1_P8 {\"stamp\":\"${STAMP}\"}"
