"""Build mixed outdoor + indoor annotation corpora for Phase-3 unified training."""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from experiments.aerial.rl.scene_profile import SCENE_INDOOR_MICRO, SCENE_OUTDOOR_LONG

DEFAULT_OUTDOOR_ANNOTATION = "artifacts/seen_airsim16_long_routes.json"
DEFAULT_INDOOR_ROUTE_INDICES = [6, 9, 12, 13]


def _load_routes(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "routes" in data:
        return list(data["routes"])
    if isinstance(data, list):
        return data
    raise ValueError(f"unsupported annotation format in {path}")


def build_indoor_segments(
    routes: Sequence[Dict[str, Any]],
    route_indices: Sequence[int],
    *,
    target_len_m: float = 10.0,
) -> List[Dict[str, Any]]:
    from experiments.aerial.scripts.indoor_mainline_baseline_eval import build_segments

    segments = build_segments(list(routes), list(route_indices), target_len_m=target_len_m)
    for seg in segments:
        seg["scene"] = SCENE_INDOOR_MICRO
        seg["pose_source"] = "gt_proxy"
    return segments


def tag_outdoor_routes(routes: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in routes:
        ep = dict(r)
        ep["scene"] = SCENE_OUTDOOR_LONG
        ep.setdefault("pose_source", "gt_proxy")
        out.append(ep)
    return out


def build_mixed_corpus(
    *,
    outdoor_routes: Sequence[Dict[str, Any]],
    indoor_segments: Sequence[Dict[str, Any]],
    outdoor_prob: float = 0.7,
    seed: int = 0,
    shuffle: bool = True,
) -> List[Dict[str, Any]]:
    """Union of all outdoor + indoor episodes, shuffled (P1 seen pool).

    ``outdoor_prob`` is recorded in metadata as the FT target mix; the episode
    pool itself includes every seen outdoor route and indoor segment.
    """
    if not 0.0 <= outdoor_prob <= 1.0:
        raise ValueError(f"outdoor_prob must be in [0, 1], got {outdoor_prob}")
    pool: List[Dict[str, Any]] = [dict(x) for x in outdoor_routes] + [dict(x) for x in indoor_segments]
    if shuffle:
        random.Random(seed).shuffle(pool)
    return pool


def build_mixed_annotation(
    outdoor_path: str | Path,
    *,
    indoor_route_indices: Sequence[int] = DEFAULT_INDOOR_ROUTE_INDICES,
    indoor_segment_len_m: float = 10.0,
    outdoor_prob: float = 0.7,
    seed: int = 0,
) -> Dict[str, Any]:
    routes = _load_routes(Path(outdoor_path))
    outdoor = tag_outdoor_routes(routes)
    indoor = build_indoor_segments(
        routes,
        indoor_route_indices,
        target_len_m=indoor_segment_len_m,
    )
    mixed = build_mixed_corpus(
        outdoor_routes=outdoor,
        indoor_segments=indoor,
        outdoor_prob=outdoor_prob,
        seed=seed,
    )
    return {
        "protocol_version": "phase3_unified_mixed_v0",
        "scene_mix": {
            "outdoor_prob": outdoor_prob,
            "indoor_prob": round(1.0 - outdoor_prob, 4),
            "outdoor_n": len(outdoor),
            "indoor_n": len(indoor),
            "mixed_n": len(mixed),
            "seed": seed,
        },
        "episodes": mixed,
    }


def write_mixed_annotation(
    out_path: str | Path,
    *,
    outdoor_path: str | Path = DEFAULT_OUTDOOR_ANNOTATION,
    indoor_route_indices: Optional[Sequence[int]] = None,
    indoor_segment_len_m: float = 10.0,
    outdoor_prob: float = 0.7,
    seed: int = 0,
) -> Path:
    payload = build_mixed_annotation(
        outdoor_path,
        indoor_route_indices=indoor_route_indices or DEFAULT_INDOOR_ROUTE_INDICES,
        indoor_segment_len_m=indoor_segment_len_m,
        outdoor_prob=outdoor_prob,
        seed=seed,
    )
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
