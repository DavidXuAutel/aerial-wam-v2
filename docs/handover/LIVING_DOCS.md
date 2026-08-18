# 活文档阅读清单（2026-08-18）

> **用途**：回答「现在该读哪些活文档」。只列**仍在维护 / 决定现状**的入口；历史备忘与已闭合细节按需下钻。  
> **防误读**：`RUNBOOK_v0.md` §8 晚¹⁹–²² / 任何「merge 从未 exit 0」叙述 = **2026-08-12 快照**，不是现状（V0 已于 08-14 merge PASS）。

---

## A. 必读（当前主线）

| 顺序 | 文档 | 读什么 |
|---|---|---|
| 1 | [`V4_GATE_STATUS.md`](V4_GATE_STATUS.md) | **当前阶段**一句话：V4 merge 状态、下一轨 |
| 2 | [`V4_PROGRESS_DIAG_125_STATUS.md`](V4_PROGRESS_DIAG_125_STATUS.md) | **① 诊断 DONE**：反目标飞；规格 goal-blind + 单 mock goal |
| 2b | [`V4_SIGNAL1_STRUCTURAL_REFREEZE_PROPOSAL.md`](V4_SIGNAL1_STRUCTURAL_REFREEZE_PROPOSAL.md) | **部分签字**：C2 已落地并重训；① = **`clip_insufficient`**。**§4 In 表搁置**（C2 cos≥0）。V3 / unique-goals **仍待签** |
| 2c | [`V4_SIGNAL1_SA_DIAG_STATUS.md`](V4_SIGNAL1_SA_DIAG_STATUS.md) | 先读「A.3 判定作废」；文末 **C2 重跑** + **cos diag** |
| 2d | [`V4_C2_COS_DIAG_125_STATUS.md`](V4_C2_COS_DIAG_125_STATUS.md) | **DONE**：C2 ①-eval cos **+0.806 / +0.762** ⇒ **不签** §4 In 表（想象-真实倒挂；洞 4：`goal_rel0` 构造性前向） |
| 3 | [`V4_GOAL_Z0_125_STATUS.md`](V4_GOAL_Z0_125_STATUS.md) | 已完成的 goal+z0 轨（① 仍 FAIL） |
| 4 | [`ACCESS.md`](ACCESS.md) | 校园直连：`cursor-125` / H100 hop；异地备用 `cursor-125-public` |
| 5 | [`../superpowers/specs/2026-08-16-v4-mvp-design.md`](../superpowers/specs/2026-08-16-v4-mvp-design.md) | V4-MVP In/Out、①/④ 判据（规格，非日志） |

可选同轨细节（按需，非每天）：

- [`V4_REWARD_HEAD_125_STATUS.md`](V4_REWARD_HEAD_125_STATUS.md) — RH 修好后 ①−3.17 / ④ PASS  
- [`V4_ENCODE_TRAIN_125_STATUS.md`](V4_ENCODE_TRAIN_125_STATUS.md) — 坏 RH → ①−68 的那轮  
- [`V4_H100_TRAIN_STATUS.md`](V4_H100_TRAIN_STATUS.md) — H100 ckpt 路径  
- [`V4_GOAL_Z0_125_PROMPT.md`](V4_GOAL_Z0_125_PROMPT.md) — 远端 agent 指令（调试用）

---

## B. 已闭合但仍常查（V0 / V1）

