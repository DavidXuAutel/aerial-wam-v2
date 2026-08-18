# V4-① 结构性不可达：规格修订待签字

> **状态**：**待签字**（2026-08-18）。文书先落地；**未**改代码 / frozen ① 阈值 / yaml。  
> **先例**：2026-08-11 ④ — shield 触发与 1.5 m 度量对齐使 ④ **结构性不可过** → **修订规格（被测系统）**，不继续调参、不降阈值。  
> **本提案同类**：goal-blind `π(a|z)` 在 goal-directed ① 上对 heuristic **不可稳健达成** → 修订 Actor/Critic **In 表**，**不**降 `δ_p=0.10`，**不**加长训当前 π。  
> **签字前置**：§A **已跑** → A.2 = **`(b)>(c)`**（碰撞项已排除）。§A.3 **已跑** → 字面 `b3_le_a`，但 **该判定作废**。§A.4 **已跑（seed=0）** → **`fwdmax_ge_pi`**（夹后最大前飞 λG0 47.64 ≥ π_clipped 18.25）。⚠️ **「§4 充分」仍不成立**，**「先修 RH」也无依据** —— 倒挂来自无界动作通道。下一件 = **动作空间一致性裁定**（是否本周期在 `imagine()` 落 clip）。

---

## 0. 正交声明

| 轴 | 是什么 | 不是什么 |
|---|---|---|
| **本缺口** | 规格规定策略看不见 goal + 训练塌成单 goal → ① 不可**稳健**达成 | 想象 horizon / z0 RGB 域差的「再调一轮」 |
| **想象目标方向性**（§A / A.3 / A.4） | **可实现集合内** RH 方向偏好正确。A.4 seed=0：最大前飞 λG0 **47.64 ≥** π_clipped **18.25**（`fwdmax_ge_pi`）；无 seed 口径前飞 49.65 vs 后退 15.99（3.1×）。π 只靠**跑出可实现集合** 才赢 | 不是本提案要改的 In 表；**确诊不是** RH 案；下一件 = 动作空间一致性裁定 |
| **动作空间一致性**（§A.4，**新**） | `imagine()` 不夹动作；部署 `collector.py:167`/`airsim_env.py:170` 夹到 `body_delta_limits(0.2)`=[1.0,0.4,0.4,0.314] | 不是阈值、不是关罩；是把既有红线「训练路径与部署一致」落到**动作轴** |
| **n re-freeze** | 合法性（评测 n） | 不改变 π 无 goal 的结构 |
| **V1-① 功效条款②③** | 碰撞率统计功效 | 与本条无关 |

**禁止的下一步**：在现 In 表下 `longer train`。预测方向与 M5c→M5d 相同：**更差**。

---

## A. 签字前置只读诊断（**第一件要做的事**）

**为什么必须先做**：§1–§2 的机制解释了首动作**恒定**（对 goal 不敏感），但**没有**解释方向为**负**。训练 mock goal `start→[30,0,5]` 与部署实测 `goal_body0 ≈ [+30, 0, 0.85]` **同向偏前**——「把那一个 goal 的动作烙进 `π(z)`」应预测 cos **正**，实测却是饱和后退 `[-1, -0.4, -0.4]`。若真因在**想象目标本身偏好后退**，改 In 表 + 多样 goal **不会**修好，而已付出「规格修订 + H100 重训 + 一轮 gate」。

**只读**：不写 ckpt、不改 yaml、不改规格、不训练、不翻 `enable_policy_update`。

### A.0 已静态排除（本次核过，无需再跑）

| 嫌疑 | 结论 |
|---|---|
| `advance_goal_rel_body` 符号 | **正确**：`g[:3] = g[:3] - disp`（`goal_features.py:71`）→ 前向动作**减少**剩余距离。不是符号 bug |
| `maneuver` 惩罚 | `maneuver = ‖a‖`（`imagination.py`）→ 与**方向无关**，不能产生方向性偏好 |

⇒ 想象里唯一能产生**方向性**偏好的项只剩 `out.progress`（学习到的 RH 输出）与 `out.p_coll`。

