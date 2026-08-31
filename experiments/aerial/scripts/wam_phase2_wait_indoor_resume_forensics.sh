#!/usr/bin/env bash
# Wait for Indoor AirSim jobs to finish, switch to outdoor env_airsim_16, run Phase-2 forensics.
# 125 only. Do not run while Phase-2 forensics is already active.
set -euo pipefail

ROOT="${AERIAL_REPO_ROOT:-/home/yao/aerial-wam-v2}"
INDOOR_ROOT="${AERIAL_INDOOR_ROOT:-/home/yao/aerial-indoor-wam}"
SCENE_SH="$INDOOR_ROOT/experiments/aerial/scripts/recover_renderer_scene.sh"
LOG="${1:-$ROOT/artifacts/wam_phase2_wait_indoor_resume_20260831.log}"
OUT_DIR="${2:-$ROOT/artifacts/videos/wam_phase2_pcoll_veto_forensics_20260831_outdoor}"
POLL_S="${POLL_S:-45}"

mkdir -p "$(dirname "$LOG")" "$(dirname "$OUT_DIR")"

log() { echo "[$(date -Iseconds)] $*" | tee -a "$LOG"; }

indoor_busy() {
  pgrep -f 'indoor_mainline_baseline_eval|indoor_building99_fixture_collect|building99_indoor' >/dev/null 2>&1
}

python_on_airsim() {
  ss -tnp 2>/dev/null | grep -E ':41451.*python|python.*:41451' >/dev/null 2>&1
}

phase2_forensics_running() {
  pgrep -f 'wam_phase2_traj_forensics\.py' >/dev/null 2>&1
}

outdoor_renderer_up() {
  pgrep -f 'env_airsim_16/LinuxNoEditor' >/dev/null 2>&1 \
    && ! pgrep -f 'Building_99/Binaries' >/dev/null 2>&1 \
    && ss -ltn 2>/dev/null | grep -q ':41451'
}

wait_indoor_clear() {
  log "waiting for Indoor collect/eval to finish (poll ${POLL_S}s)..."
  while indoor_busy; do
    pgrep -af 'indoor_mainline_baseline_eval|indoor_building99_fixture_collect' | head -3 | tee -a "$LOG" || true
    sleep "$POLL_S"
  done
  log "no indoor python jobs; waiting for :41451 python clients to drop..."
  local n=0
  while python_on_airsim; do
    ss -tnp 2>/dev/null | grep 41451 | tee -a "$LOG" || true
    sleep 15
    n=$((n + 1))
    if [ "$n" -ge 40 ]; then
      log "ERROR: python still on :41451 after indoor exit; abort"
      exit 1
    fi
  done
  sleep 5
}

switch_outdoor() {
  if [ ! -x "$SCENE_SH" ]; then
    log "ERROR: missing $SCENE_SH"
    exit 1
  fi
  log "switching renderer -> outdoor (env_airsim_16)..."
  bash "$SCENE_SH" outdoor >>"$LOG" 2>&1
  sleep 20
  if ! outdoor_renderer_up; then
    log "ERROR: outdoor renderer not up; tail airsim.log"
    tail -40 /home/yao/aerial_airsim_persistent/airsim.log >>"$LOG" 2>&1 || true
    exit 1
  fi
  log "outdoor renderer up on :41451"
}

run_forensics() {
  if phase2_forensics_running; then
    log "forensics already running; skip spawn"
    exit 0
  fi
  cd "$ROOT"
  # shellcheck disable=SC1091
  source experiments/aerial/scripts/env_4090.sh
  log "starting 16-route forensics -> $OUT_DIR"
  env PYTHONUNBUFFERED=1 "$PYTHON_BIN" experiments/aerial/scripts/wam_phase2_traj_forensics.py \
    --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt \
    --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_step_e_20260828/v4_ac_latest.pt \
    --goal-feat-mode meter \
    --annotation artifacts/seen_airsim16_long_routes.json \
    --cruise-speed 10.0 \
    --planner-horizon 5 \
    --max-steps 1000 \
    --out-dir "$OUT_DIR" \
    >>"$LOG" 2>&1
  log "forensics finished exit=$?"
}

main() {
  log "=== wait-indoor-resume-forensics ==="
  log "ROOT=$ROOT INDOOR=$INDOOR_ROOT OUT=$OUT_DIR"
  wait_indoor_clear
  switch_outdoor
  run_forensics
  log "=== done ==="
}

main "$@"
