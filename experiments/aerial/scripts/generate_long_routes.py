#!/usr/bin/env python3
"""Phase 2 mainline long-route benchmark: native A* corridors only (point-to-point).

No roundtrips, no free-space bridges, no hand-crafted turnarounds.
Exports the 16 longest native routes from seen_airsim16_m1a20.json as-is.
Lengths are honest (~90–244 m); multi-block 200–500 m requires a future
map/A* corridor planner — not geometric interpolation.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def generate_long_routes(
    input_anno: str = "artifacts/seen_airsim16_m1a20.json",
    output_anno: str = "artifacts/seen_airsim16_long_routes.json",
    n_routes: int = 16,
) -> None:
    with open(input_anno, "r", encoding="utf-8") as f:
        routes = json.load(f)

    scored = []
    for i, r in enumerate(routes):
        pts = np.asarray(r.get("pos", r.get("positions")), dtype=np.float64)
        if len(pts) < 2:
            continue
        # Skip invalid near-ground annotations (AirSim spawn death); not a runtime hack
        if float(pts[0, 2]) < 2.0 or float(np.min(pts[:, 2])) < 0.5:
            print(f"  skip R{i:02d}: near-ground annotation z0={pts[0,2]:.2f}")
            continue
        length = float(np.sum(np.linalg.norm(pts[1:] - pts[:-1], axis=1)))
        scored.append((length, i, r, pts))

    scored.sort(key=lambda x: -x[0])
    selected = scored[:n_routes]

    long_routes = []
    for idx, (length, base_i, base_r, pts) in enumerate(selected):
        yaws = np.asarray(
            base_r.get("yaw", [0.0] * len(pts)), dtype=np.float64
        ).reshape(-1)
        if len(yaws) != len(pts):
            yaws = np.zeros(len(pts), dtype=np.float64)

        entry = {
            "route_id": f"long_route_{idx + 1:02d}",
            "route_idx": idx,
            "base_route_idx": base_i,
            "category": (
                "medium_long"
                if length >= 200.0
                else ("extended_native" if length >= 150.0 else "native_short")
            ),
            "nominal_length_m": float(round(length, 2)),
            "start_pos": [float(round(x, 3)) for x in pts[0]],
            "goal_pos": [float(round(x, 3)) for x in pts[-1]],
            "pos": [[float(round(x, 3)) for x in p] for p in pts],
            "positions": [[float(round(x, 3)) for x in p] for p in pts],
            "yaw": [float(round(y, 4)) for y in yaws],
            "gpt_instruction": base_r.get("gpt_instruction", ""),
            "pattern": "native_point_to_point",
        }
        long_routes.append(entry)

    out = {
        "version": "airsim16_long_routes_mainline_native_20260828",
        "description": (
            "Phase 2 mainline: 16 longest native A* point-to-point corridors. "
            "No synthetic bridges/roundtrips."
        ),
        "n_routes": len(long_routes),
        "routes": long_routes,
    }
    out_path = Path(output_anno)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(f"Generated {len(long_routes)} native point-to-point routes:")
    for r in long_routes:
        print(
            f"  {r['route_id']}: L={r['nominal_length_m']}m "
            f"base=R{r['base_route_idx']:02d} cat={r['category']} "
            f"start≠goal dist="
            f"{float(np.linalg.norm(np.array(r['start_pos'])-np.array(r['goal_pos']))):.1f}m"
        )


if __name__ == "__main__":
    generate_long_routes()
