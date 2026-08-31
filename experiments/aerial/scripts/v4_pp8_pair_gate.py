#!/usr/bin/env python3
"""Post-P8 paired gate (P-B1..B3) vs heuristic baseline JSON."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


def _r(ep: Dict[str, Any]) -> int:
    return 1 if bool(ep.get("arrived")) else 0


def pair_gate(
    baseline: Dict[str, Any],
    actor: Dict[str, Any],
    *,
    tau_arr: float = 0.10,
) -> Dict[str, Any]:
    base_eps: List[Dict[str, Any]] = baseline.get("episodes") or []
    act_eps: List[Dict[str, Any]] = actor.get("episodes") or []
    n = min(len(base_eps), len(act_eps))
    if n == 0:
        return {"ok": False, "reason": "empty episodes"}

    dom_viol = 0
    for i in range(n):
        rh, ra = _r(base_eps[i]), _r(act_eps[i])
        if rh == 1 and ra == 0:
            dom_viol += 1

    n_scored = int(actor.get("n_scored") or n)
    arr_actor = float(actor.get("arrival_rate") or (sum(_r(e) for e in act_eps) / n))
    hc_actor = float(actor.get("hard_coll_rate") or 0.0)
    hc_base = float(baseline.get("hard_coll_rate") or 0.0)

    p_b1 = dom_viol == 0
    p_b2 = arr_actor >= float(tau_arr)
    p_b3 = hc_actor <= hc_base + 0.0625 and hc_actor <= 0.40
    ok = bool(p_b1 and p_b2 and p_b3)

    return {
        "ok": ok,
        "n_paired": n,
        "dominance_violations": dom_viol,
        "P-B1_ok": p_b1,
        "P-B2_ok": p_b2,
        "arrival_rate_actor": round(arr_actor, 4),
        "tau_arr": float(tau_arr),
        "P-B3_ok": p_b3,
        "hard_coll_actor": round(hc_actor, 4),
        "hard_coll_heuristic": round(hc_base, 4),
        "baseline_path": baseline.get("_path"),
        "actor_path": actor.get("_path"),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--baseline", required=True)
    p.add_argument("--actor", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--tau-arr", type=float, default=0.10)
    args = p.parse_args()

    base_path = Path(args.baseline)
    act_path = Path(args.actor)
    baseline = json.loads(base_path.read_text())
    actor = json.loads(act_path.read_text())
    baseline["_path"] = str(base_path)
    actor["_path"] = str(act_path)

    result = pair_gate(baseline, actor, tau_arr=float(args.tau_arr))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
