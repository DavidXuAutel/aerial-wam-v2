# Phase-2 全签 DECLARE（125 · g_norm 重训 π → 16 路 mainline）

> **日期**：2026-08-29  
> **机器**：cursor-125（4090 / AirSim）+ H100（经 `ssh h100-25`）  
> **Agent workspace**：`/home/yao/workspaces/aerial-wam-v2-phase2`  
> **协议**：`wam_phase2_mainline_native_20260829_fullfix`  
> **Verdict**：**FAIL**（如实）

---

## 1. H100 训程

| 项 | 值 |
|----|-----|
| 命令 | `python -m experiments.aerial.rl.train_v4_ac --iters 500 --device cuda --dynamics torch --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt --ckpt-dir experiments/aerial/rl/artifacts/v4_ac_ckpt_phase2_gnorm_20260829 --annotation artifacts/seen_airsim16_m1a20.json --backend mock --skip-collect --dataset experiments/aerial/rl/artifacts/dataset_v0_d_full_20260828` |
| iters | **500**（从零，**未** warm-start `step_e` ckpt） |
| ckpt | `experiments/aerial/rl/artifacts/v4_ac_ckpt_phase2_gnorm_20260829/v4_ac_latest.pt` |
| `condition_on_goal` | **True** |
| actor 首层 in_dim | **1540** = latent_dim(1536) + GOAL_NORM_DIM(4) ✅ |
| g_norm 在训 | **是** — H100 已同步 WT `goal_features.py`（`g_norm_from_goal_rel`）；训日志 iter 0–499 均含 `'condition_on_goal': True` |
| 训后想象指标 | `mean_progress=+0.673 m/step`，`mean_return=**-63.06**`（Step E 同语料为 +10.79） |
| 训日志 | `artifacts/train_v4_ac_phase2_gnorm_20260829.log`（H100 + 125 副本） |

**对比 Step E（旧米制 goal 语义，非 g_norm）**：同 WM / 同 dataset / 同 500 iter，`mean_return=+10.79`，`mean_progress=+0.767` — g_norm 重训后想象 return **符号翻转**，closed-loop SR 从旧主航道 43.8% 跌至 **0%**。

---

## 2. 16 路 mainline 指标 vs 门限

| 指标 | 实测 | 门限 | 过门？ |
|------|------|------|--------|
| **SR（到达率）** | **0.0%**（0/16） | ≥80% | ❌ |
| **SCR（严重碰撞率）** | **25.0%**（4/16） | ≤10% | ❌ |
| **SPL** | **0.0%** | ≥70% | ❌ |
| **ρ̄（mean_progress）** | **56.6%** | ≥90% | ❌ |
| **IR（干预率）** | **25.0%** | ≤25% | ⚠️ 数值贴线（均值恰在门限） |

**产物**

| 文件 | 路径 |
|------|------|
| JSON | `artifacts/wam_phase2_signoff_result_20260829.json` |
| 日志 | `artifacts/wam_phase2_signoff_20260829.log` |
| 路由 | `artifacts/seen_airsim16_long_routes.json` |
| actor ckpt | `experiments/aerial/rl/artifacts/v4_ac_ckpt_phase2_gnorm_20260829/v4_ac_latest.pt` |
| WM ckpt | `experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt` |

**栈**：AdaptiveSubgoal → `LatentActorDeployPolicy`(g_norm) → `ImaginationPlanner`(H=5) → ThreeZone → step。  
**参数**：`cruise_speed=10.0 m/s`，`max_steps=1000`，`planner-horizon=5`。

---

## 3. spawn_fail

| 项 | 值 |
|----|-----|
| `n_spawn_fail_f1` | **0** |
| F1 重试 | route 04 曾 `spawn_err=1159.5m`，z+=2 重试后 **计入** scored（非 skip） |

---

## 4. 失败 episode — F1–F14 归类

> 16 条 **全部未到达**；每条标主因。禁止用 Docking / 启发式 / 关罩关失败。

