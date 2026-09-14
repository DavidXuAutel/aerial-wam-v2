#!/usr/bin/env python3
"""Probe AirSim spawn health for handover annotation legs (outdoor + Building_99)."""
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("probe_handover_spawns")

MAP_OUTDOOR = "env_airsim_16"
MAP_INDOOR = "building_99"


def _switch_map(map_id: str, scene_sh: Path) -> None:
    arg = "outdoor" if map_id == MAP_OUTDOOR else "building99"
    logger.info("switch scene -> %s", arg)
    subprocess.run(["bash", str(scene_sh), arg], check=True)
    time.sleep(15)


def _probe_episodes(
    episodes: List[Dict[str, Any]],
    *,
    host: str,
    port: int,
    health_check: bool,
) -> List[Dict[str, Any]]:
    from experiments.aerial.rl.env.airsim_env import AirSimDroneEnv, AirSimEnvConfig

    env = AirSimDroneEnv(
        AirSimEnvConfig(
            host=host,
            port=port,
            grab_depth=False,
            health_check=health_check,
            warmup_frames=3,
        )
    )
    results: List[Dict[str, Any]] = []
    try:
        for i, ep in enumerate(episodes):
            label = ep.get("segment_name") or ep.get("trajectory_id") or f"ep{i}"
            try:
                obs = env.reset(ep)
                collided = bool(getattr(obs, "collided", False))
                pos = [float(x) for x in obs.position.reshape(3)]
                ok = not collided
                results.append({
                    "index": i,
                    "label": label,
                    "map_id": ep.get("map_id"),
                    "handover_id": ep.get("handover_id"),
                    "leg": ep.get("leg"),
                    "ok": ok,
                    "collided": collided,
                    "spawn_pos": pos,
                })
                logger.info(
                    "%s map=%s ok=%s collided=%s pos=%s",
                    label, ep.get("map_id"), ok, collided, [round(x, 1) for x in pos],
                )
            except Exception as exc:  # noqa: BLE001
                results.append({
                    "index": i,
                    "label": label,
                    "map_id": ep.get("map_id"),
                    "ok": False,
                    "error": str(exc),
                })
                logger.warning("%s FAILED: %s", label, exc)
    finally:
        env.close()
    return results


def main() -> int:
    p = argparse.ArgumentParser(description="Probe handover spawn poses on AirSim")
    p.add_argument(
        "--annotation",
        default="experiments/aerial/phase3_unified/annotations/handover_seen.json",
    )
    p.add_argument("--out", default="experiments/aerial/phase3_unified/annotations/spawn_probe_report.json")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=41451)
    p.add_argument("--no-health-check", action="store_true")
    p.add_argument(
        "--scene-script",
        default="experiments/aerial/phase3_unified/scripts/recover_renderer_scene.sh",
    )
    p.add_argument("--handover-only", action="store_true")
    args = p.parse_args()

    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from experiments.aerial.eval.run_closed_loop import load_annotation

    ann_path = root / args.annotation
    episodes = load_annotation(ann_path)
    if args.handover_only:
        episodes = [e for e in episodes if e.get("handover_id")]

    scene_sh = Path(args.scene_script)
    if not scene_sh.is_file():
        alt = Path.home() / "aerial-indoor-wam/experiments/aerial/scripts/recover_renderer_scene.sh"
        scene_sh = alt if alt.is_file() else scene_sh

    outdoor_eps = [e for e in episodes if e.get("map_id") == MAP_OUTDOOR or e.get("leg") == "outdoor"]
    indoor_eps = [e for e in episodes if e.get("map_id") == MAP_INDOOR or e.get("leg") == "indoor"]

    report: Dict[str, Any] = {"annotation": str(ann_path), "maps": {}}

    if outdoor_eps:
        _switch_map(MAP_OUTDOOR, scene_sh)
        report["maps"][MAP_OUTDOOR] = _probe_episodes(
            outdoor_eps,
            host=args.host,
            port=args.port,
            health_check=not args.no_health_check,
        )

    if indoor_eps:
        _switch_map(MAP_INDOOR, scene_sh)
        report["maps"][MAP_INDOOR] = _probe_episodes(
            indoor_eps,
            host=args.host,
            port=args.port,
            health_check=not args.no_health_check,
        )

    ok_out = sum(1 for r in report["maps"].get(MAP_OUTDOOR, []) if r.get("ok"))
    ok_in = sum(1 for r in report["maps"].get(MAP_INDOOR, []) if r.get("ok"))
    report["summary"] = {
        "outdoor_ok": ok_out,
        "outdoor_n": len(report["maps"].get(MAP_OUTDOOR, [])),
        "indoor_ok": ok_in,
        "indoor_n": len(report["maps"].get(MAP_INDOOR, [])),
    }

    out_path = root / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("wrote %s summary=%s", out_path, report["summary"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
