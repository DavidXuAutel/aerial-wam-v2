# V4 Gate 状态活文档

> **用途**：V4-MVP merge 进度（镜像 V1 活文档）。  
> **设计**：[V4-MVP 规格](../superpowers/specs/2026-08-16-v4-mvp-design.md)（方案 1）。  
> **前置**：V1 merge PASS + `tau_predictor.kind=foe_calibrated`。

---

## 1. 一句话结论（2026-08-17）

**Goal+z0 track done — merge FAIL（① −8.74 / ④ PASS）** — ① **现规格下不可稳健达成**（不是差一点；措辞 2026-08-18 由「结构性不可达」收紧，见提案 §3 精确边界）。  
根因两叠加：(1) In 表规定 `act_latent(z)` / `V(z)`，goal 只进想象 reward；(2) 权威 300 iter 只有 `_mock_goal_episode()` 一对 start→goal。修好 conditioning（M5d）把**那一个**方向烙进 `π(z)`，① 从 −3.17 **退到** −8.74。逐 ep：首动作 cos≈−0.88 vs heur ≈+0.99。  
**未解释的部分（§A 已判定方向性）**：烙印解释首动作**恒定**。§A 三臂分解（2026-08-18）：常量前飞 λG0 **49.65** > 后退 **15.99**（A.3 同跑口径；首跑无 seed 为 47.02/15.9，已 superseded），差额来自 **progress**，p_coll≈0 → **不是**想象内碰撞项主导后退。见 [§A STATUS](V4_SIGNAL1_SA_DIAG_STATUS.md)。  
**⚠️ 「§4 充分」不成立；但「先修 RH」也无依据 —— A.3 判定作废（2026-08-18 复核）**：`b3_le_a` 字面成立（前飞@3.59 λG0 **59.85** ≤ π **103.63**），但臂无效 —— (1) 只匹配了 a0=3.59，π **轨迹**均值 ‖a‖ **≈16.5**（Σmaneuver 2.47÷0.01÷15 与 ‖goal_rel‖ 30→254 互证），欠匹配 ~4.6×；(2) `imagine()` **不夹动作**而部署夹 `body_delta_limits(0.2)`=[1.0,0.4,0.4,0.314]，五臂全在**不可实现区** —— **(b) `[+1,0,0,0]` 恰是可实现最大前飞，λG0 49.65 vs 可实现最大后退 15.99（3.1×）⇒ 可实现集合内 RH 方向偏好是对的**，π 只靠跑出集合 3.6–16× 才赢（`w_progress:w_maneuver=100:1` 下恒真）；(3) (b3)@3.59 第 ~8.4 步冲过 30 m 目标（末态 23.9 = |30−53.87| ✓），后半程 goal 在身后。`pi_imagined_arrival=false` 仍成立。见 [§A STATUS](V4_SIGNAL1_SA_DIAG_STATUS.md)。  
**§A.4 DONE（2026-08-18，seed=0）= `fwdmax_ge_pi`**：夹到 `body_delta_limits(1/5)`=[1.0,0.4,0.4,0.314] 后，最大前飞 λG0 **47.64 ≥** π_clipped **18.25**（π 夹后 a0 仍后向 `[-1.0, -0.309, -0.27, -0.163]`，goal 30→45.9）。倒挂来自**无界动作通道**，不是 RH 方向偏好。配套未夹 traj 匹配：`match_scale=15.59`（印证欠匹配 ~4.3–5.0×），(b3)@15.59 λG0 18.21、过冲 30→204；字面 `b3_le_a` **不**重开 RH 案。见 [§A STATUS](V4_SIGNAL1_SA_DIAG_STATUS.md) A.4 节。  
**下一件 = 动作空间一致性裁定**（提案签字栏）：是否本周期在 `imagine()` 落与部署同一 clip，然后重跑 §A。提案方读法：属既有红线修不一致，可先落。未签字前**不改** `imagination.py`。  
**处置**：In 表修订仍在提案里但 **当前不充分**；**不**开 RH 案（A.3 依据已撤，A.4 确诊不是 RH）。不加长训、不降 `δ_p`、不翻 yaml。待签字稿：[V4_SIGNAL1_STRUCTURAL_REFREEZE_PROPOSAL](V4_SIGNAL1_STRUCTURAL_REFREEZE_PROPOSAL.md)。  
**另记**：`p_coll≈6e-4` 横跨所有臂（含 1 m/步 15 步头对头撞墙）⇒ 想象里碰撞头近乎**是死的**，④ 想象刹车同样无信号（另案）。A.2 两次跑无 seed，结果漂 ~6%（前飞 λG0 47.02→49.65）；`--seed` 已补。  
`enable_policy_update` **仍 false**。  
**Governance**：2026-08-17 frozen `n_eval_episodes=8`；V4 `n<8` → `authoritative=false`（洞 1 已关）。