### A.1 想象回报逐项分解（要跑）

ckpt：`v4_ac_ckpt_20260817_wm_rh_goal_rgb/v4_ac_latest.pt` + RH WM `wm_step_1000.pt`。在 ① 同源 headon z0 上调 `imagine(..., horizon=15, goal_rel0=<实测 body-frame goal>)`，三臂各报逐项和：

| 臂 | 动作 |
|---|---|
| (a) π 自身 | 训练后 actor 的 `act_latent(z)` |
| (b) 前飞常量 | `[+1, 0, 0, 0]` |
| (c) 后退常量 | `[-1, 0, 0, 0]` |

**必报**：`Σ progress 项` · `Σ p_coll 项` · `Σ maneuver 项` · `Σ reward` · λ-return（λ=0.95, γ=0.997）。

### A.2 判据（**先写死**，避免事后解释）

| 观测 | 判定 | 处置 |
|---|---|---|
| (c) λ-return **≥** (b)，差额主要来自 **`p_coll` 项** | 想象内 **①/④ 权衡被碰撞项主导**——后退即想象最优。这同时解释「④ PASS 与 ① −8.74 并存」 | §4 In 表修订**必要但不充分**：**先**另开 reward 配平案，否则重训必复现负 ① |
| (c) ≥ (b)，差额主要来自 **`progress` 项** | RH 的 progress 对方向学错 | 先修 RH（另案），再执行 §4 |
| (b) **>** (c) | 想象目标方向无误；负 ① 来自部署端（单 goal 烙印 + z0 域差） | §4 **可直接执行**，本提案充分 |

三种结局都**不**降 `δ_p=0.10`、都**不**翻 yaml。

> ⚠️ **第三行的处置已被 §A.3 取代**（2026-08-18）。上表为**事前**判据，原文保留以存审计链，**不**事后改写；但它只比较两个单位幅度常量，探测不到幅度通道，故 `(b)>(c)` **不**足以判「本提案充分」。以 **§A.3** 为准。

### A.2 实测（2026-08-18）与判据的洞

数字出处：[`V4_SIGNAL1_SA_DIAG_STATUS.md`](V4_SIGNAL1_SA_DIAG_STATUS.md)。

| 臂 | Σprogress | Σp_coll | Σmaneuver | λG0 |
|---|---|---|---|---|
| (a) π | **+142.23** | −0.006 | −2.47 | **+103.63** |
| (b) 前飞 `[+1,0,0,0]` | +65.72 | −0.006 | −0.15 | +49.65 |
| (c) 后退 `[-1,0,0,0]` | +9.51 | −0.006 | −0.15 | +15.99 |

> **数字口径**（2026-08-18 复核）：以上为 A.3 同一次跑（脚本 `2afcb33`）的 A.2 表，**已取代**首跑（`14d0f06`）的 143.42 / 61.50 / 9.32 与 λG0 104.72 / 47.02 / 15.90。两次同 ckpt、同 z0、同 H **结果不同**（前飞 λG0 47.02→49.65，+5.6%；‖a0‖ 3.36→3.59）——脚本**当时无 seed**，RSSM 采样使每次跑带 ~6% 量级噪声。判定符号安全（A.3 差额 43.8 ≫ 噪声），但**比值不得报到两位有效数字**。`--seed` 已于本次补上。

A.2 **字面判定 `b_gt_c` 成立**：`p_coll` 通道排除（差 ≈0）；单位幅度下 RH **认方向**（前 65.7 vs 后 9.5，6.9×）。

> **`p_coll ≈ 6e-4` 横跨所有臂**这件事同时是个**坏消息**，不只是「碰撞项已排除」：头对头起点、1 m/步、15 步撞墙，碰撞头输出仍平到 6e-4 ⇒ **想象里 `p_coll` 通道基本是死的**，④ 的想象刹车同样无信号。单列另案，不由本提案处置。

