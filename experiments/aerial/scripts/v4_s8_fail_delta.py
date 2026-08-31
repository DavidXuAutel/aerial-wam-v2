#!/usr/bin/env python3
"""Compare old-head vs S-8 three-zone / zero eval artifacts (S-8 FAIL delta)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

REPO = Path(__file__).resolve().parents[3]
ART = REPO / "artifacts"

PAIRS = [
    ("hold035", "three_zone",
     "v4_three_zone_oldhead_hold035_p45mid_s5f3_20260824.json",
     "v4_three_zone_s8_hold035_20260824.json"),
    ("full", "three_zone",
     "v4_three_zone_oldhead_full_p45mid_s5f3_20260824.json",
     "v4_three_zone_s8_full_20260824.json"),
    ("hold035", "zero",
     "v4_zero_p3_oldhead_hold035_p45mid_s5f3_20260824.json",
     "v4_zero_p3_s8_hold035_20260824.json"),
    ("full", "zero",
     "v4_zero_p3_oldhead_full_p45mid_s5f3_20260824.json",
     "v4_zero_p3_s8_full_20260824.json"),
]


def _band(d: Dict[str, Any], name: str) -> Optional[Dict[str, Any]]:
    dv = d.get("depth_vs_budget") or {}
    bands = dv.get("bands") or {}
    return bands.get(name)


def _fmt_band(b: Optional[Dict[str, Any]]) -> str:
    if not b:
        return "—"
    return f"n={b.get('n')} p95={b.get('p95_underread_m')} ok={b.get('ok')}"


def _zero_sub(d: Dict[str, Any], k: str) -> Dict[str, Any]:
    return (d.get("sub") or {}).get(k) or {}


def main() -> int:
    print("[s8-delta] repo=", REPO)
    missing = []
    for slice_name, kind, old_name, new_name in PAIRS:
        old_p, new_p = ART / old_name, ART / new_name
        print(f"\n=== {kind} {slice_name} ===")
        if not old_p.exists():
            missing.append(str(old_p))
            print(f"  OLD MISSING: {old_p}")
            continue
        if not new_p.exists():
            missing.append(str(new_p))
            print(f"  NEW MISSING: {new_p}")
            continue
        old = json.loads(old_p.read_text())
        new = json.loads(new_p.read_text())
        if kind == "three_zone":
            for band in ("engage_outer", "cap_l1", "cap_l2", "cap_l3"):
                print(f"  {band}: old {_fmt_band(_band(old, band))}")
                print(f"  {band}: new {_fmt_band(_band(new, band))}")
            oh = old.get("0h_engage_miss") or {}
            nh = new.get("0h_engage_miss") or {}
            print(f"  ⓪h: old p={oh.get('p_engage_miss')} consec={oh.get('max_consecutive_miss')}")
            print(f"  ⓪h: new p={nh.get('p_engage_miss')} consec={nh.get('max_consecutive_miss')}")
            oi = old.get("0i_three_zone_functional") or {}
            ni = new.get("0i_three_zone_functional") or {}
            print(f"  ⓪i auth: old {oi.get('ok_authoritative')} new {ni.get('ok_authoritative')}")
            print(f"  verdict: old {old.get('verdict',{}).get('ok')} new {new.get('verdict',{}).get('ok')}")
        else:
            for k in ("0a", "0b", "0c", "0h", "0e"):
                os_, ns = _zero_sub(old, k), _zero_sub(new, k)
                if os_ or ns:
                    print(f"  {k}: old ok={os_.get('ok')} new ok={ns_.get('ok')}", end="")
                    if k == "0c":
                        print(f" p90={os_.get('p90_absrel')}→{ns_.get('p90_absrel')}", end="")
                    if k == "0h":
                        print(f" consec={os_.get('max_consecutive_miss')}→{ns_.get('max_consecutive_miss')}", end="")
                    print()
            print(f"  merge: old {old.get('ok')} new {new.get('ok')}")

    if missing:
        print("\n[s8-delta] WARN missing:", ", ".join(missing))
        return 1
    print("\n[s8-delta] DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
