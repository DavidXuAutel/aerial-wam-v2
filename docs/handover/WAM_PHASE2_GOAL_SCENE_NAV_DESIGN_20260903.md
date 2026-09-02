# Phase-2 方案 · 仅 G + 场景（活页入口 · 2026-09-03）

> **权威设计**：[`docs/superpowers/specs/2026-09-03-phase2-goal-scene-nav-design.md`](../superpowers/specs/2026-09-03-phase2-goal-scene-nav-design.md)  
> **实现计划**：[`docs/superpowers/plans/2026-09-03-phase2-goal-scene-nav.md`](../superpowers/plans/2026-09-03-phase2-goal-scene-nav.md)  
> **D0**：已确认 · 2026-09-03  
> **E0 DECLARE**：[`WAM_PHASE2_GOAL_SCENE_E0_DECLARE.md`](WAM_PHASE2_GOAL_SCENE_E0_DECLARE.md)（待 4090 填数）

## 一句话

目标在远处一点 \(G\)（**主尺度 200–500 m**；~100 m 已过；1 km 非本战役过门）；输入只有 \(G\) 与眼前场景；**无预置航迹**。  
WAM 外环临时「画」近距意图 c* → Phase-1 快执行 → 罩；停机 ‖p−G‖≤3。

## 旧路

标注折线 / 滚动 GT `P_ref` / carrot 跟线 → **降级对照**，不再主航道。
