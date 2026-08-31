# Phase-2 主航道回锚声明（2026-08-30）

> **性质**：主航道纠偏（**先声明再动手**）。  
> **状态**：125 对照评测 **已完成**（2026-08-30 01:48 UTC+8）。  
> **上游规格**：[`2026-08-28-hierarchical-long-horizon-wam-design.md`](../superpowers/specs/2026-08-28-hierarchical-long-horizon-wam-design.md) §1.2 **零模型重训**。  
> **执行**：[`WAM_PHASE2_REANCHOR_STEPE_125_PROMPT.md`](WAM_PHASE2_REANCHOR_STEPE_125_PROMPT.md)。

---

## 0. 判读（诚实）

原设计 = **合法折线 + AdaptiveSubgoal（20–55 m 胡萝卜）+ 阶段 1 `step_e` 局部 WAM**，不换 π。

实际分叉：

| 步 | 后果 |
|----|------|
| F9 默认改 `g_norm` | `step_e` 米制 4 维语义被破坏 |
| R1/R2 从零重训 | 另训新 π；R1 SR=0%；R2 想象 return 回正但闭环 IR≈1 / prog≈0 |
| 动态罩 / `w_coll` 拧 | **旁支**；R2 评测栈上甚至未部署动态罩 |

**结论**：能力退化主因是 **离开基线接口去重训**，不是「分段方案本身失败」。

---

## 1. 冻结（本声明）

| 项 | 决策 |
|----|------|
| **主航道默认** | `v4_ac_ckpt_step_e_20260828` + **`goal_feat_mode=meter`** + AdaptiveSubgoal + 现 WM/深度/ThreeZone |
| **g_norm / R1/R2 ckpt** | **降级为 ablation**；未过对照门前不得当默认 deploy |
| **yaml `w_collision`** | **保持 10.0**；不因 R2 静默改默认 |
| **动态 `v_ref` 罩** | 另线；本对照 **不依赖**；未合入 125 前不得当 IR 归因 |
| **重训** | 本回合 **禁止** 新开 AC/H100 训 |

代码落地（Mac）：`ActorCriticConfig.goal_feat_mode` ∈ `{meter,g_norm}`；缺省/`step_e` 加载 → **meter**；`wam_phase2_long_eval --goal-feat-mode`。

---

## 2. 对照评测合同（125）

与 R1 协议可比：

* 16 路 `seen_airsim16_long_routes.json` · cruise=**10** · planner H=5 · max_steps=1000  
* actor=`step_e` · `--goal-feat-mode meter`  
* 门限：SR≥80% · SCR≤10% · SPL≥70% · ρ̄≥90% · IR≤25%  
* 产物：`artifacts/wam_phase2_reanchor_stepe_result_20260830.json`  
* DECLARE：`WAM_PHASE2_REANCHOR_STEPE_DECLARE_20260830.md`（评完写）

对照读法：

* 若回锚 **明显高于** R1/R2 → 确认主航道应锁 `step_e`+meter；F9 重训路径暂停。  
* 若仍远差于阶段 1 短廊 93% → 问题在 **Phase-2 路由/Subgoal/接线**，下一刀诊断那些，**仍不**默认开 g_norm 重训。

---

## 3. 红线

* 禁止用 R2 ckpt 冒充回锚  
* 禁止关罩 / Docking / 放宽 3 m  
* 禁止评测未出就改默认 yaml 或 promote g_norm

---

## 4. 评测结果（125 · 2026-08-30）

### 4.1 协议与前置

| 项 | 值 |
|----|-----|
| actor | `v4_ac_ckpt_step_e_20260828/v4_ac_latest.pt` |
| `goal_feat_mode` | **meter**（日志确认；ckpt 无字段 → 默认 meter） |
| `condition_on_goal` | **True** |
| WM | `wm_ckpt_d_full_20260828/wm_step_3500.pt` |
| 栈 | AdaptiveSubgoal → step_e π(meter) → ImaginationPlanner H=5 → ThreeZone |
| cruise / max_steps | 10.0 m/s · 1000 |
| 路由 | `artifacts/seen_airsim16_long_routes.json`（16 路） |
| 单测 | 15/15 pass（含 `test_feat_tensor_meter_mode_keeps_raw_metres`） |

**infra**：首次跑在 route 03 AirSim 空帧崩溃（`cv2.imdecode`）；`recover_renderer.sh` 后 **整轮重跑**（作废 partial log）。有效 run：PID 1550389，00:52–01:48。

### 4.2 16 路指标 vs 门限

| 指标 | 实测 | 门限 | 过门？ |
|------|------|------|--------|
| **SR** | **0.0%**（0/16） | ≥80% | ❌ |
| **SCR** | **12.5%**（2/16） | ≤10% | ❌ |
| **SPL** | **0.0%** | ≥70% | ❌ |
| **ρ̄** | **85.7%** | ≥90% | ❌ |
| **IR** | **17.7%** | ≤25% | ✅ |

**Verdict**：**FAIL**（诚实）

**产物**

| 文件 | 路径 |
|------|------|
| JSON | `artifacts/wam_phase2_reanchor_stepe_result_20260830.json` |
| 日志 | `artifacts/wam_phase2_reanchor_stepe_20260830.log` |

### 4.3 vs R1 / R2 对照

