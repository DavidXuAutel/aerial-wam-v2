# DECLARE · L1 预瞄反馈（Lookahead Feedback）· 2026-09-02

> **状态**：**已实现 · 默认 OFF** — V1 已分诊；码在 `subgoal_generator` + `--lookahead-feedback`。下一刀 `.110` 探针。  
> **前置**：[`WAM_PHASE2_HIER_V1_DIAG_20260902.md`](WAM_PHASE2_HIER_V1_DIAG_20260902.md) · 计划 L1  
> **禁止**：当主航道默认开满 16 路；冒充 L2 全局重规划；F15 / assist / 静段钉点。

---

## 1. 意图（对症）

V1：F12 多数 = **超时 + Prog 虚高 + `d_min~60`**。  
L1 假设：在 **固定折线** 上，用飞行反馈收紧/刷新 **预瞄参数**（δ、freeze、无进展），可减少「虚涨 s、胡萝卜跑飞」；**不**指望修好 R05 局部 idle。

```text
仍用 annotation 折线 P
  → AdaptiveSubgoal + 反馈律（本 DECLARE）
  → Phase-1 WAM
不到中间 c；停机仅 ‖p−G‖≤3
```

---

## 2. 拟改（实现时 · opt-in）

| 开关（建议名） | 默认 | 行为 |
|----------------|------|------|
| `lookahead_feedback` | **False** | 总闸 |
| `no_progress_shrink` | 随总闸 | 若 \(N\) 步内 `true_s` / `d_goal` 无实质进展 → 缩短 lookahead（下限仍 ≥ 安全/蠕行包络） |
| `cte_feedback_boost` | 随总闸 | CTE 大时已有 shrink；反馈只 **强化既有 CTE 回收**，不新造第二套几何 |

**明确不做（L1）**：重采样整条 P；换终点；段末硬到点；开 assist。

**文件**：`experiments/aerial/rl/subgoal_generator.py` + 单测；long_eval / probes **CLI 显式打开**。

---

## 3. 评测门（`.110` · `step_e` · assist OFF）

探针优先（勿一上来 16 路）：

| 路 | 角色 | 过门（相对回锚同路） |
|----|------|----------------------|
| idx 0 / 4 / 12 之一 | F12 代表（高 Prog、`d_min~60`） | `d_min` 不恶化 >5 m；`monotone_inflate` 不升；若步数同 cap 则 `goal_closure` ↑ |
| idx 4（R05） | 局部对照 | **不要求**修好 idle；`ds`/idle **不显著变差**即可继续 |

准出再考虑短表 16 路；主指标仍 **SR / closure**，Prog 诊断 only。

---

## 4. Fail → 停

- 反馈导致更多 freeze / 原地抖动 / IR 飙升  
- R05 短探针 idle 变差  
- 有人把 L1 写成「已做 MPC / 全局重规划」

→ 关总闸，回退；改走 L2 DECLARE 或 R05 局部专项。

---

## 5. 签字栏

| 项 | 值 |
|----|-----|
| 范围 | 预瞄反馈 only · 固定 P |
| 默认 | **OFF** |
| 下一动作 | 实现 opt-in + 单测 → `.110` 探针 |
| 非目标 | L2 \(P_{ref}\) 滚动；R05 根治 |

**产品/主航道**：认可后 agent 方可合入行为码（仍默认 OFF）。
