#!/usr/bin/env python3
"""Collect Phase-2 toward_g expert rollouts for P2e (mainline eval stack).

Uses ``wam_phase2_long_eval`` with shield + planner + toward_g — the same stack
as the outdoor regression gate — and writes per-route ``.npz`` episodes.
"""
from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("collect_phase3_p2e_phase2_expert")


def main() -> int:
    p = argparse.ArgumentParser(description="Collect Phase-2 expert outdoor rollouts for P2e")
    p.add_argument(
        "--annotation",
        default="experiments/aerial/phase3_unified/annotations/outdoor_long_only.json",
    )
    p.add_argument(
        "--actor-ckpt",
        default="experiments/aerial/rl/artifacts/v4_ac_ckpt_phase2_toward_g_20260905_112006/v4_ac_latest.pt",
    )
    p.add_argument(
        "--wm-ckpt",
        default="experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt",
    )
    p.add_argument("--out", default="experiments/aerial/rl/artifacts/dataset_phase3_p2e_phase2_expert")
    p.add_argument("--max-steps", type=int, default=1000)
    p.add_argument("--cruise-speed", type=float, default=10.0)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=41451)
    p.add_argument(
        "--scene-script",
        default="experiments/aerial/phase3_unified/scripts/recover_renderer_scene.sh",
    )
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    scene_sh = Path(args.scene_script)
    if not scene_sh.is_file():
        alt = Path.home() / "aerial-indoor-wam/experiments/aerial/scripts/recover_renderer_scene.sh"
        if alt.is_file():
            scene_sh = alt

    out_dir = root / args.out
    manifest_json = root / "artifacts" / "p2e_phase2_expert_collect_manifest.json"

    if args.dry_run:
        logger.info("[dry-run] would collect 16 routes -> %s", out_dir)
        return 0

    if scene_sh.is_file():
        logger.info("ensuring outdoor renderer")
        subprocess.run(["bash", str(scene_sh), "outdoor"], check=True)
        time.sleep(20)
    for _ in range(24):
        try:
            import socket

            socket.create_connection((args.host, int(args.port)), 3).close()
            break
        except OSError:
            time.sleep(5)

    python_bin = os.environ.get("PYTHON_BIN", sys.executable)
    cmd = [
        python_bin,
        str(root / "experiments/aerial/scripts/wam_phase2_long_eval.py"),
        "--actor-ckpt",
        str(root / args.actor_ckpt),
        "--wm-ckpt",
        str(root / args.wm_ckpt),
        "--annotation",
        str(root / args.annotation),
        "--subgoal-source",
        "toward_g",
        "--cruise-speed",
        str(args.cruise_speed),
        "--planner",
        "--success-dist",
        "3.0",
        "--max-steps",
        str(args.max_steps),
        "--save-dataset",
        str(out_dir),
        "--out",
        str(manifest_json),
    ]
    logger.info("running: %s", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=str(root))
    n_eps = len(list(out_dir.glob("episode_*.npz")))
    logger.info("collect done: %d npz in %s (exit=%d)", n_eps, out_dir, proc.returncode)
    return 0 if n_eps >= 16 else 1


if __name__ == "__main__":
    sys.exit(main())
