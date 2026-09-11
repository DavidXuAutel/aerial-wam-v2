#!/usr/bin/env python3
"""Emit a mixed outdoor+indoor annotation JSON for Phase-3 unified training.

Example::

  python -m experiments.aerial.scripts.build_phase3_mixed_annotation \\
    --out artifacts/phase3_unified_mixed_seen.json
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("build_phase3_mixed_annotation")


def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build Phase-3 mixed outdoor+indoor annotation")
    p.add_argument(
        "--outdoor",
        default="artifacts/seen_airsim16_long_routes.json",
        help="Outdoor long-route annotation (also supplies indoor segment geometry)",
    )
    p.add_argument("--out", required=True, help="Output mixed annotation JSON path")
    p.add_argument("--outdoor-prob", type=float, default=0.7)
    p.add_argument("--indoor-segment-len-m", type=float, default=10.0)
    p.add_argument("--seed", type=int, default=0)
    return p.parse_args()


def main() -> int:
    args = _parse()
    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from experiments.aerial.phase3_unified.mixed_corpus import write_mixed_annotation

    out = write_mixed_annotation(
        args.out,
        outdoor_path=args.outdoor,
        indoor_segment_len_m=float(args.indoor_segment_len_m),
        outdoor_prob=float(args.outdoor_prob),
        seed=int(args.seed),
    )
    logger.info("wrote %s", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
