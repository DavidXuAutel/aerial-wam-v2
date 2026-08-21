# V4 RUNBOOK 125 STATUS

- **date**: 2026-08-21
- **state**: ACTIVE — **控制臂 DONE**；新 depth FT **退化近场功能项**，不进部署
- **HEAD**: `3501def` (+ ⓪f fix `809cde6`)
- **enable_policy_update**: false
- **R-16**: **(B)**

## 三句结论

1. ⓪f 判错已改回（外带 AbsRel report-only）。
2. ⓪ 曾 in-sample ⇒ PASS 不可采；控制臂给了诚实 held-out。
3. **下一发不要再治深度头**（已证实 FT 使 ⓪c/d 变差）；治方向另定。

## `$INIT_DEPTH`

**是** V0 ④ 过 gate 头（`depth_ckpt_da3_r60_20260814`）。FT 不因失效 ckpt 作废，但**新头不可部署**。

## 控制臂 vs 新头（同语料 `dataset_v0_p45_merged_20260821`，77 ep）

| 项 | 老头（控制臂） | 新头 FT |
|----|----------------|---------|
| ⓪a median | **0.199** PASS* | 0.144 PASS† |
| ⓪b | 315 帧 PASS | 315 PASS |
| ⓪c p90 | **0.716** FAIL | **0.792** FAIL（更差） |
| ⓪d miss / max_consec | **0.076 / 2** FAIL | **0.142 / 4** FAIL（更差） |
| ⓪f | support PASS；outer p90 **0.466**（report） | support PASS；outer p90 0.504（report） |

\*老头 × 新语料 = **诚实 held-out**。  
†新头 × 同语料含训练帧 = **in-sample**，PASS 仍不可采。

产物：`artifacts/v4_zero_p3_oldhead_merged_20260821.json`  
Log：`logs/v4_p3_oldhead_merged_20260821.log`

## Checklist

- [x] ⓪f 代码改回
- [x] 控制臂
- [ ] 归因后的下一步（非「再 FT 深度」）
- [ ] ⓿e fix
- [ ] freeze / P7 / P8

## Running jobs

| job | PID | log |
|-----|-----|-----|
| (none) | — | — |
