#!/usr/bin/env python3
"""Build indoor-only annotation for P3-indoor (decouple path).

All episodes are tagged ``indoor_micro`` + ``building_99`` before collect/train.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("build_phase3_indoor_annotation")


def main() -> int:
    p = argparse.ArgumentParser(description="Build Phase-3 indoor-only annotation")
    p.add_argument(
        "--handover",
        default="experiments/aerial/phase3_unified/annotations/handover_seen_filtered.json",
    )
    p.add_argument(
        "--b99",
        default="experiments/aerial/phase3_unified/annotations/building99_indoor_short_routes.json",
    )
    p.add_argument(
        "--out",
        default="experiments/aerial/phase3_unified/annotations/phase3_indoor_seen.json",
    )
    p.add_argument("--no-b99-short", action="store_true", help="handover indoor legs only")
    args = p.parse_args()

    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from experiments.aerial.phase3_unified.indoor_corpus import write_indoor_annotation

    out = write_indoor_annotation(
        root / args.out,
        handover_path=root / args.handover,
        b99_path=root / args.b99,
        include_b99_short=not args.no_b99_short,
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    mix = payload["scene_mix"]
    logger.info(
        "wrote %s total=%d (handover=%d b99=%d)",
        out,
        mix["total_n"],
        mix["handover_indoor_n"],
        mix["b99_short_n"],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
