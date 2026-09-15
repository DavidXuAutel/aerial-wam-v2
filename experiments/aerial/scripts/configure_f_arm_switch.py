#!/usr/bin/env python3
"""Map H12 F switch (ch6) to ARM/DISARM on ArduPilot + indoor bench.

ch7: Orin/H12 toggle is handled in Orin software (rising-edge button).
      Keep RC7_OPTION=0 on the FC — do not use RC7_OPTION=46 (needs hold).

Run on Orin:
  pkill -f mavlink_forward.py
  python experiments/aerial/scripts/configure_f_arm_switch.py
"""
from __future__ import annotations

import sys
import time

from pymavlink import mavutil

DEVICE = "/dev/ttyACM0"
BAUD = 57600

SETTINGS: dict[str, float] = {
    "RC5_OPTION": 0,
    "RC6_OPTION": 153,
    "RC7_OPTION": 0,
    "FLTMODE_CH": 5,
    "FLTMODE1": 0,
    "FLTMODE2": 1,
    "FLTMODE3": 0,
    "FLTMODE4": 1,
    "FLTMODE5": 0,
    "FLTMODE6": 1,
    "ARMING_CHECK": 0,
    "ARMING_OPTIONS": 1,
    "ARMING_RUDDER": 0,
    "BRD_SAFETY_DEFLT": 0,
    "FENCE_ENABLE": 0,
    "AHRS_GPS_USE": 0,
    "EK3_SRC1_POSXY": 0,
    "EK3_SRC1_VELXY": 0,
    "EK3_SRC1_POSZ": 1,
    "EK3_SRC1_VELZ": 0,
    "RC_OPTIONS": 0,
    "RC_OVERRIDE_TIME": 3,
}


def main() -> int:
    m = mavutil.mavlink_connection(
        DEVICE, baud=BAUD, source_system=255, source_component=190
    )
    if m.wait_heartbeat(timeout=10) is None:
        print("ERROR: no heartbeat on", DEVICE)
        return 1
    ts, tc = m.target_system, 1
    m.set_mode_apm("STABILIZE")
    time.sleep(0.8)
    for name, value in SETTINGS.items():
        m.param_set_send(name, value)
        time.sleep(0.7)
        print(f"  {name} = {value}  readback={_read(m, ts, tc, name)}")
    m.mav.command_long_send(
        ts, tc, mavutil.mavlink.MAV_CMD_PREFLIGHT_STORAGE, 0, 1, 0, 0, 0, 0, 0, 0
    )
    print(f"mode={m.flightmode} saved.")
    print("ch5=模式 ch6 F=ARM ch7=Orin切换(Orin读上升沿, RC7_OPTION=0)")
    return 0


def _read(m, ts: int, tc: int, name: str) -> float | None:
    m.mav.param_request_read_send(ts, tc, name.encode(), -1)
    dl = time.time() + 4
    while time.time() < dl:
        msg = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=0.3)
        if msg is None:
            continue
        pid = (
            msg.param_id.decode().rstrip("\x00")
            if isinstance(msg.param_id, bytes)
            else str(msg.param_id).rstrip("\x00")
        )
        if pid == name:
            return msg.param_value
    return None


if __name__ == "__main__":
    raise SystemExit(main())
