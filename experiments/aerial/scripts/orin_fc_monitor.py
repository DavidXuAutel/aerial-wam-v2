#!/usr/bin/env python3
"""Minimal FC status on Orin terminal — no QGC / Mission Planner needed.

  ssh orin-direct
  cd ~/aerial-wam-v2
  python -m experiments.aerial.scripts.orin_fc_monitor

Shows flight mode, ARM state, and ch5/ch6/ch7. Ctrl+C to quit.
"""
from __future__ import annotations

import argparse
import sys
import time

from pymavlink import mavutil

ARDUCOPTER_MODES = {
    0: "STABILIZE (自稳)",
    1: "ACRO (特技)",
    2: "ALT_HOLD",
    4: "GUIDED ⚠室内勿用",
    5: "LOITER ⚠室内勿用",
    9: "LAND ⚠无法解锁",
}

CH_LABELS = {
    5: "ch5 E拨杆=模式",
    6: "ch6 F=ARM",
    7: "ch7 Orin切换(按一下)",
}


def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Orin terminal FC monitor (no GCS)")
    p.add_argument("--port", default="/dev/ttyACM0")
    p.add_argument("--baud", type=int, default=57600)
    p.add_argument("--hz", type=float, default=2.0)
    return p.parse_args()


def _mode_hint(ch5: int) -> str:
    if ch5 < 1200:
        return "→ 应为 STABILIZE"
    if ch5 > 1700:
        return "→ 应为 ACRO"
    return "→ 中位，确认映射"


def main() -> int:
    args = _parse()
    m = mavutil.mavlink_connection(
        args.port, baud=args.baud, source_system=255, source_component=190
    )
    if m.wait_heartbeat(timeout=10) is None:
        print(f"ERROR: no heartbeat on {args.port}")
        return 1

    print("Orin FC 监视器（无需地面站）— Ctrl+C 退出\n")
    dt = 1.0 / max(args.hz, 0.5)
    mode_id = 0
    armed = False
    channels = [0] * 8
    motor_pwm = [0] * 4
    last_statustext = ""

    try:
        while True:
            msg = m.recv_match(blocking=True, timeout=dt)
            if msg is None:
                continue
            t = msg.get_type()
            if t == "HEARTBEAT":
                mode_id = int(msg.custom_mode)
                armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
            elif t == "RC_CHANNELS":
                channels = [int(getattr(msg, f"chan{i}_raw", 0) or 0) for i in range(1, 9)]
            elif t == "SERVO_OUTPUT_RAW":
                motor_pwm = [
                    int(getattr(msg, f"servo{i}_raw", 0) or 0) for i in range(1, 5)
                ]
            elif t == "STATUSTEXT":
                txt = msg.text
                if isinstance(txt, bytes):
                    txt = txt.decode(errors="ignore")
                last_statustext = str(txt).strip()

            if t not in ("HEARTBEAT", "RC_CHANNELS", "SERVO_OUTPUT_RAW", "STATUSTEXT"):
                continue

            mode_name = ARDUCOPTER_MODES.get(mode_id, f"MODE_{mode_id}")
            ch3, ch5, ch6, ch7 = channels[2], channels[4], channels[5], channels[6]
            if armed:
                arm_text = ">>> 已解锁 ARMED <<<  (有解锁音=正常)"
                if ch3 < 1150:
                    throttle_hint = "油门最低 — 电机不转/怠速是正常的，请缓慢推油门"
                elif ch3 < 1400:
                    throttle_hint = "油门偏低 — 电机应开始转"
                else:
                    throttle_hint = "油门已推 — 电机应明显转动"
            else:
                arm_text = "未解锁 DISARMED"
                throttle_hint = (
                    "解锁前：油门必须最低 (<1150)，再 ch6 F 上位"
                    if ch3 >= 1150
                    else "油门最低 OK — ch6 F 上位可解锁"
                )
            motor_hint = (
                f"M1–M4 PWM: {motor_pwm}  (未解锁时约 1000；解锁推油门后应 >1000)"
            )
            lines = [
                "\033[2J\033[H",
                "=== Pixhawk 状态 (H12 + Orin，无地面站) ===",
                f"飞行模式: {mode_name}  (id={mode_id})",
                f"解锁状态: {arm_text}",
                "",
                "遥控器:",
                f"  ch5 {ch5:4d}  {CH_LABELS[5]}  {_mode_hint(ch5)}",
                f"  ch6 {ch6:4d}  {CH_LABELS[6]}  ({'上位ARM' if ch6 > 1700 else '下位DISARM' if ch6 < 1200 else '中间位'})",
                f"  ch3 {ch3:4d}  油门 — {throttle_hint}",
                f"  ch7 {ch7:4d}  {CH_LABELS[7]}",
                "",
                motor_hint,
                "",
                "说明: 解锁音 ≠ 电机立刻转。STABILIZE/ACRO 下油门最低时电机通常不转。",
                "      ch8=开始录 ch9=停录 | ch7=Orin/H12 切换",
            ]
            if last_statustext:
                lines.append(f"飞控消息: {last_statustext}")
            print("\n".join(lines), flush=True)
    except KeyboardInterrupt:
        print("\n退出")
    return 0


if __name__ == "__main__":
    sys.exit(main())
