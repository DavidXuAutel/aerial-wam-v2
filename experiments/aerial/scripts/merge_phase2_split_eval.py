#!/usr/bin/env python3
"""Merge Phase-2 eval JSONs from a split (multi-box) run of ONE arm.

Two boxes each own a route subset via `--routes`; this stitches their summaries
back into a single arm-level summary whose metrics are recomputed by the very
same `aggregate_metrics` the evaluator uses. Hand-averaging two partial
summaries silently gets `max_intent_dev_deg` and any future non-mean metric
wrong, and per-file `verdict` is meaningless on a subset.

Refuses to merge JSONs that do not describe the same arm.

    python -m experiments.aerial.scripts.merge_phase2_split_eval \
        --out artifacts/wam_phase2_e1_scene_merged.json \
        artifacts/wam_phase2_e1_scene_r01_110.json \
        artifacts/wam_phase2_e1_scene_r02_125.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from experiments.aerial.scripts.wam_phase2_long_eval import (  # noqa: E402
    PASS_THRESHOLDS,
    aggregate_metrics,
    format_summary_line,
)

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("wam_phase2_merge")

# Differ on any of these and the files are not the same experiment.
IDENTITY_KEYS = (
    "protocol_version",
    "subgoal_source",
    "goal_feat_mode",
    "actor_ckpt",
    "cruise_speed_m_s",
    "rolling_global",
)


def _episode_key(ep: Dict[str, Any]) -> Any:
    """Route identity that survives a split: annotation index, else base index."""
    if ep.get("route_idx") is not None:
        return ("route_idx", int(ep["route_idx"]))
    return ("base_route_idx", ep.get("base_route_idx"))


def merge_summaries(summaries: List[Dict[str, Any]], sources: List[str]) -> Dict[str, Any]:
    if not summaries:
        raise SystemExit("refuse: nothing to merge")

    head = summaries[0]
    for src, s in zip(sources[1:], summaries[1:]):
        mismatch = {
            k: (head.get(k), s.get(k)) for k in IDENTITY_KEYS if head.get(k) != s.get(k)
        }
        if mismatch:
            raise SystemExit(
                f"refuse: {sources[0]} and {src} are not the same arm: {mismatch}"
            )

    episodes: List[Dict[str, Any]] = []
    seen: Dict[Any, str] = {}
    for src, s in zip(sources, summaries):
        for ep in s.get("episodes", []):
            key = _episode_key(ep)
            if key in seen:
                raise SystemExit(
                    f"refuse: route {key} appears in both {seen[key]} and {src} — "
                    "the boxes ran overlapping --routes"
                )
            seen[key] = src
            episodes.append({**ep, "source_json": src})

    episodes.sort(key=lambda ep: _episode_key(ep)[1] if _episode_key(ep)[1] is not None else -1)
    scored, spawn_fails, metrics, verdict = aggregate_metrics(episodes)

    merged = {k: head.get(k) for k in IDENTITY_KEYS}
    merged.update(
        {
            "merged_from": list(sources),
            "route_indices": sorted(
                i for s in summaries for i in (s.get("route_indices") or [])
            ),
            "n_scored": len(scored),
            "n_spawn_fail_f1": len(spawn_fails),
            "metrics": metrics,
            "thresholds": dict(PASS_THRESHOLDS),
            "verdict": verdict,
            "episodes": episodes,
        }
    )
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", help="per-box summary JSONs of ONE arm")
    parser.add_argument("--out", required=True, help="merged summary JSON path")
    args = parser.parse_args()

    summaries = [json.loads(Path(p).read_text(encoding="utf-8")) for p in args.inputs]
    merged = merge_summaries(summaries, list(args.inputs))

    out_file = Path(args.out)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(merged, indent=2), encoding="utf-8")

    logger.info(
        format_summary_line(
            merged,
            prefix=f"Merged {len(args.inputs)} boxes → routes {merged['route_indices']}.",
        )
    )
    logger.info("wrote %s", out_file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
