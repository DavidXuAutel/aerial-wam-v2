#!/usr/bin/env python3
"""Build outdoor-heavy replay dataset for Phase-3 P2b offline FT.

``train_v4_ac`` samples episodes uniformly from the replay buffer. P2a used
44 eps (30 outdoor + 14 indoor) and regressed outdoor close (0/16 SR vs
Phase-2 13/16). P2b oversamples outdoor npz files via symlinks so imagination
replay is ~90% outdoor without changing the trainer.

Episode order matches ``handover_seen_filtered.json`` == ``episode_00000``…
from ``collect_phase3_handover``.
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("build_phase3_p2b_replay")

OUTDOOR_SCENES = frozenset({"outdoor_long", "outdoor_approach"})


def _episode_scenes(annotation: Path) -> List[str]:
    data = json.loads(annotation.read_text(encoding="utf-8"))
    eps = data.get("episodes", data)
    if not isinstance(eps, list):
        raise SystemExit(f"bad annotation: no episodes list in {annotation}")
    return [str(ep.get("scene", "")) for ep in eps]


def build_dataset(
    src: Path,
    out: Path,
    annotation: Path,
    *,
    outdoor_repeat: int,
    indoor_repeat: int,
    outdoor_only: bool,
    materialize: bool,
) -> Dict[str, Any]:
    src_eps = sorted(src.glob("episode_*.npz"))
    if not src_eps:
        raise SystemExit(f"no episode_*.npz under {src}")

    scenes = _episode_scenes(annotation)
    if len(scenes) != len(src_eps):
        raise SystemExit(
            f"annotation episodes ({len(scenes)}) != npz count ({len(src_eps)}) — "
            "re-collect or fix annotation order"
        )

    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("episode_*.npz"):
        old.unlink()

    entries: List[Dict[str, Any]] = []
    out_idx = 0
    for src_idx, (src_path, scene) in enumerate(zip(src_eps, scenes)):
        is_outdoor = scene in OUTDOOR_SCENES
        if outdoor_only and not is_outdoor:
            continue
        repeat = outdoor_repeat if is_outdoor else indoor_repeat
        for rep in range(repeat):
            dst = out / f"episode_{out_idx:05d}.npz"
            if dst.exists() or dst.is_symlink():
                dst.unlink()
            if materialize:
                shutil.copy2(src_path, dst)
            else:
                dst.symlink_to(src_path.resolve())
            entries.append(
                {
                    "out_index": out_idx,
                    "src_index": src_idx,
                    "src_file": src_path.name,
                    "scene": scene,
                    "repeat": rep,
                }
            )
            out_idx += 1

    outdoor_n = sum(1 for e in entries if e["scene"] in OUTDOOR_SCENES)
    indoor_n = len(entries) - outdoor_n
    meta = {
        "protocol": "phase3_p2b_replay_v0",
        "src_dataset": str(src),
        "annotation": str(annotation),
        "outdoor_repeat": outdoor_repeat,
        "indoor_repeat": indoor_repeat,
        "outdoor_only": outdoor_only,
        "materialize": materialize,
        "n_episodes": len(entries),
        "n_outdoor": outdoor_n,
        "n_indoor": indoor_n,
        "outdoor_fraction": round(outdoor_n / max(len(entries), 1), 4),
    }
    manifest = {"meta": meta, "episodes": entries}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logger.info(
        "wrote %s (%d episodes, outdoor=%d indoor=%d frac=%.1f%%)",
        out,
        len(entries),
        outdoor_n,
        indoor_n,
        100.0 * meta["outdoor_fraction"],
    )
    return meta


def main() -> int:
    p = argparse.ArgumentParser(description="Build P2b outdoor-heavy replay dataset")
    p.add_argument(
        "--src",
        default="experiments/aerial/rl/artifacts/dataset_phase3_handover_seen",
    )
    p.add_argument(
        "--annotation",
        default="experiments/aerial/phase3_unified/annotations/handover_seen_filtered.json",
    )
    p.add_argument(
        "--out",
        default="experiments/aerial/rl/artifacts/dataset_phase3_p2b_outdoor_heavy",
    )
    p.add_argument(
        "--mode",
        choices=("outdoor_heavy", "outdoor_only"),
        default="outdoor_heavy",
        help="outdoor_heavy: outdoor×4 indoor×1 (~90%%); outdoor_only: drop indoor",
    )
    p.add_argument("--outdoor-repeat", type=int, default=4)
    p.add_argument("--indoor-repeat", type=int, default=1)
    p.add_argument(
        "--symlink",
        action="store_true",
        help="symlink instead of copy (125-local only; H100 sync needs copies)",
    )
    args = p.parse_args()

    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    outdoor_only = args.mode == "outdoor_only"
    outdoor_repeat = max(1, int(args.outdoor_repeat))
    indoor_repeat = max(1, int(args.indoor_repeat))
    if outdoor_only:
        indoor_repeat = 0

    build_dataset(
        root / args.src,
        root / args.out,
        root / args.annotation,
        outdoor_repeat=outdoor_repeat,
        indoor_repeat=indoor_repeat,
        outdoor_only=outdoor_only,
        materialize=not args.symlink,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
