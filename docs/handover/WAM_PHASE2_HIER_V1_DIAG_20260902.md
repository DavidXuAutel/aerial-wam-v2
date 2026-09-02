# Phase-2 Hierarchical · V1 只读分诊（2026-09-02）

> **输入**：`artifacts/wam_phase2_reanchor_stepe_result_20260830.json`；短探针 R05/R01（F15 DECLARE 表）；方案 [`WAM_PHASE2_HIER_MPC_LOCAL_P1_DESIGN_20260902.md`](WAM_PHASE2_HIER_MPC_LOCAL_P1_DESIGN_20260902.md)  
> **不改行为**：本文只读结论。  
> **计划**：[`docs/superpowers/plans/2026-09-02-hier-mpc-phase1-local.md`](../superpowers/plans/2026-09-02-hier-mpc-phase1-local.md)

---

## 1. 命名

| 标签 | 含义 |
|------|------|
| **F12 多数** | 16 路回锚里超时 + arc-Prog 虚高 + Euclidean 未闭合 |
| **R05** | 短探针默认 `routes=0,2,4` 中 **idx=4**（文档口语 R05）；回锚同 idx |

到点合同：`arrived := rem≤3 ∧ ‖p−G‖≤3`（已在 long_eval）。

---

## 2. 回锚 16 路（step_e · meter · assist OFF）

| 汇总 | 值 |
|------|-----|
| SR / SPL | **0 / 0** |
| mean Prog | **0.86**（旧门限会假装接近） |
| mean `goal_closure`（事后算） | **≈0.43** |
| 1001-step 超时 | **14 / 16** |
| `monotone_inflate`（prog≥0.9 ∧ d_min≥30） | **13 / 16** |
| 早期严重碰撞 | 2（idx 3、15） |

典型超时路：`d_min ∈ [56, 71]`，Prog 常 ≥0.97，**从未到点**。  
含探针 **R05=idx4**：`prog=1.0` · `d_min=71.3` · `steps=1001` → **同属 F12 多数模式**，不是「全程零位移」在 1001 步汇总里。

---

## 3. 短探针 R05（F15 baseline · 300 步）

| | ds | idle | cos@30 |
|--|-----|------|--------|
| R05 | ≈1.3 | ≈98% | ≈0.15 |

→ **局部 yaw 死 / idle**：前 300 步几乎不沿轨。与 1001 步回锚「高 Prog、远 G」可并存：arc-s 可虚涨或后期蹭轨，**欧氏到 G 仍失败**。

R01 在 planner 修后短探针可过；**不得**用 R01 掩盖 R05 局部病。

---

## 4. 分诊表

| 假设 | F12 多数（回锚） | R05 短探针 |
|------|------------------|------------|
| Prog 灌水 / 锁死参考 | **是**（13/16 inflate） | 次要 |
| 超时非到点 | **是**（14/16） | 时限内已暴露 idle |
| 局部 yaw/idle | 长跑未必全程 idle | **是** |
| L1 预瞄反馈帮得上？ | **可能**（刷新 δ/无进展） | 弱；先要局部动 |
| L2 滚动 \(P_{ref}\) 帮得上？ | **对症方向**（参考/重规划） | **否**（局部不动刷新无效） |
| 再拧 F15 `w_eff` | **否** | 已停；并行局部专项 |

---

## 5. 对执行序的含义

1. **L0**（已并行）：评测 PASS **不得**依赖 mean Prog；主报 SR / `goal_closure` / `monotone_inflate`。  
2. **下一刀主航道**：**L1 DECLARE**（预瞄反馈）→ 再 **L2 P0** 滚动全局；目标先打 F12 多数的 `d_min`/真到点。  
3. **R05 局部专项并行**（actor / subgoal / planner 逐步 log），**不**塞进第一刀全局。  
4. 静段钉点 / assist / F15 扩面：**保持冻结**。

---

## 6. 签字

| 项 | 结论 |
|----|------|
| V1 | **完成** |
| F12 | 主失败 = 超时 + Prog 虚高 + 欧氏未闭合 |
| R05 | 局部 idle ≠ 全局锁死；分轨修 |
| 下一步 | L1 DECLARE（仅预瞄反馈，默认仍保守） |
