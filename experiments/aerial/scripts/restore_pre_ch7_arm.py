#!/usr/bin/env python3
"""Restore FC params to the snapshot from when H12 arm worked (before ch7 work).

Run on Orin (nothing else on /dev/ttyACM0):
  python experiments/aerial/scripts/restore_pre_ch7_arm.py
"""
from __future__ import annotations

import sys
import time

from pymavlink import mavutil

DEVICE = "/dev/ttyACM0"
BAUD = 57600

# Exact bench snapshot when user confirmed arming worked (before ch7 toggle).
RESTORE: dict[str, float] = {
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
        print("ERROR: no heartbeat")
        return 1
    ts, tc = m.target_system, 1
    print("Disarm first...")
    m.mav.command_long_send(
        ts, tc, mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0, 0, 0, 0, 0, 0, 0, 0
    )
    time.sleep(0.5)
    m.set_mode_apm("STABILIZE")
    time.sleep(0.8)

    print("Restoring params...")
    for name, value in RESTORE.items():
        m.param_set_send(name, value)
        time.sleep(0.7)
        got = _read(m, ts, tc, name)
        print(f"  {name} = {value}  ({got})")

    m.mav.command_long_send(
        ts, tc, mavutil.mavlink.MAV_CMD_PREFLIGHT_STORAGE, 0, 1, 0, 0, 0, 0, 0, 0
    )
    print("Saved. Rebooting FC...")
    m.mav.command_long_send(
        ts, tc, mavutil.mavlink.MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN, 0, 1, 0, 0, 0, 0, 0, 0
    )
    time.sleep(4)
    if m.wait_heartbeat(timeout=15):
        m.set_mode_apm("STABILIZE")
        time.sleep(0.5)
        print(f"FC back online. mode={m.flightmode}")
    else:
        print("Wait for FC reboot, then power-cycle if needed.")

    print("\nDone. H12: ch5=模式 ch6 F=ARM ch7=无. 油门最低 + F上位 ARM.")
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
