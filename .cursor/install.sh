#!/usr/bin/env bash
# Cloud Agent install for Aerial WAM v2.
#
# Idempotent repository bootstrap: builds a project .venv and installs the base
# package (numpy/pyyaml/opencv-headless/msgpack-rpc/einops/addict/safetensors/
# pytest) plus a CPU build of torch/torchvision so the torch-gated unit tests
# run on the (GPU-less) Cloud Agent VM. The pinned cu128 GPU stack + AirSim
# renderer stay on the H100/4090 boxes (see experiments/aerial/scripts/).
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"
VENV="${VENV:-$ROOT/.venv}"

# The default Ubuntu image ships a python3 without ensurepip, so `python3 -m
# venv` fails until python3-venv is present. Guard the apt install so reruns
# and images that already have it are no-ops.
if ! python3 -c 'import ensurepip' >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y python3-venv
fi

python3 -m venv "$VENV"
# shellcheck disable=SC1091
source "$VENV/bin/activate"

python -m pip install -U pip setuptools wheel
python -m pip install -e .

# CPU-only torch (no CUDA device on the Cloud Agent VM). This unlocks the
# torch-gated unit tests that otherwise `pytest.importorskip('torch')` away.
python -m pip install "torch==2.7.1" "torchvision==0.22.1" \
  --index-url https://download.pytorch.org/whl/cpu

echo "[install] done -> activate with: source $VENV/bin/activate"
