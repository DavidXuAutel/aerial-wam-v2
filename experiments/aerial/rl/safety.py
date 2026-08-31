"""Hard safety shield (spec §2#6, §4.5) — interface + null stub.

The shield sits ABOVE the learned policy: if inflated predicted depth ``D̂``,
time-to-contact ``τ``, or world-model collision probability ``p_coll`` breaches a
threshold, it overrides the policy's action with a conservative one (brake /
hover / retreat). It is a *hard* override, not a learned behaviour — so it lives
outside the RL graph.

Only the contract is fixed here. ``NullSafetyShield`` never overrides (V0/V1
default). A real ``DepthTauShield`` is deferred until the perception heads that
produce ``D̂`` / ``τ`` exist (V2+); ``ThresholdSafetyShield`` shows the intended
trigger wiring against fields that may not be populated yet.

**Three-zone deploy (2026-08-23)**: ``ThreeZoneSpeedShield`` replaces the single
3 m depth latch with a graduated speed governor (8/5/1.5 m @ 2/1/0.2 m/s).
τ emergencies still latch + retreat; ``p_coll`` latch is vetoed when forward
clearance exceeds L1 (false WM collision while corridor is open).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, runtime_checkable

import numpy as np

from experiments.aerial.rl.env.action import MAX_BODY_VELOCITY, clip_body_delta
from experiments.aerial.rl.env.obs import Observation
from experiments.aerial.rl.three_zone import (
    ThreeZoneSpec,
    engage_outer_for_speed,
    planned_speed_m_s,
    resolve_v_ref_m_s,
)
from experiments.aerial.rl.tau_predictor import (
    DEFAULT_MIN_CLOSING_M_S,
    closing_speed_m_s,
)


@runtime_checkable
class SafetyShield(Protocol):
    def should_override(self, obs: Observation, wm_out: Optional[Any] = None) -> bool: ...

    def override_action(self, obs: Observation) -> np.ndarray: ...


class NullSafetyShield:
    """No-op shield: never intervenes. Default until D̂/τ heads exist."""

    def should_override(self, obs: Observation, wm_out: Optional[Any] = None) -> bool:
        return False

    def override_action(self, obs: Observation) -> np.ndarray:
        return np.zeros(4, dtype=np.float64)

    def apply_action(
        self,
        action: np.ndarray,
        obs: Observation,
        wm_out: Optional[Any] = None,
        limits: Optional[np.ndarray] = None,
    ) -> tuple[np.ndarray, bool]:
        lim = limits
        return clip_body_delta(action, lim), False


@dataclass
class ThresholdSafetyShield:
    """Trigger contract for D̂ ∪ τ ∪ p_coll (fields wired at V2+).

    **Standoff semantics (v5, 2026-08-22)** — ``min_depth_m`` is the boundary of
    the *stable-hover zone*, not the distance at which braking *starts*. The
    vehicle must bleed closing speed **before** crossing the standoff so it is
    near-stationary **inside** ``min_depth_m``. Kinematic engage when::

        D̂ < min_depth_m + v_fwd * min_tau_s

    (same ``min_tau_s`` reaction budget as the τ leg; thresholds unchanged).

    Override uses **graduated body −x** scaled to ``v_fwd`` (capped by
    ``retreat_step_m``), including while still **outside** the standoff but
    inside the braking envelope — not a step function at 3 m.

    Prior latch + bounded retreat history (晚¹⁰–¹²) remains; v5 fixes the
    high-speed “coast into 3 m then panic” failure mode.

    **Legacy** — superseded for deploy by :class:`ThreeZoneSpeedShield`.
    """

    # Reaction standoff outer boundary — must be stable/hovering inside, not enter at cruise.
    min_depth_m: float = 3.0
    min_tau_s: float = 1.0            # τ breach + kinematic depth braking horizon (s)
    max_p_coll: float = 0.5           # brake if WM collision prob > this
    min_closing_m_s: float = DEFAULT_MIN_CLOSING_M_S
    brake_gain: float = 1.0           # retreat dx ≈ v_fwd * brake_gain per step (then clipped)
    retreat_step_m: float = 3.0       # max |body −x| per override step
    _engaged: bool = field(default=False, init=False, repr=False)

    def reset(self) -> None:
        """Clear the per-episode latch (the shield instance is reused across episodes)."""
        self._engaged = False

    def _kinematic_standoff_limit_m(self, v_fwd: float) -> float:
        """Outer engage surface: standoff + distance closed in ``min_tau_s`` at ``v_fwd``."""
        return float(self.min_depth_m) + max(float(v_fwd), 0.0) * float(self.min_tau_s)

    def _depth_channel_breach(self, d_hat: float, v_fwd: float) -> bool:
        d = float(d_hat)
        if d < float(self.min_depth_m):
            return True
        if v_fwd > float(self.min_closing_m_s):
            return d < self._kinematic_standoff_limit_m(v_fwd)
        return False

    def _needs_speed_bleed(self, obs: Observation) -> bool:
        d_hat = obs.info.get("depth_min_pred")
        if d_hat is None:
            return False
        v = closing_speed_m_s(obs)
        return self._depth_channel_breach(float(d_hat), v)

    def _breached(self, obs: Observation, wm_out: Optional[Any] = None) -> bool:
        d_hat = obs.info.get("depth_min_pred")
        tau = obs.info.get("tau_pred")
        p_coll = None
        if wm_out is not None:
            p_coll = getattr(wm_out, "p_coll", None)
        if d_hat is not None and self._depth_channel_breach(
            float(d_hat), closing_speed_m_s(obs)
        ):
            return True
        if tau is not None and float(tau) < self.min_tau_s:
            return True
        if p_coll is not None and float(p_coll) > self.max_p_coll:
            return True
        return False

    def should_override(self, obs: Observation, wm_out: Optional[Any] = None) -> bool:
        if self._engaged:
            return True
        if self._breached(obs, wm_out):
            self._engaged = True
            return True
        return False

    def override_action(self, obs: Observation) -> np.ndarray:
        if not self._needs_speed_bleed(obs):
            return np.zeros(4, dtype=np.float64)
        v = closing_speed_m_s(obs)
        # Graduated −x: bleed closing speed before/at standoff; collector clips to rate cap.
        mag = min(
            float(self.retreat_step_m),
            max(float(v), float(self.min_closing_m_s)) * float(self.brake_gain),
        )
        return np.array([-abs(mag), 0.0, 0.0, 0.0], dtype=np.float64)

    def apply_action(
        self,
        action: np.ndarray,
        obs: Observation,
        wm_out: Optional[Any] = None,
        limits: Optional[np.ndarray] = None,
    ) -> tuple[np.ndarray, bool]:
        if self.should_override(obs, wm_out):
            return clip_body_delta(self.override_action(obs), limits), True
        return clip_body_delta(action, limits), False


@dataclass
class DepthTauShield(ThresholdSafetyShield):
    """τ/D̂ dual-channel hard shield (frozen spec V1).

    Same trigger/override contract as :class:`ThresholdSafetyShield`, but records
    which independent channel(s) breached for V1-③ diagnostics. Writes
    ``obs.info['shield_channels']`` on the step the latch engages.

    **Legacy** — deploy uses :class:`ThreeZoneSpeedShield`.
    """

    _last_channels: tuple[str, ...] = field(default=(), init=False, repr=False)

    @property
    def last_channels(self) -> tuple[str, ...]:
        return self._last_channels

    def reset(self) -> None:
        super().reset()
        self._last_channels = ()

    def _channels_breached(self, obs: Observation, wm_out: Optional[Any] = None) -> tuple[str, ...]:
        out: list[str] = []
        d_hat = obs.info.get("depth_min_pred")
        tau = obs.info.get("tau_pred")
        p_coll = None
        if wm_out is not None:
            p_coll = getattr(wm_out, "p_coll", None)
        if d_hat is not None and self._depth_channel_breach(
            float(d_hat), closing_speed_m_s(obs)
        ):
            out.append("depth")
        if tau is not None and float(tau) < self.min_tau_s:
            out.append("tau")
        if p_coll is not None and float(p_coll) > self.max_p_coll:
            out.append("p_coll")
        return tuple(out)

    def should_override(self, obs: Observation, wm_out: Optional[Any] = None) -> bool:
        if self._engaged:
            return True
        channels = self._channels_breached(obs, wm_out)
        if channels:
            self._engaged = True
            self._last_channels = channels
            obs.info["shield_channels"] = list(channels)
            return True
        return False


@dataclass
class ThreeZoneSpeedShield:
    """Graduated speed governor from ``D̂_fwd`` (+ cones) + τ/p_coll latch.

    * **L3 brake (BA)**: when ``d̂_fwd ≤ L3``, per-step −x retreat.
    * **L3 3D (BB)**: after −x, ``‖Δ‖₂ ≤ v_stop·dt`` (``three_zone_3d``) + active
      lateral clamp in L3 when cones ≤ L2 (``three_zone_lat``).
  * **Depth (P0b)**: ``min(cones['forward'], full-min)`` for +x / L3; L3 **外**
    side cones ≤ L2 clamp toward-obstacle to ≤ v2·dt (``three_zone_lat``, report-only).
  * **τ / p_coll**: latch + graduated −x retreat (same as v5 threshold shield).

  Default zones: **8 / 5 / 1.5 m @ 2 / 1 / 0.2 m/s**, cruise ceiling **25 m/s**;
  outer engage is **dynamic** from body-forward ``v_now`` / commanded ``v_x``
  (capped by cruise). Static engage at full cruise ≈ **134.6 m**.
    """

    zone: ThreeZoneSpec = field(default_factory=ThreeZoneSpec)
    min_tau_s: float = 1.0
    max_p_coll: float = 0.5
    min_closing_m_s: float = DEFAULT_MIN_CLOSING_M_S
    brake_gain: float = 1.0
    retreat_step_m: float = 3.0
    deadlock_thresh_steps: int = 3
    #: Mainline default 0 (F7): non-zero re-enables sustained lateral escape SM.
    escape_hold_steps: int = 0
    enable_sustained_escape: bool = False
    #: When True (default), size outer band from ``max(v_now, v_cmd)`` each step.
    dynamic_v_ref: bool = True
    #: Ignore WM ``p_coll`` emergency when forward clearance exceeds this (metres).
    #: ``None`` (default) → use zone L1. Set ``<=0`` to disable the veto.
    #: Prevents false p_coll latch → body −x retreat while the corridor is open
    #: (Phase-2: anti-parallel crawl off the polyline).
    p_coll_clearance_veto_m: Optional[float] = None
    _emergency_engaged: bool = field(default=False, init=False, repr=False)
    _last_channels: tuple[str, ...] = field(default=(), init=False, repr=False)
    _consecutive_forward_blocks: int = field(default=0, init=False, repr=False)
    _escape_steps_remaining: int = field(default=0, init=False, repr=False)
    _escape_direction: int = field(default=0, init=False, repr=False)
    _clear_danger_steps: int = field(default=0, init=False, repr=False)

    @property
    def last_channels(self) -> tuple[str, ...]:
        return self._last_channels

    def reset(self) -> None:
        self._emergency_engaged = False
        self._last_channels = ()
        self._consecutive_forward_blocks = 0
        self._escape_steps_remaining = 0
        self._escape_direction = 0
        self._clear_danger_steps = 0

    def _p_coll_clearance_veto_m(self) -> Optional[float]:
        if self.p_coll_clearance_veto_m is None:
            return float(self.zone.l1_m)
        v = float(self.p_coll_clearance_veto_m)
        return v if v > 0.0 else None

    def _emergency_channels(self, obs: Observation, wm_out: Optional[Any] = None) -> tuple[str, ...]:
        out: list[str] = []
        tau = obs.info.get("tau_pred")
        p_coll = None
        if wm_out is not None:
            p_coll = getattr(wm_out, "p_coll", None)
        if tau is not None and float(tau) < self.min_tau_s:
            out.append("tau")
        if p_coll is not None and float(p_coll) > self.max_p_coll:
            veto = self._p_coll_clearance_veto_m()
            d_fwd = self._forward_d_hat(obs)
            if (
                veto is not None
                and d_fwd is not None
                and np.isfinite(float(d_fwd))
                and float(d_fwd) > float(veto)
            ):
                obs.info["shield_p_coll_vetoed"] = True
                obs.info["shield_p_coll_veto_d_fwd_m"] = round(float(d_fwd), 4)
            else:
                out.append("p_coll")
        return tuple(out)

    def _emergency_override(self, obs: Observation) -> np.ndarray:
        v = closing_speed_m_s(obs)
        mag = min(
            float(self.retreat_step_m),
            max(float(v), float(self.min_closing_m_s)) * float(self.brake_gain),
        )
        return np.array([-abs(mag), 0.0, 0.0, 0.0], dtype=np.float64)

    def _dt_from_limits(self, limits: Optional[np.ndarray]) -> float:
        if limits is not None and float(limits[0]) > 0:
            return float(limits[0]) / float(MAX_BODY_VELOCITY[0])
        return float(self.zone.dt_s)

    def _cones(self, obs: Observation) -> Optional[dict]:
        raw = obs.info.get("depth_cones_pred")
        return raw if isinstance(raw, dict) else None

    def _forward_d_hat(self, obs: Observation) -> Optional[float]:
        """Forward clearance: prioritize dedicated forward cone.
        Only fall back to full-min if cones are unavailable.
        """
        cones = self._cones(obs)
        if cones is not None:
            fwd = cones.get("forward")
            if fwd is not None and np.isfinite(float(fwd)):
                return float(fwd)
        full = obs.info.get("depth_min_pred")
        if full is not None and np.isfinite(float(full)):
            return float(full)
        return None

    def _cap_forward(self, action: np.ndarray, obs: Observation, limits: Optional[np.ndarray]) -> tuple[np.ndarray, bool]:
        d_hat = self._forward_d_hat(obs)
        if d_hat is None:
            return action, False
        dt = self._dt_from_limits(limits)
        capped = np.asarray(action, dtype=np.float64).reshape(4).copy()
        v_now = float(closing_speed_m_s(obs))
        v_cmd = max(0.0, float(capped[0]) / max(dt, 1e-6))
        if bool(self.dynamic_v_ref):
            v_ref = resolve_v_ref_m_s(self.zone, v_now_m_s=v_now, v_cmd_m_s=v_cmd)
            v_cap = planned_speed_m_s(float(d_hat), self.zone, v_ref_m_s=v_ref)
            eng = engage_outer_for_speed(self.zone, v_ref)
        else:
            v_ref = float(self.zone.v_cruise_m_s)
            v_cap = planned_speed_m_s(float(d_hat), self.zone)
            eng = float(self.zone.engage_outer_m)
        obs.info["three_zone_speed_cap_m_s"] = round(v_cap, 4)
        obs.info["three_zone_d_hat_fwd_m"] = round(float(d_hat), 4)
        obs.info["three_zone_v_ref_m_s"] = round(v_ref, 4)
        obs.info["three_zone_engage_outer_m"] = round(float(eng), 4)
        max_dx = v_cap * dt
        if capped[0] > max_dx + 1e-6:
            capped[0] = max_dx
            return capped, True
        return capped, False

    def _cap_lateral(
        self, action: np.ndarray, obs: Observation, limits: Optional[np.ndarray]
    ) -> tuple[np.ndarray, bool]:
        """P0b: when side/up/down cone ≤ L2, clamp toward-obstacle axis to ≤ v2·dt.

        Body frame: +x fwd, +y left, +z up. ``three_zone_lat`` is report-only
        (not an emergency latch channel).
        """
        cones = self._cones(obs)
        if cones is None:
            return action, False
        dt = self._dt_from_limits(limits)
        max_lat = float(self.zone.v2_m_s) * dt
        l2 = float(self.zone.l2_m)
        capped = np.asarray(action, dtype=np.float64).reshape(4).copy()
        hit: list[str] = []

        def _finite(key: str) -> Optional[float]:
            v = cones.get(key)
            if v is None:
                return None
            f = float(v)
            return f if np.isfinite(f) else None

        left = _finite("left")
        right = _finite("right")
        up = _finite("up")
        down = _finite("down")
        # +y = left: toward left obstacle ⇒ clamp positive y
        if left is not None and left <= l2 and capped[1] > max_lat + 1e-6:
            capped[1] = max_lat
            hit.append("left")
        # −y = right
        if right is not None and right <= l2 and capped[1] < -max_lat - 1e-6:
            capped[1] = -max_lat
            hit.append("right")
        # +z = up
        if up is not None and up <= l2 and capped[2] > max_lat + 1e-6:
            capped[2] = max_lat
            hit.append("up")
        # −z = down
        if down is not None and down <= l2 and capped[2] < -max_lat - 1e-6:
            capped[2] = -max_lat
            hit.append("down")
        if not hit:
            return capped, False
        ch = list(obs.info.get("shield_channels") or [])
        if "three_zone_lat" not in ch:
            ch.append("three_zone_lat")
        if "three_zone" not in ch:
            ch.append("three_zone")
        obs.info["shield_channels"] = ch
        obs.info["three_zone_lat_axes"] = hit
        return capped, True

    def _norm_clamp_l3(
        self, action: np.ndarray, obs: Observation, limits: Optional[np.ndarray]
    ) -> tuple[np.ndarray, bool]:
        """BB B1: when in L3 brake path, cap ‖Δbody‖₂ ≤ v_stop·dt."""
        dt = self._dt_from_limits(limits)
        max_norm = float(self.zone.v_stop_m_s) * dt
        capped = np.asarray(action, dtype=np.float64).reshape(4).copy()
        norm = float(np.linalg.norm(capped))
        if norm <= max_norm + 1e-9 or norm < 1e-12:
            return capped, False
        scaled = capped * (max_norm / norm)
        ch = list(obs.info.get("shield_channels") or [])
        if "three_zone_3d" not in ch:
            ch.append("three_zone_3d")
        if "three_zone" not in ch:
            ch.append("three_zone")
        obs.info["shield_channels"] = ch
        return scaled, True

    def _cap_lateral_l3_active(
        self, action: np.ndarray, obs: Observation, limits: Optional[np.ndarray]
    ) -> tuple[np.ndarray, bool]:
        """BB B2: L3内 cones≤L2 ⇒ clamp |Δ_axis| ≤ v_stop·dt (both directions)."""
        d_hat = self._forward_d_hat(obs)
        if d_hat is None or float(d_hat) > float(self.zone.l3_m):
            return action, False
        cones = self._cones(obs)
        if cones is None:
            return action, False
        dt = self._dt_from_limits(limits)
        max_axis = float(self.zone.v_stop_m_s) * dt
        l2 = float(self.zone.l2_m)
        capped = np.asarray(action, dtype=np.float64).reshape(4).copy()
        hit: list[str] = []

        def _finite(key: str) -> Optional[float]:
            v = cones.get(key)
            if v is None:
                return None
            f = float(v)
            return f if np.isfinite(f) else None

        left = _finite("left")
        right = _finite("right")
        up = _finite("up")
        down = _finite("down")
        if (left is not None and left <= l2) or (right is not None and right <= l2):
            if abs(capped[1]) > max_axis + 1e-6:
                capped[1] = float(np.clip(capped[1], -max_axis, max_axis))
                if left is not None and left <= l2:
                    hit.append("left")
                if right is not None and right <= l2:
                    hit.append("right")
        if (up is not None and up <= l2) or (down is not None and down <= l2):
            if abs(capped[2]) > max_axis + 1e-6:
                capped[2] = float(np.clip(capped[2], -max_axis, max_axis))
                if up is not None and up <= l2:
                    hit.append("up")
                if down is not None and down <= l2:
                    hit.append("down")
        if not hit:
            return capped, False
        ch = list(obs.info.get("shield_channels") or [])
        if "three_zone_lat" not in ch:
            ch.append("three_zone_lat")
        if "three_zone" not in ch:
            ch.append("three_zone")
        obs.info["shield_channels"] = ch
        obs.info["three_zone_lat_axes"] = hit
        return capped, True

    def _l3_active_brake(
        self, obs: Observation, limits: Optional[np.ndarray]
    ) -> Optional[tuple[np.ndarray, bool]]:
        """BA declare: when min(d̂_fwd, full_min) <= L3, per-step −x retreat (no episode latch)."""
        d_hat = self._forward_d_hat(obs)
        full = obs.info.get("depth_min_pred")
        full_f = float(full) if full is not None and np.isfinite(float(full)) else None

        d_crit = d_hat
        if full_f is not None and (d_crit is None or full_f < d_crit):
            d_crit = full_f

        if d_crit is None or float(d_crit) > float(self.zone.l3_m):
            return None
        ch = list(obs.info.get("shield_channels") or [])
        if "three_zone_brake" not in ch:
            ch.append("three_zone_brake")
        if "three_zone" not in ch:
            ch.append("three_zone")
        obs.info["shield_channels"] = ch
        obs.info["three_zone_speed_cap_m_s"] = round(float(self.zone.v_stop_m_s), 4)
        obs.info["three_zone_d_hat_fwd_m"] = round(float(d_crit), 4)
        self._last_channels = tuple(ch)
        return clip_body_delta(self._emergency_override(obs), limits), True

    def apply_action(
        self,
        action: np.ndarray,
        obs: Observation,
        wm_out: Optional[Any] = None,
        limits: Optional[np.ndarray] = None,
    ) -> tuple[np.ndarray, bool]:
        action = np.asarray(action, dtype=np.float64).reshape(4)
        channels = self._emergency_channels(obs, wm_out)
        if self._emergency_engaged:
            if not channels:
                self._clear_danger_steps += 1
                if self._clear_danger_steps >= 3:
                    self._emergency_engaged = False
                    self._clear_danger_steps = 0
            else:
                self._clear_danger_steps = 0
            if self._emergency_engaged:
                obs.info["shield_emergency_override"] = True
                return clip_body_delta(self._emergency_override(obs), limits), True

        if channels:
            self._emergency_engaged = True
            self._last_channels = channels
            obs.info["shield_channels"] = list(channels)
            obs.info["shield_emergency_override"] = True
            return clip_body_delta(self._emergency_override(obs), limits), True

        braked = self._l3_active_brake(obs, limits)
        if braked is not None:
            out, _ = braked
            out, norm_ch = self._norm_clamp_l3(out, obs, limits)
            out, lat_ch = self._cap_lateral_l3_active(out, obs, limits)
            if norm_ch or lat_ch:
                self._last_channels = tuple(obs.info.get("shield_channels") or [])
            obs.info["shield_emergency_override"] = True
            return clip_body_delta(out, limits), True

        capped, changed = self._cap_forward(action, obs, limits)
        lat, lat_ch = self._cap_lateral(capped, obs, limits)
        if changed or lat_ch:
            self._consecutive_forward_blocks += 1
            obs.info["shield_governor_cap"] = True
        else:
            self._consecutive_forward_blocks = max(0, self._consecutive_forward_blocks - 1)

        # Risk 4: Sustained Directional Wall-Following Escape (OFF on mainline; F7)
        d_fwd = self._forward_d_hat(obs)
        if bool(self.enable_sustained_escape) and int(self.escape_hold_steps) > 0:
            if self._escape_steps_remaining > 0:
                if d_fwd is not None and float(d_fwd) > 4.5:
                    self._escape_steps_remaining = 0
                else:
                    self._escape_steps_remaining -= 1
                    dt = self._dt_from_limits(limits)
                    v_lat_escape = min(0.35, float(self.zone.v2_m_s) * 0.6)
                    lat[1] = self._escape_direction * v_lat_escape * dt
                    lat[3] = self._escape_direction * 0.18
                    ch = list(obs.info.get("shield_channels") or [])
                    if "three_zone_sustained_escape" not in ch:
                        ch.append("three_zone_sustained_escape")
                    obs.info["shield_channels"] = ch
                    lat_ch = True
            elif self._consecutive_forward_blocks >= self.deadlock_thresh_steps:
                cones = self._cones(obs)
                l_val = float(cones.get("left", 5.0)) if cones and cones.get("left") is not None else 5.0
                r_val = float(cones.get("right", 5.0)) if cones and cones.get("right") is not None else 5.0
                self._escape_direction = 1 if l_val >= r_val else -1
                self._escape_steps_remaining = int(self.escape_hold_steps)
                dt = self._dt_from_limits(limits)
                v_lat_escape = min(0.35, float(self.zone.v2_m_s) * 0.6)
                lat[1] = self._escape_direction * v_lat_escape * dt
                lat[3] = self._escape_direction * 0.18
                ch = list(obs.info.get("shield_channels") or [])
                if "three_zone_sustained_escape" not in ch:
                    ch.append("three_zone_sustained_escape")
                obs.info["shield_channels"] = ch
                lat_ch = True

        if changed:
            ch = list(obs.info.get("shield_channels") or [])
            if "three_zone" not in ch:
                ch.append("three_zone")
            obs.info["shield_channels"] = ch
        if changed or lat_ch:
            self._last_channels = tuple(obs.info.get("shield_channels") or [])
        return clip_body_delta(lat, limits), bool(changed or lat_ch)

    def should_override(self, obs: Observation, wm_out: Optional[Any] = None) -> bool:
        """Backward-compat: true only for τ/p_coll emergency latch."""
        if self._emergency_engaged:
            return True
        return bool(self._emergency_channels(obs, wm_out))

    def override_action(self, obs: Observation) -> np.ndarray:
        return self._emergency_override(obs)
