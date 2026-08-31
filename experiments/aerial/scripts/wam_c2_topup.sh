#!/usr/bin/env bash
# WAM C2 topup — merge usable eps into dataset_wam_loop_20260827
set -euo pipefail
cd "$(dirname "$0")/../../.."
source experiments/aerial/scripts/env_4090.sh

MAIN="${MAIN:-experiments/aerial/rl/artifacts/dataset_wam_loop_20260827}"
TOPUP="${TOPUP:-experiments/aerial/rl/artifacts/dataset_wam_loop_20260827_topup2}"
N="${N:-3}"
STAMP="${STAMP:-20260827}"

mkdir -p logs "$TOPUP"
echo "=== topup2 $(date -Iseconds) n=$N ===" | tee -a "logs/wam_c2_collect_${STAMP}.log"

PYTHONUNBUFFERED=1 "$AERIAL_PY" -m experiments.aerial.rl.collect_dataset \
  --backend airsim --host 127.0.0.1 --step-hz 5.0 --grab-depth \
  --episodes "$N" --max-steps 200 \
  --annotation artifacts/seen_airsim16_m1a20.json \
  --out "$TOPUP" 2>&1 | tee -a "logs/wam_c2_topup2_${STAMP}.log"

python3 - <<PY
import json, shutil
from pathlib import Path
main = Path("$MAIN")
topup = Path("$TOPUP")
manifest = json.loads((topup / "manifest.json").read_text())
episodes = manifest["episodes"] if isinstance(manifest, dict) else manifest
usable = [m for m in episodes if m.get("usable")]
next_idx = len(list(main.glob("episode_*.npz")))
added = []
for m in usable:
    src = topup / m["file"]
    dst = main / f"episode_{next_idx:05d}.npz"
    shutil.copy2(src, dst)
    added.append(dst.name)
    next_idx += 1
meta_path = main / "dataset_meta.json"
meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
meta.setdefault("topups", []).append({"date": "$STAMP", "dir": str(topup), "merged": added})
meta["n_collected"] = len(list(main.glob("episode_*.npz")))
meta["n_ok"] = int(meta.get("n_ok", 0)) + len(added)
meta_path.write_text(json.dumps(meta, indent=2) + "\n")
print("merged", len(added), "-> total", meta["n_collected"], "n_ok=", meta["n_ok"])
PY