**但 A.2 判据本身有洞，不足以支持「§4 充分」**：三行判据只比较 (b) 与 (c) 两个**单位幅度**常量，**从未把任何一臂与 π 自己比**，因此结构上探测不到**幅度通道**。而第一行暴露的正是幅度通道：

| | 想象 λG0 | 真实 ① |
|---|---|---|
| (a) π | **+104.72**（最高） | **−8.74**（最低） |
| (b) 前飞 / heuristic | +47.02 | **+8.42** |

**想象把 π 排在前飞的 2.1 倍之上，现实把它排在 heuristic 之下** —— 排序倒挂就是想象目标被薅（命门 A）的直接证据。机制是幅度而非碰撞项：π 的 `a0` 模长 ≈ **3.59**，幅度换来 Σprogress 2.2×；代价那边 Σmaneuver 仅从 −0.15 涨到 −2.47 —— **progress +76.5 对惩罚 +2.32，约 30× 量级欠罚**（`w_progress:w_maneuver = 1.0:0.01`，即结构上 **100:1**）。想象最优解因此是「把 ‖a‖ 顶大」，方向退化为次要项；顶大的那个向量在真机被夹回后只剩方向，而方向指向后方，① 即塌。

> ⚠️ **更正（2026-08-18 复核）**：上一版本此处写「`action_scale=3` 饱和」，**错**。`_MLP` 末层是裸 `nn.Linear`，`mean = actor(z) * action_scale`（`actor_critic.py:200`）—— `action_scale` 是**增益不是界**，`v4:` 块也未暴露它、`from_config` 亦不读取。**动作幅度无上界**，3.59 不是饱和值，而且 π 的**整条轨迹**平均 ‖a[:3]‖ **≈16.5**（由 Σmaneuver 2.47÷0.01=Σ‖a‖=247÷15 反推，并由 ‖goal_rel‖ 30→253.9 需 ≈14.9/步 独立印证），远大于 a0 的 3.59。这一更正是 §A.3 作废的**第一个**理由。

**§A STATUS 残差段的处置更正**：排除 `p_coll` 配平案 ✅ 成立；但「此残差可在 In 表落地后的重训里用多样 goal 消化」**无依据** —— 多样 goal 修的是**方向条件化**，不改变「回报随幅度涨、惩罚跟不上」。加 `goal_rel` 后 π 仍会顶满幅度，只是**可能**顶向前方。可能 ≠ 已验证。

**另三项未报**：
1. **`goal_rel` 被推 OOD**：`propagate_goal_rel=True` 且 `g ← g − a[:3]`，后退臂 15 步把 ‖goal_rel‖ 从 30 推到 ≈80（训练分布 ~30）→ (a)/(c) 的 progress 都是 OOD 查询，(c) 作为对照偏弱。
2. **(a) 的逐步动作 / `‖goal_rel‖` 轨迹未报**：若想象里 ‖goal_rel‖ 收到 ~0（以为到达），病灶在 **z 转移保真**而非 RH 标定，处置不同。
3. 小注：`goal_rel0` 只用 ep0 一个 `[+30, 0, 0.85]` 套在 8 个 z0 上。作为 probe 无问题，但**不能**读成 goal 分布覆盖。

### A.3 幅度匹配补跑（只读，同脚本第二遍）+ 判据（**先写死**）

`v4_imagine_return_decomp.py` 已追加匹配幅度臂与逐步轨迹（`--match-scale`，`0` = 自动取 π 实测 ‖a0[:3]‖）：

| 臂 | 动作 |
|---|---|
| (b3) 前飞@匹配幅度 | `[+3.36, 0, 0, 0]` |
| (c3) 后退@匹配幅度 | `[-3.36, 0, 0, 0]` |

五臂均报逐步 `progress_t` · `p_coll_t` · `‖a_t‖` · `‖goal_rel‖_t`。

