#!/usr/bin/env python3
"""Export flight spawn annotation from red-car anchor/distance sweep report."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, List


def _load_poses(report_path: Path) -> List[Dict[str, Any]]:
    data = json.loads(report_path.read_text(encoding="utf-8"))
    return list(data.get("poses") or [])


def _pose_key(row: Dict[str, Any], pos_round: float) -> tuple:
    p = row["pos"]
    return (
        round(float(p[0]) / pos_round) * pos_round,
        round(float(p[1]) / pos_round) * pos_round,
        round(float(p[2]), 1),
        round(math.degrees(float(row["yaw_rad"])), 0),
    )


def export_routes(
    poses: List[Dict[str, Any]],
    *,
    min_conf: float,
    require_hit_raw: bool,
    max_routes: int,
    pos_round_m: float,
    visual_prompt: str,
) -> List[Dict[str, Any]]:
    pool: List[Dict[str, Any]] = []
    for row in poses:
        conf = float(row.get("yolo_conf") or 0.0)
        if require_hit_raw and not row.get("hit_raw"):
            continue
        if conf < float(min_conf):
            continue
        pool.append(row)
    pool.sort(key=lambda r: (-float(r.get("yolo_conf") or 0.0), float(r.get("pix_offset_px") or 9999)))

    seen: set = set()
    routes: List[Dict[str, Any]] = []
    for row in pool:
        key = _pose_key(row, float(pos_round_m))
        if key in seen:
            continue
        seen.add(key)
        conf = float(row.get("yolo_conf") or 0.0)
        pos = [round(float(x), 3) for x in row["pos"]]
        yaw = float(row["yaw_rad"])
        rid = f"red_car_anchor_{len(routes):02d}"
        src = (
            f"anchor_export conf={row.get('yolo_conf')} "
            f"fwd={row.get('anchor_fwd_m')} lat={row.get('anchor_lat_m')} "
            f"yaw_off={row.get('yaw_off_deg')}"
        )
        routes.append(
            {
                "route_id": rid,
                "route_idx": len(routes),
                "source": src,
                "pos": [pos, pos],
                "yaw": [yaw, yaw],
                "gpt_instruction": f"Find and approach the {visual_prompt}",
                "visual_prompt": visual_prompt,
                "detector": "open_vocab",
                "probe_conf": round(float(row.get("yolo_conf") or 0.0), 4),
                "snapshot": row.get("snapshot"),
                "search_area": {
                    "half_m": 15.0,
                    "sweep_spacing_m": 8.0,
                },
            }
        )
        if len(routes) >= int(max_routes):
            break
    return routes


def main() -> int:
    parser = argparse.ArgumentParser(description="Export red-car spawn routes from sweep report")
    parser.add_argument(
        "--report",
        default="artifacts/red_car_anchor_autoyaw_1080m.json",
    )
    parser.add_argument(
        "--out",
        default="experiments/aerial/phase2-vgoal/airsim16_red_car_spawn_probe_1080m_v2.json",
    )
    parser.add_argument("--min-conf", type=float, default=0.20)
    parser.add_argument("--max-routes", type=int, default=12)
    parser.add_argument("--pos-round-m", type=float, default=0.5)
    parser.add_argument("--visual-prompt", default="red car")
    parser.add_argument("--require-hit-raw", action="store_true", default=True)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[3]
    report_path = (root / args.report).resolve()
    if not report_path.is_file():
        raise SystemExit(f"report not found: {report_path}")

    routes = export_routes(
        _load_poses(report_path),
        min_conf=float(args.min_conf),
        require_hit_raw=bool(args.require_hit_raw),
        max_routes=int(args.max_routes),
        pos_round_m=float(args.pos_round_m),
        visual_prompt=str(args.visual_prompt),
    )
    if not routes:
        raise SystemExit("no routes exported — lower --min-conf or check report")

    out = {
        "version": "airsim16_red_car_spawn_probe_v2",
        "description": (
            f"Auto-yaw anchor export (min_conf={args.min_conf}). "
            f"Source: {report_path.name}"
        ),
        "visual_prompt": str(args.visual_prompt),
        "detector": "open_vocab",
        "yolo_model": "yolov8m-worldv2.pt",
        "n_routes": len(routes),
        "routes": routes,
    }
    out_path = (root / args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Written {len(routes)} routes -> {out_path}")
    for r in routes:
        print(f"  {r['route_id']} conf={r['probe_conf']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
