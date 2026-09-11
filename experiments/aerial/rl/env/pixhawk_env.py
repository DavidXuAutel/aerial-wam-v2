"""``PixhawkDroneEnv`` — real-aircraft env with MAVLink + companion camera.

Mirrors the ``AirSimDroneEnv`` surface used by Phase-2 / vgoal eval:
``reset / step / observe / close``. RGB comes from a local camera; pose and
velocity come from PX4 ``LOCAL_POSITION_NED`` + ``ATTITUDE``.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np

from experiments.aerial.rl.env.action import body_delta_limits, clip_body_delta
from experiments.aerial.rl.env.mavlink_bridge import MavlinkBridge, MavlinkBridgeConfig
from experiments.aerial.rl.env.obs import Observation

logger = logging.getLogger(__name__)


@dataclass
class PixhawkEnvConfig:
    mavlink_port: str = "/dev/ttyACM0"
    mavlink_baud: int = 115200
    step_hz: float = 30.0
    camera_device: str = "0"
    capture_w: int = 1280
    capture_h: int = 720
    capture_fps: int = 30
    wam_encode_size: int = 224
    offboard_on_reset: bool = False
    arm_on_reset: bool = False
    offboard_warmup_s: float = 3.0
    mock_camera: bool = False


class PixhawkDroneEnv:
    """MAVLink velocity-step env for Orin + Pixhawk deploy."""

    def __init__(self, config: Optional[PixhawkEnvConfig] = None, **kwargs: Any) -> None:
        self.config = config or PixhawkEnvConfig(**kwargs)
        self._bridge = MavlinkBridge(
            MavlinkBridgeConfig(
                port=self.config.mavlink_port,
                baud=self.config.mavlink_baud,
                stream_hz=self.config.step_hz,
            )
        )
        self._camera: Any = None
        self._goal: Optional[np.ndarray] = None
        self._t0 = time.perf_counter()
        self._offboard_active = False

    @property
    def goal(self) -> Optional[np.ndarray]:
        return self._goal

    def _open_camera(self) -> None:
        if self._camera is not None:
            return
        if self.config.mock_camera:
            from experiments.aerial.deploy.real_camera import MockCamera

            self._camera = MockCamera(wam_size=self.config.wam_encode_size)
        else:
            from experiments.aerial.deploy.real_camera import RealCamera, RealCameraConfig

            self._camera = RealCamera(
                RealCameraConfig(
                    device=str(self.config.camera_device),
                    width=int(self.config.capture_w),
                    height=int(self.config.capture_h),
                    wam_size=int(self.config.wam_encode_size),
                    fps=int(self.config.capture_fps),
                )
            )
        self._camera.open()

    def reset(self, episode: Optional[Dict[str, Any]] = None) -> Observation:
        if not self._bridge.connected:
            self._bridge.connect()
        self._open_camera()

        self._goal = None
        if episode is not None:
            positions = np.asarray(episode["pos"], dtype=np.float64)
            self._goal = positions[-1].copy()

        logger.info(
            "Pixhawk reset offboard=%s arm=%s warmup=%.1fs",
            self.config.offboard_on_reset,
            self.config.arm_on_reset,
            self.config.offboard_warmup_s,
        )
        self._bridge.stream_hover(self.config.offboard_warmup_s)

        if self.config.offboard_on_reset:
            self._bridge.set_mode_offboard()
            self._offboard_active = True
            self._bridge.stream_hover(0.5)
        else:
            self._offboard_active = False

        if self.config.arm_on_reset:
            self._bridge.arm()
            time.sleep(0.5)

        self._t0 = time.perf_counter()
        return self.observe()

    def observe(self) -> Observation:
        self._bridge.poll(timeout_s=0.05)
        state = self._bridge.observe_state(timeout_s=0.2)
        bgr, rgb = self._camera.read()
        info: Dict[str, Any] = {"capture_shape": list(bgr.shape), "bgr_native": bgr}
        if self._goal is not None:
            info["goal"] = self._goal.copy()
        return Observation(
            rgb=rgb,
            state=state,
            collided=False,
            depth=None,
            imu={},
            t=time.perf_counter() - self._t0,
            info=info,
        )

    def step(self, action: np.ndarray) -> tuple[Observation, Dict[str, Any]]:
        dt = 1.0 / float(self.config.step_hz)
        t0 = time.perf_counter()
        cmd = clip_body_delta(action, body_delta_limits(dt))
        state = self._bridge.observe_state(timeout_s=0.05)
        yaw = float(state[6])
        vx, vy, vz_ned, yaw_rate_deg = self._bridge.send_body_delta(cmd, yaw, dt)

        remaining = dt - (time.perf_counter() - t0)
        if remaining > 0:
            time.sleep(remaining)
        obs = self.observe()
        info = {
            "cmd": cmd.tolist(),
            "vx": vx,
            "vy": vy,
            "vz_ned": vz_ned,
            "yaw_rate_deg": yaw_rate_deg,
            "offboard": self._offboard_active,
            "armed": self._bridge.is_armed(),
        }
        return obs, info

    def close(self) -> None:
        try:
            if self._bridge.connected:
                self._bridge.stream_hover(0.5)
                if self._bridge.is_armed():
                    self._bridge.disarm()
        except Exception:  # noqa: BLE001
            pass
        self._bridge.close()
        if self._camera is not None:
            try:
                self._camera.close()
            except Exception:  # noqa: BLE001
                pass
        self._camera = None

    def __enter__(self) -> "PixhawkDroneEnv":
        return self

    def __exit__(self, *exc: Any) -> bool:
        self.close()
        return False