| 观测 | 判定 | 处置 |
|---|---|---|
| **(b3) λG0 > (a)** | 匹配幅度下 RH 方向偏好**存活** ⇒ goal 条件化会把饱和动作掰向前方 | §4 **充分**；但幅度欠罚作为**已知 exploit 入账**，再 gate 强制报 ‖a‖ 分布 + 想象-真实回报相关性 |
| **(b3) ≤ (a)** | 匹配幅度下 RH 仍偏好 π 那个后向向量 | 落 A.2 第二支：**先修 RH（另案）**，再执行 §4 |
| (a) `‖goal_rel‖` 收到 ≤ `success_dist_m` | 想象以为已到达 → 病灶在 **z 转移保真** | 另案，不由本提案处置 |

命令（125，离线，无渲染器）：

```bash
source experiments/aerial/scripts/env_4090.sh && $PYTHON_BIN experiments/aerial/scripts/v4_imagine_return_decomp.py --repo ~/aerial-wam-v2 --dataset ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_headon_20260811 --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_20260817_wm_rh_goal_rgb/v4_ac_latest.pt --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_r60_rh_20260816/wm_step_1000.pt --match-scale 0 --out artifacts/v4_imagine_return_decomp_a3_20260818.json
```

> ⚠️ **上表处置已被 §A.4 取代**（2026-08-18 复核）。事前判据原文保留以存审计链，**不**事后改写。实测触发第二支 `b3_le_a`（59.85 ≤ 103.63），**但该臂无效**，故「先修 RH」**不成立**。三个理由见 §A.3 复核。

### A.3 复核（2026-08-18）：`b3_le_a` **作废**，洞仍在提出方（我）

**理由 1 — 幅度没匹配上（~4.6×）**：`match_scale` 取 `act0_norm3_mean`=3.591，只匹配**第 0 步**；π 整条轨迹平均 ‖a[:3]‖ **≈16.5**（两条独立算路互证，见上文更正框）。脚本其实已算 `act_norm3_mean` 并写进 JSON（`v4_imagine_return_decomp.py:331`），但 auto 分支取的是 `act0_`（`:366`）——**这是 §A.3 设计错误，责任在提案方**。

**理由 2 — 五条臂全在物理不可实现区**：`env.step_hz=5.0`（`configs/aerial_rl.yaml:20`）⇒ 部署每步硬夹 `body_delta_limits(0.2)` = **[1.0, 0.4, 0.4, 0.314]**（`env/action.py:57`），`collector.py:167` 与 `airsim_env.py:170` 都夹；**`imagine()` 一次都不夹**（`imagination.py:120-127`）。于是：

- (b) `[+1,0,0,0]` **恰好等于可实现的最大前飞步**。它拿 λG0 **49.65**；可实现最大后退 (c) 只有 **15.99** ⇒ **在可实现集合内 RH 方向偏好是对的（3.1×）**。
- π 的 103.63 只来自**跑出可实现集合** 3.6×（a0）→16×（轨迹均值）。在 `w_progress:w_maneuver = 100:1` 下「把 ‖a‖ 顶大净赚」是**恒真**的，不需要任何方向判断。
- (b3)@3.591 在现实里被夹回 **就是 (b)**（已用真 `clip_body_delta` 验证）。所以 A.3 测的是「无界打赢有界」，**这是权重的推论，不是 RH 的方向偏好**。
- 同理 RH 训练时的位移是 `body_vel × reward_dt=0.2` ≤ ~1 m/步（`configs/aerial_rl.yaml:74-76`），想象却拿 3.6–16 m 去查它 ⇒ **幅度轴 OOD**，与 ‖goal_rel‖ 8.5× 是**两条独立** OOD。

**理由 3 — (b3) 还被额外扣两刀**：15×3.591 = 53.87 > 30 ⇒ 第 ~8.4 步**冲过目标**，末态 30−53.87 → ‖·‖ = **23.87**（实测 23.9 ✓；(c3) 30+53.87 = 83.87 vs 实测 83.9 ✓ —— 两个精确对上反向验证了 `_goal_dist_traj`）。故 STATUS 里「23.9（靠近）」是**读反**：是冲过目标 23.9 m，后半程 goal 在身后，progress 自然掉。且 `_apply_a3` 只对 (a) 查 arrival（`:134`），**没查 (b3)** —— (b3) 想象里很可能到达过（min ≤ `success_dist_m=3.0`）又飞走。

