# V4 RUNBOOK 125 STATUS

- **date**: 2026-08-21
- **state**: ACTIVE — next = **控制臂**（老头 × 新语料）；新 depth FT **不进部署**
- **HEAD**: `809cde6`
- **enable_policy_update**: false
- **R-16**: **(B)**

## 三句结论（2026-08-21）

1. **⓪f 曾判错**：给 report-only 的外带 AbsRel 套了 ⓪c 的 `p90≤0.50`（代码 `v4_zero_eval`）；已改回——(1)(2) 只报，pre-freeze `ok`=外带 support；(3)(4) 等 `[lo,hi]`。
2. **整套 ⓪ 在训练帧上评** ⇒ **PASS 不可采、FAIL 更硬**；且一次改了语料+头 ⇒ ⓪c/d 变化不可归因。
3. **下一发 = 控制臂**（老头 `depth_ckpt_da3_r60_20260814` × `dataset_v0_p45_merged_20260821`）——同时解 in-sample 与「一次改两件事」；**不再治深度头**。

## `$INIT_DEPTH` 出处（已答）

**是** V0 ④ 实际过 gate 的头。

- 活文档 [`V0_GATE_STATUS.md`](V0_GATE_STATUS.md)：r60 部署线 depth = `depth_ckpt_da3_r60_20260814`；②④ rollout 命令明示 `depth=depth_ckpt_da3_r60_20260814`；merge PASS `v0_partial_24_r60_20260814` / `v0_gate_r60_20260814`。
- 文件：`depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt`（holdout AbsRel 0.0641）。
- ⇒ **本轮 depth FT 不因「失效 ckpt warm-start」作废**；但新头因 ⓪d/`max_consec_miss` **仍不得进部署**（见 GATE_STATUS (G)）。

## Checklist

- [x] merge + depth FT + WM + re-P3/P1（in-sample / 双改 方法论阻塞）
- [x] ⓪f 代码判错改回
- [ ] **控制臂** → `artifacts/v4_zero_p3_oldhead_merged_20260821.json`
- [ ] ⓿e fix（orthogonal）
- [ ] freeze / P7 / P8

## Running jobs

| job | PID | log |
|-----|-----|-----|
| 控制臂 oldhead×merged | **3136001** | `logs/v4_p3_oldhead_merged_20260821.log` → `artifacts/v4_zero_p3_oldhead_merged_20260821.json` |

## Notes

- Primary merge = ⓪a–e only；`ok_0f` 不再拖垮 overall `ok`。
- 控制臂产物同时是诚实 held-out（老头未见新语料）与可归因对照（同语料新旧头）。
