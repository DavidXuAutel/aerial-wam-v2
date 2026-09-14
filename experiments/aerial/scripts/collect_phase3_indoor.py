#!/usr/bin/env python3
"""Collect P3-indoor rollouts on Building_99 only.

Validates every annotation episode is ``indoor_micro`` / ``building_99`` before
collect. Always switches renderer to ``building99`` once at start.
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
logger = logging.getLogger("collect_phase3_indoor")

MAP_INDOOR = "building_99"


def _load_episodes(path: Path) -> List[Dict[str, Any]]:
    from experiments.aerial.eval.run_closed_loop import load_annotation

    raw = load_annotation(path)
    if isinstance(raw, list):
        return raw
    return list(raw.get("episodes") or [])


def _switch_building99(scene_sh: Path, *, dry_run: bool = False) -> None:
    if dry_run:
        logger.info("[dry-run] would switch scene -> building99")
        return
    if not scene_sh.is_file():
        raise FileNotFoundError(f"missing scene switch script: {scene_sh}")
    logger.info("switching AirSim scene -> building99 (indoor)")
    subprocess.run(["bash", str(scene_sh), "building99"], check=True)
    time.sleep(15)


def main() -> int:
    p = argparse.ArgumentParser(description="Collect P3-indoor corpus (Building_99 only)")
    p.add_argument("--config", default="configs/aerial_rl_phase3_indoor.yaml")
    p.add_argument(
        "--annotation",
        default="experiments/aerial/phase3_unified/annotations/phase3_indoor_seen.json",
    )
    p.add_argument(
        "--scene-script",
        default="experiments/aerial/phase3_unified/scripts/recover_renderer_scene.sh",
    )
    p.add_argument("--out", default="experiments/aerial/rl/artifacts/dataset_phase3_indoor_seen")
    p.add_argument("--episodes", type=int, default=0, help="0 = all in annotation")
    p.add_argument("--max-steps", type=int, default=60)
    p.add_argument("--step-hz", type=float, default=5.0)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=41451)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--spawn-retries", type=int, default=3)
    p.add_argument("--start-idx", type=int, default=0)
    args = p.parse_args()

    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from experiments.aerial.phase3_unified.indoor_corpus import assert_indoor_episode

    ann_path = root / args.annotation
    if not ann_path.is_file():
        logger.error("missing annotation %s — run build_phase3_indoor_annotation.py first", ann_path)
        return 1

    episodes = _load_episodes(ann_path)
    for ep in episodes:
        assert_indoor_episode(ep, label=str(ep.get("segment_name") or ep.get("trajectory_id")))

    n = int(args.episodes) if int(args.episodes) > 0 else len(episodes)
    episodes = episodes[:n]
    logger.info("indoor collect: %d episodes (all scene=indoor_micro map=%s)", len(episodes), MAP_INDOOR)

    scene_sh = Path(args.scene_script)
    if not scene_sh.is_file():
        alt = Path.home() / "aerial-indoor-wam/experiments/aerial/scripts/recover_renderer_scene.sh"
        if alt.is_file():
            scene_sh = alt

    _switch_building99(scene_sh, dry_run=bool(args.dry_run))

    if args.dry_run:
        for i, ep in enumerate(episodes):
            logger.info(
                "[dry-run] ep %d %s scene=%s map=%s",
                i,
                ep.get("segment_name") or ep.get("trajectory_id"),
                ep.get("scene"),
                ep.get("map_id"),
            )
        return 0

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
        idx = int(args.start_idx) + len(manifest)
        path = ds.write_episode(out_dir, idx, transitions)
        info0 = getattr(transitions[0], "info", {}) if transitions else {}
        scene = str(info0.get("scene") or "")
        map_id = str(info0.get("map_id") or "")
        if scene != "indoor_micro" or map_id != MAP_INDOOR:
            raise RuntimeError(
                f"non-indoor rollout saved {path.name}: scene={scene!r} map_id={map_id!r}"
            )
        manifest.append({
            "file": path.name,
            "steps": len(transitions),
            "scene": scene,
            "map_id": map_id,
            "handover_id": info0.get("handover_id"),
            "segment_name": info0.get("segment_name"),
            "achieved_hz": round(stats.achieved_hz, 2),
        })
        logger.info("ep %d saved %s scene=%s map=%s", idx, path.name, scene, map_id)

    loop.collector.on_episode = _sink

    try:
        for i, ep in enumerate(episodes):
            assert_indoor_episode(ep, label=str(ep.get("segment_name") or ep.get("trajectory_id")))
            ep_run = dict(ep)
            ep_run.setdefault("map_id", MAP_INDOOR)
            ep_run.setdefault("scene", "indoor_micro")
            ep_run.setdefault("leg", "indoor")
            stats = None
            for attempt in range(max(1, int(args.spawn_retries))):
                _, stats = loop.collector.collect_episode(ep_run)
                if not stats.skipped:
                    break
                if attempt + 1 < int(args.spawn_retries):
                    logger.warning(
                        "spawn collision ep %d (%s) attempt %d/%d",
                        i,
                        ep.get("segment_name") or ep.get("trajectory_id"),
                        attempt + 1,
                        int(args.spawn_retries),
                    )
                    time.sleep(0.5)
            if stats is not None and stats.skipped:
                logger.warning(
                    "skipped ep %d (%s) after %d spawn retries",
                    i,
                    ep.get("segment_name") or ep.get("trajectory_id"),
                    int(args.spawn_retries),
                )
    finally:
        close = getattr(loop.collector.env, "close", None)
        if callable(close):
            close()

    prior: List[dict] = []
    if int(args.start_idx) > 0:
        prior_path = out_dir / "collection_summary.json"
        if prior_path.is_file():
            try:
                prior = list(json.loads(prior_path.read_text(encoding="utf-8")).get("episodes", []))
            except Exception:  # noqa: BLE001
                prior = []
    all_eps = prior + manifest
    summary = {
        "annotation": str(ann_path),
        "renderer": "building99",
        "n_collected": len(all_eps),
        "episodes": all_eps,
    }
    from experiments.aerial.phase3_unified.indoor_corpus import assert_indoor_collection_summary

    assert_indoor_collection_summary(summary)
    (out_dir / "collection_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    logger.info("done: %d indoor episodes -> %s", len(manifest), out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
