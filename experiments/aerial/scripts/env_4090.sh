#!/usr/bin/env bash
# Aerial WAM — eval / collect env for 125 (4090 + AirSim).
# .110 retired 2026-09-04 (PCIe x1 defect + AirSim teleport bug).
#
#   source experiments/aerial/scripts/env_4090.sh

set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/aerial-wam-v2")"
export REPO_ROOT="$ROOT"
export PYTHONPATH="$ROOT:${PYTHONPATH:-}"
if [[ -z "${PYTHON_BIN:-}" ]]; then
  if [[ -x "$HOME/sim_verify/.venv/bin/python" ]]; then
    PYTHON_BIN="$HOME/sim_verify/.venv/bin/python"
  else
    PYTHON_BIN=python3
  fi
fi
export PYTHON_BIN
export AERIAL_PY="$PYTHON_BIN"
export AIRSIM_PORT="${AIRSIM_PORT:-41451}"
# 125 binds AirSim to 127.0.0.1; use loopback by default.
export AIRSIM_HOST="${AIRSIM_HOST:-127.0.0.1}"
export AIRSIM_CAMERA=front_custom
export AIRSIM_VEHICLE=drone_1
export ANNOTATION="${ANNOTATION:-$ROOT/artifacts/seen_airsim16_m1a20.json}"
export AERIAL_PERSIST_ROOT="${AERIAL_PERSIST_ROOT:-$HOME/aerial_airsim_persistent}"

echo "[env_4090] REPO_ROOT=$REPO_ROOT"
echo "[env_4090] PYTHON_BIN=$PYTHON_BIN ($("$PYTHON_BIN" --version 2>&1))"
echo "[env_4090] AIRSIM_HOST=${AIRSIM_HOST:-<none: no local renderer>} AIRSIM_PORT=$AIRSIM_PORT"
echo "[env_4090] ANNOTATION=$ANNOTATION"
echo "[env_4090] renderer: $AERIAL_PERSIST_ROOT/recover_renderer.sh"
