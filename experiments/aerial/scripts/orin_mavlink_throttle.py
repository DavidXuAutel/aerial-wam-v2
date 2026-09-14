#!/usr/bin/env python3
"""Orin MAVLink throttle control for ArduPilot (RC override on ch3).

Bench / flight: ramps throttle via RC_CHANNELS_OVERRIDE while armed.

  # Dry-run: connect + print state only
  python -m experiments.aerial.scripts.orin_mavlink_throttle --dry-run

  # Recommended: ARM with H12 F-switch first, then Orin ramps throttle:
  python -m experiments.aerial.scripts.orin_mavlink_throttle \\
    --wait-armed --throttle-pct 30 --hold-s 3 --i-know-props-are-on

  # Or MAVLink arm (may fail indoors without GPS fix):
  python -m experiments.aerial.scripts.orin_mavlink_throttle \\
    --arm --throttle-pct 30 --hold-s 3 --i-know-props-are-on
"""
from __future__ import annotations

import argparse
import logging
import sys
import time

from pymavlink import mavutil

from experiments.aerial.rl.env.mavlink_bridge import (
    ARDUCOPTER_MODE_GUIDED,
    MavlinkBridge,
    MavlinkBridgeConfig,
)

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("orin_mavlink_throttle")

NO_OVERRIDE = 65535


def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Orin MAVLink throttle via RC override")
    p.add_argument("--port", default="/dev/ttyACM0")
    p.add_argument("--baud", type=int, default=57600)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--arm", action="store_true", help="Arm via MAVLink before throttle ramp")
    p.add_argument(
        "--wait-armed",
        action="store_true",
        help="Wait for pilot ARM (H12 F-switch); do not MAVLink-arm",
    )
    p.add_argument("--wait-timeout-s", type=float, default=120.0)
    p.add_argument("--i-know-props-are-on", action="store_true")
    p.add_argument("--no-disarm", action="store_true", help="Leave armed after run")
    p.add_argument(
        "--throttle-pct",
        type=float,
        default=30.0,
        help="Target throttle percent above idle (10-80)",
    )
    p.add_argument("--ramp-s", type=float, default=2.0, help="Seconds to ramp up")
    p.add_argument("--hold-s", type=float, default=2.0, help="Hold at target throttle")
    p.add_argument("--hz", type=float, default=20.0)
    return p.parse_args()


def pwm_from_pct(pct: float) -> int:
    pct = max(0.0, min(100.0, pct))
    return int(1000 + pct * 10.0)


def send_throttle_override(mav: any, ts: int, tc: int, throttle_pwm: int) -> None:
    mav.mav.rc_channels_override_send(
        ts,
        tc,
        NO_OVERRIDE,
        NO_OVERRIDE,
        int(throttle_pwm),
        NO_OVERRIDE,
        NO_OVERRIDE,
        NO_OVERRIDE,
        NO_OVERRIDE,
        NO_OVERRIDE,
    )


def main() -> int:
    args = _parse()
    if (args.arm or args.wait_armed) and not args.i_know_props_are_on:
        logger.error("Refusing throttle test without --i-know-props-are-on")
        return 2
    if args.arm and args.wait_armed:
        logger.error("Use --arm or --wait-armed, not both")
        return 2
    pct = max(10.0, min(80.0, float(args.throttle_pct)))

    bridge = MavlinkBridge(MavlinkBridgeConfig(port=args.port, baud=args.baud))
    bridge.connect(timeout_s=8)
    mav = bridge._mav
    ts, tc = bridge.target_system, 1

    bridge.poll(timeout_s=1.0)
    logger.info(
        "connected ardupilot=%s armed=%s mode=%s",
        bridge.is_ardupilot(),
        bridge.is_armed(),
        bridge._last_heartbeat.custom_mode if bridge._last_heartbeat else None,
    )

    if args.dry_run:
        logger.info("dry-run OK")
        bridge.close()
        return 0

    if not bridge.is_ardupilot():
        logger.error("This script targets ArduPilot; use GUIDED/OFFBOARD velocity for PX4")
        bridge.close()
        return 1

    if bridge.is_armed():
        logger.info("already ARMED")
    elif args.wait_armed:
        logger.info(
            "Waiting for pilot ARM (F-switch, throttle low, Acro/Stabilize)... %.0fs",
            args.wait_timeout_s,
        )
        deadline = time.perf_counter() + args.wait_timeout_s
        while time.perf_counter() < deadline:
            bridge.poll(timeout_s=0.2)
            if bridge.is_armed():
                break
            time.sleep(0.1)
        if not bridge.is_armed():
            logger.error("Timeout: FC not ARMED — use H12 F-switch to arm")
            bridge.close()
            return 1
    elif args.arm:
        logger.info("ARM via MAVLink")
        bridge.arm()
        time.sleep(1.0)
        bridge.poll(timeout_s=0.5)
        if not bridge.is_armed():
            msg = bridge._mav.recv_match(type="STATUSTEXT", blocking=True, timeout=2)
            logger.error(
                "ARM failed%s — try --wait-armed and arm with H12 F-switch",
                f": {msg.text}" if msg else "",
            )
            bridge.close()
            return 1
    else:
        logger.error("Pass --wait-armed or --arm (with --i-know-props-are-on)")
        bridge.close()
        return 2

    logger.info("ARMED — Orin taking over throttle on ch3 (RC override)")
    idle_pwm = 1051
    target_pwm = pwm_from_pct(pct)
    dt = 1.0 / float(args.hz)
    logger.info("throttle ramp %d -> %d (%.0f%%) over %.1fs", idle_pwm, target_pwm, pct, args.ramp_s)

    try:
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < args.ramp_s:
            u = min(1.0, (time.perf_counter() - t0) / max(args.ramp_s, 0.01))
            thr = int(idle_pwm + u * (target_pwm - idle_pwm))
            send_throttle_override(mav, ts, tc, thr)
            bridge.poll(timeout_s=0.0)
            time.sleep(dt)

        logger.info("hold throttle %d for %.1fs", target_pwm, args.hold_s)
        t_hold0 = time.perf_counter()
        while time.perf_counter() - t_hold0 < args.hold_s:
            send_throttle_override(mav, ts, tc, target_pwm)
            bridge.poll(timeout_s=0.0)
            time.sleep(dt)

        logger.info("ramp down to idle")
        t_down0 = time.perf_counter()
        while time.perf_counter() - t_down0 < args.ramp_s:
            u = min(1.0, (time.perf_counter() - t_down0) / max(args.ramp_s, 0.01))
            thr = int(target_pwm - u * (target_pwm - idle_pwm))
            send_throttle_override(mav, ts, tc, thr)
            bridge.poll(timeout_s=0.0)
            time.sleep(dt)

        send_throttle_override(mav, ts, tc, idle_pwm)
        time.sleep(0.2)
    finally:
        # release overrides
        for _ in range(5):
            mav.mav.rc_channels_override_send(ts, tc, 0, 0, 0, 0, 0, 0, 0, 0)
            time.sleep(0.05)
        if bridge.is_armed() and not args.no_disarm:
            logger.info("DISARM via MAVLink (or use H12 F-switch)")
            bridge.disarm()
            time.sleep(0.5)
        bridge.close()

    logger.info("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
