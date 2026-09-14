#!/usr/bin/env bash
# Resumable watchdog for Phase-3 outdoor regression gate (125).
#
# - Monitors wam_phase2_long_eval; logs progress every poll.
# - On crash mid-run: restart renderer, eval remaining routes, merge partials.
# - When 16/16 scored: write regression_gate_p2c.json verdict.
#
# Usage (background on 125):
#   nohup bash experiments/aerial/scripts/monitor_phase3_outdoor_gate.sh \
#     experiments/aerial/rl/artifacts/v4_ac_ckpt_phase3_unified_p2c_20260913/v4_ac_latest.pt \
#     >> artifacts/p2c_gate_watchdog.log 2>&1 &
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh

ACTOR_CKPT="${1:?usage: $0 <actor_ckpt>}"
BASELINE_JSON="${2:-artifacts/phase3_unified_eval_20260911/outdoor_long_eval_phase2_baseline.json}"
OUT_DIR="${OUT_DIR:-artifacts/phase3_unified_eval_$(date +%Y%m%d)}"
FINAL_JSON="${OUT_DIR}/outdoor_long_eval_p2c_candidate.json"
PARTIAL_DIR="${OUT_DIR}/partials"
GATE_JSON="${OUT_DIR}/regression_gate_p2c.json"
WATCH_LOG="${WATCH_LOG:-artifacts/p2c_gate_watchdog.log}"
EVAL_LOG="${EVAL_LOG:-artifacts/p2c_final_gate.log}"
SCENE_SH="${SCENE_SCRIPT:-$HOME/aerial-indoor-wam/experiments/aerial/scripts/recover_renderer_scene.sh}"
WM_CKPT="${WM_CKPT:-experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt}"
POLL_SEC="${POLL_SEC:-120}"
MIN_ARRIVALS="${MIN_ARRIVALS:-11}"
MIN_RATE="${MIN_RATE:-0.7125}"

mkdir -p "$OUT_DIR" "$PARTIAL_DIR"

log() { echo "[$(date -Iseconds)] [watchdog] $*"; }

routes_done_from_logs() {
  local eval_active="${1:-0}"
  ACTOR_CKPT="$ACTOR_CKPT" EVAL_RUNNING="$eval_active" python3 - "$WATCH_LOG" "$EVAL_LOG" "$FINAL_JSON" "${OUT_DIR}/outdoor_long_eval_p2b_candidate.json" "$PARTIAL_DIR" <<'PY'
import json, os, re, sys
from pathlib import Path

def _ckpt_match(summary: dict, actor_ckpt: str) -> bool:
    if not actor_ckpt:
        return True
    got = str(summary.get("actor_ckpt", ""))
    return got.endswith(actor_ckpt) or actor_ckpt in got

done: set[int] = set()
actor_ckpt = os.environ.get("ACTOR_CKPT", "")
eval_running = os.environ.get("EVAL_RUNNING", "0") == "1"
args = sys.argv[1:]
partial = Path(args[-1])
json_paths = [Path(p) for p in args[2:-1]]
log_paths = [Path(p) for p in args[:2]]

for path in log_paths:
    if not path.is_file():
        continue
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.search(r"Route (\d+) \(\d+/16\)", line)
        if m:
            done.add(int(m.group(1)) - 1)

if eval_running:
    print(",".join(str(i) for i in sorted(done)))
    raise SystemExit(0)

for jf in json_paths:
    if not jf.is_file():
        continue
    try:
        d = json.loads(jf.read_text())
    except Exception:
        continue
    if not _ckpt_match(d, actor_ckpt):
        continue
    for ep in d.get("episodes", []):
        if ep.get("route_idx") is not None:
            done.add(int(ep["route_idx"]))

if partial.is_dir():
    for jf in partial.glob("chunk_*.json"):
        try:
            d = json.loads(jf.read_text())
        except Exception:
            continue
        for ep in d.get("episodes", []):
            if ep.get("route_idx") is not None:
                done.add(int(ep["route_idx"]))

print(",".join(str(i) for i in sorted(done)))
PY
}

eval_running() {
  pgrep -f "wam_phase2_long_eval.py.*${ACTOR_CKPT##*/}" >/dev/null 2>&1
}

wait_airsim() {
  for _ in $(seq 1 36); do
    if python3 -c "import socket;socket.create_connection(('127.0.0.1',41451),3).close()" 2>/dev/null; then
      return 0
    fi
    sleep 5
  done
  return 1
}

restart_renderer() {
  if [[ -x "$SCENE_SH" ]]; then
    log "restart renderer outdoor via $SCENE_SH"
    bash "$SCENE_SH" outdoor
    sleep 30
    wait_airsim
  else
    log "WARN: missing scene script $SCENE_SH"
  fi
}

run_routes() {
  local routes_csv="$1"
  local out_json="$2"
  log "eval routes=[$routes_csv] -> $out_json"
  restart_renderer
  "${PYTHON_BIN:-python3}" experiments/aerial/scripts/wam_phase2_long_eval.py \
    --actor-ckpt "$ACTOR_CKPT" \
    --wm-ckpt "$WM_CKPT" \
    --subgoal-source toward_g \
    --cruise-speed 10 \
    --planner \
    --success-dist 3.0 \
    --routes "$routes_csv" \
    --out "$out_json" >>"$EVAL_LOG" 2>&1
}

