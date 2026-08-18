# V4 Gate 状态活文档

> **用途**：V4-MVP merge 进度（镜像 V1 活文档）。  
> **设计**：[V4-MVP 规格](../superpowers/specs/2026-08-16-v4-mvp-design.md)（方案 1）。  
> **前置**：V1 merge PASS + `tau_predictor.kind=foe_calibrated`。

---

## 1. 一句话结论（2026-08-17）

**Goal+z0 track done — merge FAIL（① −8.74 / ④ PASS）** — ① **现规格下不可稳健达成**（不是差一点；措辞 2026-08-18 由「结构性不可达」收紧，见提案 §3 精确边界）。  
根因两叠加：(1) In 表规定 `act_latent(z)` / `V(z)`，goal 只进想象 reward；(2) 权威 300 iter 只有 `_mock_goal_episode()` 一对 start→goal。修好 conditioning（M5d）把**那一个**方向烙进 `π(z)`，① 从 −3.17 **退到** −8.74。逐 ep：首动作 cos≈−0.88 vs heur ≈+0.99。  
**未解释的部分（§A 已判定方向性）**：烙印解释首动作**恒定**。§A 三臂分解（2026-08-18）：常量前飞 λG0 **47.0** > 后退 **15.9**，差额来自 **progress**，p_coll≈0 → **不是**想象内碰撞项主导后退。见 [§A STATUS](V4_SIGNAL1_SA_DIAG_STATUS.md)。§4 In 表按 A.2 **充分**，仍待签字。  
**处置同类 08-11 ④**：修订 Actor/Critic In 表，**不**加长训、**不**降 `δ_p`。待签字：[V4_SIGNAL1_STRUCTURAL_REFREEZE_PROPOSAL](V4_SIGNAL1_STRUCTURAL_REFREEZE_PROPOSAL.md)。  
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
- **2026-08-18（§A DONE）** — 只读三臂 imagine：`(b)>(c)` λG0 47 vs 16，progress 主导，p_coll≈0。§4 充分。STATUS `V4_SIGNAL1_SA_DIAG_STATUS.md`。yaml 未翻。
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
