#!/usr/bin/env python3
"""Pixhawk USB / MAVLink smoke + optional Offboard hover test.

Default (**dry-run**): connect, print telemetry, stream zero-velocity setpoints
**without** entering OFFBOARD or arming — safe on the bench.

Stages (each requires the previous flags):

  --offboard   Enter PX4 OFFBOARD after warming up setpoint stream (still disarmed)
  --arm        Arm motors (DANGER: props must be off or aircraft secured)
  --hover-s    Hold zero-velocity Offboard for N seconds after arm

Example (bench, props OFF):

  python -m experiments.aerial.scripts.pixhawk_offboard_hover \\
    --port /dev/ttyACM0 --dry-run

  python -m experiments.aerial.scripts.pixhawk_offboard_hover \\
    --port /dev/ttyACM0 --offboard --warmup-s 5

Outdoor / secured hover (props ON, explicit consent):

  python -m experiments.aerial.scripts.pixhawk_offboard_hover \\
    --port /dev/ttyACM0 --offboard --arm --hover-s 10 --i-know-props-are-on
"""
from __future__ import annotations

import argparse
import logging
import sys
import time

from experiments.aerial.rl.env.mavlink_bridge import MavlinkBridge, MavlinkBridgeConfig

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("pixhawk_offboard_hover")


def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Pixhawk MAVLink / Offboard hover probe")
    p.add_argument("--port", default="/dev/ttyACM0")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--stream-hz", type=float, default=30.0)
    p.add_argument("--warmup-s", type=float, default=3.0, help="Setpoint stream before OFFBOARD")
    p.add_argument("--hover-s", type=float, default=0.0, help="Hover duration after arm")
    p.add_argument("--offboard", action="store_true", help="Switch to OFFBOARD mode")
    p.add_argument("--arm", action="store_true", help="Arm after OFFBOARD (DANGER)")
    p.add_argument(
        "--i-know-props-are-on",
        action="store_true",
        help="Required with --arm when motors can spin",
    )
    return p.parse_args()


def main() -> int:
    args = _parse()

    if args.arm and not args.offboard:
        logger.error("--arm requires --offboard")
        return 2
    if args.arm and not args.i_know_props_are_on:
        logger.error("Refusing --arm without --i-know-props-are-on")
        return 2
    if args.hover_s > 0 and not args.arm:
        logger.error("--hover-s requires --arm")
        return 2

    # Any active stage disables pure dry-run label in logs.
    stage = "dry-run"
    if args.arm:
        stage = "arm-hover"
    elif args.offboard:
        stage = "offboard"

    cfg = MavlinkBridgeConfig(
        port=args.port,
        baud=args.baud,
        stream_hz=args.stream_hz,
    )
    bridge = MavlinkBridge(cfg)

    try:
        bridge.connect()
        logger.info("Stage=%s sys=%s", stage, bridge.target_system)

        st = bridge.observe_state(timeout_s=2.0)
        logger.info(
            "State ENU-ish: pos=[%.2f, %.2f, %.2f] vel=[%.2f, %.2f, %.2f] yaw=%.2f°",
            st[0], st[1], st[2], st[3], st[4], st[5], st[6] * 57.3,
        )
        logger.info("Armed=%s", bridge.is_armed())

        logger.info("Warming setpoint stream %.1fs @ %.0f Hz (zero velocity) ...",
                    args.warmup_s, args.stream_hz)
        n = bridge.stream_hover(args.warmup_s)
        logger.info("Sent %d zero-velocity setpoints", n)

        if not args.offboard:
            logger.info("DRY-RUN complete — did not enter OFFBOARD or ARM")
            return 0

        if args.offboard:
            bridge.set_mode_offboard()
            time.sleep(0.5)
            bridge.poll(timeout_s=1.0)
            logger.info("Requested OFFBOARD; armed=%s", bridge.is_armed())
            bridge.stream_hover(1.0)

        if not args.arm:
            logger.info("OFFBOARD probe complete — still disarmed")
            return 0

        logger.warning("ARMING — motors may spin")
        bridge.arm()
        time.sleep(1.0)
        bridge.poll(timeout_s=1.0)
        if not bridge.is_armed():
            logger.error("Arm failed — check preflight / safety switch / RC")
            return 1
        logger.info("ARMED — streaming hover setpoints for %.1fs", args.hover_s)
        bridge.stream_hover(max(args.hover_s, 1.0))

        logger.info("Disarming")
        bridge.disarm()
        time.sleep(0.5)
        logger.info("Done. armed=%s", bridge.is_armed())
        return 0

    except KeyboardInterrupt:
        logger.warning("Interrupted — disarming if connected")
        try:
            bridge.disarm()
        except Exception:  # noqa: BLE001
            pass
        return 130
    finally:
        bridge.close()


if __name__ == "__main__":
    sys.exit(main())