| 轮 | π | goal 语义 | SR | SCR | ρ̄ | IR | 主失败形态 |
|----|---|-----------|-----|-----|-----|-----|-----------|
| **R1** | g_norm 重训 | g_norm | 0% | 25% | 56.6% | 25% | F11 空转 / F12 / F9 语义错 |
| **R2** | g_norm 重训 w_coll=1 | g_norm | 0% | 6.2% | 13.5% | 98.7% | **F5** 罩全程钳住 |
| **回锚** | **step_e（零重训）** | **meter** | 0% | 12.5% | **85.7%** | **17.7%** | **F12** 系统性距目标 57–71 m |

**读法**：回锚 **远高于** R1/R2 的 ρ̄ 与 IR（IR 从 R2 的 99% 降至 18%），确认 **主航道应锁 step_e+meter**；F9 g_norm 重训路径继续 **ablation 冻结**。SR 仍 0% — 缺口在 **Phase-2 终段/subgoal 交接**（一致 ~60 m 短停），**非** π 权或 goal 特征尺度。

### 4.4 spawn_fail

| 项 | 值 |
|----|-----|
| `n_spawn_fail_f1` | **0** |

### 4.5 失败 episode — F1–F14 归类

> 16 条 **全部未到达**（3 m 球）。

| route_idx | base | d_min | prog | SCR | IR | 主因 | 次要 |
|-----------|------|-------|------|-----|-----|------|------|
| 0 | 5 | 64.7 m | 98% | | 6.5% | **F12** | — |
| 1 | 16 | 64.8 m | 100% | | 31.6% | **F12** | F11 |
| 2 | 7 | 69.8 m | 100% | | 3.1% | **F12** | — |
| 3 | 17 | 141.7 m | 0% | ✓ | 98.9% | **F1/F3** 首段 SCR | F5 |
| 4 | 10 | 71.3 m | 100% | | 5.9% | **F12** | — |
| 5 | 13 | 67.0 m | 100% | | 18.3% | **F12** | — |
| 6 | 1 | 64.2 m | 98% | | 4.6% | **F12** | — |
| 7 | 9 | 63.0 m | 82% | | 5.8% | **F12** | F4 |
| 8 | 18 | 68.5 m | 100% | | 23.5% | **F12** | — |
| 9 | 14 | 63.0 m | 100% | | 6.7% | **F12** | — |
| 10 | 4 | 59.1 m | 93% | | 3.1% | **F12** | — |
| 11 | 11 | 59.0 m | 100% | | 5.9% | **F12** | — |
| 12 | 15 | 57.1 m | 100% | | 9.7% | **F12** | — |
| 13 | 2 | 59.3 m | 97% | | 2.7% | **F12** | — |
| 14 | 0 | 56.7 m | 100% | | 6.9% | **F12** | — |
| 15 | 19 | 105.7 m | 2% | ✓ | 50.0% | **F1/F3** 2 step SCR | — |

| F 码 | 条数 | 说明 |
|------|------|------|
| **F12** | **14**（系统性） | 高 prog、低 IR，但 d_min 稳定在 **57–71 m** — 终段/subgoal 未送入 3 m 到达球 |
| **F1/F3** | 2 | r03/r15 起步即 SCR |
| **F11** | 1 | r01 prog=100% 仍距 64 m |
| **F5** | 1 | 仅 r03（SCR 伴生） |

### 4.6 纪律确认

本轮 **未**做：H100 重训、Docking、关罩、escape、放宽 3 m、改门限、用 R1/R2 g_norm ckpt 冒充回锚。

### 4.7 未签项与下一刀

| 未过门 | 主因 |
|--------|------|
| SR / SPL | 零到达 — **F12 终段短停 ~60 m** |
| SCR | r03/r15 硬撞（12.5%） |
| ρ̄ | 85.7% — 两 SCR + r07 82% prog 拉低均值 |

**下一刀（一句）**：诊断 **AdaptiveSubgoal 终段 carrot 距离 / re-anchor 触发 / 最后 subgoal→goal 切换** 为何一致停在 ~60 m；**不**默认开 g_norm 重训（回锚已证 meter+step_e 远优于 R1/R2）。

## 评测结果（2026-08-30 01:48 CST · 125）

| 项 | 值 |
|----|----|
| 协议 | `step_e` · `goal_feat_mode=meter` · cruise=10 · planner H=5 |
| ckpt | `v4_ac_ckpt_step_e_20260828/v4_ac_latest.pt` |
| **Verdict** | **FAIL** |
| SR / SPL | 0.0% / 0.0% |
| SCR | 12.5% |
| ρ̄ (Prog) | **85.7%** |
| IR | **17.7%** |
| 产物 | `artifacts/wam_phase2_reanchor_stepe_result_20260830.json` |

### vs R1 / R2

| | SR | Prog | IR | SCR | Verdict |
|--|----|------|----|-----|---------|
| R1 g_norm | 0% | ~0 | — | — | FAIL |
| R2 g_norm w_coll=1 | 0% | 13.5% | 98.7% | 6.2% | FAIL |
| **Re-anchor step_e+meter** | **0%** | **85.7%** | **17.7%** | **12.5%** | **FAIL** |

**读数**：回锚证明「不换基线权」可恢复走廊推进（Prog 大幅回升、IR 从≈1 降到 0.18）；门限仍卡在 **到点 SR=0**（多数路 `min_d≈57–70m` 未进到达球）与 SCR=12.5%。**禁止**因此再开 g_norm 重训；下一刀应查到达判据 / 末端对齐，而非特征尺度。
