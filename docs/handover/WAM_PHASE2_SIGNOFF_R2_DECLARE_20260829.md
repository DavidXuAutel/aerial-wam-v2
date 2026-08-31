# Phase-2 全签 R2 DECLARE（125 · w_collision=1.0 重训 π → 16 路 mainline）

> **日期**：2026-08-29（晚）  
> **机器**：cursor-125（4090 / AirSim）+ H100 `10.239.121.22:31126`  
> **Agent workspace**：`/home/yao/workspaces/aerial-wam-v2-phase2`  
> **协议**：`wam_phase2_mainline_native_20260829_fullfix`  
> **Verdict**：**FAIL**（如实）

---

## 1. H100 训程（R2 delta）

| 项 | R1 | **R2** |
|----|-----|--------|
| H100 主机 | h100-25（旧） | **`10.239.121.22`** |
| `--w-collision` | 10.0（yaml 默认） | **1.0** |
| iters | 500 | **500**（训满，~4 min wall） |
| ckpt-dir | `v4_ac_ckpt_phase2_gnorm_20260829` | **`v4_ac_ckpt_phase2_gnorm_r2_20260829`** |
| 想象 `mean_return` | **−63.06** | **+3.68** ✅ |
| 想象 `mean_progress` | +0.673 m/step | **+0.744 m/step** |
| iter 0 `mean_return` | — | −10.41 → iter 4 转正 |
| iter 499 `mean_return` | — | +2.90 |
| `condition_on_goal` | True | **True** |
| actor 首层 in_dim | 1540 | **1540** |

**命令**

```bash
python -m experiments.aerial.rl.train_v4_ac \
  --iters 500 --device cuda --dynamics torch \
  --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt \
  --ckpt-dir experiments/aerial/rl/artifacts/v4_ac_ckpt_phase2_gnorm_r2_20260829 \
  --annotation artifacts/seen_airsim16_m1a20.json \
  --backend mock --skip-collect \
  --dataset experiments/aerial/rl/artifacts/dataset_v0_d_full_20260828 \
  --w-collision 1.0
```

**产物**

| 文件 | 路径 |
|------|------|
| ckpt | `experiments/aerial/rl/artifacts/v4_ac_ckpt_phase2_gnorm_r2_20260829/v4_ac_latest.pt` |
| 训日志 | `artifacts/train_v4_ac_phase2_gnorm_r2_20260829.log` |

**假设验证**：R1 阻塞（`w_collision=10 × p_coll≈0.5 → 每步 −5 碰撞税`）在想象域 **成立** — R2 将 `mean_return` 从 −63 拉回 **+3.68**（Step E 同语料 +10.79，仍略低但已进正域）。

---

## 2. 16 路 mainline 指标 vs 门限

| 指标 | R1 | **R2** | 门限 | R2 过门？ |
|------|-----|--------|------|-----------|
| **SR** | 0.0% | **0.0%** | ≥80% | ❌ |
| **SCR** | 25.0% | **6.2%** | ≤10% | ✅ |
| **SPL** | 0.0% | **0.0%** | ≥70% | ❌ |
| **ρ̄** | 56.6% | **13.5%** | ≥90% | ❌ |
| **IR** | 25.0% | **98.7%** | ≤25% | ❌ |

**产物**

| 文件 | 路径 |
|------|------|
| JSON | `artifacts/wam_phase2_signoff_r2_result_20260829.json` |
| 日志 | `artifacts/wam_phase2_signoff_r2_20260829.log` |
| 路由 | `artifacts/seen_airsim16_long_routes.json` |

**栈 / 参数**：同 R1 — AdaptiveSubgoal → LatentActorDeployPolicy(g_norm) → ImaginationPlanner(H=5) → ThreeZone → step；`cruise_speed=10.0`，`max_steps=1000`，`planner-horizon=5`。

---

## 3. R1 vs R2 对照摘要

| 维度 | R1 | R2 | 解读 |
|------|-----|-----|------|
| 想象 return | −63 | **+3.7** | 碰撞税假设 **修复** |
| closed-loop SR | 0% | 0% | 仍零到达 |
| SCR | 25% | **6.2%** | 硬撞减少（4→1 条） |
| ρ̄ | 56.6% | **13.5%** | **大幅退化** |
| IR | 25% | **98.7%** | **罩几乎全程介入** |
| 典型 L_act | ~500–4900 m（空转） | **~55–65 m**（被罩钳住） | 策略 bolder → deploy 罩拒 |

