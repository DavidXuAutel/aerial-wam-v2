# DECLARE · F15 效率 iter2（2026-09-02）

> **状态**：**已收** · iter2 probe 完成 · R01 **过** · R05 **部分改善、未准出**  
> yaml 默认 `w_eff_*` 仍 **0**；仅本回合 CLI 抬权。

---

## 0. iter1 + planner fix 验收（assist OFF · 300 步）

产物：`artifacts/videos/wam_phase2_f15_eff_plannerfix_probe_20260902/`  
ckpt：`v4_ac_ckpt_f15_eff_ft_20260901` · `planner.py` goal aux 已修。

| 路 | ds | cte_end | cos@0–30 | idle (v&lt;1) | vs F15 baseline |
|----|-----|---------|----------|---------------|-----------------|
| R01 | **37.7** | **15.3** | **0.86** | 4.7% | ds↑ cte↓ cos↑ → **过** |
| R05 | **0.0** | **30.2** | **−0.10** | 9% | ds≈ cte↑ cos↓ → **不过** |

读数：planner fix 消除倒飞转圈；R05 仍 **CTE 升 + arc-s freeze**（`frac_frozen=82%`），iter1 想象 `mean_return≈−75` → **效率罚过重**。

---

## 1. iter2 短训（冻结）

| 项 | 值 |
|----|-----|
| 动机 | 降 F15 罚量级，保留 iter1 对 idle/yaw 的偏置；不回到 step_e |
| 底座 | **`v4_ac_ckpt_f15_eff_ft_20260901`** warm-start |
| WM / 语料 | 同 iter1（`wm_step_3500` · `dataset_v0_d_full_20260828`） |
| 权重（CLI only） | `w_eff_idle=0.02` · `w_eff_heading=0.04` · `w_eff_strafe=0.015`（iter1 ÷10；heading 略抬相对 idle） |
| iters | **300** |
| ckpt-dir | **`v4_ac_ckpt_f15_eff_ft_iter2_20260902`**（勿覆盖 iter1 / step_e） |
| 机器 | **H100**（经 125）；评测 **`.110`** · planner fix 已 sync |
| 评测 | assist **OFF** · R05/R01 probe 300 步 |

### 准出（相对 F15 baseline + iter1 plannerfix probe）

* R05：`ds` ↑ vs baseline 1.3；`cte_end` ≤ iter1 plannerfix（30.2）且 early `cos30` ≥ baseline 0.15  
* R01：`ds` 不掉于 iter1 plannerfix（37.7）、`cte_end` 不恶化  
* 想象日志 `w_eff_*` 非零；yaml 默认仍为 0

### 禁止

* 默认 assist；heading_reentry；改 cruise / subgoal 几何当主修  
* 覆盖 `step_e` / iter1 ckpt；未 DECLARE 改 yaml 默认

---

## 2. 执行

H100 训练日志：`artifacts/train_v4_ac_f15_eff_ft_iter2_20260902.log`  
`.110` probe out：`artifacts/videos/wam_phase2_f15_eff_iter2_probe_20260902/`

---

## 3. iter2 probe 验收（2026-09-02 · assist OFF · 300 步 · planner fix）

| 路 | ds | cte_end | cos@0–30 | idle | vs baseline | verdict |
|----|-----|---------|----------|------|-------------|---------|
| R01 | **94.2** | **15.9** | **0.94** | 5.3% | ds↑↑ cte↓ cos↑ | **过** |
| R05 | **25.3** | **28.9** | **−0.13** | 7.0% | ds↑ idle↓；cte↑ cos↓ | **不过** |

读数：iter2 恢复 R05 **沿轨 ds**（25m vs baseline 1.3）；主关仍为 **body 轴 vs 路径切线**（`cos_heading_ref<0`）+ **CTE 高**。`g_align` 高但切线角不对 → 下一刀仍 F15 heading，抬 `w_eff_heading`、压 idle。

**Verdict**：iter2 **部分 PASS** → 开 **iter3**（warm iter2 · heading 加权）。
