#!/usr/bin/env python3
"""Tag 16 native outdoor long routes for Phase-3 P2c online collect."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("build_phase3_outdoor_long_only")


def main() -> int:
    p = argparse.ArgumentParser(description="Build outdoor-long-only Phase-3 annotation")
    p.add_argument("--outdoor", default="artifacts/seen_airsim16_long_routes.json")
    p.add_argument(
        "--out",
        default="experiments/aerial/phase3_unified/annotations/outdoor_long_only.json",
    )
    args = p.parse_args()

    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from experiments.aerial.phase3_unified.mixed_corpus import tag_outdoor_routes, _load_routes

    routes = tag_outdoor_routes(_load_routes(root / args.outdoor))
    payload = {
        "protocol_version": "phase3_outdoor_long_only_v0",
        "scene": "outdoor_long",
        "n_episodes": len(routes),
        "episodes": routes,
    }
    out = root / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("wrote %s (%d outdoor_long episodes)", out, len(routes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
