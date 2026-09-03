# E0 DECLARE — goal+scene / no polyline main arm

> **Status**: **done** (2026-09-03 09:01 → 10:24 CST) · 接线绿灯 / 导航仍 FAIL  
> **Plan**: [`docs/superpowers/plans/2026-09-03-phase2-goal-scene-nav.md`](../superpowers/plans/2026-09-03-phase2-goal-scene-nav.md)  
> **Spec**: [`docs/superpowers/specs/2026-09-03-phase2-goal-scene-nav-design.md`](../superpowers/specs/2026-09-03-phase2-goal-scene-nav-design.md)

## Live runs

**机器**：110 与 125 **均可并行**（各有独立 AirSim）；第三臂挂到**先空闲**的那台，不故意单机串三条。

| Arm | Host | subgoal_source | episodes | max-steps | log | out |
|-----|------|----------------|----------|-----------|-----|-----|
| main | **110** | `toward_g` | 2 | 400 | `logs/wam_phase2_e0_toward_g_110_20260903_090102.log` | `artifacts/wam_phase2_e0_toward_g_110.json` |
| A | **125** | `direct_g` | 2 | 400 | `logs/wam_phase2_e0_direct_g_125_20260903_090105.log` | `artifacts/wam_phase2_e0_direct_g_125.json` |
| waterline | **125 链**（若 110 先空则改挂 110） | `polyline` | 2 | 400 | `logs/wam_phase2_e0_polyline_125_20260903_090105.log` | `artifacts/wam_phase2_e0_polyline_125.json` |

Assist OFF · `step_e` · no `--rolling-global` · anno `seen_airsim16_long_routes.json` · cruise 10 · planner H=5.

粗估：~20–40 min/路 → 每臂约 **1–1.5 h**；125 两臂串行约 **2–3 h**。

## Results

三臂均 **Verdict=FAIL**（SR=0）。`EXIT_CODE=1` 是 FAIL 判定，**不是 crash**。

| Arm | subgoal_source | routes | mean d_min | mean d_final | mean closure | SR | SCR | IR | JSON |
|-----|----------------|--------|------------|--------------|--------------|----|-----|----|------|
| main | `toward_g` | 0–1 @110 | **78.34 m** | **78.74 m** | **0.487** | 0.0% | **0.0%** | 0.6% | `artifacts/wam_phase2_e0_toward_g_110.json` |
| A | `direct_g` | 0–1 @125 | 78.31 m | **300.72 m** | 0.487 | 0.0% | 0.0% | **29.9%** | `artifacts/wam_phase2_e0_direct_g_125.json` |
| waterline | `polyline` | 0–1 @125 | 96.16 m | 96.16 m | 0.370 | 0.0% | 0.0% | 0.1% | `artifacts/wam_phase2_e0_polyline_125.json` |

逐路（`d_start` 由 `closure=1−d_min/d_start` 反推 ≈ **154 / 151 m** —— 再次确认标注航道**不是** 200–500 m）：

| Arm | Route | L_ref | L_act | d_min | d_final | closure | IR |
|-----|-------|-------|-------|-------|---------|---------|----|
| `toward_g` | 01 | 168.0 | 184.9 | 52.28 | 53.05 | 0.66 | 0.000 |
| `toward_g` | 02 | 156.0 | 144.6 | 104.40 | 104.43 | 0.31 | 0.013 |
| `direct_g` | 01 | 168.0 | **717.9** | 52.25 | **493.97** | 0.66 | 0.112 |
| `direct_g` | 02 | 156.0 | 128.6 | 104.36 | 107.47 | 0.31 | 0.486 |
| `polyline` | 01 | 168.0 | 117.3 | 81.21 | 81.21 | 0.47 | 0.000 |
| `polyline` | 02 | 156.0 | 66.3 | 111.11 | 111.11 | 0.27 | 0.003 |

**读法**

1. **`closure` 是 best-approach 指标**（[`wam_phase2_long_eval.py:39`](../../experiments/aerial/scripts/wam_phase2_long_eval.py#L39) `1 − d_min/d_start`），**不惩罚抵近后再飞走**。所以 main 与 A 的 closure 完全相同（0.487）、`d_min` 也几乎相同（78.34 / 78.31）—— 两臂「最好那一刻」一样近。区分它们的是 `d_final`。
2. **A（`direct_g`）是 F11 gross detour 的干净反例**：Route 01 飞了 **717.9 m**（`L_ref` 168 m，4.3×）后停在离 G **493.97 m** 处，IR 冲到 29.9%。main 同一条路 `L_act` 184.9 m、`d_final` 53.05 m、IR 0.0%。⇒ **`toward_g` 的截断/受控抵近是稳定性的来源，裸 `direct_g` 会散架**，A 作为强制消融给出了预期的负面结果。
3. **main 优于 waterline**：closure 0.487 vs 0.370，`d_final` 78.74 vs 96.16 m。即**不用 GT 折线**反而离 G 更近 —— polyline 臂两条路都提前停住（`L_act` 117.3 / 66.3 m 远短于 `L_ref`），`Prog` 38.0% 是它唯一好看的数，而 Prog 按治理红线**不参与主线判定**。
4. **SCR = 0.0% 三臂全清零**，对比 08-30 裸 `step_e` 回锚基线 SCR **0.125** —— 无安全回退。`inflate 0/2` 三臂全 0。
5. **导航本身仍然失败**：SR=0、closure≈0.49 意味着最好也只走完约一半的对 G 距离，两条路都在 ~52 m / ~104 m 处停滞（`d_min ≈ d_final`，main/waterline 都是），**F12 terminal non-convergence 未解**。E0 只证明接线正确、方向排序成立，**不证明能到达**。

## Gate

- [x] Runs complete (no wiring crash) — 三臂各跑完 2 路；日志首行 `subgoal_source=` 与臂一致，main 确实未走 polyline 分支
- [x] SCR not worse than chaotic / waterline baseline in a scary way — 三臂 SCR 均 **0.0%**，优于 08-30 `step_e` 基线 0.125
- [x] **Not** claiming 200–500 m PASS（`d_start` ≈ 151–154 m = engineering probe only）

**E0 结论**：**接线绿灯**（`toward_g` > `polyline` > 无；`direct_g` 明确劣化），**导航红灯**（SR=0，F12 未解）。仅 2 路 × 3 臂，样本量不足以做强声明。

## Next

- E0 green → flip CLI default `polyline` → `toward_g` (dedicated commit)
- Then E1 `--subgoal-source scene` probe + DECLARE
