"""Indoor-only annotation corpus for Phase-3 decouple (P3-indoor).

Every episode must be ``scene=indoor_micro``, ``map_id=building_99``, ``leg=indoor``.
Collect and train scripts call ``assert_indoor_episode`` before running.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Sequence

from experiments.aerial.rl.scene_profile import SCENE_INDOOR_MICRO

MAP_INDOOR = "building_99"
LEG_INDOOR = "indoor"
DEFAULT_HANDOVER_ANNOTATION = "experiments/aerial/phase3_unified/annotations/handover_seen_filtered.json"
DEFAULT_B99_ROUTES = "experiments/aerial/phase3_unified/annotations/building99_indoor_short_routes.json"


class IndoorSceneError(ValueError):
    """Episode failed indoor scene contract."""


def _load_json_episodes(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "episodes" in data:
        return list(data["episodes"])
    if isinstance(data, list):
        return list(data)
    raise ValueError(f"unsupported annotation format in {path}")


def tag_indoor_episode(ep: MutableMapping[str, Any], *, source: str) -> Dict[str, Any]:
    out = dict(ep)
    out["scene"] = SCENE_INDOOR_MICRO
    out["map_id"] = MAP_INDOOR
    out["leg"] = LEG_INDOOR
    out.setdefault("pose_source", "gt_proxy")
    out["indoor_source"] = source
    return out


def assert_indoor_episode(ep: Mapping[str, Any], *, label: str = "") -> None:
    scene = str(ep.get("scene") or "").strip()
    map_id = str(ep.get("map_id") or "").strip()
    leg = str(ep.get("leg") or "").strip().lower()
    prefix = f"{label}: " if label else ""
    if scene != SCENE_INDOOR_MICRO:
        raise IndoorSceneError(f"{prefix}scene must be {SCENE_INDOOR_MICRO!r}, got {scene!r}")
    if map_id != MAP_INDOOR:
        raise IndoorSceneError(f"{prefix}map_id must be {MAP_INDOOR!r}, got {map_id!r}")
    if leg and leg != LEG_INDOOR:
        raise IndoorSceneError(f"{prefix}leg must be {LEG_INDOOR!r}, got {leg!r}")


def filter_handover_indoor_legs(episodes: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for ep in episodes:
        scene = str(ep.get("scene") or "").strip()
        map_id = str(ep.get("map_id") or "").strip()
        leg = str(ep.get("leg") or "").strip().lower()
        if scene == SCENE_INDOOR_MICRO or map_id == MAP_INDOOR or leg == LEG_INDOOR:
            tagged = tag_indoor_episode(ep, source="handover")
            assert_indoor_episode(tagged, label=str(ep.get("segment_name") or ep.get("trajectory_id")))
            out.append(tagged)
    return out


def load_b99_short_routes(path: Path) -> List[Dict[str, Any]]:
    routes = _load_json_episodes(path)
    out: List[Dict[str, Any]] = []
    for r in routes:
        tagged = tag_indoor_episode(r, source="b99_short")
        assert_indoor_episode(tagged, label=str(tagged.get("trajectory_id")))
        out.append(tagged)
    return out


def _dedupe_key(ep: Mapping[str, Any]) -> str:
    """Handover legs are unique per ``handover_id``; B99 shorts by ``trajectory_id``."""
    hid = str(ep.get("handover_id") or "").strip()
    seg = str(ep.get("segment_name") or ep.get("trajectory_id") or "").strip()
    if hid:
        return f"handover:{hid}:{seg}"
    return f"b99:{seg}"


def _trajectory_id(ep: Mapping[str, Any]) -> str:
    return str(ep.get("trajectory_id") or ep.get("segment_name") or "").strip()


def merge_indoor_episodes(
    handover_indoor: Sequence[Dict[str, Any]],
    b99_short: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    merged: List[Dict[str, Any]] = []
    handover_tids = {_trajectory_id(ep) for ep in handover_indoor if _trajectory_id(ep)}

    for ep in handover_indoor:
        key = _dedupe_key(ep)
        if not key or key in seen:
            continue
        seen.add(key)
        assert_indoor_episode(ep, label=key)
        merged.append(ep)

    for ep in b99_short:
        tid = _trajectory_id(ep)
        if tid and tid in handover_tids:
            continue
        key = _dedupe_key(ep)
        if not key or key in seen:
            continue
        seen.add(key)
        assert_indoor_episode(ep, label=key)
        merged.append(ep)
    return merged


def build_indoor_annotation(
    *,
    handover_path: str | Path = DEFAULT_HANDOVER_ANNOTATION,
    b99_path: str | Path = DEFAULT_B99_ROUTES,
    include_b99_short: bool = True,
) -> Dict[str, Any]:
    handover_eps = _load_json_episodes(Path(handover_path))
    handover_indoor = filter_handover_indoor_legs(handover_eps)
    b99_eps: List[Dict[str, Any]] = []
    if include_b99_short:
        b99_eps = load_b99_short_routes(Path(b99_path))
    episodes = merge_indoor_episodes(handover_indoor, b99_eps)
    if not episodes:
        raise ValueError("no indoor episodes after merge — check handover + B99 annotations")
    for ep in episodes:
        assert_indoor_episode(ep, label=_dedupe_key(ep))
    return {
        "protocol_version": "phase3_indoor_v0",
        "maps": {MAP_INDOOR: "Building_99 indoor lobby (separate renderer; z~1.5m)"},
        "scene_mix": {
            "outdoor_prob": 0.0,
            "indoor_prob": 1.0,
            "require_scene_tag": True,
            "allowed_scenes": [SCENE_INDOOR_MICRO],
            "handover_indoor_n": len(handover_indoor),
            "b99_short_n": len(b99_eps),
            "total_n": len(episodes),
        },
        "episodes": episodes,
    }


def write_indoor_annotation(
    out_path: str | Path,
    *,
    handover_path: str | Path = DEFAULT_HANDOVER_ANNOTATION,
    b99_path: str | Path = DEFAULT_B99_ROUTES,
    include_b99_short: bool = True,
) -> Path:
    payload = build_indoor_annotation(
        handover_path=handover_path,
        b99_path=b99_path,
        include_b99_short=include_b99_short,
    )
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def assert_indoor_collection_summary(summary: Mapping[str, Any]) -> None:
    for row in summary.get("episodes") or []:
        scene = str(row.get("scene") or "").strip()
        map_id = str(row.get("map_id") or "").strip()
        label = str(row.get("file") or row.get("segment_name") or "?")
        if scene != SCENE_INDOOR_MICRO:
            raise IndoorSceneError(f"collected {label}: scene={scene!r}")
        if map_id != MAP_INDOOR:
            raise IndoorSceneError(f"collected {label}: map_id={map_id!r}")
