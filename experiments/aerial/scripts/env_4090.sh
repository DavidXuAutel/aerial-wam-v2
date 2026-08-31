#!/usr/bin/env bash
# Aerial WAM — eval / collect on **10.229.20.110 only** (4090 + AirSim).
# SOURCE on .110 after: ssh cursor-125[-public] → ssh a26125-110
#
#   source experiments/aerial/scripts/env_4090.sh
#
# 125 is bridge-only — do NOT source this on cursor-125 / user yao.
# See docs/handover/ACCESS.md and AIRSIM_MIGRATE_110_20260831.md.

# Hard gate BEFORE set -e (so a refused `source` does not kill the parent shell mid-script).
if [[ "${AERIAL_ALLOW_125:-0}" != "1" ]]; then
  if [[ "$(whoami 2>/dev/null || true)" == "yao" ]] \
    || [[ "${HOME:-}" == "/home/yao" ]] \
    || [[ -d /home/yao/aerial-wam-v2 && "$(hostname -I 2>/dev/null | tr ' ' '\n' | grep -c '^10\.229\.20\.125$' || true)" -ge 1 ]]; then
    echo "[env_4090] REFUSED: aerial eval/collect runs on 10.229.20.110 only." >&2
    echo "[env_4090] From Mac/125 bridge: ssh a26125-110   then source this script there." >&2
    echo "[env_4090] (override for emergency only: AERIAL_ALLOW_125=1)" >&2
    return 1 2>/dev/null || exit 1
  fi
fi

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
export AIRSIM_HOST="${AIRSIM_HOST:-10.229.20.110}"
export AIRSIM_PORT="${AIRSIM_PORT:-41451}"
export AIRSIM_CAMERA=front_custom
export AIRSIM_VEHICLE=drone_1
export ANNOTATION="${ANNOTATION:-$ROOT/artifacts/seen_airsim16_m1a20.json}"
export AERIAL_PERSIST_ROOT="${AERIAL_PERSIST_ROOT:-$HOME/aerial_airsim_persistent}"

echo "[env_4090] REPO_ROOT=$REPO_ROOT"
echo "[env_4090] PYTHON_BIN=$PYTHON_BIN ($("$PYTHON_BIN" --version 2>&1))"
echo "[env_4090] AIRSIM_HOST=$AIRSIM_HOST AIRSIM_PORT=$AIRSIM_PORT"
echo "[env_4090] ANNOTATION=$ANNOTATION"
echo "[env_4090] renderer: $AERIAL_PERSIST_ROOT/recover_renderer.sh"
