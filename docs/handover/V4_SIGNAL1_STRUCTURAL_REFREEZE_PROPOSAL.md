# V4-① 结构性不可达：规格修订待签字

> **状态**：**待签字**（2026-08-18）。文书先落地；**未**改代码 / frozen ① 阈值 / yaml。  
> **先例**：2026-08-11 ④ — shield 触发与 1.5 m 度量对齐使 ④ **结构性不可过** → **修订规格（被测系统）**，不继续调参、不降阈值。  
> **本提案同类**：goal-blind `π(a|z)` 在 goal-directed ① 上对 heuristic **不可稳健达成** → 修订 Actor/Critic **In 表**，**不**降 `δ_p=0.10`，**不**加长训当前 π。  
> **签字前置**：§A **已跑**（2026-08-18）→ A.2 = **`(b)>(c)`**（**碰撞项通道已排除**）。⚠️ **「§4 充分」尚不成立**（A.2 探测不到幅度通道；π 想象/真实**排序倒挂**）。下一件 = **§A.3 幅度匹配补跑**。

---

## 0. 正交声明

| 轴 | 是什么 | 不是什么 |
|---|---|---|
| **本缺口** | 规格规定策略看不见 goal + 训练塌成单 goal → ① 不可**稳健**达成 | 想象 horizon / z0 RGB 域差的「再调一轮」 |
| **想象目标方向性**（§A） | 单位幅度下前飞优于后退；**碰撞项通道已排除**。**幅度通道未排除**（待 §A.3） | 不是本提案要改的 In 表；A.3 决定 In 表修订**是否充分** |
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
| (a) π | **+143.42** | −0.005 | −2.47 | **+104.72** |
| (b) 前飞 `[+1,0,0,0]` | +61.50 | −0.005 | −0.15 | +47.02 |
| (c) 后退 `[-1,0,0,0]` | +9.32 | −0.005 | −0.15 | +15.90 |

A.2 **字面判定 `b_gt_c` 成立**：`p_coll` 通道排除（差 ≈0）；单位幅度下 RH **认方向**（前 61.5 vs 后 9.3，6.6×）。

**但 A.2 判据本身有洞，不足以支持「§4 充分」**：三行判据只比较 (b) 与 (c) 两个**单位幅度**常量，**从未把任何一臂与 π 自己比**，因此结构上探测不到**幅度通道**。而第一行暴露的正是幅度通道：

| | 想象 λG0 | 真实 ① |
|---|---|---|
| (a) π | **+104.72**（最高） | **−8.74**（最低） |
| (b) 前飞 / heuristic | +47.02 | **+8.42** |

**想象把 π 排在前飞的 2.2 倍之上，现实把它排在 heuristic 之下** —— 排序倒挂就是想象目标被薅（命门 A）的直接证据。机制是幅度而非碰撞项：π 的 `a0` 模长 ≈ **3.36**（`action_scale=3` 饱和），幅度 3.4× 换来 Σprogress 2.3×；代价那边 Σmaneuver 仅从 −0.15 涨到 −2.47 —— **progress +81.92 对惩罚 +2.32，约 35× 欠罚**。想象最优解因此是「顶满 ‖a‖」，方向退化为次要项；顶满的那个向量在真机指向后方，① 即塌。

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

**签字后才动代码**（且须 **§A.3** 判定为「§4 充分」或已先落 RH 另案）：`actor_critic.py` + `imagination.py` `act_latent` + deploy + 单测 + H100 重训 + 125 ① 再 gate（n≥8）。

---

## 5. 签字清单

- [x] **先做 §A 只读诊断**（第一件事）；A.2 判定 = **`(b)>(c)`**（λG0 47.02 vs 15.90；差额 = progress，p_coll≈0）→ **碰撞项通道已排除**。数字：[`V4_SIGNAL1_SA_DIAG_STATUS.md`](V4_SIGNAL1_SA_DIAG_STATUS.md)
- [ ] ⚠️ **「§4 充分」尚不成立** —— A.2 判据只比两个单位幅度常量，探测不到**幅度通道**；实测 π 想象 λG0 **+104.72** 却真实 ① **−8.74**（对前飞 +47.02 / heur +8.42）＝**排序倒挂**，约 **35× 幅度欠罚**。须先跑 **§A.3 幅度匹配臂**。A.3 判定 = ______（`b3_gt_a` → §4 充分 · `b3_le_a` → 先修 RH）
- [ ] 接受 §1–§3 为**已发生结构事实**（写入 `V4_GATE_STATUS`；M5c/M5d 仍诚实 FAIL）
- [ ] 接受 §4：改 In 表，**不**改 `δ_p`
- [ ] **V3 范围裁定**：为 actor/critic MLP 增加 `goal_rel` 输入是否触及「goal-input 属 V3，本周期不给 RSSM 加 goal 张量输入」？裁定 = ______（不触及 / 触及需另开 V3 案）。*提案方读法：不触及——RSSM 完全不动，只加策略/价值 MLP 的输入维。*
- [ ] ① 再 gate 的 accepted n ≥ **8** 已确认（M5d 的 n=7 为非全权）
- [ ] 权威训最少 unique goals = ______（建议 ≫ 1，且与 ① 评测同分布、不同实例）
- [ ] 在签字前 **禁止** 现 ckpt 加长训 / 翻 yaml

**签字栏**：日期 ______ · A.3 判定 ______ · V3 裁定 ______ · unique-goals 下限 ______
