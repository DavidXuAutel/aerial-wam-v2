#!/usr/bin/env bash
# From Mac: SSH to Orin, start MAVLink bridge, open QGC.
# Usage:
#   ORIN_HOST=10.229.20.127 ./mac_gcs_via_orin.sh
#   ./mac_gcs_via_orin.sh orin-direct
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
ORIN_SSH="${1:-${ORIN_HOST:-orin-direct}}"
MAC_IP="$(ipconfig getifaddr en7 2>/dev/null || ipconfig getifaddr en0 2>/dev/null || true)"
MAC_IP="${MAC_IP:-10.229.20.126}"
PORT="${PORT:-14550}"
QGC_APP="/Applications/QGroundControl.app"

echo "Mac IP for MAVLink: ${MAC_IP}"
echo "Orin SSH target: ${ORIN_SSH}"

if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "${ORIN_SSH}" true 2>/dev/null; then
  echo "ERROR: Cannot SSH to ${ORIN_SSH}."
  echo "  - Check ethernet link (Mac en7 should ping Orin)"
  echo "  - Try: ORIN_HOST=<orin-ip> $0"
  echo "  - On Orin: sudo ip addr add 10.229.20.127/24 dev eth0  (example)"
  exit 1
fi

echo "Pushing bridge script to Orin..."
scp -q "${ROOT}/experiments/aerial/scripts/orin_gcs_bridge.sh" "${ORIN_SSH}:~/orin_gcs_bridge.sh"
ssh "${ORIN_SSH}" "chmod +x ~/orin_gcs_bridge.sh"

echo "Starting bridge on Orin (background)..."
ssh -f "${ORIN_SSH}" "MAC_IP=${MAC_IP} PORT=${PORT} nohup ~/orin_gcs_bridge.sh > /tmp/orin_gcs_bridge.log 2>&1 &"
sleep 2
ssh "${ORIN_SSH}" "tail -20 /tmp/orin_gcs_bridge.log 2>/dev/null || true"

if [[ -d "$QGC_APP" ]]; then
  echo "Opening QGroundControl..."
  open -a QGroundControl
else
  echo "QGC not installed. Install to ${QGC_APP} then re-run."
  echo "DMG: https://github.com/mavlink/qgroundcontrol/releases/download/v4.4.5/QGroundControl.dmg"
fi

cat <<EOF

QGC setup (one-time):
  1. Application Settings -> Comm Links -> Add
  2. Type: UDP, Port: ${PORT}, Auto Connect: ON
  3. Connect -> should show heartbeat / mode / RC channels

To learn H12 mapping: Vehicle Setup -> Radio, move sticks and E/F switches.

Stop bridge on Orin:
  ssh ${ORIN_SSH} 'pkill -f mavproxy.py'

EOF
