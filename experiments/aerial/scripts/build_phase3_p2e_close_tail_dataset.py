#!/usr/bin/env python3
"""Build close-tail replay slices from Phase-2 expert outdoor rollouts (P2e).

Keeps only timesteps where Euclidean distance to goal is in [dist_min, dist_max].
Each qualifying contiguous run becomes one replay episode (symlink or copy).
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("build_phase3_p2e_close_tail")


def _goal_distances(raw: np.lib.npyio.NpzFile) -> np.ndarray:
    proprio = np.asarray(raw["proprio"], dtype=np.float64)
    if "goal" not in raw.files:
        raise ValueError("npz missing goal array — re-collect with goal stamped")
    goal = np.asarray(raw["goal"], dtype=np.float64).reshape(3)
    pos = proprio[:, :3]
    return np.linalg.norm(pos - goal, axis=1)


def _contiguous_runs(mask: np.ndarray, min_len: int) -> List[Tuple[int, int]]:
    runs: List[Tuple[int, int]] = []
    start = None
    for i, ok in enumerate(mask):
        if ok and start is None:
            start = i
        elif not ok and start is not None:
            if i - start >= min_len:
                runs.append((start, i))
            start = None
    if start is not None and len(mask) - start >= min_len:
        runs.append((start, len(mask)))
    return runs


def _slice_npz(src: Path, dst: Path, start: int, end: int) -> None:
    raw = np.load(src)
    sliced: Dict[str, Any] = {}
    for key in raw.files:
        arr = raw[key]
        if arr.ndim >= 1 and arr.shape[0] == raw["rgb"].shape[0]:
            sliced[key] = arr[start:end]
        else:
            sliced[key] = arr
    np.savez_compressed(dst, **sliced)


def build_close_tail_dataset(
    src: Path,
    out: Path,
    *,
    dist_min_m: float,
    dist_max_m: float,
    min_steps: int,
    repeat: int,
    materialize: bool,
) -> Dict[str, Any]:
    src_eps = sorted(src.glob("episode_*.npz"))
    if not src_eps:
        raise SystemExit(f"no episode_*.npz under {src}")

    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("episode_*.npz"):
        old.unlink()

    entries: List[Dict[str, Any]] = []
    out_idx = 0
    for src_idx, src_path in enumerate(src_eps):
        with np.load(src_path) as raw:
            dists = _goal_distances(raw)
        mask = (dists >= dist_min_m) & (dists <= dist_max_m)
        runs = _contiguous_runs(mask, min_steps)
        if not runs:
            logger.warning("no close-tail run in %s (min_d=%.2f max_d=%.2f)", src_path.name, dists.min(), dists.max())
            continue
        for run_i, (start, end) in enumerate(runs):
            for rep in range(max(1, repeat)):
                dst = out / f"episode_{out_idx:05d}.npz"
                if dst.exists() or dst.is_symlink():
                    dst.unlink()
                tmp = out / f"_slice_{out_idx:05d}.npz"
                _slice_npz(src_path, tmp, start, end)
                if materialize:
                    shutil.move(str(tmp), str(dst))
                else:
                    dst.symlink_to(tmp.resolve())
                entries.append(
                    {
                        "out_index": out_idx,
                        "src_index": src_idx,
                        "src_file": src_path.name,
                        "slice_start": start,
                        "slice_end": end,
                        "steps": end - start,
                        "repeat": rep,
                        "d_min_m": float(dists[start:end].min()),
                        "d_max_m": float(dists[start:end].max()),
                    }
                )
                out_idx += 1

    meta = {
        "protocol": "phase3_p2e_close_tail_v0",
        "src_dataset": str(src),
        "dist_min_m": dist_min_m,
        "dist_max_m": dist_max_m,
        "min_steps": min_steps,
        "repeat": repeat,
        "materialize": materialize,
        "n_episodes": len(entries),
    }
    (out / "manifest.json").write_text(
        json.dumps({"meta": meta, "episodes": entries}, indent=2),
        encoding="utf-8",
    )
    logger.info("wrote %s (%d close-tail episodes)", out, len(entries))
    if len(entries) < 16:
        logger.warning("fewer than 16 slices — check expert collect or widen dist band")
    return meta


def main() -> int:
    p = argparse.ArgumentParser(description="Build P2e close-tail replay dataset")
    p.add_argument(
        "--src",
        default="experiments/aerial/rl/artifacts/dataset_phase3_p2e_phase2_expert",
    )
    p.add_argument(
        "--out",
        default="experiments/aerial/rl/artifacts/dataset_phase3_p2e_close_tail",
    )
    p.add_argument("--dist-min", type=float, default=3.0)
    p.add_argument("--dist-max", type=float, default=18.0)
    p.add_argument("--min-steps", type=int, default=24)
    p.add_argument("--repeat", type=int, default=4)
    p.add_argument("--symlink", action="store_true")
    args = p.parse_args()

    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    build_close_tail_dataset(
        root / args.src,
        root / args.out,
        dist_min_m=float(args.dist_min),
        dist_max_m=float(args.dist_max),
        min_steps=int(args.min_steps),
        repeat=max(1, int(args.repeat)),
        materialize=not args.symlink,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
