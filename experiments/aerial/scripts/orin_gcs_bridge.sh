#!/usr/bin/env bash
# Start MAVLink bridge on Orin: Pixhawk USB -> UDP to Mac QGC.
# Usage (on Orin):
#   MAC_IP=10.229.20.126 ./orin_gcs_bridge.sh
set -euo pipefail

MAC_IP="${MAC_IP:-10.229.20.126}"
PORT="${PORT:-14550}"
DEVICE="${DEVICE:-/dev/ttyACM0}"
BAUD="${BAUD:-57600}"

if [[ ! -e "$DEVICE" ]]; then
  echo "ERROR: $DEVICE not found. Is Pixhawk USB plugged in?"
  ls -la /dev/ttyACM* /dev/ttyUSB* 2>/dev/null || true
  exit 1
fi

if [[ -d "$HOME/sim_verify/.venv" ]]; then
  # shellcheck disable=SC1091
  source "$HOME/sim_verify/.venv/bin/activate"
fi

python3 -m pip install -q --upgrade MAVProxy pymavlink

pkill -f "mavproxy.py.*${DEVICE}" 2>/dev/null || true
sleep 0.5

echo "Bridging ${DEVICE}@${BAUD} -> udp:${MAC_IP}:${PORT}"
echo "Mac QGC: Comm Link UDP, port ${PORT}"

exec mavproxy.py \
  --master="${DEVICE},${BAUD}" \
  --out="udp:${MAC_IP}:${PORT}" \
  --out="udp:127.0.0.1:${PORT}"
