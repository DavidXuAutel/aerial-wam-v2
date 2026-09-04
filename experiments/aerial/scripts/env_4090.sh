#!/usr/bin/env bash
# Aerial WAM — eval / collect env for 110 and 125 (both have 4090 + AirSim).
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
# Point at THIS box's renderer, detected the same way the Python client does
# (env/renderer_host.py — one implementation, so bash and Python cannot diverge).
# Was hardcoded 10.229.20.110: on 125 that silently aimed every run at 110's
# renderer, and two boxes shared one drone (2026-09-03 incident). Set AIRSIM_HOST
# yourself to override; a non-local host also needs AIRSIM_ALLOW_REMOTE_HOST=1.
if [[ -z "${AIRSIM_HOST:-}" ]]; then
  if AIRSIM_HOST="$("$PYTHON_BIN" -m experiments.aerial.rl.env.renderer_host \
      --port "$AIRSIM_PORT" 2>/dev/null)"; then
    export AIRSIM_HOST
  else
    echo "[env_4090] WARNING: no local AirSim renderer on :$AIRSIM_PORT" >&2
    echo "[env_4090]   start it: \$AERIAL_PERSIST_ROOT/recover_renderer.sh" >&2
    unset AIRSIM_HOST
  fi
else
  export AIRSIM_HOST
fi
export AIRSIM_CAMERA=front_custom
export AIRSIM_VEHICLE=drone_1
export ANNOTATION="${ANNOTATION:-$ROOT/artifacts/seen_airsim16_m1a20.json}"
export AERIAL_PERSIST_ROOT="${AERIAL_PERSIST_ROOT:-$HOME/aerial_airsim_persistent}"

echo "[env_4090] REPO_ROOT=$REPO_ROOT"
echo "[env_4090] PYTHON_BIN=$PYTHON_BIN ($("$PYTHON_BIN" --version 2>&1))"
echo "[env_4090] AIRSIM_HOST=${AIRSIM_HOST:-<none: no local renderer>} AIRSIM_PORT=$AIRSIM_PORT"
echo "[env_4090] ANNOTATION=$ANNOTATION"
echo "[env_4090] renderer: $AERIAL_PERSIST_ROOT/recover_renderer.sh"