---

## 2. 里程碑

| 步 | 内容 | 状态 |
|---|---|---|
| M0 | 设计规格入库 | ✅ |
| M1 | actor_critic + 单测 | ✅ |
| M2 | corrector 接线 + smoke | ✅ `v4_ac_smoke.py` |
| M3 | H100 短训 ckpt | ✅ PASS — `v4_ac_ckpt_20260816/` (stub, superseded) |
| M3b | H100 WM encode 300-iter train | ✅ — `v4_ac_ckpt_20260816_wm/` latent_dim=1536 |
| M4 | `_v4_gate` self-check | ✅ |
| M5 | 4090 ①④ eval (stub) | ❌ merge FAIL — ① −13.54 vs heur 9.71; ④ PASS |
| M5b | 4090 ①④ re-gate (torch WM, legacy RH) | ❌ merge FAIL — ① −68.88; ④ v4_hard 0.143 vs v1 0.00 |
| M5c | reward-head finetune + AC `*_wm_rh` + re-gate | ❌ merge FAIL — ① −3.17 vs heur 7.44; ④ **PASS** (0.143 vs v1 0.25) |
| M5d | goal inject + real RGB z0 + re-gate | ❌ merge FAIL — ① −8.74 vs heur 8.42; ④ **PASS** (0.000 vs v1 0.429) |
| M6 | flip yaml | **禁止**（merge 未 PASS） |

---

## 3. 变更记录

