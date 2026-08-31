#!/usr/bin/env bash
# Resume P-A1→P8 chain from H100 sync (P-A1 already DONE).
export SKIP_PA1_WAIT=1
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/aerial-wam-v2")"
cd "$ROOT"
exec bash experiments/aerial/scripts/v4_pa1_p8_chain.sh
