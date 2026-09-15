#!/usr/bin/env python3
"""Full Orin bench integration test (props OFF, battery charged).

  python -m experiments.aerial.scripts.orin_full_bench_test

Phases:
  1. MAVLink + battery + H12 reset
  2. ch8/ch9 recording gate (30s window)
  3. ch7 Orin throttle handoff (user ARM + press ch7)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np


def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Orin full bench test")
    p.add_argument("--port", default="/dev/ttyACM0")
    p.add_argument("--baud", type=int, default=57600)
    p.add_argument("--record-wait-s", type=float, default=35.0)
    p.add_argument("--skip-throttle", action="store_true")
    p.add_argument("--skip-record", action="store_true")
    return p.parse_args()


def _fake_obs(bridge: object) -> SimpleNamespace:
    bgr = np.zeros((480, 640, 3), dtype=np.uint8)
    return SimpleNamespace(
        position=np.zeros(3),
        yaw=0.0,
        state=np.zeros(7, dtype=np.float32),
        rgb=None,
        info={
            "bgr_native": bgr,
            "mavlink": bridge.status_dict(),
            "corpus": {"scene": "bench_test"},
        },
    )


def _phase_mavlink(args: argparse.Namespace) -> tuple[object, object]:
    from pymavlink import mavutil

    from experiments.aerial.rl.env.mavlink_bridge import MavlinkBridge, MavlinkBridgeConfig

    print("\n=== [1/3] MAVLink + battery + H12 reset ===")
    bridge = MavlinkBridge(MavlinkBridgeConfig(port=args.port, baud=int(args.baud)))
    bridge.connect(timeout_s=12)
    bridge.restore_h12_passthrough(disarm=False)
    time.sleep(0.5)

    bat_v = None
    armed = False
    end = time.time() + 10.0
    while time.time() < end:
        msg = bridge._mav.recv_match(blocking=True, timeout=0.3)
        if msg is None:
            continue
        t = msg.get_type()
        if t == "HEARTBEAT":
            armed = bool(msg.base_mode & 0x80)
        elif t == "BATTERY_STATUS" and msg.voltages and msg.voltages[0] not in (0, 65535):
            bat_v = msg.voltages[0] / 1000.0
        elif t == "SYS_STATUS" and msg.voltage_battery not in (0, 65535):
            bat_v = msg.voltage_battery / 1000.0
        if bat_v is not None:
            break
    if not armed:
        armed = bridge.is_armed()

    rc = bridge.rc_pwm_dict()
    mode = bridge.flight_mode_info().get("mode_name", "?")
    print(f"  mode={mode} armed={armed} battery={bat_v}V")
    print(f"  RC ch3={rc.get('ch3','?')} ch5={rc.get('ch5','?')} ch6={rc.get('ch6','?')}")
    if bat_v is None:
        print("  WARN: no battery telemetry (continuing)")
    elif bat_v < 10.0:
        print(f"  FAIL: battery too low ({bat_v}V)")
        sys.exit(1)
    print("  PASS")
    return bridge, mavutil


def _phase_record(args: argparse.Namespace, bridge: object) -> Path | None:
    from experiments.aerial.deploy.orin_deploy_recorder import OrinDeployRecorder
    from experiments.aerial.rl.env.orin_rc_handoff import RcRecordGate, RcRecordGateConfig

    print(f"\n=== [2/3] ch8/ch9 recording ({args.record_wait_s:.0f}s) ===")
    print("  Press ch8 = START record, ch9 = STOP record")
    gate = RcRecordGate(RcRecordGateConfig())
    base = Path.home() / "aerial-wam-v2" / "artifacts" / "orin_deploy"
    manifest = {"test": "orin_full_bench_test", "phase": "record_gate"}
    recorder = None
    run_dir: Path | None = None
    t_end = time.time() + float(args.record_wait_s)
    while time.time() < t_end:
        bridge.poll(timeout_s=0.05)
        event = gate.update_rc_dict(bridge.rc_pwm_dict())
        if event == "start":
            if recorder is not None:
                recorder.close()
            recorder = OrinDeployRecorder.open_run(base, manifest)
            run_dir = recorder.root
            print(f"  >>> RECORD START {run_dir}")
        elif event == "stop" and recorder is not None:
            recorder.close()
            print(f"  >>> RECORD STOP {run_dir}")
            recorder = None
        if recorder is not None and gate.active:
            recorder.record_step(_fake_obs(bridge), step_info={"phase": "bench_test"})
        time.sleep(0.05)

    if recorder is not None:
        recorder.close()

    if run_dir is None or not run_dir.is_dir():
        print("  SKIP: no ch8 press detected (no recording run)")
        return None

    frames = list((run_dir / "frames").glob("*.jpg"))
    lines = (run_dir / "traj.jsonl").read_text(encoding="utf-8").strip().splitlines()
    print(f"  run={run_dir.name} frames={len(frames)} traj_lines={len(lines)}")
    if frames and lines:
        print("  PASS")
    else:
        print("  FAIL: empty recording")
    return run_dir


def _phase_throttle(args: argparse.Namespace) -> bool:
    print("\n=== [3/3] ch7 Orin throttle handoff ===")
    print("  Steps: throttle LOW -> ch6 F ARM -> run script -> press ch7 once")
    print("  Props OFF. Script ramps throttle ~15% for 2s.")
    cmd = [
        sys.executable,
        "-m",
        "experiments.aerial.scripts.orin_mavlink_throttle",
        "--wait-armed",
        "--ch7-handoff",
        "--throttle-pct",
        "15",
        "--hold-s",
        "2",
        "--ramp-s",
        "2",
        "--i-know-props-are-on",
        "--port",
        args.port,
        "--wait-timeout-s",
        "90",
    ]
    print("  $", " ".join(cmd))
    rc = subprocess.call(cmd)
    if rc == 0:
        print("  PASS")
        return True
    print(f"  FAIL: exit code {rc}")
    return False


def main() -> int:
    args = _parse()
    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    results: dict[str, str] = {}
    bridge, _mav = _phase_mavlink(args)
    results["mavlink"] = "pass"

    if not args.skip_record:
        run_dir = _phase_record(args, bridge)
        results["record"] = "pass" if run_dir else "skip"
    else:
        results["record"] = "skip"

    bridge.restore_h12_passthrough(disarm=False)
    bridge.close()

    if not args.skip_throttle:
        results["throttle"] = "pass" if _phase_throttle(args) else "fail"
    else:
        results["throttle"] = "skip"

    print("\n=== SUMMARY ===")
    for k, v in results.items():
        print(f"  {k}: {v}")
    summary_path = Path.home() / "aerial-wam-v2" / "artifacts" / "orin_deploy" / "bench_test_summary.json"
    summary_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"  written: {summary_path}")
    return 0 if all(v in ("pass", "skip") for v in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
