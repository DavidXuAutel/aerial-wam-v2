#!/usr/bin/env python3
"""Lightweight MAVLink monitor for learning RC mapping (no QGC required)."""
from __future__ import annotations

import argparse
import time

from pymavlink import mavutil


def main() -> None:
    p = argparse.ArgumentParser(description="Print PX4 mode + RC channels from MAVLink UDP.")
    p.add_argument("--udp-port", type=int, default=14550)
    args = p.parse_args()

    conn = mavutil.mavlink_connection(f"udp:0.0.0.0:{args.udp_port}")
    print(f"Listening udp:{args.udp_port} ... (start Orin bridge first)")
    conn.wait_heartbeat(timeout=30)
    print("Heartbeat OK. Move sticks / switches on H12.\n")

    last_rc: tuple[int, ...] | None = None
    while True:
        msg = conn.recv_match(blocking=True, timeout=1.0)
        if msg is None:
            continue
        t = msg.get_type()
        if t == "HEARTBEAT" and msg.get_srcComponent() != 0:
            armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
            print(f"mode={msg.custom_mode} armed={armed}")
        elif t == "RC_CHANNELS":
            rc = tuple(
                int(getattr(msg, f"chan{i}_raw", 0) or 0) for i in range(1, 9)
            )
            if rc != last_rc:
                last_rc = rc
                print(
                    "RC "
                    + " ".join(f"ch{i}={v}" for i, v in enumerate(rc, start=1))
                )
        time.sleep(0.05)


if __name__ == "__main__":
    main()
