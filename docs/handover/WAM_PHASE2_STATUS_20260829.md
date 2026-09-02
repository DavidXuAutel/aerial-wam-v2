# Phase-2 STATUS（活页 · 2026-09-02）

> **方案**：[`WAM_PHASE2_HIER_MPC_LOCAL_P1_DESIGN_20260902.md`](WAM_PHASE2_HIER_MPC_LOCAL_P1_DESIGN_20260902.md)  
> **完整计划**：[`docs/superpowers/plans/2026-09-02-phase2-receding-global-full.md`](../superpowers/plans/2026-09-02-phase2-receding-global-full.md)  
> **P0 DECLARE**：[`WAM_PHASE2_HIER_P0_ROLLING_GLOBAL_DECLARE_20260902.md`](WAM_PHASE2_HIER_P0_ROLLING_GLOBAL_DECLARE_20260902.md)

---

## 一句话

滚动全局 `P_ref` + 冻结 Phase-1；`--rolling-global` **已接线、默认 OFF**。  
下一刀：**`.110` P0 评测**（勿再开单路/L1/F15 坑）。

---

## 进度

| Task | 状态 |
|------|------|
| 1–2 `GlobalRefPlanner` + 跳变约束 | **done** · 单测绿 |
| 3 `long_eval --rolling-global` | **done** |
| 4 P0 DECLARE | **done** |
| 5 `.110` P0 评测 | **下一步** |
| 6 P1 代价 / 7 默认决策 | 排队 |

搁置：L1 探针、单路局部坑、assist、F15。
