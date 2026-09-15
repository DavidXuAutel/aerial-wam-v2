#!/usr/bin/env python3
"""Live RC + ARM/DISARM dashboard for Pixhawk via MAVLink UDP (Orin bridge)."""
from __future__ import annotations

import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from pymavlink import mavutil

ARDUCOPTER_MODE_NAMES = {
    0: "STABILIZE",
    1: "ACRO",
    2: "ALT_HOLD",
    3: "AUTO",
    4: "GUIDED",
    5: "LOITER",
    6: "RTL",
    9: "LAND",
}

PX4_MODE_NAMES = {
    6: "POSITION_SLOW",
    16: "STABILIZED",
    65536: "MANUAL",
    131072: "ALTCTL",
    196608: "POSCTL",
    50593792: "OFFBOARD",
}

CHANNEL_LABELS = {
    1: "横滚 Roll (右杆左右)",
    2: "俯仰 Pitch (右杆上下)",
    3: "油门 Throttle (左杆上下)",
    4: "偏航 Yaw (左杆左右)",
    5: "E 拨杆 (飞行模式)",
    6: "F 开关 (ARM)",
    7: "Orin 按钮",
    8: "ch8",
}


class MavlinkState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.connected = False
        self.last_heartbeat = 0.0
        self.armed = False
        self.custom_mode = 0
        self.mode_name = "—"
        self.is_ardupilot = False
        self.channels: list[int] = [0] * 8
        self.rssi: int | None = None

    def update_heartbeat(self, msg: Any) -> None:
        with self.lock:
            self.connected = True
            self.last_heartbeat = time.time()
            self.armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
            self.is_ardupilot = int(msg.autopilot) == mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA
            self.custom_mode = int(msg.custom_mode)
            names = ARDUCOPTER_MODE_NAMES if self.is_ardupilot else PX4_MODE_NAMES
            self.mode_name = names.get(self.custom_mode, f"MODE_{self.custom_mode}")

    def update_rc(self, msg: Any) -> None:
        with self.lock:
            self.channels = [
                int(getattr(msg, f"chan{i}_raw", 0) or 0) for i in range(1, 9)
            ]

    def update_rssi(self, msg: Any) -> None:
        with self.lock:
            self.rssi = int(msg.rssi)

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            age = time.time() - self.last_heartbeat if self.last_heartbeat else None
            return {
                "connected": self.connected and age is not None and age < 3.0,
                "heartbeat_age_s": round(age, 2) if age is not None else None,
                "armed": self.armed,
                "arm_text": "ARMED" if self.armed else "DISARMED",
                "custom_mode": self.custom_mode,
                "mode_name": self.mode_name,
                "rssi": self.rssi,
                "channels": [
                    {
                        "ch": i,
                        "label": CHANNEL_LABELS.get(i, f"ch{i}"),
                        "value": v,
                        "pct": _pwm_pct(v),
                    }
                    for i, v in enumerate(self.channels, start=1)
                ],
            }


def _pwm_pct(v: int) -> float:
    v = max(1000, min(2000, v))
    return round((v - 1000) / 10.0, 1)


def mavlink_reader(state: MavlinkState, udp_port: int, stop: threading.Event) -> None:
    conn = mavutil.mavlink_connection(f"udp:0.0.0.0:{udp_port}")
    while not stop.is_set():
        msg = conn.recv_match(
            type=["HEARTBEAT", "RC_CHANNELS", "RADIO_STATUS"],
            blocking=True,
            timeout=1.0,
        )
        if msg is None:
            with state.lock:
                if state.last_heartbeat and time.time() - state.last_heartbeat > 3.0:
                    state.connected = False
            continue
        t = msg.get_type()
        if t == "HEARTBEAT" and msg.get_srcComponent() != 0:
            state.update_heartbeat(msg)
        elif t == "RC_CHANNELS":
            state.update_rc(msg)
        elif t == "RADIO_STATUS":
            state.update_rssi(msg)


HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>遥控器 / 飞控状态</title>
  <style>
    :root {
      --bg: #0f1419;
      --card: #1a2332;
      --text: #e7ecf3;
      --muted: #8b9cb3;
      --disarmed: #2ecc71;
      --armed: #e74c3c;
      --accent: #4da3ff;
      --bar-bg: #2a3548;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0; padding: 24px;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg); color: var(--text);
    }
    h1 { margin: 0 0 8px; font-size: 1.4rem; }
    .sub { color: var(--muted); margin-bottom: 20px; font-size: 0.9rem; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    @media (max-width: 800px) { .grid { grid-template-columns: 1fr; } }
    .card {
      background: var(--card); border-radius: 12px; padding: 16px 18px;
      border: 1px solid #2d3a4f;
    }
    .status-row { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
    .pill {
      padding: 10px 18px; border-radius: 999px; font-weight: 700;
      font-size: 1.1rem; letter-spacing: 0.04em;
    }
    .pill.disarmed { background: rgba(46,204,113,.18); color: var(--disarmed); border: 2px solid var(--disarmed); }
    .pill.armed { background: rgba(231,76,60,.18); color: var(--armed); border: 2px solid var(--armed); }
    .pill.offline { background: rgba(139,156,179,.12); color: var(--muted); border: 2px solid #445066; }
    .meta { color: var(--muted); font-size: 0.92rem; line-height: 1.6; }
    .meta strong { color: var(--text); }
    .channel { margin-bottom: 14px; }
    .ch-head { display: flex; justify-content: space-between; margin-bottom: 6px; font-size: 0.9rem; }
    .ch-name { color: var(--muted); }
    .ch-val { font-variant-numeric: tabular-nums; }
    .bar {
      height: 14px; background: var(--bar-bg); border-radius: 7px; position: relative; overflow: hidden;
    }
    .bar-fill {
      height: 100%; background: linear-gradient(90deg, #3d7eff, #5cc8ff);
      border-radius: 7px; transition: width .12s ease;
    }
    .bar-center {
      position: absolute; top: 0; bottom: 0; width: 2px; left: 50%;
      background: rgba(255,255,255,.35);
    }
    .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-right: 6px; }
    .dot.ok { background: #2ecc71; }
    .dot.bad { background: #e74c3c; }
  </style>
</head>
<body>
  <h1>遥控器 / 飞控状态</h1>
  <div class="sub">MAVLink UDP · 动杆/开关可实时更新</div>
  <div class="grid">
    <div class="card">
      <div class="status-row">
        <div id="arm-pill" class="pill offline">OFFLINE</div>
        <div class="meta" id="link-meta">连接中…</div>
      </div>
      <div class="meta" style="margin-top:14px" id="flight-meta"></div>
    </div>
    <div class="card">
      <div class="meta">
        <strong>H12 键位</strong><br>
        ch1 右杆左右 · ch2 右杆上下 · ch3 左杆油门 · ch4 左杆偏航<br>
        ch5 E 开关 · ch6 F 开关
      </div>
    </div>
  </div>
  <div class="card" style="margin-top:16px">
    <h2 style="margin:0 0 14px;font-size:1rem">通道</h2>
    <div id="channels"></div>
  </div>
  <script>
    const channelsEl = document.getElementById('channels');
    const armPill = document.getElementById('arm-pill');
    const linkMeta = document.getElementById('link-meta');
    const flightMeta = document.getElementById('flight-meta');

    function renderChannels(channels) {
      channelsEl.innerHTML = channels.map(ch => `
        <div class="channel">
          <div class="ch-head">
            <span class="ch-name">${ch.label}</span>
            <span class="ch-val">${ch.value} (${ch.pct}%)</span>
          </div>
          <div class="bar">
            <div class="bar-center"></div>
            <div class="bar-fill" style="width:${ch.pct}%"></div>
          </div>
        </div>`).join('');
    }

    async function tick() {
      try {
        const r = await fetch('/api/status');
        const d = await r.json();
        if (!d.connected) {
          armPill.className = 'pill offline';
          armPill.textContent = 'OFFLINE';
          linkMeta.innerHTML = '<span class="dot bad"></span>未收到飞控心跳（检查 Orin 桥接）';
        } else if (d.armed) {
          armPill.className = 'pill armed';
          armPill.textContent = 'ARMED 已解锁';
          linkMeta.innerHTML = '<span class="dot ok"></span>已连接 · 电机可转';
        } else {
          armPill.className = 'pill disarmed';
          armPill.textContent = 'DISARMED 已上锁';
          linkMeta.innerHTML = '<span class="dot ok"></span>已连接 · 电机禁止';
        }
        flightMeta.innerHTML =
          `<strong>飞行模式</strong> ${d.mode_name} (custom_mode=${d.custom_mode})<br>` +
          (d.rssi != null ? `<strong>RC RSSI</strong> ${d.rssi}<br>` : '') +
          `<strong>心跳</strong> ${d.heartbeat_age_s}s 前`;
        renderChannels(d.channels);
      } catch (e) {
        armPill.className = 'pill offline';
        armPill.textContent = 'ERROR';
      }
      setTimeout(tick, 200);
    }
    tick();
  </script>
</body>
</html>
"""


def make_handler(state: MavlinkState):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            if self.path == "/api/status":
                body = json.dumps(state.snapshot()).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path in ("/", "/index.html"):
                body = HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_error(404)

    return Handler


def main() -> None:
    p = argparse.ArgumentParser(description="RC + ARM/DISARM web dashboard")
    p.add_argument("--udp-port", type=int, default=14550)
    p.add_argument("--http-port", type=int, default=8765)
    args = p.parse_args()

    state = MavlinkState()
    stop = threading.Event()
    threading.Thread(
        target=mavlink_reader, args=(state, args.udp_port, stop), daemon=True
    ).start()

    server = ThreadingHTTPServer(("127.0.0.1", args.http_port), make_handler(state))
    print(f"Dashboard: http://127.0.0.1:{args.http_port}")
    print(f"MAVLink UDP listen: {args.udp_port}")
    print("Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        stop.set()
        server.shutdown()


if __name__ == "__main__":
    main()
