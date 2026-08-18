# V4-① 结构性不可达：规格修订待签字

> **状态**：**待签字**（2026-08-18）。文书先落地；**未**改代码 / frozen ① 阈值 / yaml。  
> **先例**：2026-08-11 ④ — shield 触发与 1.5 m 度量对齐使 ④ **结构性不可过** → **修订规格（被测系统）**，不继续调参、不降阈值。  
> **本提案同类**：goal-blind `π(a|z)` 在 goal-directed ① 上对 heuristic **结构性不可达** → 修订 Actor/Critic **In 表**，**不**降 `δ_p=0.10`，**不**加长训当前 π。

---

## 0. 正交声明

| 轴 | 是什么 | 不是什么 |
|---|---|---|
| **本缺口** | 规格规定策略看不见 goal + 训练塌成单 goal → ① 不可达 | 想象 horizon / RH / z0 RGB 域差的「再调一轮」 |
| **n re-freeze** | 合法性（评测 n） | 不改变 π 无 goal 的结构 |
| **V1-① 功效条款②③** | 碰撞率统计功效 | 与本条无关 |

**禁止的下一步**：在现 In 表下 `longer train`。预测方向与 M5c→M5d 相同：**更差**。

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

修好 conditioning 反而更差，是该假设的**预测方向**（强化了部署端错误信号），不是意外。

---

## 3. 为什么现规格下 ① 数学上不可达

①：`mean_progress_actor ≥ mean_progress_heuristic × 1.10`。  
progress = 朝 **goal** 的位移。heuristic 吃 `goal_getter`（稳定 +7~+11）。

goal-blind `π(a|z)` 要赢，唯一途径是 **goal 泄漏进 z**。z = RGB(+深度头) RSSM latent；3-D 航点不在图像里，**无泄漏通道**。故在现 In 表下 ① **不可达**。

与 ④「触发对齐 1.5 m → 结构性不可过」同类：继续调 shield / 继续训 AC **都不是**处置。

---

## 4. 待签字修订（推荐）

**改被测系统接口，不改 ① 数值。**

| 项 | 现状 | 修订草案 |
|---|---|---|
| Actor In | `act_latent(z)` | `act_latent(z, goal_rel)` 或 `π([z ‖ goal_rel])`；deploy 必须喂 **同一** body-frame `goal_rel` |
| Critic In | `V(z)` | `V(z, goal_rel)`（剩余距离进 value） |
| ① 阈值 | `δ_p=0.10` vs Heuristic | **不动** |
| 权威 AC 训 | 允许 length-1 mock | mock 单 goal **仅诊断**；权威训须 **多样 annotation/① 同源 goal**（签字填最少 unique goals / episodes） |
| yaml | `enable_policy_update=false` | merge 前仍 false |

**明确不做**：降 1.10；把 ① 改成 N/A 冒充 PASS；在现 π 上加长训；为过门关掉 shield。

**签字后才动代码**：`actor_critic.py` + `imagination.py` `act_latent` + deploy + 单测 + H100 重训 + 125 ① 再 gate。

---

## 5. 签字清单

- [ ] 接受 §1–§3 为**已发生结构事实**（写入 `V4_GATE_STATUS`；M5c/M5d 仍诚实 FAIL）
- [ ] 接受 §4：改 In 表，**不**改 `δ_p`
- [ ] 权威训最少 unique goals = ______（建议 ≥ ① 评测同源 annotation，且 ≫ 1）
- [ ] 在签字前 **禁止** 现 ckpt 加长训 / 翻 yaml

**签字栏**：日期 ______ · unique-goals 下限 ______
