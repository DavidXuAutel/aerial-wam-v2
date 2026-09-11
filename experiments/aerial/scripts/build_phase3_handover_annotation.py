#!/usr/bin/env python3
"""Build Phase-3 indoor-outdoor handover annotation JSON."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("build_phase3_handover")


def main() -> int:
    p = argparse.ArgumentParser(description="Build Phase-3 handover annotation")
    p.add_argument("--outdoor", default="artifacts/seen_airsim16_long_routes.json")
    p.add_argument(
        "--indoor",
        default="experiments/aerial/phase3_unified/annotations/building99_indoor_short_routes.json",
    )
    p.add_argument("--out", required=True)
    p.add_argument("--outdoor-approach-len-m", type=float, default=30.0)
    p.add_argument("--no-long-outdoor", action="store_true")
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()

    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from experiments.aerial.phase3_unified.handover_corpus import write_handover_annotation

    out = write_handover_annotation(
        args.out,
        outdoor_path=args.outdoor,
        indoor_path=args.indoor,
        outdoor_approach_len_m=float(args.outdoor_approach_len_m),
        include_long_outdoor=not args.no_long_outdoor,
        seed=int(args.seed),
    )
    logger.info("wrote %s", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
