# Phase-2 STATUS（活页 · 2026-09-03）

> **主方案（新）**：[`docs/superpowers/specs/2026-09-03-phase2-goal-scene-nav-design.md`](../superpowers/specs/2026-09-03-phase2-goal-scene-nav-design.md)  
> **入口**：[`WAM_PHASE2_GOAL_SCENE_NAV_DESIGN_20260903.md`](WAM_PHASE2_GOAL_SCENE_NAV_DESIGN_20260903.md)

---

## 一句话

**主航道重置**：只有 \(G\) + 场景；无线可跟；主尺度 **200–500 m**（~100 m 已过）；WAM 外环生成近距意图，Phase-1 执行。  
旧「滚动 GT 折线」评测可继续作**水位**，不决定方向。

---

## 进度

| 项 | 状态 |
|----|------|
| 旧 GT 滚动 P0 评测（110/125） | 水位进行中（对照） |
| **新方案设计** | **D0 已确认（2026-09-03）** |
| **实现计划** | [`2026-09-03-phase2-goal-scene-nav.md`](../superpowers/plans/2026-09-03-phase2-goal-scene-nav.md) |
| E0 接线（`--subgoal-source`） | **已合入本分支**；单元测试 PASS |
| E0 AirSim 探针 / DECLARE | **待 `.110`/`125`** → [`WAM_PHASE2_GOAL_SCENE_E0_DECLARE.md`](WAM_PHASE2_GOAL_SCENE_E0_DECLARE.md) |
| E1 `scene` 探针 | 接线已有；待 E0 后跑 |

搁置（非主航道）：古典跟线当主修、L1 carrot、F15、assist 默认开。