| 文档 | 读什么 |
|---|---|
| [`V0_GATE_STATUS.md`](V0_GATE_STATUS.md) | **§1+§2** = V0 权威现状；§3.3 = 旧 ①a–c 失格史；§4 = **n=8 已 re-freeze**；§4.1 = **④b 空过终态已收口** |
| [`V1_GATE_STATUS.md`](V1_GATE_STATUS.md) | V1 三信号严谨 PASS + 部署 flags；**§4.1/§4.2 = ②-coll 独立诊断**（不改 08-15 merge）；§2 ① **功效脆弱已记** |
| [`V1_SIGNAL1_POWER_REFREEZE_PROPOSAL.md`](V1_SIGNAL1_POWER_REFREEZE_PROPOSAL.md) | **待签字**：V1-① 条款②配对强制 + ③裕度带（与 n re-freeze 正交） |
| [`V1_COLL_HELDOUT_COLLECT_125_STATUS.md`](V1_COLL_HELDOUT_COLLECT_125_STATUS.md) | 125 碰撞富集 held-out 采集 **DONE**（usable 65 / coll usable 8） |
| [`V1_COLL_HELDOUT_DIAGNOSTIC_STATUS.md`](V1_COLL_HELDOUT_DIAGNOSTIC_STATUS.md) | H100 ②-coll 新 held-out 诊断 **CLAIMED**（pos=20 / AUROC 0.977） |
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
- 「n=8 相对冻结 16 越界」—— **2026-08-17 已 re-freeze，n=8 即冻结值**（洞 1 = **事后合法化**，见 `V0_GATE_STATUS` §4；非事前干净通过）。
- 「n=8 re-freeze 治了 V1-① 擦边」—— **否**；合法性 ≠ 统计功效。① 裕度 0.8 局 / McNemar p≈0.5 见 `V1_GATE_STATUS` §2 + [待签字条款②③](V1_SIGNAL1_POWER_REFREEZE_PROPOSAL.md)。
- 「V4-① 再训一轮 / 对齐 z0 就能过」—— **否（再训现 π）**；C2 已从零重训仍 FAIL。**对齐 z0 / WM 保真**是 08-18 后的**活假设**（cos≥0 后的倒挂），尚未验证、不得当「就能过」。见 [cos STATUS](V4_C2_COS_DIAG_125_STATUS.md)。
- 「§A `b>c` 已证明改 In 表就够」—— **否**，§4 仍不充分（A.2 只排除碰撞项通道）。
- 「A.3 = `b3_le_a` ⇒ 先修 RH」—— **否，2026-08-18 已作废**：那条臂无效（① 幅度只匹配第 0 步、欠 ~4.6×，π 轨迹均值 ‖a[:3]‖≈16.5；② 五臂全超部署上限 `body_delta_limits(1/5Hz)`=[1.0,0.4,0.4,0.314]，`imagine()` 不夹；③ (b3) 冲过目标 23.9 m）。**可实现集合内 RH 方向偏好是对的**。A.4 seed=0 已实测：夹后最大前飞 λG0 **47.64 ≥** π_clipped **18.25**（`fwdmax_ge_pi`）⇒ 倒挂来自无界动作通道，**确诊不是 RH 案**。裁定已签 = **C2**（08-18，代码已落地），见 `V4_GATE_STATUS` §1/§3。
- 「`action_scale=3.0` 是动作上界 / π 已饱和」—— **否**；`_MLP` 末层裸 `nn.Linear`，它是**增益**，‖a‖ 无上界（`actor_critic.py:200`）。**← 描述 pre-C2**；C2 起 `action_scale` 默认 **1.0** 且是 **pre-tanh 增益**，动作由 `limits ⊙ tanh(u)` **构造性有界**（旧 ckpt 仍按 legacy 类以 3.0 回放）。
- 「一致性修 = 在 `imagine()` 加一行 clip」—— **不够**（提案 §4.1）。actor 更新是 **REINFORCE**（`actor_critic.py:257`/`:271`，无梯度穿 `dynamics.step`），字面 clip ⇒ 用未夹高斯给夹后动作算 logp（似然错配）+ 探索塌缩（σ=0.607 四维同值 > 后三维上限；盒内采样概率 8.6%，现 ckpt 3.4e-6）。推荐 **C2 有界策略分布**（`a = limits ⊙ tanh(u)` + 雅可比修正），须**从零重训**。**← 已按 C2 落地**（08-18）；`imagine()` 里的 clip 保留为**计数器** `n_action_clipped`（C2 下实测 0），不是修本身。
- **「C2 已落地 ⇒ V4-① 已修好 / 可以翻 flags」—— 否**（08-18）。C2 已从零重训并再 gate：`n_action_clipped=0`，① **仍 FAIL**（−7.43 / −3.53 vs heur ~9），`enable_policy_update` 仍 **false**。判定 `clip_insufficient`。
- **「`clip_insufficient` 已判实 ⇒ 直接签 §4 In 表」—— 否**（08-18 cos diag DONE）。mean cos actor **+0.806 / +0.762**（≥0）⇒ 事前表 **不签** In 表；活假设 = 想象-真实倒挂（imagΣG ~85 vs real ~−5）。见 [`V4_C2_COS_DIAG_125_STATUS.md`](V4_C2_COS_DIAG_125_STATUS.md)。
- **「那个 cos 已在 C2 re-gate 产物里」—— 否**（08-18）。gate partial-1 只落 progress / final_dist / scan，**无 cos 无动作**。出 cos 的是 `v4_progress_diag.py`（M5d ≈−0.88；C2 **+0.76~+0.81**）。
- **「评测 `goal_rel0` 是一个分布」—— 否，是构造性常量**（08-18 洞 4 + 实测）。`goal_dist_m=30.0` + `goal=start+heading*30` + spawn yaw=heading ⇒ t=0 body goal ≈ `[+30,0,z]`（diag |az|≤0.8°）。正 cos **不能**读成「随 goal 转向」。
- **「n=5 = 扫描期 spawn_collision」—— 否**（08-18 读盘）。seed=0：accepted 9 → scored 5（评测期丢）；`rejections.open_ahead=708` 是扫描期拒收。键名 **`rejections`**（不是 `rej`）。修扫描拒收 ≠ 修 `_run_one_resilient→None`。
- **「训后 λG0 59.09 > 最大前飞 47.78 ⇒ 又在薅想象」—— 否**（08-18）。事前 `clip_helped` 行写的「λG0(π)≤最大前飞」隐含「纯前飞是盒内最优」，**四自由度盒里不成立**。`goal_rel` 30→17.8 = 闭合 **12.2 m**，H=15 × 上限 1.0 m/步 ⇒ 盒内理论上限 15 m 的 **81%** ⇒ 是真接近目标。**不**重开 RH 案。
- **「① n=5 只是样本少一点」—— 不止**（08-18）。spawn-in-collision 丢的是**杂乱起点** ⇒ 存活局偏开阔空间，**非随机**丢失。FAIL 方向对 n 稳健（补 3 局须各 ≈37.9 / 33.7，heuristic 每局仅 ~8.7），但**两跑均非全权**、不得入账干净 gate；**④ PASS 同为非全权**（off-rate 2/5；on-rate=0 ⇒ ④b 大概率 `before_vacuous`）。要全权 ① 须先解 spawn，**不**降 `n`。
- 「V1 部署侧动作空间已一致」—— **未核**；`planner.default_candidates`（`planner.py:31-42`）在未夹空间打分，到 `collector.py:167` 才夹。**不**重开 08-15 merge，仅记为同源不一致。**← C2 未改这条**：`planner.action_limits` 默认 `None`，V1 部署路径逐位不变（打开须 V1 re-gate）。
- 「④b before=1.0 是测得的干预先于接触」—— **否**；`n_contact=0` 时空过终态，④ 实证=④c。
- 「headon 可作 V1-② coll OOD」—— **否**；headon `coll_eps=0`。
- `PROJECT_STATUS.md` / `RUNBOOK_v0.md` §1 若仍写「V1 进行中 / V4 未开始」而与 `V4_GATE_STATUS` 冲突时 → **以 V4 活文档为准**（并应回写那两处）。

---

## E. 最短路径（5 分钟对齐）

1. `V4_GATE_STATUS.md` §1  
2. [`V4_C2_COS_DIAG_125_STATUS.md`](V4_C2_COS_DIAG_125_STATUS.md) — C2 cos diag **DONE**：mean cos **+0.806/+0.762** ⇒ **不签** §4；下一件 = 想象-真实倒挂另案（WM/z0，非 In 表）  
3. `ACCESS.md`  
4. 需要 V0/V1 数字时再打开 `V0_GATE_STATUS` / `V1_GATE_STATUS` 的 §1
