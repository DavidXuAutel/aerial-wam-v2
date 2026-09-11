"""MAVLink bridge for Pixhawk / PX4 companion-computer control.

Maps PX4 ``LOCAL_POSITION_NED`` + ``ATTITUDE`` into the same +up world
``state`` vector ``AirSimDroneEnv.observe_state`` uses::

    [x, y, z_up, vx, vy, vz_up, yaw]

Offboard velocity setpoints use NED (``vx_n, vy_e, vz_down``) per PX4.
"""
from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

try:
    from pymavlink import mavutil
    from pymavlink.dialects.v20 import common as mavlink
except ImportError:  # pragma: no cover - optional on sim-only hosts
    mavutil = None  # type: ignore
    mavlink = None  # type: ignore


def ned_to_wam_state(
    x_n: float,
    y_e: float,
    z_d: float,
    vx_n: float,
    vy_e: float,
    vz_d: float,
    yaw: float,
) -> np.ndarray:
    """PX4 local NED → WAM ``Observation.state`` (+up z, same xy as AirSim env)."""
    return np.array(
        [x_n, y_e, -z_d, vx_n, vy_e, -vz_d, yaw],
        dtype=np.float32,
    )


def velocity_mask_ignore_position() -> int:
    """``SET_POSITION_TARGET_LOCAL_NED`` mask: velocity + yaw_rate only."""
    if mavlink is None:
        raise ImportError("pymavlink is required for mavlink_bridge")
    return (
        mavlink.POSITION_TARGET_TYPEMASK_X_IGNORE
        | mavlink.POSITION_TARGET_TYPEMASK_Y_IGNORE
        | mavlink.POSITION_TARGET_TYPEMASK_Z_IGNORE
        | mavlink.POSITION_TARGET_TYPEMASK_AX_IGNORE
        | mavlink.POSITION_TARGET_TYPEMASK_AY_IGNORE
        | mavlink.POSITION_TARGET_TYPEMASK_AZ_IGNORE
        | mavlink.POSITION_TARGET_TYPEMASK_YAW_IGNORE
    )


@dataclass
class MavlinkBridgeConfig:
    port: str = "/dev/ttyACM0"
    baud: int = 115200
    source_system: int = 255
    source_component: int = 190
    stream_hz: float = 30.0


