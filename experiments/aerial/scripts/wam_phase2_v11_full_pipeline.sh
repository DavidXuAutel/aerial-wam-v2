#!/usr/bin/env bash
# V11 stack end-to-end: full16 → Route-10 ×2 → summary → representative dual-view videos.
# Run on 125 only (AirSim exclusive). Monitor: tail -f artifacts/wam_phase2_v11_pipeline_20260915/pipeline.log
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source "$ROOT/experiments/aerial/scripts/env_4090.sh"
PY="${AERIAL_PY:-${PYTHON_BIN:-python3}}"

PIPE_ROOT="artifacts/wam_phase2_v11_pipeline_20260915"
FULL16_OUT="artifacts/wam_phase2_v11_full16_20260915"
R10_OUT="artifacts/wam_phase2_route10_v11_validate_20260915"
VIDEO_OUT="artifacts/videos/wam_phase2_v11_full16_dual"
ANNO="experiments/aerial/phase3_unified/annotations/outdoor_long_only.json"

mkdir -p "$PIPE_ROOT" "$VIDEO_OUT"
exec > >(tee -a "${PIPE_ROOT}/pipeline.log") 2>&1

log() { echo "[$(date '+%H:%M:%S')] $*"; }

log "=== Step 1/4: V11 full16 eval ==="
OUT_ROOT="$FULL16_OUT" bash experiments/aerial/scripts/wam_phase2_best_stack_full16.sh

log "=== Step 2/4: Route-10 V11 ×2 repeat ==="
OUT_ROOT="$R10_OUT" bash experiments/aerial/scripts/wam_phase2_route10_v11_validate.sh all

log "=== Step 3/4: Aggregate summary ==="
"$PY" << 'PY'
import json, statistics as st
from pathlib import Path

def load_eps(p):
    if not p.exists():
        return []
    d = json.load(open(p))
    return d.get("episodes", [])

full = Path("artifacts/wam_phase2_v11_full16_20260915/full16.json")
r10d = Path("artifacts/wam_phase2_route10_v11_validate_20260915")
eps = load_eps(full)
print("\n========== V11 FULL16 ==========")
if eps:
    arr = [e for e in eps if e["arrived"]]
    spls = [e["spl"] for e in arr]
    ge07 = sum(1 for s in spls if s >= 0.70)
    print(f"SR {len(arr)}/{len(eps)} ({100*len(arr)/len(eps):.1f}%)")
    if spls:
        print(f"SPL mean={st.fmean(spls):.3f} med={st.median(spls):.3f}  SPL>=0.7: {ge07}/{len(arr)}")
    print("\nPer-route:")
    for e in sorted(eps, key=lambda x: x["route_idx"]):
        ri = e["route_idx"]
        print(f"  R{ri+1:02d} arr={e['arrived']} SPL={e['spl']:.3f} L={e['actual_length_m']:.0f}m IR={e['intervention_rate']:.2f}")
    fails = [e for e in eps if not e["arrived"]]
    low = [e for e in arr if e["spl"] < 0.50]
    best = sorted(arr, key=lambda x: -x["spl"])[:3]
    worst_arr = sorted(arr, key=lambda x: x["spl"])[:3]
    summary = {
        "full16": str(full),
        "n_routes": len(eps),
        "arrival_rate": len(arr) / len(eps),
        "spl_ge_07": ge07,
        "best_routes": [e["route_idx"] for e in best],
        "worst_arrived_routes": [e["route_idx"] for e in worst_arr],
        "failed_routes": [e["route_idx"] for e in fails],
        "low_spl_routes": [e["route_idx"] for e in low],
    }
    Path("artifacts/wam_phase2_v11_pipeline_20260915/summary.json").write_text(
        json.dumps(summary, indent=2)
    )
else:
    print("full16.json missing or empty")

print("\n========== Route-10 repeats ==========")
for p in sorted(r10d.glob("v11_r*.json")):
    e = json.load(open(p))["episodes"][0]
    print(f"  {p.stem}: arr={e['arrived']} SPL={e['spl']:.3f} L={e['actual_length_m']:.1f}m")
PY

log "=== Step 4/4: Dual-view videos (best + worst + R10) ==="
"$PY" << 'PY'
import json
import subprocess
import sys
from pathlib import Path

PIPE = Path("artifacts/wam_phase2_v11_pipeline_20260915/summary.json")
FULL = Path("artifacts/wam_phase2_v11_full16_20260915/full16.json")
TRAJ_DIR = Path("artifacts/wam_phase2_v11_full16_20260915/traj")
R10_TRAJ = Path("artifacts/wam_phase2_route10_v11_validate_20260915")
VIDEO_OUT = Path("artifacts/videos/wam_phase2_v11_full16_dual")
ANNO = "experiments/aerial/phase3_unified/annotations/outdoor_long_only.json"
PYBIN = sys.executable

def render(traj_jsonl, route_idx, label, prefix):
    out = VIDEO_OUT / f"{prefix}_dual_view_dashboard.mp4"
    cmd = [
        PYBIN, "-m", "experiments.aerial.scripts.wam_phase2_dual_view_from_traj",
        "--traj-jsonl", str(traj_jsonl),
        "--ref-polyline-json", ANNO,
        "--route-idx", str(route_idx),
        "--plan-mode", "polyline",
        "--route-label", label,
        "--out-dir", str(VIDEO_OUT),
        "--out-prefix", prefix,
        "--fps", "5", "--source-hz", "5",
    ]
    print("render", prefix, "...", flush=True)
    subprocess.run(cmd, check=True)
    return out

targets = []
if PIPE.exists():
    s = json.load(open(PIPE))
    seen = set()
    for key in ("best_routes", "worst_arrived_routes", "failed_routes"):
        for ri in s.get(key, [])[:2]:
            if ri not in seen:
                targets.append(ri)
                seen.add(ri)
if not targets and FULL.exists():
    eps = json.load(open(FULL))["episodes"]
    arr = sorted([e for e in eps if e["arrived"]], key=lambda x: -x["spl"])
    if arr:
        targets.append(arr[0]["route_idx"])
    if len(arr) > 1:
        targets.append(arr[-1]["route_idx"])

for ri in targets[:4]:
    traj = TRAJ_DIR / f"route{ri:02d}.jsonl"
    alt = TRAJ_DIR / f"route{ri:02d}" / f"route{ri:02d}.jsonl"
    path = traj if traj.exists() else alt
    if not path.exists():
        print("skip video R", ri, "no traj", path)
        continue
    e = next(x for x in json.load(open(FULL))["episodes"] if x["route_idx"] == ri)
    render(path, ri, f"V11 R{ri+1:02d} SPL={e['spl']:.2f}", f"full16_r{ri+1:02d}")

# Route 10 repeat (latest)
r10 = sorted(R10_TRAJ.glob("v11_r*_traj/route09/route09.jsonl"))
if not r10:
    r10 = sorted(R10_TRAJ.glob("v11_r*_traj/route09.jsonl"))
if r10:
    p = r10[-1]
    tag = p.parent.parent.name.replace("_traj", "")
    ej = json.load(open(R10_TRAJ / f"{tag}.json"))["episodes"][0]
    render(p, 9, f"V11 R10 {tag} SPL={ej['spl']:.2f}", f"route10_{tag}")

print("videos ->", VIDEO_OUT)
PY

log "=== V11 pipeline DONE ==="
