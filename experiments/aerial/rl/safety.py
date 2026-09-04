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
from experiments.aerial.rl.three_zone import ThreeZoneSpec
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
    """TTI speed governor: single-line + 3 m hard exclusion + τ/p_coll latch.

    Forward cap: v_fwd ≤ d_fwd / tti_coeff  (enforces TTI ≥ tti_coeff seconds).
    Lateral cap: v_lat ≤ d_lat / tti_coeff  per axis (same TTI budget).
    Hard exclusion: d_fwd ≤ exclusion_m → per-step −x retreat (no episode latch).
    τ / p_coll: latch + graduated −x retreat (unchanged from prior design).

    Default tti_coeff=4.0 → at 25 m/s trigger at 100 m; at 10 m/s trigger at 40 m.
    """

    zone: ThreeZoneSpec = field(default_factory=ThreeZoneSpec)
    min_tau_s: float = 1.0
    max_p_coll: float = 0.5
    min_closing_m_s: float = DEFAULT_MIN_CLOSING_M_S
    brake_gain: float = 1.0
    retreat_step_m: float = 3.0
    #: TTI budget (seconds). Trigger distance = tti_coeff × v_eff.
    tti_coeff: float = 4.0
    #: Hard exclusion zone (metres). Below this → retreat, no forward motion.
    exclusion_m: float = 3.0
    #: When True (default), use max(v_now, v_cmd) as effective speed reference.
    dynamic_v_ref: bool = True
    #: Ignore WM ``p_coll`` emergency when forward clearance exceeds this (metres).
    #: ``None`` → use zone.l1_m (8 m). Set <=0 to disable.
    p_coll_clearance_veto_m: Optional[float] = None
    _emergency_engaged: bool = field(default=False, init=False, repr=False)
    _last_channels: tuple[str, ...] = field(default=(), init=False, repr=False)
    _clear_danger_steps: int = field(default=0, init=False, repr=False)

    @property
    def last_channels(self) -> tuple[str, ...]:
        return self._last_channels

    def reset(self) -> None:
        self._emergency_engaged = False
        self._last_channels = ()
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
        """TTI forward cap: v_fwd ≤ d_fwd / tti_coeff. Exclusion zone handled by _exclusion_brake."""
        d_hat = self._forward_d_hat(obs)
        if d_hat is None:
            return action, False
        d = float(d_hat)
        if d <= float(self.exclusion_m):
            return action, False  # handled by _exclusion_brake
        dt = self._dt_from_limits(limits)
        capped = np.asarray(action, dtype=np.float64).reshape(4).copy()
        v_now = float(closing_speed_m_s(obs))
        v_cmd = max(0.0, float(capped[0]) / max(dt, 1e-6))
        v_ref = max(v_now, v_cmd) if bool(self.dynamic_v_ref) else float(self.zone.v_cruise_m_s)
        trigger = float(self.tti_coeff) * v_ref
        if d >= trigger or v_ref < 1e-6:
            return action, False
        v_cap = d / float(self.tti_coeff)
        obs.info["tii_speed_cap_m_s"] = round(v_cap, 4)
        obs.info["tii_d_hat_fwd_m"] = round(d, 4)
        max_dx = v_cap * dt
        if capped[0] > max_dx + 1e-6:
            capped[0] = max_dx
            return capped, True
        return action, False

    def _cap_lateral(
        self, action: np.ndarray, obs: Observation, limits: Optional[np.ndarray]
    ) -> tuple[np.ndarray, bool]:
        """TTI lateral cap: v_lat ≤ d_lat / tti_coeff per axis (body +y=left, +z=up)."""
        cones = self._cones(obs)
        if cones is None:
            return action, False
        dt = self._dt_from_limits(limits)
        capped = np.asarray(action, dtype=np.float64).reshape(4).copy()
        hit: list[str] = []

        def _finite(key: str) -> Optional[float]:
            v = cones.get(key)
            if v is None:
                return None
            f = float(v)
            return f if np.isfinite(f) else None

        def _tti_clamp(d_obs: Optional[float], delta: float, moving_toward: bool) -> tuple[float, bool]:
            if not moving_toward or d_obs is None:
                return delta, False
            v_abs = abs(delta) / max(dt, 1e-6)
            if v_abs < 1e-6:
                return delta, False
            trigger = float(self.tti_coeff) * v_abs
            if float(d_obs) >= trigger:
                return delta, False
            max_delta = float(d_obs) / float(self.tti_coeff) * dt
            if abs(delta) <= max_delta + 1e-6:
                return delta, False
            return float(np.sign(delta)) * max_delta, True

        left = _finite("left")
        right = _finite("right")
        up = _finite("up")
        down = _finite("down")

        new_y, hl = _tti_clamp(left, capped[1], capped[1] > 1e-6)
        if hl:
            capped[1] = new_y
            hit.append("left")
        new_y2, hr = _tti_clamp(right, capped[1], capped[1] < -1e-6)
        if hr:
            capped[1] = new_y2
            hit.append("right")
        new_z, hu = _tti_clamp(up, capped[2], capped[2] > 1e-6)
        if hu:
            capped[2] = new_z
            hit.append("up")
        new_z2, hd = _tti_clamp(down, capped[2], capped[2] < -1e-6)
        if hd:
            capped[2] = new_z2
            hit.append("down")

        if not hit:
            return capped, False
        ch = list(obs.info.get("shield_channels") or [])
        if "tii_lat" not in ch:
            ch.append("tii_lat")
        obs.info["shield_channels"] = ch
        obs.info["tii_lat_axes"] = hit
        return capped, True

    def _exclusion_brake(
        self, obs: Observation, limits: Optional[np.ndarray]
    ) -> Optional[tuple[np.ndarray, bool]]:
        """Hard exclusion zone: when d_fwd ≤ exclusion_m, per-step −x retreat (no episode latch)."""
        d_hat = self._forward_d_hat(obs)
        full = obs.info.get("depth_min_pred")
        full_f = float(full) if full is not None and np.isfinite(float(full)) else None
        d_crit = d_hat
        if full_f is not None and (d_crit is None or full_f < d_crit):
            d_crit = full_f
        if d_crit is None or float(d_crit) > float(self.exclusion_m):
            return None
        ch = list(obs.info.get("shield_channels") or [])
        if "tii_exclusion" not in ch:
            ch.append("tii_exclusion")
        obs.info["shield_channels"] = ch
        obs.info["tii_speed_cap_m_s"] = 0.0
        obs.info["tii_d_hat_fwd_m"] = round(float(d_crit), 4)
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

        # 1. τ / p_coll emergency latch (unchanged)
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

        # 2. Hard exclusion zone: d_fwd ≤ exclusion_m → retreat
        braked = self._exclusion_brake(obs, limits)
        if braked is not None:
            out, _ = braked
            obs.info["shield_emergency_override"] = True
            return clip_body_delta(out, limits), True

        # 3. TTI forward + lateral cap
        capped, fwd_ch = self._cap_forward(action, obs, limits)
        lat, lat_ch = self._cap_lateral(capped, obs, limits)
        if fwd_ch or lat_ch:
            obs.info["shield_governor_cap"] = True
            self._last_channels = tuple(obs.info.get("shield_channels") or [])
        return clip_body_delta(lat, limits), bool(fwd_ch or lat_ch)

    def should_override(self, obs: Observation, wm_out: Optional[Any] = None) -> bool:
        """Backward-compat: true only for τ/p_coll emergency latch."""
        if self._emergency_engaged:
            return True
        return bool(self._emergency_channels(obs, wm_out))

    def override_action(self, obs: Observation) -> np.ndarray:
        return self._emergency_override(obs)