class MavlinkBridge:
    """Thin PX4 MAVLink helper for Offboard velocity + state readback."""

    def __init__(self, config: Optional[MavlinkBridgeConfig] = None) -> None:
        if mavutil is None:
            raise ImportError("pymavlink is required; pip install pymavlink pyserial")
        self.config = config or MavlinkBridgeConfig()
        self._mav: Any = None
        self._last_local: Optional[Any] = None
        self._last_attitude: Optional[Any] = None
        self._last_heartbeat: Optional[Any] = None

    @property
    def connected(self) -> bool:
        return self._mav is not None

    @property
    def target_system(self) -> int:
        return int(self._mav.target_system) if self._mav is not None else 0

    @property
    def target_component(self) -> int:
        return int(self._mav.target_component) if self._mav is not None else 0

    def connect(self, timeout_s: float = 10.0) -> None:
        self._mav = mavutil.mavlink_connection(
            self.config.port,
            baud=self.config.baud,
            source_system=self.config.source_system,
            source_component=self.config.source_component,
        )
        logger.info("Waiting heartbeat on %s ...", self.config.port)
        hb = self._mav.wait_heartbeat(timeout=timeout_s)
        if hb is None:
            raise TimeoutError(f"No MAVLink heartbeat on {self.config.port}")
        logger.info(
            "Heartbeat sys=%s comp=%s autopilot=%s type=%s",
            self._mav.target_system,
            self._mav.target_component,
            hb.autopilot,
            hb.type,
        )
        self._last_heartbeat = hb

    def close(self) -> None:
        if self._mav is not None:
            try:
                self._mav.close()
            except Exception:  # noqa: BLE001
                pass
        self._mav = None

    def poll(self, timeout_s: float = 0.0) -> None:
        """Drain incoming MAVLink and cache pose/attitude."""
        if self._mav is None:
            raise RuntimeError("not connected")
        deadline = time.perf_counter() + max(0.0, timeout_s)
        while True:
            remain = deadline - time.perf_counter()
            if timeout_s > 0 and remain <= 0:
                break
            msg = self._mav.recv_match(blocking=timeout_s > 0, timeout=max(remain, 0.0))
            if msg is None:
                break
            t = msg.get_type()
            if t == "LOCAL_POSITION_NED":
                self._last_local = msg
            elif t == "ATTITUDE":
                self._last_attitude = msg
            elif t == "HEARTBEAT":
                self._last_heartbeat = msg

    def is_armed(self) -> bool:
        if self._last_heartbeat is None:
            self.poll(timeout_s=0.5)
        if self._last_heartbeat is None:
            return False
        return bool(self._last_heartbeat.base_mode & mavlink.MAV_MODE_FLAG_SAFETY_ARMED)

    def observe_state(self, timeout_s: float = 1.0) -> np.ndarray:
        """Return WAM-compatible ``[x,y,z,vx,vy,vz,yaw]`` or zeros if stale."""
        self.poll(timeout_s=timeout_s)
        yaw = float(self._last_attitude.yaw) if self._last_attitude is not None else 0.0
        if self._last_local is not None:
            loc = self._last_local
            return ned_to_wam_state(
                float(loc.x),
                float(loc.y),
                float(loc.z),
                float(loc.vx),
                float(loc.vy),
                float(loc.vz),
                yaw,
            )
        return np.zeros(7, dtype=np.float32)

    def send_velocity_ned(
        self,
        vx_n: float,
        vy_e: float,
        vz_d: float,
        yaw_rate_rad_s: float = 0.0,
    ) -> None:
        """Stream one Offboard velocity setpoint (LOCAL_NED frame)."""
        if self._mav is None:
            raise RuntimeError("not connected")
        self._mav.mav.set_position_target_local_ned_send(
            0,
            self.target_system,
            self.target_component,
            mavlink.MAV_FRAME_LOCAL_NED,
            velocity_mask_ignore_position(),
            0.0,
            0.0,
            0.0,
            float(vx_n),
            float(vy_e),
            float(vz_d),
            0.0,
            0.0,
            0.0,
            0.0,
            float(yaw_rate_rad_s),
        )

    def send_hover(self) -> None:
        self.send_velocity_ned(0.0, 0.0, 0.0, 0.0)

    def send_body_delta(self, delta: np.ndarray, yaw: float, dt: float) -> Tuple[float, float, float, float]:
        """WAM body delta → PX4 NED velocity setpoint."""
        from experiments.aerial.rl.env.action import body_delta_to_velocity_ned

        vx, vy, vz_ned, yaw_rate_deg = body_delta_to_velocity_ned(delta, yaw, dt)
        self.send_velocity_ned(vx, vy, vz_ned, math.radians(yaw_rate_deg))
        return vx, vy, vz_ned, yaw_rate_deg

    def stream_hover(self, duration_s: float) -> int:
        """Send zero-velocity setpoints at ``stream_hz`` for ``duration_s``."""
        dt = 1.0 / float(self.config.stream_hz)
        n = 0
        t_end = time.perf_counter() + duration_s
        while time.perf_counter() < t_end:
            t0 = time.perf_counter()
            self.send_hover()
            self.poll(timeout_s=0.0)
            n += 1
            sleep_s = dt - (time.perf_counter() - t0)
            if sleep_s > 0:
                time.sleep(sleep_s)
        return n

    def set_mode_offboard(self) -> None:
        if self._mav is None:
            raise RuntimeError("not connected")
        mapping = getattr(self._mav, "mode_mapping_px4", None)
        if callable(mapping):
            px4_modes = mapping()
            mode_id = px4_modes.get("OFFBOARD") if px4_modes else None
            if mode_id is not None:
                self._mav.set_mode(mode_id)
                return
        self._mav.set_mode("OFFBOARD")

    def disarm(self) -> None:
        if self._mav is None:
            raise RuntimeError("not connected")
        self._mav.mav.command_long_send(
            self.target_system,
            self.target_component,
            mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
        )

    def arm(self) -> None:
        if self._mav is None:
            raise RuntimeError("not connected")
        self._mav.mav.command_long_send(
            self.target_system,
            self.target_component,
            mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            1,
            0,
            0,
            0,
            0,
            0,
            0,
        )

    def status_dict(self) -> Dict[str, Any]:
        st = self.observe_state(timeout_s=0.2)
        return {
            "armed": self.is_armed(),
            "state": st.tolist(),
            "port": self.config.port,
            "target_system": self.target_system,
        }
