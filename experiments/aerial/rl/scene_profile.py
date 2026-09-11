"""Per-episode scene profiles for unified outdoor + indoor navigation.

Episodes may carry ``scene ∈ {outdoor_long, indoor_micro}``. When present,
``apply_episode_scene_profile`` returns action limits, success distance, and
optional three-zone overrides for the collector loop.

Config source: ``configs/aerial_rl_phase3_unified.yaml`` §``scene_profiles``.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

import numpy as np
import yaml

from experiments.aerial.rl.env.action import body_delta_limits
from experiments.aerial.rl.reward import RewardConfig
from experiments.aerial.rl.three_zone import ThreeZoneSpec

SCENE_OUTDOOR_LONG = "outdoor_long"
SCENE_INDOOR_MICRO = "indoor_micro"
DEFAULT_SCENES = (SCENE_OUTDOOR_LONG, SCENE_INDOOR_MICRO)


@dataclass(frozen=True)
class SceneProfile:
    scene: str
    action_limits: np.ndarray
    success_dist_m: float
    three_zone: Optional[ThreeZoneSpec] = None
    cruise_speed_m_s: Optional[float] = None

    def as_limits_list(self) -> list:
        return [float(x) for x in self.action_limits.reshape(4)]


def _limits_from_mapping(lim: Mapping[str, Any]) -> np.ndarray:
    return np.array(
        [
            float(lim["max_dx"]),
            float(lim["max_dy"]),
            float(lim["max_dz"]),
            float(lim["max_dyaw"]),
        ],
        dtype=np.float64,
    )


def _three_zone_from_mapping(safety: Mapping[str, Any]) -> ThreeZoneSpec:
    return ThreeZoneSpec(
        l1_m=float(safety["l1_m"]),
        l2_m=float(safety["l2_m"]),
        l3_m=float(safety["l3_m"]),
        v1_m_s=float(safety["v1_m_s"]),
        v2_m_s=float(safety["v2_m_s"]),
        v_stop_m_s=float(safety["v_stop_m_s"]),
        v_cruise_m_s=float(safety["v_cruise_m_s"]),
        a_max_m_s2=float(safety.get("a_max_m_s2", 2.5)),
        delay_s=float(safety.get("delay_s", 0.2)),
    )


def load_scene_profiles_from_mapping(profiles_raw: Mapping[str, Any]) -> Dict[str, SceneProfile]:
    out: Dict[str, SceneProfile] = {}
    for scene, block in dict(profiles_raw or {}).items():
        limits = _limits_from_mapping(block["action_limits"])
        safety = block.get("safety") or {}
        tz = _three_zone_from_mapping(safety) if safety.get("kind") == "three_zone" else None
        cruise = float(safety.get("v_cruise_m_s", 0.0)) if safety else None
        out[str(scene)] = SceneProfile(
            scene=str(scene),
            action_limits=limits,
            success_dist_m=float(block["success_dist_m"]),
            three_zone=tz,
            cruise_speed_m_s=cruise if cruise and cruise > 0 else None,
        )
    return out


def load_scene_profiles(config_path: str | Path) -> Dict[str, SceneProfile]:
    path = Path(config_path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    profiles_raw = dict(raw.get("scene_profiles") or {})
    return load_scene_profiles_from_mapping(profiles_raw)


def default_outdoor_profile(step_hz: float) -> SceneProfile:
    limits = body_delta_limits(1.0 / step_hz)
    return SceneProfile(
        scene=SCENE_OUTDOOR_LONG,
        action_limits=limits,
        success_dist_m=3.0,
        three_zone=None,
        cruise_speed_m_s=None,
    )


def resolve_scene_profile(
    episode: Optional[Mapping[str, Any]],
    *,
    step_hz: float,
    profiles: Optional[Mapping[str, SceneProfile]] = None,
) -> SceneProfile:
    if not episode:
        return default_outdoor_profile(step_hz)
    scene = str(episode.get("scene") or "").strip()
    if profiles and scene in profiles:
        return profiles[scene]
    if scene == SCENE_INDOOR_MICRO:
        return SceneProfile(
            scene=SCENE_INDOOR_MICRO,
            action_limits=np.array([0.15, 0.08, 0.08, 0.10], dtype=np.float64),
            success_dist_m=0.5,
            three_zone=ThreeZoneSpec(
                l1_m=1.5,
                l2_m=0.8,
                l3_m=0.4,
                v1_m_s=0.6,
                v2_m_s=0.3,
                v_stop_m_s=0.05,
                v_cruise_m_s=1.0,
                a_max_m_s2=1.5,
                delay_s=0.1,
            ),
            cruise_speed_m_s=1.0,
        )
    return default_outdoor_profile(step_hz)


@dataclass
class SceneProfileContext:
    profile: SceneProfile
    limits: np.ndarray
    prev_shield_zone: Optional[ThreeZoneSpec] = None
    prev_reward_success_dist: Optional[float] = None


def apply_episode_scene_profile(
    episode: Optional[Mapping[str, Any]],
    reward_cfg: RewardConfig,
    safety: Any,
    *,
    step_hz: float,
    profiles: Optional[Mapping[str, SceneProfile]] = None,
) -> SceneProfileContext:
    """Apply scene tag to limits, reward success_dist, and shield zone (if wired)."""
    profile = resolve_scene_profile(episode, step_hz=step_hz, profiles=profiles)
    limits = profile.action_limits.copy()

    ep_cs = float((episode or {}).get("cruise_speed", 0.0))
    if ep_cs > 0.0:
        limits = limits.copy()
        limits[0] = ep_cs / step_hz
    elif profile.cruise_speed_m_s and profile.cruise_speed_m_s > 0:
        limits = limits.copy()
        limits[0] = profile.cruise_speed_m_s / step_hz

    prev_reward = float(reward_cfg.success_dist_m)
    reward_cfg.success_dist_m = float(profile.success_dist_m)

    prev_zone: Optional[ThreeZoneSpec] = None
    if safety is not None and profile.three_zone is not None:
        zone = getattr(safety, "zone", None)
        if zone is not None and isinstance(zone, ThreeZoneSpec):
            prev_zone = zone
            safety.zone = profile.three_zone

    return SceneProfileContext(
        profile=profile,
        limits=limits,
        prev_shield_zone=prev_zone,
        prev_reward_success_dist=prev_reward,
    )


def restore_scene_profile_context(ctx: SceneProfileContext, reward_cfg: RewardConfig, safety: Any) -> None:
    if ctx.prev_reward_success_dist is not None:
        reward_cfg.success_dist_m = ctx.prev_reward_success_dist
    if ctx.prev_shield_zone is not None and safety is not None:
        safety.zone = ctx.prev_shield_zone
