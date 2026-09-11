"""Build indoor-outdoor handover annotation corpora for Phase-3.

AirSim has **separate maps** (no single Unreal level with a doorway):
  - ``env_airsim_16`` — outdoor OpenFly city (z ~ 8–84 m)
  - ``building_99`` — indoor lobby (z ~ 1.5 m, local origin)

A *handover* episode pair = outdoor approach leg on ``env_airsim_16`` +
indoor micro leg on ``building_99``. Legs share ``handover_id`` but require
renderer switch between collects (see ``collect_phase3_handover.py``).
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from experiments.aerial.rl.scene_profile import SCENE_INDOOR_MICRO, SCENE_OUTDOOR_LONG

MAP_OUTDOOR = "env_airsim_16"
MAP_INDOOR = "building_99"
SCENE_OUTDOOR_APPROACH = "outdoor_approach"

_BUILDING_KEYWORDS = (
    "building",
    "skyscraper",
    "facade",
    "rooftop",
    "apartment",
    "commercial",
    "structure",
    "ventilation",
)


def _load_routes(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "routes" in data:
        return list(data["routes"])
    if isinstance(data, list):
        return data
    raise ValueError(f"unsupported annotation format in {path}")


def _slice_approach_segment(
    route: Dict[str, Any],
    *,
    target_len_m: float = 30.0,
    route_idx: int,
) -> Dict[str, Any]:
    pos_arr = np.asarray(route["pos"], dtype=np.float64)
    yaw_arr = np.asarray(route["yaw"], dtype=np.float64).reshape(-1)
    end_idx = 1
    cum = 0.0
    for k in range(len(pos_arr) - 1):
        cum += float(np.linalg.norm(pos_arr[k + 1] - pos_arr[k]))
        end_idx = k + 1
        if cum >= target_len_m:
            break
    start = pos_arr[0].copy()
    goal = pos_arr[end_idx].copy()
    return {
        "route_id": route.get("route_id"),
        "source_route_idx": route_idx,
        "segment_name": f"Approach_Route_{route_idx + 1:02d}",
        "pos": [start.tolist(), goal.tolist()],
        "yaw": [float(yaw_arr[0]), float(yaw_arr[min(end_idx, len(yaw_arr) - 1)])],
        "d0_m": round(float(np.linalg.norm(goal - start)), 3),
        "gpt_instruction": (route.get("gpt_instruction", "")[:120] + " (outdoor approach)"),
        "map_id": MAP_OUTDOOR,
        "scene": SCENE_OUTDOOR_APPROACH,
        "leg": "outdoor",
        "pose_source": "gt_proxy",
    }


def build_outdoor_approach_segments(
    outdoor_path: str | Path,
    *,
    route_indices: Optional[Sequence[int]] = None,
    target_len_m: float = 30.0,
) -> List[Dict[str, Any]]:
    routes = _load_routes(Path(outdoor_path))
    chosen: List[int] = []
    if route_indices is not None:
        chosen = list(route_indices)
    else:
        for i, r in enumerate(routes):
            ins = (r.get("gpt_instruction") or "").lower()
            if any(k in ins for k in _BUILDING_KEYWORDS):
                chosen.append(i)
    segs: List[Dict[str, Any]] = []
    for idx in chosen:
        if idx >= len(routes):
            continue
        seg = _slice_approach_segment(routes[idx], target_len_m=target_len_m, route_idx=idx)
        segs.append(seg)
    return segs


def tag_building99_routes(
    routes: Sequence[Dict[str, Any]],
    *,
    segment_len_m: float = 3.0,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in routes:
        ep = dict(r)
        ep["map_id"] = MAP_INDOOR
        ep["scene"] = SCENE_INDOOR_MICRO
        ep["leg"] = "indoor"
        ep.setdefault("pose_source", "gt_proxy")
        ep.setdefault("segment_name", ep.get("trajectory_id", "B99"))
        pos = ep.get("pos") or []
        if len(pos) >= 2:
            p0 = [float(x) for x in pos[0]]
            p1 = [float(x) for x in pos[-1]]
            ep["d0_m"] = round(
                math.sqrt((p1[0] - p0[0]) ** 2 + (p1[1] - p0[1]) ** 2 + (p1[2] - p0[2]) ** 2),
                3,
            )
        out.append(ep)
    return out


def build_handover_pairs(
    outdoor_legs: Sequence[Dict[str, Any]],
    indoor_legs: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Interleave outdoor→indoor legs with shared ``handover_id``."""
    pairs: List[Dict[str, Any]] = []
    n = max(len(outdoor_legs), len(indoor_legs), 1)
    for i in range(n):
        hid = f"HO{i + 1:02d}"
        out_leg = dict(outdoor_legs[i % len(outdoor_legs)])
        in_leg = dict(indoor_legs[i % len(indoor_legs)])
        out_leg["handover_id"] = hid
        in_leg["handover_id"] = hid
        pairs.append(out_leg)
        pairs.append(in_leg)
    return pairs


def build_handover_annotation(
    *,
    outdoor_path: str | Path = "artifacts/seen_airsim16_long_routes.json",
    indoor_path: str | Path = "experiments/aerial/phase3_unified/annotations/building99_indoor_short_routes.json",
    outdoor_route_indices: Optional[Sequence[int]] = None,
    outdoor_approach_len_m: float = 30.0,
    include_long_outdoor: bool = True,
    seed: int = 0,
) -> Dict[str, Any]:
    outdoor_routes = _load_routes(Path(outdoor_path))
    approach = build_outdoor_approach_segments(
        outdoor_path,
        route_indices=outdoor_route_indices,
        target_len_m=outdoor_approach_len_m,
    )
    indoor_raw = _load_routes(Path(indoor_path))
    indoor = tag_building99_routes(indoor_raw)

    handover_eps = build_handover_pairs(approach, indoor)

    extra: List[Dict[str, Any]] = []
    if include_long_outdoor:
        from experiments.aerial.phase3_unified.mixed_corpus import tag_outdoor_routes

        extra = tag_outdoor_routes(outdoor_routes)

    import random

    pool = list(handover_eps) + list(extra)
    random.Random(seed).shuffle(pool)

    return {
        "protocol_version": "phase3_handover_v0",
        "maps": {
            MAP_OUTDOOR: "outdoor OpenFly city (AirVLN / env_airsim_16)",
            MAP_INDOOR: "Building_99 indoor lobby (z~1.5m, separate renderer)",
        },
        "note": (
            "No single-map doorway — handover pairs switch renderer between legs. "
            "handover_id links outdoor_approach + indoor_micro."
        ),
        "scene_mix": {
            "handover_pairs": len(approach),
            "outdoor_approach_n": len(approach),
            "indoor_b99_n": len(indoor),
            "outdoor_long_n": len(extra),
            "total_n": len(pool),
            "seed": seed,
        },
        "episodes": pool,
    }


def write_handover_annotation(out_path: str | Path, **kwargs: Any) -> Path:
    payload = build_handover_annotation(**kwargs)
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
