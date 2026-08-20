# V4 RUNBOOK 125 STATUS

- **date**: 2026-08-20
- **state**: ACTIVE — **P4.5 补采 in flight** (open 1:1 top-up + near enrich)
- **HEAD**: `559fe31`
- **current step**: 补采 → merge → depth/WM retrain → re-P3 / re-P1（⓿e 另修）
- **P3 (post-P4.5 v1)**: ⓪b **PASS** (150 frames); ⓪c/⓪d FAIL; `[lo,hi]=null` — `artifacts/v4_zero_p3_p45_20260820.json`
- **P1 (post-P4.5 v1)**: **FAIL** reward `beat_frac=0.67`; `one_step_ok=True`
- **P4 (post-P4.5 v1)**: ⓿a–d PASS; **⓿e FAIL** (`rel_l2=1.39`) — harness，**不靠补采**
- **enable_policy_update**: false
- **R-16**: **(B)**
- **signed**: `--spare-count=16`

## Checklist

- [x] P0c / P2 wiring / P6
- [x] P4.5 v1 — corpus 34 eps (open **11** / blocked **24**) + WM `wm_step_500.pt`
- [x] re-P3 / re-P1 / re-P4 (v1) — ⓪b 过；⓪c/P1/⓿e 未过
- [ ] **P4.5 补采** — open top-up + near enrich（本轮）
- [ ] merge → depth head / WM retrain → re-P3 / re-P1
- [ ] freeze / P7-accept / P8 — still blocked until gates re-pass

## Running jobs

| job | PID | log |
|-----|-----|-----|
| P4.5 top-up (open→near) | **3018192** (phase1) / wrapper **3018181** | `logs/v4_p45_topup_20260820.log` |

## Top-up plan

| phase | layer | n | approach | out |
|-------|-------|--:|----------|-----|
| 1 | open | 24 | 15 m | `dataset_v0_p45_topup_open_20260820` |
| 2 | blocked | 24 | 12 m | `dataset_v0_p45_near_enrich_20260820` |

Baseline after v1: open:blocked = **11:24**. Phase1 aims ~1:1；phase2 抬近带（服务 ⓪c / depth 重训，不只再堆帧）。

## Notes

- Harness: `--only-layer` (`559fe31`).
- ⓪c p90=0.66 / ⓪d miss=0.088 ⇒ **补采后仍须 depth head 重训**，单靠堆语料不够。
- ⓿e teleport 与补采正交。
- Freeze 仍 `lo>hi`（diag）；补采不直接解 freeze。
