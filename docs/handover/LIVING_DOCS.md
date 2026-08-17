# 活文档阅读清单（2026-08-17）

> **用途**：回答「现在该读哪些活文档」。只列**仍在维护 / 决定现状**的入口；历史备忘与已闭合细节按需下钻。  
> **防误读**：`RUNBOOK_v0.md` §8 晚¹⁹–²² / 任何「merge 从未 exit 0」叙述 = **2026-08-12 快照**，不是现状（V0 已于 08-14 merge PASS）。

---

## A. 必读（当前主线）

| 顺序 | 文档 | 读什么 |
|---|---|---|
| 1 | [`V4_GATE_STATUS.md`](V4_GATE_STATUS.md) | **当前阶段**一句话：V4 merge 状态、下一轨 |
| 2 | [`V4_GOAL_Z0_125_STATUS.md`](V4_GOAL_Z0_125_STATUS.md) | **正在跑**的 125 agent（goal 注入 / 真 RGB z0 / 重 gate） |
| 3 | [`ACCESS.md`](ACCESS.md) | 校园直连：`cursor-125` / H100 hop；异地备用 `cursor-125-public` |
| 4 | [`../superpowers/specs/2026-08-16-v4-mvp-design.md`](../superpowers/specs/2026-08-16-v4-mvp-design.md) | V4-MVP In/Out、①/④ 判据（规格，非日志） |

可选同轨细节（按需，非每天）：

- [`V4_REWARD_HEAD_125_STATUS.md`](V4_REWARD_HEAD_125_STATUS.md) — RH 修好后 ①−3.17 / ④ PASS  
- [`V4_ENCODE_TRAIN_125_STATUS.md`](V4_ENCODE_TRAIN_125_STATUS.md) — 坏 RH → ①−68 的那轮  
- [`V4_H100_TRAIN_STATUS.md`](V4_H100_TRAIN_STATUS.md) — H100 ckpt 路径  
- [`V4_GOAL_Z0_125_PROMPT.md`](V4_GOAL_Z0_125_PROMPT.md) — 远端 agent 指令（调试用）

---

## B. 已闭合但仍常查（V0 / V1）

| 文档 | 读什么 |
|---|---|
| [`V0_GATE_STATUS.md`](V0_GATE_STATUS.md) | **§1+§2** = V0 权威现状；§3.3 = 旧 ①a–c 失格史；§4 = **n=8 已 re-freeze** |
| [`V1_GATE_STATUS.md`](V1_GATE_STATUS.md) | V1 三信号严谨 PASS + 部署 flags |
| [`../../experiments/aerial/RUNBOOK_v0.md`](../../experiments/aerial/RUNBOOK_v0.md) | V0 顶层入口；**§1–§2 现状**；§8 = 变更考古（勿把晚¹⁹ 当今天） |
| [`../PROJECT_STATUS.md`](../PROJECT_STATUS.md) | 项目鸟瞰（若与 V4 活文档冲突，**以 V4_GATE_STATUS 为准**） |
| [`../design/2026-08-15-v1-v4-design.md`](../design/2026-08-15-v1-v4-design.md) | V1/V4 母本设计 |

阈值唯一真相源（改阈值才读、才改）：

- [`../superpowers/specs/2026-08-04-aerial-wam-v2-frozen-spec.md`](../superpowers/specs/2026-08-04-aerial-wam-v2-frozen-spec.md) §4.1

---

## C. 运维 / 采集（按任务）

| 文档 | 何时读 |
|---|---|
| [`ACCESS.md`](ACCESS.md) | SSH / origin / 异地 |
| [`../../experiments/aerial/scripts/RUNBOOK_sync_and_env.md`](../../experiments/aerial/scripts/RUNBOOK_sync_and_env.md) | 三机同步与环境 |
| [`2026-08-04-v0-4090-local-collect-runbook.md`](2026-08-04-v0-4090-local-collect-runbook.md) | **4090 本地采集**（与 sync RUNBOOK 有冲突，见 `V0_GATE_STATUS` §3.5；实操以本文件 + r60 为准） |
| [`2026-08-10-signal3-reprojection-estimator.md`](2026-08-10-signal3-reprojection-estimator.md) | V0 ③ 估计器细节 |
| [`2026-08-10-da3-depth-backbone.md`](2026-08-10-da3-depth-backbone.md) | DA3 深度头 |

---

## D. 不要当作「当前权威」的东西

- 任何指向下列**空文件**的链接（已确认不存在）：  
  `2026-08-12-v2-plan-risk-assessment.md`、`2026-08-12-v0-gate-status-and-roadmap.md`  
  → 内容只活在 `RUNBOOK_v0.md` §8 晚¹⁹/晚²⁰ 正文。
- 「`_v0_gate --merge` 从未 exit 0」「仍在 Step 6 合拢」类 8/12 备忘。
- 「n=8 相对冻结 16 越界」—— **2026-08-17 已 re-freeze，n=8 即冻结值**。
- `PROJECT_STATUS.md` / `RUNBOOK_v0.md` §1 若仍写「V1 进行中 / V4 未开始」而与 `V4_GATE_STATUS` 冲突时 → **以 V4 活文档为准**（并应回写那两处）。

---

## E. 最短路径（5 分钟对齐）

1. `V4_GATE_STATUS.md` §1  
2. `V4_GOAL_Z0_125_STATUS.md`（若 in_progress）  
3. `ACCESS.md`  
4. 需要 V0/V1 数字时再打开 `V0_GATE_STATUS` / `V1_GATE_STATUS` 的 §1
