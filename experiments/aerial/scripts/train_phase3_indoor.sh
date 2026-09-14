#!/usr/bin/env bash
# P3-indoor — 125 collect (Building_99) → H100 offline FT → indoor eval.
#
# Outdoor Phase-2 ckpt is NOT modified. Post-train:
#   - indoor: eval_phase3_building99_indoor.py / eval_phase3_handover_decouple.sh
#   - outdoor sanity: eval_phase3_outdoor_regression_gate.sh <phase2_ckpt> only
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
CONFIG_REL="configs/aerial_rl_phase3_indoor.yaml"
ANN_REL="experiments/aerial/phase3_unified/annotations/phase3_indoor_seen.json"
DATASET_REL="experiments/aerial/rl/artifacts/dataset_phase3_indoor_seen"
WM_REL="experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828"
INIT_REL="${INIT_REL:-experiments/aerial/rl/artifacts/v4_ac_ckpt_phase2_toward_g_20260905_112006/v4_ac_latest.pt}"
CKPT_REL="experiments/aerial/rl/artifacts/v4_ac_ckpt_phase3_indoor_${STAMP}"
LOG_REL="artifacts/train_phase3_indoor_${STAMP}.log"
ITERS="${ITERS:-200}"
SKIP_COLLECT="${SKIP_COLLECT:-0}"
MIN_INDOOR_NPZ="${MIN_INDOOR_NPZ:-8}"

ssh_h100() {
  ssh -i "$H100_SSH_KEY" -o IdentitiesOnly=yes -o BatchMode=yes \
    -o StrictHostKeyChecking=accept-new -p "$H100_PORT" \
    "${H100_USER}@${H100_HOST}" "$@"
}

tar_push_h100() {
  local rel="$1"
  tar czf - -C "$ROOT" "$rel" | ssh_h100 "mkdir -p ${H100_REPO}/$(dirname "$rel") && tar xzf - -C ${H100_REPO}"
}

say() { echo "[p3-indoor] $*"; }

say "=== step 0: build indoor-only annotation (scene=indoor_micro) ==="
"${PYTHON_BIN:-python3}" -m experiments.aerial.scripts.build_phase3_indoor_annotation --out "$ANN_REL"

if [[ "$SKIP_COLLECT" != "1" ]]; then
  say "=== step 1: collect on 125 (Building_99 renderer) ==="
  bash experiments/aerial/scripts/collect_phase3_indoor.sh
fi

say "=== verify indoor dataset scene tags ==="
SUMMARY="$ROOT/$DATASET_REL/collection_summary.json"
if [[ ! -f "$SUMMARY" ]]; then
  say "ERROR missing $SUMMARY — run collect first"
  exit 1
fi
"${PYTHON_BIN:-python3}" - "$SUMMARY" <<'PY'
import json, sys
from pathlib import Path
root = Path(".")
summary = json.loads(Path(sys.argv[1]).read_text())
from experiments.aerial.phase3_unified.indoor_corpus import assert_indoor_collection_summary
assert_indoor_collection_summary(summary)
bad = [e for e in summary.get("episodes", []) if e.get("scene") != "indoor_micro" or e.get("map_id") != "building_99"]
if bad:
    raise SystemExit(f"non-indoor rows in collection_summary: {bad[:3]}")
print(f"collection_summary OK: {len(summary.get('episodes', []))} indoor episodes")
PY

N125=$(ls "$ROOT/$DATASET_REL"/episode_*.npz 2>/dev/null | wc -l | tr -d ' ')
say "125 indoor npz=$N125 (min $MIN_INDOOR_NPZ)"
test "$N125" -ge "$MIN_INDOOR_NPZ"

say "=== sync indoor dataset -> H100 ==="
tar_push_h100 "$DATASET_REL"

say "=== sync warm-start + WM -> H100 (if needed) ==="
if [[ -f "$INIT_REL" ]]; then
  tar_push_h100 "$(dirname "$INIT_REL")"
fi
if ! ssh_h100 "test -f ${H100_REPO}/${WM_REL}/wm_step_3500.pt"; then
  tar_push_h100 "$WM_REL"
fi

say "=== sync p3-indoor config + code ==="
tar_push_h100 "$CONFIG_REL"
tar_push_h100 "$ANN_REL"
tar_push_h100 experiments/aerial/phase3_unified
tar_push_h100 experiments/aerial/rl/scene_profile.py
tar_push_h100 experiments/aerial/rl/train_v4_ac.py
tar_push_h100 experiments/aerial/rl/train_rl.py
tar_push_h100 experiments/aerial/rl/corrector.py
tar_push_h100 experiments/aerial/rl/collector.py
tar_push_h100 experiments/aerial/rl/actor_critic.py
tar_push_h100 experiments/aerial/eval/run_closed_loop.py
tar_push_h100 experiments/aerial/scripts/build_phase3_indoor_annotation.py
tar_push_h100 experiments/aerial/scripts/collect_phase3_indoor.py
tar_push_h100 experiments/aerial/scripts/collect_phase3_indoor.sh
tar_push_h100 experiments/aerial/scripts/train_phase3_indoor.sh
tar_push_h100 experiments/aerial/scripts/eval_phase3_building99_indoor.py
tar_push_h100 experiments/aerial/scripts/eval_phase3_handover_decouple.py
tar_push_h100 experiments/aerial/scripts/eval_phase3_handover_decouple.sh

INIT_ARG=""
if [[ -f "$INIT_REL" ]]; then
  INIT_ARG="--init-actor-ckpt ${INIT_REL}"
fi

say "=== H100 indoor-only offline FT (iters=$ITERS, mock env) ==="
ssh_h100 "cd ${H100_REPO} && source experiments/aerial/scripts/env_h100.sh && \
  mkdir -p $(dirname ${CKPT_REL}) artifacts && \
  nohup \$AERIAL_PY -m experiments.aerial.rl.train_v4_ac \
    --config ${CONFIG_REL} \
    --iters ${ITERS} --episodes-per-iter 0 --skip-collect \
    --imagine-batch 16 --imagine-horizon 8 \
    --device cuda --dynamics torch --backend mock \
    --wm-ckpt ${WM_REL}/wm_step_3500.pt \
    --dataset ${DATASET_REL} \
    --annotation ${ANN_REL} \
    ${INIT_ARG} \
    --w-collision 1.0 \
    --ckpt-dir ${CKPT_REL} \
    > ${LOG_REL} 2>&1 & echo TRAIN_PID=\$!"

say "log: ${H100_REPO}/${LOG_REL}"
say "ckpt: ${H100_REPO}/${CKPT_REL}/v4_ac_latest.pt"
say "post-train indoor eval (125):"
say "  python experiments/aerial/scripts/eval_phase3_building99_indoor.py --actor-ckpt ${CKPT_REL}/v4_ac_latest.pt"
say "  bash experiments/aerial/scripts/eval_phase3_handover_decouple.sh \\"
say "    ${INIT_REL} ${CKPT_REL}/v4_ac_latest.pt"
say "outdoor sanity (Phase-2 only, NOT indoor ckpt):"
say "  bash experiments/aerial/scripts/eval_phase3_outdoor_regression_gate.sh ${INIT_REL}"
