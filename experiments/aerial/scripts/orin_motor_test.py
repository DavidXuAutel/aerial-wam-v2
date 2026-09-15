#!/usr/bin/env python3
"""Direct ArduPilot MOTOR_TEST — bypasses RC/H12/override path.

  # Props OFF. Arm with H12 first, then:
  python -m experiments.aerial.scripts.orin_motor_test --motor 1 --pct 10 --duration-s 2
"""
from __future__ import annotations

import argparse
import sys
import time

from pymavlink import mavutil

# MAV_CMD_DO_MOTOR_TEST
MOTOR_TEST_THROTTLE_PERCENT = 1


def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ArduPilot direct motor test")
    p.add_argument("--port", default="/dev/ttyACM0")
    p.add_argument("--baud", type=int, default=57600)
    p.add_argument("--motor", type=int, default=1, help="Motor 1-4")
    p.add_argument("--pct", type=float, default=10.0, help="Throttle percent")
    p.add_argument("--duration-s", type=float, default=2.0)
    p.add_argument("--require-armed", action="store_true", default=True)
    p.add_argument("--i-know-props-are-off", action="store_true")
    return p.parse_args()


def main() -> int:
    args = _parse()
    if not args.i_know_props_are_off:
        print("Refusing without --i-know-props-are-off")
        return 2

    m = mavutil.mavlink_connection(
        args.port, baud=args.baud, source_system=255, source_component=190
    )
    if m.wait_heartbeat(timeout=10) is None:
        print("ERROR: no heartbeat")
        return 1
    ts, tc = m.target_system, 1

    armed = False
    servo = [0, 0, 0, 0]
    bat_v = None
    texts: list[str] = []
    end = time.time() + 2.0
    while time.time() < end:
        msg = m.recv_match(blocking=True, timeout=0.1)
        if msg is None:
            continue
        t = msg.get_type()
        if t == "HEARTBEAT":
            armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
        elif t == "SERVO_OUTPUT_RAW":
            servo = [int(getattr(msg, f"servo{i}_raw", 0) or 0) for i in range(1, 5)]
        elif t == "BATTERY_STATUS":
            if msg.voltages and msg.voltages[0] != 65535:
                bat_v = msg.voltages[0] / 1000.0
        elif t == "STATUSTEXT":
            s = msg.text.decode(errors="ignore") if isinstance(msg.text, bytes) else str(msg.text)
            texts.append(s.strip())

    print(f"pre-test: armed={armed} mode={m.flightmode} bat={bat_v}V M_pwm={servo}")
    if args.require_armed and not armed:
        print("ERROR: not ARMED — arm with H12 (throttle low + ch6 F up) first")
        return 1

    motor = max(1, min(4, int(args.motor)))
    pct = max(1.0, min(25.0, float(args.pct)))
    dur = max(0.5, float(args.duration_s))
    print(f"MOTOR_TEST motor={motor} pct={pct} duration={dur}s ...")

    m.mav.command_long_send(
        ts,
        tc,
        mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST,
        0,
        float(motor),
        float(MOTOR_TEST_THROTTLE_PERCENT),
        float(pct),
        float(dur),
        0,
        0,
        0,
    )
    ack = m.recv_match(type="COMMAND_ACK", blocking=True, timeout=3)
    if ack:
        print(f"COMMAND_ACK result={ack.result} ({'ACCEPTED' if ack.result == 0 else 'DENIED'})")

    t_end = time.time() + dur + 1.0
    while time.time() < t_end:
        msg = m.recv_match(blocking=True, timeout=0.1)
        if msg is None:
            continue
        t = msg.get_type()
        if t == "SERVO_OUTPUT_RAW":
            servo = [int(getattr(msg, f"servo{i}_raw", 0) or 0) for i in range(1, 5)]
            print(f"  during test M_pwm={servo}")
        elif t == "STATUSTEXT":
            s = msg.text.decode(errors="ignore") if isinstance(msg.text, bytes) else str(msg.text)
            print(f"  [STATUSTEXT] {s.strip()}")

    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
