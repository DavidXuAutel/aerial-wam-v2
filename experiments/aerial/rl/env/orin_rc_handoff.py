"""RC momentary buttons: ch7 Orin handoff, ch8/ch9 record start/stop."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal


@dataclass
class RcRisingEdgeConfig:
    press_threshold: int = 1600
    debounce_s: float = 0.25


class RcRisingEdge:
    """Detect one button press (low → high crossing ``press_threshold``)."""

    def __init__(self, config: RcRisingEdgeConfig | None = None) -> None:
        self.config = config or RcRisingEdgeConfig()
        self._last_pwm: int | None = None
        self._last_edge_t = 0.0

    def reset(self) -> None:
        self._last_pwm = None
        self._last_edge_t = 0.0

    def update_pwm(self, pwm: int | None) -> bool:
        if pwm is None:
            return False
        thr = self.config.press_threshold
        last = self._last_pwm
        self._last_pwm = int(pwm)
        if last is None:
            return False
        rising = last < thr and int(pwm) >= thr
        if not rising:
            return False
        now = time.monotonic()
        if now - self._last_edge_t < self.config.debounce_s:
            return False
        self._last_edge_t = now
        return True


@dataclass
class RcRecordGateConfig:
    start_channel: int = 8
    stop_channel: int = 9
    press_threshold: int = 1600
    debounce_s: float = 0.25


class RcRecordGate:
    """ch8 rising edge → start recording; ch9 rising edge → stop."""

    def __init__(self, config: RcRecordGateConfig | None = None) -> None:
        self.config = config or RcRecordGateConfig()
        edge_cfg = RcRisingEdgeConfig(
            press_threshold=self.config.press_threshold,
            debounce_s=self.config.debounce_s,
        )
        self._start = RcRisingEdge(edge_cfg)
        self._stop = RcRisingEdge(edge_cfg)
        self.active = False

    def reset(self) -> None:
        self.active = False
        self._start.reset()
        self._stop.reset()

    def update_rc_dict(self, rc: dict[str, int]) -> Literal["start", "stop", "none"]:
        start_pwm = rc.get(f"ch{self.config.start_channel}")
        stop_pwm = rc.get(f"ch{self.config.stop_channel}")
        if self._stop.update_pwm(stop_pwm):
            self.active = False
            return "stop"
        if self._start.update_pwm(start_pwm):
            self.active = True
            return "start"
        return "none"


@dataclass
class OrinRcHandoffConfig:
    channel: int = 7
    press_threshold: int = 1600
    debounce_s: float = 0.25


class OrinRcHandoff:
    """Toggle Orin active on each ch7 button press (rising edge only).

    Default: H12 control (``active=False``). Each press flips state.
    Does not require holding the button.
    """

    def __init__(self, config: OrinRcHandoffConfig | None = None) -> None:
        self.config = config or OrinRcHandoffConfig()
        self.active = False
        self._last_pwm: int | None = None
        self._last_toggle_t = 0.0

    def reset(self) -> None:
        self.active = False
        self._last_pwm = None
        self._last_toggle_t = 0.0

    @staticmethod
    def _rc_pwm(msg: object, ch: int) -> int | None:
        if ch < 1 or ch > 18:
            return None
        raw = getattr(msg, f"chan{ch}_raw", None)
        if raw is None:
            return None
        return int(raw)

    def update_pwm(self, pwm: int) -> bool:
        """Feed one RC sample. Returns True if ``active`` toggled."""
        thr = self.config.press_threshold
        last = self._last_pwm
        self._last_pwm = pwm
        if last is None:
            return False
        rising = last < thr and pwm >= thr
        if not rising:
            return False
        now = time.monotonic()
        if now - self._last_toggle_t < self.config.debounce_s:
            return False
        self.active = not self.active
        self._last_toggle_t = now
        return True

    def update_rc_message(self, msg: object) -> bool:
        pwm = self._rc_pwm(msg, self.config.channel)
        if pwm is None:
            return False
        return self.update_pwm(pwm)

    def poll_mavlink(self, mav: object) -> bool:
        """Non-blocking: process one RC_CHANNELS message if present."""
        msg = mav.recv_match(type="RC_CHANNELS", blocking=False)
        if msg is None:
            return False
        return self.update_rc_message(msg)

    def wait_first_orin(
        self, mav: object, timeout_s: float, poll_cb: object | None = None
    ) -> bool:
        """Block until first rising edge sets ``active=True``."""
        if self.active:
            return True
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            msg = mav.recv_match(type="RC_CHANNELS", blocking=True, timeout=0.2)
            if msg is not None:
                if self.update_rc_message(msg) and self.active:
                    return True
                if poll_cb is not None:
                    poll_cb()
            elif poll_cb is not None:
                poll_cb()
        return self.active


_NO_OVERRIDE = 65535


def release_rc_overrides(mav: object, ts: int, tc: int, repeats: int = 5) -> None:
    """Release MAVLink RC override — must use UINT16_MAX per channel, not 0."""
    for _ in range(repeats):
        mav.mav.rc_channels_override_send(
            ts,
            tc,
            _NO_OVERRIDE,
            _NO_OVERRIDE,
            _NO_OVERRIDE,
            _NO_OVERRIDE,
            _NO_OVERRIDE,
            _NO_OVERRIDE,
            _NO_OVERRIDE,
            _NO_OVERRIDE,
        )
        time.sleep(0.05)