---

## 4. spawn_fail

| 项 | 值 |
|----|-----|
| `n_spawn_fail_f1` | **0** |

---

## 5. 失败 episode — F1–F14 归类

> 16 条 **全部未到达**。

| route_idx | base | d_min | prog | SCR | IR | 主因 | 次要 |
|-----------|------|-------|------|-----|-----|------|------|
| 0 | 5 | 153.5 m | 0% | | 99.8% | **F5** 罩全程钳住 | F4 |
| 1 | 16 | 150.6 m | 9% | | 99.5% | **F5** | F4 |
| 2 | 7 | 147.9 m | 0% | | 99.7% | **F5** | F4 |
| 3 | 17 | 135.1 m | 7% | | 99.4% | **F5** | F4 |
| 4 | 10 | 134.2 m | 0% | | 99.7% | **F5** | F4 |
| 5 | 13 | 140.5 m | 0% | | 99.8% | **F5** | F4 |
| 6 | 1 | 135.0 m | 0% | | 99.6% | **F5** | F4 |
| 7 | 9 | 104.4 m | 0% | | 99.9% | **F5** | F4 |
| 8 | 18 | 122.0 m | 0% | | 99.8% | **F5** | F4 |
| 9 | 14 | 110.9 m | 0% | | 99.7% | **F5** | F4 |
| 10 | 4 | 92.8 m | 0% | | 99.7% | **F5** | F4 |
| 11 | 11 | 118.5 m | 0% | | 99.7% | **F5** | F4 |
| 12 | 15 | 116.0 m | 0% | | 98.2% | **F5** | F4 |
| 13 | 2 | 113.8 m | 100% | | 99.6% | **F11** L_act=345 m 空转 | F5 |
| 14 | 0 | 109.9 m | 100% | | 99.6% | **F11** L_act=341 m 空转 | F5 |
| 15 | 19 | 107.9 m | 0% | ✓ | 85.7% | **F1/F3** 7 step 即 SCR | — |

### 按 F 码汇总

| F 码 | 条数 | 说明 |
|------|------|------|
| **F5** | **14**（系统性） | IR≈99%，L_act≪L_ref — **ThreeZone 罩拒 π 动作** 为主因 |
| **F11** | 2 | r13/r14 prog=100% 但 d_min>109 m |
| **F4** | 14 | 低 prog / 不到点 |
| **F1/F3** | 1 | r15 首段 SCR |

---

## 6. 纪律确认

本轮 **未**做：Docking、往返刷分、关罩 / `safety.kind=null`、开 escape、放宽 3 m 到达、改门限凑 PASS、用 R1 / step_e ckpt 冒充 R2。

---

## 7. 未签项与归因（诚实）

| 未过门 | 主因 | 次要 |
|--------|------|------|
| SR=0% | **想象→deploy 鸿沟** — 想象 return 已正，但 π 动作 bolder，closed-loop 被罩钳（IR 99%） | F11 空转 |
| SCR=6.2% | 较 R1 改善；仅 r15 硬撞 | — |
| SPL=0% | 零到达 | — |
| ρ̄=13.5% | **F5 罩拒** 导致 L_act≈60 m（R1 虽空转但 L_act 更长） | F11 |
| IR=98.7% | **系统性罩拒** — 非「罩救 SR」而是 **阻止 π 执行** | — |

**结论**：R2 **证实** R1 想象 return 负因碰撞税过重；但 `w_collision=1.0` 矫枉过正 → π 学 bold latent 动作 → deploy ThreeZone **几乎逐步 override**，closed-loop **劣于 R1**（ρ̄ 56.6%→13.5%）。

---

## 8. Verdict

**FAIL** — SR / SPL / ρ̄ / IR 均未过门；SCR 单独过门不足以签。

---

## 9. 下一切主航道（一句）

在 H100 上 **扫 w_collision 中间档（如 3–5）或加 deploy-action 正则**，使想象 return 保持正域同时 π 动作与 ThreeZone 可共存，再复跑 16 路 — **禁止**关罩 / 改 safety.py deploy / 回退 step_e ckpt。

---

## 10. 快速复查

```bash
cd ~/aerial-wam-v2
python3 -c "
import json
r=json.load(open('artifacts/wam_phase2_signoff_r2_result_20260829.json'))
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
