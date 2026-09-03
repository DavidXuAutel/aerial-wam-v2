#!/usr/bin/env python3
"""Plot per-step intent trace from --traj-out JSONL files.

Usage:
    python -m experiments.aerial.scripts.plot_intent_trace \
        --traj-dir artifacts/traj_e1_forensics \
        --anno artifacts/seen_airsim16_long_routes.json \
        --routes 0,1 \
        --out artifacts/traj_e1_forensics/plots
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def plot_route(
    rows: list[dict],
    ref_pts: np.ndarray | None,
    goal: np.ndarray | None,
    route_idx: int,
    out_path: Path,
) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.cm as cm

    pos = np.array([r["pos"][:2] for r in rows])  # XY only
    d_to_g = np.array([r["d_to_g"] for r in rows])
    d_fwd = np.array([r["d_fwd"] if r["d_fwd"] is not None else float("nan") for r in rows])
    replan = np.array([bool(r.get("replan")) for r in rows])
    chosen_idx = np.array([r.get("chosen_idx") if r.get("chosen_idx") is not None else 0 for r in rows])
    offaxis = chosen_idx != 0

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle(f"Route {route_idx} — intent trace forensics", fontsize=12)

    # ── panel 1: XY trajectory + intent arrows ──────────────────────────────
    ax = axes[0]
    ax.set_title("XY trajectory + intent arrows")
    if ref_pts is not None:
        ax.plot(ref_pts[:, 0], ref_pts[:, 1], "k--", lw=1, label="ref polyline", zorder=1)
    # colour trajectory by step
    cmap = cm.get_cmap("viridis")
    for i in range(len(pos) - 1):
        c = cmap(i / max(1, len(pos) - 1))
        ax.plot(pos[i:i+2, 0], pos[i:i+2, 1], color=c, lw=1.0, zorder=2)
    # intent arrows on replan steps (subsample to avoid clutter)
    arrow_steps = [r for r in rows if r.get("replan") and r.get("intent_target")]
    for r in arrow_steps[::max(1, len(arrow_steps) // 40)]:
        px, py = r["pos"][0], r["pos"][1]
        tx, ty = r["intent_target"][0], r["intent_target"][1]
        color = "red" if r.get("chosen_idx", 0) != 0 else "blue"
        ax.annotate("", xy=(tx, ty), xytext=(px, py),
                    arrowprops=dict(arrowstyle="->", color=color, lw=0.8))
    ax.scatter(pos[0, 0], pos[0, 1], c="green", s=60, zorder=5, label="start")
    ax.scatter(pos[-1, 0], pos[-1, 1], c="orange", s=60, zorder=5, label="final")
    if goal is not None:
        ax.scatter(goal[0], goal[1], c="red", s=100, marker="*", zorder=5, label="goal")
    ax.set_aspect("equal", adjustable="datalim")
    ax.legend(fontsize=7)
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")

    # ── panel 2: d_to_g over steps ──────────────────────────────────────────
    ax = axes[1]
    ax.set_title("Distance to goal over steps")
    ax.plot(d_to_g, lw=1.2, color="#1f77b4")
    ax.axhline(d_to_g[0], color="k", lw=0.8, ls="--", label=f"d_start={d_to_g[0]:.1f}m")
    ax.set_xlabel("step")
    ax.set_ylabel("d_to_g (m)")
    ax.legend(fontsize=7)

    # ── panel 3: d_fwd + offaxis markers ────────────────────────────────────
    ax = axes[2]
    ax.set_title("d_fwd & offaxis replans")
    valid = ~np.isnan(d_fwd)
    if valid.any():
        ax.plot(np.where(valid)[0], d_fwd[valid], lw=1.0, color="#2ca02c", label="d_fwd")
    ax.axhline(3.0, color="red", lw=0.8, ls="--", label="d_danger=3m")
    ax.axhline(22.0, color="orange", lw=0.8, ls="--", label="d_clear=22m")
    offaxis_steps = np.where(offaxis & replan)[0]
    if len(offaxis_steps):
        ax.scatter(offaxis_steps, np.full(len(offaxis_steps), 0.5),
                   c="red", s=10, zorder=4, label=f"offaxis ({len(offaxis_steps)})")
    ax.set_xlabel("step")
    ax.set_ylabel("depth (m)")
    ax.legend(fontsize=7)

    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=120)
    plt.close()
    print(f"saved: {out_path}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--traj-dir", required=True, help="Dir with routeXX.jsonl files")
    p.add_argument("--anno", default="artifacts/seen_airsim16_long_routes.json")
    p.add_argument("--routes", default="", help="Comma-separated route indices")
    p.add_argument("--out", default=None, help="Output dir for PNGs (default: traj-dir/plots)")
    args = p.parse_args()

    traj_dir = Path(args.traj_dir)
    out_dir = Path(args.out) if args.out else traj_dir / "plots"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load annotation for ref polyline
    anno_path = Path(args.anno)
    routes_data: list[dict] = []
    if anno_path.exists():
        raw = json.loads(anno_path.read_text())
        routes_data = raw.get("routes", raw) if isinstance(raw, dict) else raw

    route_indices = [int(x) for x in args.routes.split(",") if x.strip()] if args.routes else None

    jsonl_files = sorted(traj_dir.glob("route*.jsonl"))
    if not jsonl_files:
        print(f"No route*.jsonl files found in {traj_dir}")
        return

    for f in jsonl_files:
        # parse route index from filename
        try:
            idx = int(f.stem.replace("route", ""))
        except ValueError:
            continue
        if route_indices is not None and idx not in route_indices:
            continue

        rows = load_jsonl(f)
        if not rows:
            print(f"empty: {f}")
            continue

        ref_pts = None
        goal = None
        if idx < len(routes_data):
            r_info = routes_data[idx]
            pos_key = "pos" if "pos" in r_info else "positions"
            if pos_key in r_info:
                ref_pts = np.array(r_info[pos_key], dtype=np.float64)
            if "goal" in r_info:
                goal = np.array(r_info["goal"], dtype=np.float64)
            elif ref_pts is not None and len(ref_pts):
                goal = ref_pts[-1]

        out_png = out_dir / f"route{idx:02d}_intent_trace.png"
        plot_route(rows, ref_pts, goal, idx, out_png)

    print(f"done. plots in {out_dir}")


if __name__ == "__main__":
    main()
