# Phase-2 STATUS（活页 · 2026-09-01）

> **评测**：`.110` Outdoor · 本回合不开 g_norm / 16 路全签

---

## 一句话

**罩 bug 已关单**；**H1 ablation 在跑**（R01/R03/R05 × wam / nofreeze / tangent_subgoal / rejoin）。g_align 探针已出：early g_align≈0 + freeze≈0.85。

---

## 已完成

| 阶段 | 产物 | 结论 |
|------|------|------|
| cones 修复 + 复测 | `wam_phase2_cones_fix_probe_20260901` | iv 1→0.03，罩假阳性清 |
| cones 后法医 | `wam_phase2_conesfix_forensics_20260901` | R01/R03/R05 全 F_OFFTRACK，IR≈0.02 |
| g_align 探针 | `wam_phase2_galign_probe_20260901` | R01/R03：g_align_e50≈0，H1=input_geometry_suspect |

## 在跑（.110）

```bash
# H1 ablation + R05 g_align + H3 nofreeze + rejoin 上界
artifacts/videos/wam_phase2_h1_ablation_20260901/
# routes 0,2,4 × arms wam,wam_nofreeze,tangent_subgoal,rejoin × 300 steps
# 预计 ~3h
```

新增 arm **`tangent_subgoal`**：true projection + 固定 20 m 折线 lookahead → π/planner 不变，测 H1。

## 准出（ablation 跑完后）

- H1：**wam vs tangent_subgoal** ds_true / cte_end 显著改善 → 定刀 subgoal 几何
- H3：**wam vs wam_nofreeze** ds 无差 → freeze 降级
- **rejoin** 若 ds 高 → 走廊可飞，问题在 π/输入
- 仍 **不开** 16 路 / g_norm
