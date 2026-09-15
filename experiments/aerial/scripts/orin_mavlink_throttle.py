#!/usr/bin/env python3
"""Orin MAVLink throttle via RC override on ch3.

ch7 button (rising edge): toggle Orin vs H12. No need to hold ch7.

  python -m experiments.aerial.scripts.orin_mavlink_throttle \\
    --wait-armed --ch7-handoff --throttle-pct 25 --hold-s 2 --i-know-props-are-on
"""
from __future__ import annotations

import argparse
import logging
import sys
import time

from experiments.aerial.rl.env.mavlink_bridge import MavlinkBridge, MavlinkBridgeConfig
from experiments.aerial.rl.env.orin_rc_handoff import (
    OrinRcHandoff,
    OrinRcHandoffConfig,
    release_rc_overrides,
)

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("orin_mavlink_throttle")

NO_OVERRIDE = 65535


def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Orin MAVLink throttle via RC override")
    p.add_argument("--port", default="/dev/ttyACM0")
    p.add_argument("--baud", type=int, default=57600)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--arm", action="store_true")
    p.add_argument("--wait-armed", action="store_true")
    p.add_argument(
        "--ch7-handoff",
        action="store_true",
        help="Use ch7 rising-edge toggle (Orin <-> H12); default ch7",
    )
    p.add_argument("--handoff-ch", type=int, default=7)
    p.add_argument("--handoff-threshold", type=int, default=1600)
    p.add_argument("--wait-timeout-s", type=float, default=120.0)
    p.add_argument("--i-know-props-are-on", action="store_true")
    p.add_argument(
        "--no-disarm",
        action="store_true",
        default=True,
        help="Leave armed after run (default: True for bench)",
    )
    p.add_argument(
        "--disarm-on-exit",
        action="store_true",
        help="Disarm when script exits (overrides --no-disarm)",
    )
    p.add_argument("--throttle-pct", type=float, default=30.0)
    p.add_argument("--ramp-s", type=float, default=2.0)
    p.add_argument("--hold-s", type=float, default=2.0)
    p.add_argument("--hz", type=float, default=20.0)
    return p.parse_args()


def _read_param(mav: object, ts: int, tc: int, name: str) -> float | None:
    mav.mav.param_request_read_send(ts, tc, name.encode(), -1)
    deadline = time.time() + 4
    while time.time() < deadline:
        msg = mav.recv_match(type="PARAM_VALUE", blocking=True, timeout=0.3)
        if msg is None:
            continue
        pid = (
            msg.param_id.decode().rstrip("\x00")
            if isinstance(msg.param_id, bytes)
            else str(msg.param_id).rstrip("\x00")
        )
        if pid == name:
            return float(msg.param_value)
    return None


def pwm_from_pct(pct: float, rc_min: int = 1100, rc_max: int = 1900) -> int:
    pct = max(0.0, min(100.0, pct))
    return int(rc_min + max(1, rc_max - rc_min) * pct / 100.0)


def send_throttle_override(mav: object, ts: int, tc: int, throttle_pwm: int) -> None:
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


def _poll_handoff(
    handoff: OrinRcHandoff,
    mav: object,
    bridge: MavlinkBridge,
    ts: int,
    tc: int,
) -> None:
    if handoff.poll_mavlink(mav):
        if handoff.active:
            logger.info("ch%d -> Orin control", handoff.config.channel)
        else:
            logger.info("ch%d -> H12 control (override released)", handoff.config.channel)
            release_rc_overrides(mav, ts, tc)
    bridge.poll(timeout_s=0.0)


def _override_loop(
    handoff: OrinRcHandoff | None,
    mav: object,
    bridge: MavlinkBridge,
    ts: int,
    tc: int,
    duration_s: float,
    throttle_fn: object,
    dt: float,
) -> None:
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < duration_s:
        if handoff is not None:
            _poll_handoff(handoff, mav, bridge, ts, tc)
        else:
            bridge.poll(timeout_s=0.0)
        if handoff is None or handoff.active:
            send_throttle_override(mav, ts, tc, throttle_fn(time.perf_counter() - t0))
        time.sleep(dt)