| route_idx | base | d_min | prog | SCR | IR | 主因 | 次要 |
|-----------|------|-------|------|-----|-----|------|------|
| 0 | 5 | 153.1 m | 100% | ✓ | 0.57 | **F11** 空转（L_act≈29×L_ref） | F3, F5 |
| 1 | 16 | 115.6 m | 100% | | 0.41 | **F11/F4** 满弧仍距目标 >100 m | F5 |
| 2 | 7 | **26.8 m** | 88% | ✓ | 0.11 | **F12** 终末未进 3 m 球 | F3 |
| 3 | 17 | 136.0 m | 6% | ✓ | 0.21 | **F4** 起步丢轨 | F1(重试), F9 |
| 4 | 10 | 89.8 m | 79% | | 0.09 | **F12** | F9 |
| 5 | 13 | 118.3 m | 17% | | 0.14 | **F4** | F9 |
| 6 | 1 | 61.7 m | 88% | | 0.13 | **F12** | F9 |
| 7 | 9 | 57.5 m | 82% | | 0.24 | **F12** | F9 |
| 8 | 18 | 117.1 m | 100% | | 0.58 | **F11** 超时空转 | F5 |
| 9 | 14 | 73.9 m | 71% | | 0.15 | **F12** | F9 |
| 10 | 4 | 79.3 m | 17% | | 0.13 | **F4/F12** | F9 |
| 11 | 11 | 107.2 m | 23% | | 0.11 | **F4/F12** | F9 |
| 12 | 15 | 107.9 m | 15% | | 0.35 | **F4/F12** | F5 |
| 13 | 2 | 98.1 m | 21% | | 0.10 | **F4/F12** | F9 |
| 14 | 0 | 56.5 m | 97% | | 0.18 | **F12** 最近非 SCR 但仍 >3 m | F9 |
| 15 | 19 | 105.7 m | 2% | ✓ | 0.50 | **F1** 2 step 即 SCR / 首段几何 | F5 |

### 按 F 码汇总

| F 码 | 条数 | 说明 |
|------|------|------|
| **F9** | **16**（系统性） | g_norm 重训 π 想象 return 为负，closed-loop **零到达** — **π 弱**为主因 |
| **F12** | 10 | 终末 3 m 合同未满足（最佳 d_min=26.8 m，仍 >3 m） |
| **F4** | 6 | 低 prog 或满弧不到点 |
| **F11** | 3 | L_act≫L_ref 空转（r0,r1,r8） |
| **F3** | 4（SCR 侧） | 硬撞 episode |
| **F5** | 4 | 高 IR 仍 SCR 或高 IR 空转（r0,r8,r12,r15） |
| **F1** | 1 | r15 首段；r04 重试未 skip |

---

## 5. 纪律确认

本轮 **未**做：Docking、往返刷分、关罩 / `safety.kind=null`、开 escape、放宽 3 m 到达、改门限凑 PASS、用旧 `step_e` ckpt 冒充全签。

---

## 6. 未签项与归因（诚实）

| 未过门 | 主因 | 次要 |
|--------|------|------|
| SR=0% | **π 弱** — g_norm 从零重训后想象 `mean_return≈-63`，策略未学到可闭合到点的 goal 条件行为 | F12 终末区、F11 空转 |
| SCR=25% | π 轨迹 + 10 m/s 弯障（F3）；4/16 硬撞 | 非罩主导（IR 均值 25%，多条 IR<15% 仍不到点） |
| SPL=0% | 零到达 ⇒ SPL 全 0 | — |
| ρ̄=56.6% | F4 丢轨 + F11 假满弧（prog=100% 但 d_min 仍 >50 m） | — |
| IR=25% | 贴线；高 IR 路由（r0,r1,r8）为 **罩在纠空转**，非 SR 主因 | — |

**不得**将 FAIL 归因于「仅 F3 限速」或「仅 spawn」— 在 `n_spawn_fail_f1=0`、fullfix 代码栈下，**g_norm π 重训质量**是当前第一阻塞。

---

## 7. Verdict

**FAIL** — SR / SCR / SPL / ρ̄ 均未过门；IR 恰在门限无实质余量。

---

## 8. 下一切主航道（一句）

在 H100 上 **审计 g_norm 想象训程**（reward 符号、actor 输入与 deploy 一致、必要时延长 iters 或调 imagination batch）直至想象 `mean_return` 恢复正域，再复跑 16 路 — **禁止**回退旧 step_e ckpt 或关罩/加 Docking 凑 PASS。

---

## 9. 快速复查

```bash
cd ~/aerial-wam-v2
python3 -c "
import json
r=json.load(open('artifacts/wam_phase2_signoff_result_20260829.json'))
m=r['metrics']
print('verdict', r['verdict'])
print('SR', f\"{m['arrival_rate']:.1%}\")
print('SCR', f\"{m['severe_collision_rate']:.1%}\")
print('SPL', f\"{m['spl']:.1%}\")
print('Prog', f\"{m['mean_progress_ratio']:.1%}\")
print('IR', f\"{m['mean_intervention_rate']:.1%}\")
print('spawn_fail_f1', r['n_spawn_fail_f1'])
"
```