### A.4 可实现集合内的方向判定（只读）+ 判据（**先写死**）

`v4_imagine_return_decomp.py` 已追加 `--clip-actions`：用**部署同一函数** `clip_body_delta(a, body_delta_limits(1/step_hz))` 包住**策略**（`imagine()` 本体不动，故仍是只读诊断），使三条臂全部落在可实现集合内；`--seed` 同时补上；`--match-basis {a0,traj}` 保留 `a0` 为默认以复现 A.3，新论断须用 `traj`。夹动作后 (b3)/(c3) 退化为 (b)/(c)，故第二遍自动跳过。

| 观测 | 判定 | 处置 |
|---|---|---|
| **λG0(b) ≥ λG0(a)**（夹后） | 倒挂**全部**来自无界动作通道，与 RH 方向无关 | 在 `imagine()` 里落**与部署同一的 clip**（一致性红线，非阈值改动），重跑 §A/§A.3，重新推 ① 根因。**不是** RH 案；`b3_le_a` 作废 |
| **λG0(a) > λG0(b)**（夹后） | 幅度可执行时 RH **仍**偏好 π 的方向 | A.2 第二支**确诊**：先修 RH（另案），再执行 §4 |
| 任一臂 `goal_dist_min ≤ success_dist_m` | 该臂想象里到达过（(b3) 的过冲即此类） | 记录，不单独触发处置 |

两支都**不**降 `δ_p=0.10`、**不**动 `n=8`、**不**翻 yaml。

> **实测（2026-08-18，seed=0，`700dbe6`）**：触发第一支 **`fwdmax_ge_pi`**。λG0 (b)=**47.64** ≥ (a)=**18.25**；(c)=15.87。π 夹后仍后向但落在 limits 内。JSON：`artifacts/v4_imagine_return_decomp_a4_20260818.json`。配套 traj 匹配：`match_scale=15.59`，(b3)@15.59 λG0 18.21 / 过冲 30→203.9；`..._a3traj_20260818.json`。事前表原文保留。

命令（125，离线，无渲染器）：

```bash
source experiments/aerial/scripts/env_4090.sh && $PYTHON_BIN experiments/aerial/scripts/v4_imagine_return_decomp.py --repo ~/aerial-wam-v2 --dataset ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_headon_20260811 --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_20260817_wm_rh_goal_rgb/v4_ac_latest.pt --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_r60_rh_20260816/wm_step_1000.pt --clip-actions --seed 0 --out artifacts/v4_imagine_return_decomp_a4_20260818.json
```

配套（同 seed 的**未夹**基线，供 `clip_shrink_ratio` 与 traj 匹配对照）：

```bash
source experiments/aerial/scripts/env_4090.sh && $PYTHON_BIN experiments/aerial/scripts/v4_imagine_return_decomp.py --repo ~/aerial-wam-v2 --dataset ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_headon_20260811 --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_20260817_wm_rh_goal_rgb/v4_ac_latest.pt --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_r60_rh_20260816/wm_step_1000.pt --match-basis traj --seed 0 --out artifacts/v4_imagine_return_decomp_a3traj_20260818.json
```

---

## 1. 两个叠加缺陷（已核）

### (1) 规格本身：actor/critic 看不见 goal

V4-MVP 规格 §In（`2026-08-16-v4-mvp-design.md`）原文：

| Actor | `act_latent(z)`（或 `h‖z`）；输出 4-D 运动学动作 |
| Critic | `V(z)` on latent |

实现忠实：`_MLP(ld, ad, hd)` / `_MLP(ld, 1, hd)`，输入维 = `latent_dim`。  
`goal_rel` 只经 `attach_goal` / `imagine(..., goal_rel0=)` 进 **reward**，从不进策略输入。  
`LatentActorDeployPolicy.act` = `encode(RGB+proprio4)` → `act_latent(z)`。

这不是实现 drift，是 **照规格做对了**。

### (2) 训练只见过一个 goal

`train_v4_ac.py` mock 注入：

