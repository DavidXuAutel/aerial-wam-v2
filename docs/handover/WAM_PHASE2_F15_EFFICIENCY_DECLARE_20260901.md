# DECLARE · F15 效率合同（2026-09-01）

> **状态**：baseline ✓ · heading_reentry **FAIL** · **开短训（H100）**  
> yaml / 部署权重仍默认 **0**；仅本回合 `train_v4_ac --w-eff-*` 抬权。

---

## 0. 已封卷对照

### F15 baseline（assist OFF · R05/R01 · 300 步）

产物：`artifacts/videos/wam_phase2_f15_strafe_baseline_20260901/`

| 路 | ds | cte末 | idle | tiny dyaw | cos_h@0–30 |
|----|-----|-------|------|-----------|------------|
| R05 | 1.3 | 16.8 | **98%** | **97%** | **0.15** |
| R01 | 20.5 | 18.0 | 61% | 95% | 0.51 |

读数：**主因 = 开局 yaw 死 + 不扭头 + 沿轨空转**，不是大侧移蹭点。

### heading_reentry（零重训 · cos&lt;0.7→R≤15）— **FAIL**

产物：`artifacts/videos/wam_phase2_heading_reentry_probe_20260901/`

| 路 | baseline ds | reentry ds | Δcte_end |
|----|-------------|------------|----------|
| R05 | 1.3 | **−0.0** | +0.6 |
| R01 | 20.5 | 24.9 | −1.6 |

R05 仍 idle/frozen；carrot shrink **不可当主修**。assist 早已 FAIL。

---

## 1. 本回合短训（冻结）

| 项 | 值 |
|----|-----|
| 动机 | 想象回报里真正罚 **空耗 + 偏航仍机动**；补训 step_e，不换主航道栈 |
| 底座 | `v4_ac_ckpt_step_e_20260828` · `goal_feat_mode=meter` · `condition_on_goal=True` |
| WM / 语料 | `wm_ckpt_d_full_20260828/wm_step_3500.pt` · `dataset_v0_d_full_20260828` |
| 权重（CLI only） | `w_eff_idle=0.2` · `w_eff_heading=0.3` · `w_eff_strafe=0.15` |
| iters | **300**（warm-start；到点用 latest） |
| ckpt-dir | **`v4_ac_ckpt_f15_eff_ft_20260901`**（勿覆盖 step_e） |
| 机器 | **H100**（经 125 跳板）；评测回 **`.110`** |
| 评测 | assist **OFF** · R05/R01 probe 先；再决定是否 16 路 |

### 准出（相对 F15 baseline，assist OFF）

* R05：`ds` ↑ 且 early `cos30` 不差于 baseline；idle 显著下降  
* R01：`ds` 不掉、`cte_end` 不恶化  
* 想象日志须打印 `w_eff_*` 非零；默认 yaml 仍为 0

### 禁止

* 默认开 heading-assist 刷分  
* 覆盖 `step_e` ckpt  
* 未 DECLARE 改 yaml 默认 `w_eff_*`  
* 关罩 / Docking / 放宽 3 m

---

## 2. 代码合同（本回合已接线）

* `efficiency_cost`：heading = `|yaw_err| × 1{|dx|+|dy|>ε}`（对准「拧头前仍推力」）  
* `imagine(...)` 扣 F15（yaw←`atan2(g_left,g_fwd)`；idle←analytic progress）  
* `train_v4_ac --w-eff-*` + `--init-actor-ckpt`

执行手顺：[`WAM_PHASE2_F15_SHORT_TRAIN_125_PROMPT.md`](WAM_PHASE2_F15_SHORT_TRAIN_125_PROMPT.md)
