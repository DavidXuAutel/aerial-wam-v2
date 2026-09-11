#!/usr/bin/env python3
"""Collect Phase-3 handover corpus with per-episode AirSim map switching.

Switches ``env_airsim_16`` ↔ ``building_99`` via ``recover_renderer_scene.sh``
when ``episode.map_id`` changes.
"""
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("collect_phase3_handover")

MAP_OUTDOOR = "env_airsim_16"
MAP_INDOOR = "building_99"


def _load_episodes(path: Path) -> List[Dict[str, Any]]:
    from experiments.aerial.eval.run_closed_loop import load_annotation

    return load_annotation(path)


def _switch_map(map_id: str, scene_sh: Path, *, dry_run: bool = False) -> None:
    if map_id == MAP_OUTDOOR:
        arg = "outdoor"
    elif map_id in (MAP_INDOOR, "building_99", "Building_99"):
        arg = "building99"
    else:
        raise ValueError(f"unknown map_id {map_id!r}")
    if dry_run:
        logger.info("[dry-run] would switch scene -> %s", arg)
        return
    if not scene_sh.is_file():
        raise FileNotFoundError(f"missing scene switch script: {scene_sh}")
    logger.info("switching AirSim scene -> %s", arg)
    subprocess.run(["bash", str(scene_sh), arg], check=True)
    time.sleep(15)


def main() -> int:
    p = argparse.ArgumentParser(description="Collect Phase-3 handover corpus")
    p.add_argument(
        "--config",
        default="configs/aerial_rl_phase3_unified.yaml",
    )
    p.add_argument(
        "--annotation",
        default="experiments/aerial/phase3_unified/annotations/handover_seen.json",
    )
    p.add_argument(
        "--scene-script",
        default="experiments/aerial/phase3_unified/scripts/recover_renderer_scene.sh",
        help="On 125, prefer ~/aerial-indoor-wam/experiments/aerial/scripts/recover_renderer_scene.sh",
    )
    p.add_argument("--out", default="experiments/aerial/rl/artifacts/dataset_phase3_handover_seen")
    p.add_argument("--episodes", type=int, default=0, help="0 = all in annotation")
    p.add_argument("--max-steps", type=int, default=200)
    p.add_argument("--step-hz", type=float, default=5.0)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=41451)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--handover-only", action="store_true", help="Skip outdoor_long-only episodes")
    args = p.parse_args()

    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    ann_path = root / args.annotation
    episodes = _load_episodes(ann_path)
    if args.handover_only:
        episodes = [e for e in episodes if e.get("handover_id")]
    n = int(args.episodes) if int(args.episodes) > 0 else len(episodes)
    episodes = episodes[:n]

    scene_sh = Path(args.scene_script)
    if not scene_sh.is_file():
        alt = Path.home() / "aerial-indoor-wam/experiments/aerial/scripts/recover_renderer_scene.sh"
        if alt.is_file():
            scene_sh = alt

    from experiments.aerial.rl.collect_dataset import _resolve_cfg
    from experiments.aerial.rl.train_rl import build_from_config
    from experiments.aerial.rl.collector import CollectStats
    from experiments.aerial.rl import dataset as ds

    ns = argparse.Namespace(
        backend="airsim",
        episodes=n,
        max_steps=args.max_steps,
        step_hz=args.step_hz,
        out=str(args.out),
        host=args.host,
        port=args.port,
        camera="front_custom",
        vehicle="drone_1",
        grab_depth=False,
        config=str(root / args.config),
        annotation=None,
        approach_bias=False,
        approach_dist_m=25.0,
    )
    cfg = _resolve_cfg(ns)
    loop = build_from_config(cfg)

    out_dir = root / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest: List[dict] = []

    def _sink(transitions, stats: CollectStats) -> None:
        idx = len(manifest)
        path = ds.write_episode(out_dir, idx, transitions)
        info0 = getattr(transitions[0], "info", {}) if transitions else {}
        manifest.append({
            "file": path.name,
            "steps": len(transitions),
            "scene": info0.get("scene"),
            "map_id": info0.get("map_id"),
            "handover_id": info0.get("handover_id"),
            "achieved_hz": round(stats.achieved_hz, 2),
        })
        logger.info(
            "ep %d saved %s scene=%s map=%s handover=%s",
            idx,
            path.name,
            info0.get("scene"),
            info0.get("map_id"),
            info0.get("handover_id"),
        )

    loop.collector.on_episode = _sink
    current_map: Optional[str] = None

    try:
        for i, ep in enumerate(episodes):
            map_id = str(ep.get("map_id") or MAP_OUTDOOR)
            if map_id != current_map:
                _switch_map(map_id, scene_sh, dry_run=bool(args.dry_run))
                current_map = map_id
            if args.dry_run:
                logger.info(
                    "[dry-run] would collect ep %d map=%s scene=%s handover=%s",
                    i,
                    map_id,
                    ep.get("scene"),
                    ep.get("handover_id"),
                )
                continue
            ep_run = dict(ep)
            ep_run.setdefault("map_id", map_id)
            loop.collector.collect_episode(ep_run)
    finally:
        close = getattr(loop.collector.env, "close", None)
        if callable(close):
            close()

    summary = {
        "annotation": str(ann_path),
        "n_collected": len(manifest),
        "episodes": manifest,
    }
    (out_dir / "collection_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    logger.info("done: %d episodes -> %s", len(manifest), out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
