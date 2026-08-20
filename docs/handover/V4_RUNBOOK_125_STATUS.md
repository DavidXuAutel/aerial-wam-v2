# V4 RUNBOOK 125 STATUS

- **date**: 2026-08-20
- **state**: ACTIVE — **P4.5 补采 DONE**; next = merge → depth/WM retrain → re-P3/P1
- **HEAD**: `98fc7a7`
- **P3 (post-P4.5 v1)**: ⓪b PASS; ⓪c/⓪d FAIL
- **P1 (post-P4.5 v1)**: FAIL reward `beat_frac=0.67`
- **P4**: ⓿e FAIL — harness，不靠补采
- **enable_policy_update**: false
- **R-16**: **(B)**

## Checklist

- [x] P4.5 v1 — 34 usable (open 11 / blocked ~23–24)
- [x] **P4.5 补采** — phase1+2 DONE `23:22`
- [ ] merge corpora → depth head + WM retrain
- [ ] re-P3 / re-P1
- [ ] ⓿e fix (orthogonal)
- [ ] freeze / P7-accept / P8

## Top-up results

| phase | out | usable | layers |
|-------|-----|-------:|--------|
| 1 open | `dataset_v0_p45_topup_open_20260820` | **24/24** | open 24 |
| 2 near | `dataset_v0_p45_near_enrich_20260820` | **19/19** | blocked 19（目标 24，scan 未满） |

若三库 concat：open **35** / blocked **~42**（仍偏 blocked；open 已从 11 抬到可合并 35）。

Log: `logs/v4_p45_topup_20260820.log` — `[topup] DONE 2026-08-20T23:22:26+08:00`

## Running jobs

| job | PID | log |
|-----|-----|-----|
| (none) | — | — |

## Notes

- Launch SSH wrapper exited 1；**采集本身 exit=0 双阶段完成**。
- 下一步不是再采，是 **merge + depth/WM 重训**（⓪c 单靠堆帧不够）。
