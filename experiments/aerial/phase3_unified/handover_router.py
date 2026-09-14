"""Handover scene router for Phase-3 decouple (outdoor frozen + indoor ckpt).

The router selects FSM state, scene profile, and policy id. It does **not**
run the policy — eval / deploy code loads the ckpt named by ``policy_id``.

Modes:
  * ``oracle`` — read ``scene`` / ``leg`` / ``map_id`` from episode metadata (sim eval).
  * ``waypoint`` — distance to handover waypoint + optional GCS command (deploy stub).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence

import numpy as np

from experiments.aerial.rl.scene_profile import (
    SCENE_INDOOR_MICRO,
    SCENE_OUTDOOR_APPROACH,
    SCENE_OUTDOOR_LONG,
)

POLICY_PHASE2_OUTDOOR = "phase2_outdoor"
POLICY_PHASE3_INDOOR = "phase3_indoor"

MAP_OUTDOOR = "env_airsim_16"
MAP_INDOOR = "building_99"


class FsmState(str, Enum):
    OUTDOOR = "OUTDOOR"
    APPROACH = "APPROACH"
    INDOOR = "INDOOR"


@dataclass(frozen=True)
class RouterOutput:
    fsm_state: FsmState
    scene: str
    policy_id: str
    map_id: str


@dataclass
class RouterInput:
    mission_segment: Optional[str] = None
    p_hat: Optional[np.ndarray] = None
    handover_wp: Optional[np.ndarray] = None
    gnss_ok: Optional[bool] = None
    gcs_command: Optional[str] = None
    episode: Optional[Dict[str, Any]] = None


def scene_to_policy_id(scene: str) -> str:
    if scene == SCENE_INDOOR_MICRO:
        return POLICY_PHASE3_INDOOR
    return POLICY_PHASE2_OUTDOOR


def episode_scene(episode: Mapping[str, Any]) -> str:
    scene = str(episode.get("scene") or "").strip()
    if scene:
        return scene
    leg = str(episode.get("leg") or "").strip().lower()
    if leg == "indoor":
        return SCENE_INDOOR_MICRO
    if leg == "outdoor":
        return SCENE_OUTDOOR_APPROACH
    map_id = str(episode.get("map_id") or "").strip()
    if map_id == MAP_INDOOR:
        return SCENE_INDOOR_MICRO
    return SCENE_OUTDOOR_LONG


def episode_map_id(episode: Mapping[str, Any], scene: str) -> str:
    map_id = str(episode.get("map_id") or "").strip()
    if map_id:
        return map_id
    return MAP_INDOOR if scene == SCENE_INDOOR_MICRO else MAP_OUTDOOR


def scene_to_fsm_state(scene: str) -> FsmState:
    if scene == SCENE_INDOOR_MICRO:
        return FsmState.INDOOR
    if scene == SCENE_OUTDOOR_APPROACH:
        return FsmState.APPROACH
    return FsmState.OUTDOOR


def resolve_oracle(episode: Mapping[str, Any]) -> RouterOutput:
    """Oracle router: ground-truth scene from annotation (sim / replay eval)."""
    scene = episode_scene(episode)
    return RouterOutput(
        fsm_state=scene_to_fsm_state(scene),
        scene=scene,
        policy_id=scene_to_policy_id(scene),
        map_id=episode_map_id(episode, scene),
    )


@dataclass
class HandoverRouter:
    """Stateful router with optional waypoint hysteresis (deploy path)."""

    mode: str = "oracle"
    approach_radius_m: float = 10.0
    indoor_confirm_frames: int = 5
    outdoor_confirm_frames: int = 5
    indoor_geofence: Optional[np.ndarray] = None  # [N, 3] polygon vertices xy (z ignored)

    _state: FsmState = FsmState.OUTDOOR
    _indoor_streak: int = 0
    _outdoor_streak: int = 0

    def reset(self, initial: FsmState = FsmState.OUTDOOR) -> None:
        self._state = initial
        self._indoor_streak = 0
        self._outdoor_streak = 0

    def step(self, inp: RouterInput) -> RouterOutput:
        if self.mode == "oracle":
            if inp.episode is None:
                raise ValueError("oracle mode requires RouterInput.episode")
            out = resolve_oracle(inp.episode)
            self._state = out.fsm_state
            return out
        return self._step_waypoint(inp)

    def _step_waypoint(self, inp: RouterInput) -> RouterOutput:
        cmd = (inp.gcs_command or "").strip().lower()
        if cmd in ("switch_indoor", "indoor"):
            self._state = FsmState.INDOOR
        elif cmd in ("switch_outdoor", "outdoor"):
            self._state = FsmState.OUTDOOR

        pos = None
        if inp.p_hat is not None:
            pos = np.asarray(inp.p_hat, dtype=np.float64).reshape(3)

        if self._state != FsmState.INDOOR and pos is not None and inp.handover_wp is not None:
            wp = np.asarray(inp.handover_wp, dtype=np.float64).reshape(3)
            if float(np.linalg.norm(pos[:2] - wp[:2])) <= float(self.approach_radius_m):
                self._state = FsmState.APPROACH

        in_fence = False
        if pos is not None and self.indoor_geofence is not None and len(self.indoor_geofence) >= 3:
            in_fence = _point_in_polygon_xy(pos[:2], self.indoor_geofence[:, :2])

        if in_fence or (inp.gnss_ok is False and self._state == FsmState.APPROACH):
            self._indoor_streak += 1
            self._outdoor_streak = 0
        else:
            self._outdoor_streak += 1
            self._indoor_streak = 0

        if self._state != FsmState.INDOOR and self._indoor_streak >= int(self.indoor_confirm_frames):
            self._state = FsmState.INDOOR
        if self._state == FsmState.INDOOR and self._outdoor_streak >= int(self.outdoor_confirm_frames):
            if not in_fence:
                self._state = FsmState.OUTDOOR

        seg = (inp.mission_segment or "").strip().lower()
        if seg == "indoor":
            scene = SCENE_INDOOR_MICRO
        elif seg == "approach":
            scene = SCENE_OUTDOOR_APPROACH
        elif seg == "outdoor":
            scene = SCENE_OUTDOOR_LONG
        else:
            scene = {
                FsmState.OUTDOOR: SCENE_OUTDOOR_LONG,
                FsmState.APPROACH: SCENE_OUTDOOR_APPROACH,
                FsmState.INDOOR: SCENE_INDOOR_MICRO,
            }[self._state]

        return RouterOutput(
            fsm_state=self._state,
            scene=scene,
            policy_id=scene_to_policy_id(scene),
            map_id=MAP_INDOOR if scene == SCENE_INDOOR_MICRO else MAP_OUTDOOR,
        )


def _point_in_polygon_xy(point: np.ndarray, polygon: np.ndarray) -> bool:
    """Ray-casting test; polygon closed or open."""
    x, y = float(point[0]), float(point[1])
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = float(polygon[i, 0]), float(polygon[i, 1])
        xj, yj = float(polygon[j, 0]), float(polygon[j, 1])
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def build_router_manifest(episodes: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    router = HandoverRouter(mode="oracle")
    rows: List[Dict[str, Any]] = []
    for i, ep in enumerate(episodes):
        out = router.step(RouterInput(episode=dict(ep)))
        rows.append(
            {
                "index": i,
                "handover_id": ep.get("handover_id"),
                "segment_name": ep.get("segment_name") or ep.get("trajectory_id"),
                "fsm_state": out.fsm_state.value,
                "scene": out.scene,
                "policy_id": out.policy_id,
                "map_id": out.map_id,
            }
        )
    return rows
