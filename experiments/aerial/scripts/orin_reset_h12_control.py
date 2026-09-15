#!/usr/bin/env python3
"""Force-release MAVLink RC override and return FC to H12 STABILIZE bench state.

Run after orin_mavlink_throttle or any companion script that may leave override latched:

  python -m experiments.aerial.scripts.orin_reset_h12_control
"""
from __future__ import annotations

import argparse
import sys
import time

from pymavlink import mavutil

from experiments.aerial.rl.env.mavlink_bridge import MavlinkBridge, MavlinkBridgeConfig


def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Release RC override, STABILIZE, optional disarm")
    p.add_argument("--port", default="/dev/ttyACM0")
    p.add_argument("--baud", type=int, default=57600)
    p.add_argument("--disarm", action="store_true", help="Disarm after releasing override")
    return p.parse_args()


def main() -> int:
    args = _parse()
    bridge = MavlinkBridge(MavlinkBridgeConfig(port=args.port, baud=int(args.baud)))
    bridge.connect(timeout_s=10)
    m = bridge._mav
    print("Releasing override + STABILIZE (H12 passthrough)...")
    bridge.restore_h12_passthrough(disarm=bool(args.disarm))
    time.sleep(0.3)
    armed = False
    rc = {}
    end = time.time() + 2.0
    while time.time() < end:
        msg = m.recv_match(blocking=True, timeout=0.1)
        if msg is None:
            continue
        if msg.get_type() == "HEARTBEAT":
            armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
        elif msg.get_type() == "RC_CHANNELS":
            for i in range(1, 8):
                v = getattr(msg, f"chan{i}_raw", None)
                if v:
                    rc[i] = int(v)
    print(f"mode={m.flightmode} armed={armed}")
    print(f"RC ch3={rc.get(3, '?')} ch5={rc.get(5, '?')} ch6={rc.get(6, '?')}")
    print("H12 should control throttle now. Arm: throttle LOW + ch6 F up.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