merge_and_verdict() {
  local -a parts=()
  local alias_json="${OUT_DIR}/outdoor_long_eval_p2b_candidate.json"
  for cand in "$FINAL_JSON" "$alias_json"; do
    if [[ -f "$cand" ]]; then
      local n
      n="$(ACTOR_CKPT="$ACTOR_CKPT" python3 -c "import json,os,sys;d=json.load(open(sys.argv[1]));ck=str(d.get('actor_ckpt',''));a=os.environ['ACTOR_CKPT'];ok=(a in ck or ck.endswith(a));print(len(d.get('episodes',[])) if ok else 0)" "$cand")"
      if [[ "$n" == "16" ]]; then
        if [[ "$cand" != "$FINAL_JSON" ]]; then
          cp "$cand" "$FINAL_JSON"
        fi
        parts=("$FINAL_JSON")
        break
      fi
    fi
  done
  if [[ ${#parts[@]} -eq 0 ]]; then
    shopt -s nullglob
    parts=("$PARTIAL_DIR"/chunk_*.json)
    shopt -u nullglob
    if [[ ${#parts[@]} -eq 0 ]]; then
      log "ERROR: no partial JSONs to merge"
      return 1
    fi
    log "merge ${#parts[@]} partial(s) -> $FINAL_JSON"
    python3 -m experiments.aerial.scripts.merge_phase2_split_eval \
      --out "$FINAL_JSON" "${parts[@]}"
  fi

  python3 - <<PY
import json, sys
from pathlib import Path

baseline = json.loads(Path("$BASELINE_JSON").read_text())
candidate = json.loads(Path("$FINAL_JSON").read_text())
b_eps = baseline["episodes"]
c_eps = candidate["episodes"]
b_arr = sum(1 for e in b_eps if e.get("arrived"))
c_arr = sum(1 for e in c_eps if e.get("arrived"))
n = len(c_eps)
b_rate = b_arr / max(len(b_eps), 1)
c_rate = c_arr / max(n, 1)
min_arr = int("$MIN_ARRIVALS")
min_rate = float("$MIN_RATE")
delta = b_rate - c_rate
ok = c_arr >= min_arr and c_rate >= min_rate and n >= 16
verdict = "PASS" if ok else "FAIL"
print("=== regression gate ===")
print(f"baseline:  {b_arr}/{len(b_eps)} ({b_rate:.1%})")
print(f"candidate: {c_arr}/{n} ({c_rate:.1%})")
print(f"delta:     {delta:+.1%}")
print(f"verdict:   {verdict}")
Path("$GATE_JSON").write_text(
    json.dumps(
        {
            "verdict": verdict,
            "baseline_json": "$BASELINE_JSON",
            "candidate_json": "$FINAL_JSON",
            "baseline_arrivals": b_arr,
            "candidate_arrivals": c_arr,
            "n_routes": n,
            "baseline_rate": round(b_rate, 4),
            "candidate_rate": round(c_rate, 4),
            "delta_rate": round(delta, 4),
            "min_arrivals": min_arr,
            "min_rate": min_rate,
        },
        indent=2,
    ),
    encoding="utf-8",
)
sys.exit(0 if ok else 2)
PY
}

log "watchdog start actor=$ACTOR_CKPT out=$FINAL_JSON poll=${POLL_SEC}s"

while true; do
  if [[ -f "$GATE_JSON" ]]; then
    log "gate verdict exists: $(cat "$GATE_JSON" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("verdict"))')"
    exit 0
  fi

  running_flag=0
  if eval_running; then running_flag=1; fi
  done_csv="$(routes_done_from_logs "$running_flag")"
  done_n=0
  if [[ -n "$done_csv" ]]; then
    done_n="$(echo "$done_csv" | awk -F, '{print NF}')"
  fi
  log "progress: ${done_n}/16 routes done [$done_csv] eval_running=$(eval_running && echo yes || echo no)"

  if eval_running; then
    sleep "$POLL_SEC"
    continue
  fi

  if [[ "$done_n" -ge 16 ]]; then
    log "all routes accounted — merge + verdict"
    merge_and_verdict || true
    continue
  fi

  # Eval not running and incomplete — resume remaining routes.
  remaining="$(DONE_CSV="$done_csv" python3 - <<'PY'
import os
done=set()
csv=os.environ.get("DONE_CSV","")
if csv:
    done={int(x) for x in csv.split(",") if x}
rem=[i for i in range(16) if i not in done]
print(",".join(str(i) for i in rem))
PY
)"
  if [[ -z "$remaining" ]]; then
    merge_and_verdict || true
    continue
  fi

  chunk_tag="${remaining//,/_}"
  chunk_out="${PARTIAL_DIR}/chunk_${chunk_tag}.json"
  if [[ -f "$chunk_out" ]]; then
    log "chunk already exists $chunk_out — skipping re-run"
  else
    if ! run_routes "$remaining" "$chunk_out"; then
      log "WARN: eval chunk failed for routes [$remaining] — will retry after poll"
    fi
  fi
  sleep "$POLL_SEC"
done