- **2026-08-16** — 规格落地；125 agent 接手 M0–M4。
- **2026-08-16 晚** — M1–M4 代码入库；`_v4_gate --self-check` PASS；`v4_ac_smoke` OK。
- **2026-08-16(M3)** — 125→H100 SSH key; H100 `train_v4_ac` 10 iters PASS (stub).
- **2026-08-16(M5)** — 125 4090 rollout (stub encode): ① FAIL / ④ PASS; yaml 未翻。
- **2026-08-16(encode-train)** — Align train+deploy to torch WM encode; H100 300 iters; re-gate `v4_gate_r60_20260816_wm`: ① FAIL, ④ FAIL; merge FAIL; yaml 未翻.
- **2026-08-16(reward-head)** — M5c done: RH finetune 1000 steps (`wm_ckpt_r60_rh_20260816`); AC 300 iters; re-gate `v4_gate_r60_20260816_wm_rh`: ① FAIL, ④ PASS; merge FAIL; yaml 未翻.
- **2026-08-18** — **① 结构性不可达入账**：In 表 goal-blind + 单 mock goal；M5d 变差是预测方向。待签字改 In 表（不降 ①、不加长训）。提案 `V4_SIGNAL1_STRUCTURAL_REFREEZE_PROPOSAL.md`。
- **2026-08-18（§A DONE）** — 只读三臂 imagine：`(b)>(c)` λG0 47 vs 16，progress 主导，p_coll≈0。§4 充分。STATUS `V4_SIGNAL1_SA_DIAG_STATUS.md`。yaml 未翻。**←「§4 充分」已由下一条撤回；本行仅存历史。**
- **2026-08-18（§A.4 DONE → `fwdmax_ge_pi`；A.3traj 印证欠匹配）** — 改了什么：本文 §1 把「下一件 = §A.4」改为 **「A.4 = `fwdmax_ge_pi`、下一件 = 动作空间一致性裁定」**；`V4_SIGNAL1_SA_DIAG_STATUS` 追加 A.4 实测表 + A.3traj 配套表（事前判据表**不改写**）；提案 §A.4 填判定、§5 勾 A.4 项，签字栏 A.4 填 `fwdmax_ge_pi`，「动作空间一致性裁定」仍空（待人签）；`LIVING_DOCS` 2b/2c + §D/§E、`PROJECT_STATUS` §2 + §6 同步。为什么：A.4 预提交第一支触发 —— 夹后最大前飞赢过夹后 π，倒挂来自无界动作通道。依据：125 seed=0 `--clip-actions` JSON `artifacts/v4_imagine_return_decomp_a4_20260818.json` —— λG0 (b) **47.64** ≥ (a) **18.25**（差额 29.4）；π 夹后 a0=`[-1.0,-0.309,-0.27,-0.163]` 仍后向但 ‖a0[:3]‖=1.12 落在 limits 内，goal 30→45.9（`arrived=false`）；(b)>(c) 47.64 vs 15.87 与无 seed 口径 49.65/15.99 同号。配套未夹 `--match-basis traj` JSON `..._a3traj_20260818.json`：`match_scale=15.59`（相对旧 A.3 a0=3.59 为 **4.3×**，相对本跑 a0=3.13 为 **5.0×**），印证作废理由 1； (b3)@15.59 λG0 **18.21**、过冲 30→**203.9**；(c3) Σp_coll **−60.14**（仅 OOD 15 m/步才亮，可实现 1 m/步仍死）。`--match-scale auto` 不是 float，命令用 `0`（脚本 auto 约定）；`~/data`/`~/ckpt` 不存在，改用 artifact 路径。门禁未动：`δ_p=0.10`、`n=8`、`enable_policy_update=false`、yaml / `imagine()` 本体全未改（clip 只包策略）。
- **2026-08-18（§A.3 复核 → 判定作废，追加 §A.4）** — **←本条「下一件 = §A.4」已由上一条完成；判定作废三条理由与数字仍成立，保留存审计链。** 改了什么：本文 §1 把「下一件 = 先修 RH」改为 **「A.3 判定作废、下一件 = §A.4 只读」**；`V4_SIGNAL1_SA_DIAG_STATUS` 加「A.3 判定作废」段 + Next（原实测表与 `b3_le_a` 字面判定**保留不改写**，处置行划删除线并注明撤回）；提案加 **§A.3 复核** + **§A.4 判据/命令**，A.3 事前判据表标「已被 §A.4 取代」但**原文保留**，§0 正交表新增「动作空间一致性」一轴，§4 新增「独立于本提案、可先落的一致性修」，§5/签字栏加 A.4 与动作空间裁定两项；`v4_imagine_return_decomp.py` 追加 `--clip-actions`（`_ClippedPolicy` 用部署同一 `clip_body_delta`+`body_delta_limits(1/step_hz)` 包**策略**，`imagine()` 本体不动 → 仍只读）、`--step-hz`、`--seed`、`--match-basis {a0,traj}`（默认 `a0` 以复现 A.3）、`_apply_a4` 预提交判据、JSON 增 `A4`/`seed`/`clip_actions`/`body_delta_limits`；`LIVING_DOCS` A 表 2b/2c + §D、`PROJECT_STATUS` §2 + §6 同步。为什么：`b3_le_a` 字面成立但**臂无效**，故其处置「先修 RH」无依据 —— 洞又出在提案方（我）写的事前判据上，与 A.2 那个洞同类，故照同一办法标 superseded 而**不**事后改写。依据（三条，均逐字核过代码）：**(1) 幅度欠匹配 ~4.6×** —— `match_scale` 取 `act0_norm3_mean`=3.591 只匹配第 0 步，π 轨迹均值 ‖a[:3]‖**≈16.5**，由 Σmaneuver 2.47÷`w_maneuver`0.01=Σ‖a‖247÷15 与 ‖goal_rel‖ 30→253.9 需 ≈14.9/步 **两条独立算路互证**；脚本已算 `act_norm3_mean`（`:331`）但 auto 走 `act0_`（`:366`）。**(2) 五臂全在物理不可实现区** —— `env.step_hz=5.0`（`configs/aerial_rl.yaml:20`）⇒ 部署每步夹 `body_delta_limits(0.2)`=[1.0,0.4,0.4,0.314]（`env/action.py:57`，`collector.py:167`/`airsim_env.py:170`），而 `imagine()` 一次不夹（`imagination.py:120-127`）；于是 **(b) `[+1,0,0,0]` 恰等于可实现最大前飞步，λG0 49.65 vs 可实现最大后退 15.99（3.1×）⇒ 可实现集合内 RH 方向偏好正确**，π 的 103.63 只来自跑出集合 3.6×（a0）→16×（轨迹），而 `w_progress:w_maneuver=1.0:0.01`=**100:1** 使「顶大 ‖a‖ 净赚」恒真、无需方向判断；(b3)@3.591 现实夹回**就是 (b)**（已用真 `clip_body_delta` 验证）。同时更正上一条记录里的错误：**`action_scale=3` 不是饱和界**，`_MLP` 末层裸 `nn.Linear` + `mean=actor(z)*action_scale`（`actor_critic.py:200`）⇒ 幅度**无上界**，`v4:` 块也未暴露、`from_config` 不读；另 RH 训练位移 = `body_vel×reward_dt=0.2` ≤ ~1 m/步（`configs/aerial_rl.yaml:74-76`）⇒ 想象查 3.6–16 m 属**幅度轴 OOD**，与 ‖goal_rel‖ 8.5× 是两条独立 OOD。**(3) (b3) 另被扣两刀** —— 15×3.591=53.87>30 ⇒ 第 ~8.4 步冲过目标，末态 |30−53.87|=**23.87**（实测 23.9 ✓，(c3) 30+53.87=83.87 vs 83.9 ✓，两个精确对上反验 `_goal_dist_traj`），故 STATUS「23.9（靠近）」是读反；`_apply_a3` 只对 (a) 查 arrival（`:134`）。**另记两项**：`p_coll≈6e-4` 横跨所有臂（含头对头 1 m/步 15 步撞墙）⇒ 想象里碰撞头**近乎是死的**，④ 想象刹车同样无信号（另案，不是「碰撞项已排除」的好消息）；A.2 首跑（`14d0f06`）与 A.3 同跑（`2afcb33`）**同 ckpt 同 z0 结果不同**（λG0 π 104.72→103.63、前飞 47.02→**49.65**(+5.6%)、‖a0‖ 3.36→3.59）—— 脚本当时**无 seed**，故 33×/35× 不得报两位有效数字；判定符号安全（A.3 差额 43.8 ≫ 6%）。门禁未动：`δ_p=0.10`、`n=8`、`enable_policy_update=false`、yaml 全未改；`--clip-actions` 只包策略，`imagine()` 行为不变（是否在 `imagine()` 里永久落 clip 已列入签字栏，A.4 后裁定）。
- **2026-08-18（§A.3 DONE → `b3_le_a`）** — **←本条处置「先修 RH」已由上一条撤回；判定与数字仍为实测，保留存审计链。** 改了什么：只读幅度匹配臂 (b3)/(c3) @ π ‖a0[:3]‖=**3.59**；活文档把「§4 充分」从「待 A.3」改为 **不成立、先修 RH**。为什么：A.3 预提交判据 (b3)≤(a) ⇒ RH 在 π 的幅度下仍偏好其后向向量。依据：λG0 π **103.63** > 前飞@3.59 **59.85** > 后退@3.59 **15.31**；Σprogress 142 vs 83 vs 9；`pi_imagined_arrival=false`（‖goal_rel‖ 30→254，排除「想象以为到达」）。yaml / `δ_p` / In 表均未改。
- **2026-08-18（§A 复核 → 撤回「§4 充分」，追加 A.3）** — 改了什么：`V4_SIGNAL1_SA_DIAG_STATUS`「§4 可直接执行」**撤回**并加更正段；提案新增 **§A.3 幅度匹配臂**判据 + 命令，§5 首项改为「碰撞项通道已排除」并新增 A.3 待填项；`v4_imagine_return_decomp.py` 追加 (b3)/(c3) 匹配幅度臂、`--match-scale`、五臂逐步 `progress_t`/`p_coll_t`/`‖a_t‖`/`‖goal_rel‖_t` 与 `_apply_a3`；本文 §1、`LIVING_DOCS` A 表 + §D、`PROJECT_STATUS` §2 + 洞表同步。为什么：A.2 三行判据只比 (b)/(c) 两个**单位幅度**常量，从未与 π 自比，**结构上探测不到幅度通道**（判据的洞在提出方，即我）。依据：同表第一行 —— π 想象 λG0 **+104.72** 为最高，真实 ① **−8.74** 为最低（前飞 +47.02 / heur +8.42），**排序倒挂**＝命门 A 的直接证据；`a0` 模长 ≈3.36（`action_scale=3` 饱和），幅度 3.4× 换 Σprogress 2.3×，而 Σmaneuver 仅 −0.15→−2.47，即 progress +81.92 对惩罚 +2.32（≈**35× 欠罚**）。同时更正残差段：排除 `p_coll` 配平案成立，但「多样 goal 重训可消化」**无依据**（多样 goal 修方向条件化，不改幅度欠罚）。另记三项未报：`goal_rel` 被 `g−=a[:3]` 推至 ≈80（训练 ~30）故 (a)/(c) progress 属 OOD 查询；(a) 逐步 `‖goal_rel‖` 未报（若收到 ~0 则病灶在 z 转移保真，另案）；`goal_rel0` 只用 ep0 一个值套 8 个 z0，不得读成 goal 分布覆盖。未改代码行为以外的任何门禁：`δ_p=0.10`、`n=8`、yaml 全未动；A.3 为**只读**。
- **2026-08-18（提案审核 4 处修订）** — 复核提案属实（规格 In 表、`_MLP(ld,·)`、`imagine(goal_rel0=)`、`LatentActorDeployPolicy.act`、`loop.episodes` 长度 1、cos −0.88 出处均逐字对上）后改 4 处：**(1)**「数学上不可达」→「**不可稳健达成**」（依据：实测 `goal_body0≈[+30,0,0.85]` 偏前，goal-blind 常量前飞能得正 progress，故非数学不可能；同时把「固定前向偏置冒充定向」列入明确不做，堵凑过通道）；**(2)** 新增 **§A 签字前置只读诊断**为第一件事，理由：根因只解释首动作**恒定**、不解释方向为**负**（训练/部署 goal 同向偏前），已静态排除 `advance_goal_rel_body` 符号（`goal_features.py:71` 为 `g-disp`，正确）与 `maneuver=‖a‖`（与方向无关），余下嫌疑为 RH `progress` 与 `p_coll`；A.2 判据先写死；**(3)** §4 补 ① 再 gate `n≥8`（M5d ① 实跑 n=7，`v4_metrics.py:46` 下非全权）与「训练 goal 同分布、不同实例」；**(4)** §5 增 **V3 范围裁定**签字行（改 actor/critic MLP 输入是否触及「不给 RSSM 加 goal 张量」；提案方读法为不触及）。§2 第三行补 artifact/log/script 出处。未改代码 / `δ_p` / yaml。
- **2026-08-17(goal+z0)** — M5d done: goal inject + headon RGB z0 AC 300 iters (`v4_ac_ckpt_20260817_wm_rh_goal_rgb`); re-gate `v4_gate_r60_20260817_wm_rh_goal`: ① FAIL (−8.74), ④ PASS; merge FAIL; yaml 未翻.