def main() -> int:
    args = _parse()
    if (args.arm or args.wait_armed) and not args.i_know_props_are_on:
        logger.error("Refusing throttle test without --i-know-props-are-on")
        return 2
    if args.arm and args.wait_armed:
        logger.error("Use --arm or --wait-armed, not both")
        return 2

    pct = max(10.0, min(80.0, float(args.throttle_pct)))
    handoff = OrinRcHandoff(
        OrinRcHandoffConfig(
            channel=args.handoff_ch,
            press_threshold=args.handoff_threshold,
        )
    )

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
        bridge.close()
        return 0

    if not bridge.is_ardupilot():
        logger.error("ArduPilot only")
        bridge.close()
        return 1

    if not bridge.is_armed():
        if args.wait_armed:
            logger.info("Waiting for H12 ARM (F switch)... %.0fs", args.wait_timeout_s)
            deadline = time.perf_counter() + args.wait_timeout_s
            while time.perf_counter() < deadline:
                bridge.poll(timeout_s=0.2)
                if bridge.is_armed():
                    break
                time.sleep(0.1)
        elif args.arm:
            bridge.arm()
            time.sleep(1.0)
            bridge.poll(timeout_s=0.5)
        if not bridge.is_armed():
            logger.error("Not ARMED")
            bridge.close()
            return 1

    active_handoff: OrinRcHandoff | None = handoff
    if args.ch7_handoff:
        logger.info(
            "Press ch%d once for Orin (press again for H12)... %.0fs",
            args.handoff_ch,
            args.wait_timeout_s,
        )

        def _poll() -> None:
            bridge.poll(timeout_s=0.0)

        if not handoff.wait_first_orin(mav, args.wait_timeout_s, poll_cb=_poll):
            logger.error("Timeout: press ch%d to enable Orin", args.handoff_ch)
            bridge.close()
            return 1
        logger.info("Orin active — press ch%d again to return to H12", args.handoff_ch)
    else:
        logger.info("No ch7 handoff — Orin override active immediately")
        active_handoff = None

    rc_opts = _read_param(mav, ts, tc, "RC_OPTIONS")
    if rc_opts is not None and int(rc_opts) & 2:
        logger.error("RC_OPTIONS blocks override — run configure_f_arm_switch.py")
        bridge.close()
        return 1

    rc_min = int(_read_param(mav, ts, tc, "RC3_MIN") or 1100)
    rc_max = int(_read_param(mav, ts, tc, "RC3_MAX") or 1900)
    idle_pwm = rc_min
    target_pwm = pwm_from_pct(pct, rc_min, rc_max)
    dt = 1.0 / float(args.hz)

    logger.info("throttle ramp %d -> %d over %.1fs", idle_pwm, target_pwm, args.ramp_s)

    try:
        _override_loop(
            active_handoff,
            mav,
            bridge,
            ts,
            tc,
            args.ramp_s,
            lambda e: int(
                idle_pwm + min(1.0, e / max(args.ramp_s, 0.01)) * (target_pwm - idle_pwm)
            ),
            dt,
        )
        _override_loop(
            active_handoff,
            mav,
            bridge,
            ts,
            tc,
            args.hold_s,
            lambda _e: target_pwm,
            dt,
        )
        _override_loop(
            active_handoff,
            mav,
            bridge,
            ts,
            tc,
            args.ramp_s,
            lambda e: int(
                target_pwm - min(1.0, e / max(args.ramp_s, 0.01)) * (target_pwm - idle_pwm)
            ),
            dt,
        )
        if active_handoff is None or active_handoff.active:
            send_throttle_override(mav, ts, tc, idle_pwm)
    finally:
        release_rc_overrides(mav, ts, tc)
        bridge.restore_h12_passthrough(disarm=False)
        if bridge.is_armed() and args.disarm_on_exit:
            bridge.disarm()
        bridge.close()

    logger.info("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