```python
loop.episodes = [_mock_goal_episode()]   # start→[30,0,5]，长度 1
```

M5d 权威 300 iter（STATUS：`_mock_goal_episode`）想象全部针对这一对。Phase 2 headon `--dataset --skip-collect` 是 **2-iter probe**，不是多样 goal 的 300 iter 重训。

叠起来：学到的是「对这一个 goal 的固定行为」烙进 `π(z)`。部署换 annotation/obstacle-facing goal **必然错**。

---

## 2. 四轮 gate 被同一假设解释

| 轨 | train `goal_rel` | reward 里的 goal | 部署 ① actor_mean |
|---|---|---|---|
| M5c RH-only | ≈0 | 几乎没有 → 弱定向 `π(z)` | **−3.17** |
| M5d goal+z0 | 3.05 | 强 → 把**那一个**固定方向烙进 `π(z)` | **−8.74**（更差） |
| 125 逐 ep 诊 | — | — | 首动作 cos(goal_body) **≈−0.88** vs heur **≈+0.99** |

第三行出处：[`V4_PROGRESS_DIAG_125_STATUS.md`](V4_PROGRESS_DIAG_125_STATUS.md) — script `experiments/aerial/scripts/v4_progress_diag.py`（`37e5cb9`）· JSON `artifacts/v4_progress_diag_20260817.json` · log `logs/v4_progress_diag_20260817.log` · n=7 scored（1 spawn drop）。

**该假设解释到哪一步（不夸大）**：解释了首动作**恒定**、对 goal 不敏感，以及 M5c→M5d 幅度**放大**（弱定向 → 强行烙一个固定方向）。**未**解释方向为**负**：训练 goal 与部署 goal 同向偏前，烙印假设本应预测 cos 正。方向的成因待 **§A** 判定。

---

## 3. 为什么现规格下 ① 不可**稳健**达成

①：`mean_progress_actor ≥ mean_progress_heuristic × 1.10`。  
progress = 朝 **goal** 的位移。heuristic 吃 `goal_getter`（稳定 +7~+11）。

goal-blind `π(a|z)` 要**按 goal 调整方向**，唯一途径是 **goal 泄漏进 z**。z = RGB(+深度头) RSSM latent；3-D 航点不在图像里，**无泄漏通道**。故现 In 表下 π 只能输出与 goal 无关的行为。

**精确边界（不说过头）**：这**不是**「数学上恒为负」。obstacle-facing 起点下 goal 系统性偏前（实测 `goal_body0 ≈ [+30, 0, 0.85]`），一个 goal-blind 的**常量前飞**策略能拿到正 progress，甚至可能逼近 heuristic。所以准确表述是 ① **不可稳健达成**：任何过门只能来自「评测 goal 恰好与烙印方向同向」的偶然，换 annotation/goal 几何即失效。**该偶然属凑过，不接受**（见 §4 明确不做）。

与 ④「触发对齐 1.5 m → 结构性不可过」同类：继续调 shield / 继续训 AC **都不是**处置。

---

## 4. 待签字修订（推荐）

**改被测系统接口，不改 ① 数值。**

| 项 | 现状 | 修订草案 |
|---|---|---|
| Actor In | `act_latent(z)` | `act_latent(z, goal_rel)` 或 `π([z ‖ goal_rel])`；deploy 必须喂 **同一** body-frame `goal_rel` |
| Critic In | `V(z)` | `V(z, goal_rel)`（剩余距离进 value） |
| ① 阈值 | `δ_p=0.10` vs Heuristic | **不动** |
| 权威 AC 训 | 允许 length-1 mock | mock 单 goal **仅诊断**；权威训须 **多样 goal**，与 ① 评测**同分布、不同实例**（禁止拿评测 accepted start 当训练集）（签字填最少 unique goals / episodes） |
| ① 再 gate 的 n | M5d ① 实跑 **n=7** | accepted **≥ 8**（frozen §4.1 re-freeze 2026-08-17；`v4_metrics.py:46` 下 n<8 → `authoritative=false`）。因 spawn drop，请起点须**多请**以确保落到 8 |
| yaml | `enable_policy_update=false` | merge 前仍 false |