---

## 4. Latest gate numbers (goal+RGB z0, 2026-08-17)

| Signal | Criterion | Result | Numbers |
|---|---|---|---|
| **V4-①** | actor ≥ heur × 1.10 | ❌ | actor_mean **−8.74** vs heur **8.42** (target **9.26**); n=7 |
| **V4-④** | v4_hard ≤ v1_hard | ✅ | v4_hard **0.000** vs v1 **0.429** (remeasured same starts) |
| **Merge** | both pass | ❌ | `ok=false` `{1: false, 4: true}` |

Artifacts: `experiments/aerial/rl/artifacts/v4_gate_r60_20260817_wm_rh_goal/v4_gate_r60_20260816.json`

### Prior (reward-head WM, 2026-08-16 — superseded)

| Signal | Criterion | Result | Numbers |
|---|---|---|---|
| **V4-①** | actor ≥ heur × 1.10 | ❌ | actor_mean **−3.17** vs heur **7.44** (target **8.18**); n=5 |
| **V4-④** | v4_hard ≤ v1_hard | ✅ | v4_hard **0.143** vs v1 **0.25** (remeasured same starts) |
| **Merge** | both pass | ❌ | `ok=false` `{1: false, 4: true}` |

Artifacts: `experiments/aerial/rl/artifacts/v4_gate_r60_20260816_wm_rh/v4_gate_r60_20260816.json`

### Prior (encode-train, legacy RH skipped — superseded)
| **V4-①** | ❌ | actor_mean **−68.88** vs heur **10.66** |
| **V4-④** | ❌ | v4_hard **0.143** vs v1 **0.00** |

Artifacts: `experiments/aerial/rl/artifacts/v4_gate_r60_20260816_wm/v4_gate_r60_20260816.json`
