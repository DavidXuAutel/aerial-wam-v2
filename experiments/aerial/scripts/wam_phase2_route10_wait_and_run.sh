#!/usr/bin/env bash
# Wait for 125 to be idle, then run Route-10 efficiency ablation (all arms).
# Run ON 125 (or via: ssh cursor-125-public 'bash -s' < this_file)
set -euo pipefail

ROOT="${AERIAL_REPO_ROOT:-/home/yao/aerial-wam-v2}"
LOG="${1:-$ROOT/artifacts/wam_phase2_route10_efficiency_wait_$(date +%Y%m%d_%H%M%S).log}"
POLL_S="${POLL_S:-45}"

mkdir -p "$(dirname "$LOG")"

log() { echo "[$(date -Iseconds)] $*" | tee -a "$LOG"; }

eval_busy() {
  pgrep -f \
    'wam_phase2_long_eval\.py|wam_phase2_traj_forensics\.py|wam_phase2_record_route\.py|wam_phase2_live_dual_view|indoor_mainline_baseline_eval|indoor_building99_fixture_collect|building99_indoor|collect_phase3|train_v4_ac|train_rl' \
    >/dev/null 2>&1
}

python_on_airsim() {
  ss -tnp 2>/dev/null | grep -E ':41451.*python|python.*:41451' >/dev/null 2>&1
}

route10_ablation_running() {
  pgrep -f 'wam_phase2_route10_efficiency_plan\.sh' >/dev/null 2>&1
}

outdoor_renderer_up() {
  pgrep -f 'env_airsim_16/LinuxNoEditor' >/dev/null 2>&1 \
    && ! pgrep -f 'Building_99/Binaries' >/dev/null 2>&1 \
    && ss -ltn 2>/dev/null | grep -q ':41451'
}

gpu_heavy() {
  # Renderer idle-ish: util < 85% unless only Xorg/desktop
  local util
  util="$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' ')"
  [[ -n "$util" && "$util" -ge 90 ]]
}

wait_idle() {
  log "polling every ${POLL_S}s for 125 idle (log=$LOG)"
  while true; do
    local reasons=()
    if eval_busy; then reasons+=("eval/collect python running"); fi
    if python_on_airsim; then reasons+=("python client on :41451"); fi
    if ! outdoor_renderer_up; then reasons+=("outdoor renderer not ready"); fi
    if gpu_heavy; then reasons+=("GPU util>=90%"); fi

    if ((${#reasons[@]} == 0)); then
      log "125 idle — proceeding"
      return 0
    fi

    log "busy: $(IFS='; '; echo "${reasons[*]}")"
    pgrep -af 'wam_phase2_long_eval|wam_phase2_traj_forensics|indoor_mainline|python.*41451' 2>/dev/null \
      | head -5 | tee -a "$LOG" || true
    ss -tnp 2>/dev/null | grep 41451 | head -3 | tee -a "$LOG" || true
    sleep "$POLL_S"
  done
}

run_ablation() {
  if route10_ablation_running; then
    log "route10 ablation already running; exit"
    exit 0
  fi
  cd "$ROOT"
  if [[ ! -x experiments/aerial/scripts/wam_phase2_route10_efficiency_plan.sh ]]; then
    log "ERROR: missing wam_phase2_route10_efficiency_plan.sh — sync repo first"
    exit 1
  fi
  # shellcheck disable=SC1091
  source experiments/aerial/scripts/env_4090.sh
  local run_log="$ROOT/artifacts/wam_phase2_route10_efficiency_run_$(date +%Y%m%d_%H%M%S).log"
  log "starting ablation (all arms) -> $run_log"
  env PYTHONUNBUFFERED=1 nohup bash experiments/aerial/scripts/wam_phase2_route10_efficiency_plan.sh all \
    >>"$run_log" 2>&1 &
  echo $! >"$ROOT/artifacts/wam_phase2_route10_efficiency.pid"
  log "ablation pid=$(cat "$ROOT/artifacts/wam_phase2_route10_efficiency.pid") log=$run_log"
}

main() {
  log "=== route10 wait-and-run ==="
  log "ROOT=$ROOT"
  wait_idle
  sleep 5
  run_ablation
  log "=== launched ==="
}

main "$@"