**明确不做**：降 1.10；把 ① 改成 N/A 冒充 PASS；在现 π 上加长训；为过门关掉 shield；**以固定前向偏置（goal-blind 常量）冒充定向能力**（§3 精确边界）。

**签字后才动代码**（当前 **A.3 作废、A.4 = `fwdmax_ge_pi`** → In 表**不签充分**；也**不**开 RH 案）：`actor_critic.py` + `imagination.py` `act_latent` + deploy + 单测 + H100 重训 + 125 ① 再 gate（n≥8）。

**独立于本提案、可先落的一致性修**（不属 In 表、不需 ① 判定）：`imagine()` 用 `clip_body_delta(a, body_delta_limits(1/step_hz))` 夹动作，与 `collector.py:167` / `airsim_env.py:170` 同函数同上限。理由是既有红线「训练路径与 V1 部署一致」在**动作轴**上目前不成立（部署夹 [1.0,0.4,0.4,0.314]，想象不夹；A.4 夹后 π ‖a[:3]‖=1.15，未夹轨迹 15.59，shrink ≈13.6×）。这是**修不一致**，不是调阈值、不是关罩、不是为凑过。**§A.4 已确认量级（`fwdmax_ge_pi`）**；是否本周期落 → 签字栏裁定。未签前不改 `imagination.py`。

---

## 5. 签字清单

- [x] **先做 §A 只读诊断**；A.2 = **`(b)>(c)`** → **碰撞项通道已排除**（附带发现：`p_coll≈6e-4` 平到底，碰撞头在想象里近乎死，另案）。
- [x] §A.3 已跑，字面 `b3_le_a`（λG0 π 103.63 vs 前飞@3.59 59.85）；**复核后作废**：幅度欠匹配 ~4.6×、五臂全在不可实现区、(b3) 过冲扣分。数字：[`V4_SIGNAL1_SA_DIAG_STATUS.md`](V4_SIGNAL1_SA_DIAG_STATUS.md)
- [x] ⚠️ **「§4 充分」不成立**，**且「先修 RH」无依据** —— §A.4（只读，`--clip-actions`，seed=0）判定 = **`fwdmax_ge_pi`**（λG0 47.64 ≥ 18.25）→ 倒挂来自无界动作通道；先落动作空间一致性并重跑 §A。**不是** RH 案。数字：[`V4_SIGNAL1_SA_DIAG_STATUS.md`](V4_SIGNAL1_SA_DIAG_STATUS.md) A.4 节
- [ ] **动作空间一致性裁定**：`imagine()` 是否本周期就落 `clip_body_delta`？裁定 = ______（A.4 = `fwdmax_ge_pi` 后填；提案方读法：属「训练=部署」既有红线的修不一致，不属新增功能）
- [ ] 接受 §1–§3 为**已发生结构事实**（写入 `V4_GATE_STATUS`；M5c/M5d 仍诚实 FAIL）
- [ ] 接受 §4：改 In 表，**不**改 `δ_p`
- [ ] **V3 范围裁定**：为 actor/critic MLP 增加 `goal_rel` 输入是否触及「goal-input 属 V3，本周期不给 RSSM 加 goal 张量输入」？裁定 = ______（不触及 / 触及需另开 V3 案）。*提案方读法：不触及——RSSM 完全不动，只加策略/价值 MLP 的输入维。*
- [ ] ① 再 gate 的 accepted n ≥ **8** 已确认（M5d 的 n=7 为非全权）
- [ ] 权威训最少 unique goals = ______（建议 ≫ 1，且与 ① 评测同分布、不同实例）
- [ ] 在签字前 **禁止** 现 ckpt 加长训 / 翻 yaml

**签字栏**：日期 ______ · A.3 判定 **`b3_le_a`（已测，已作废）** · **A.4 判定 `fwdmax_ge_pi`（已测）** · 动作空间一致性裁定 ______ · V3 裁定 ______ · unique-goals 下限 ______
