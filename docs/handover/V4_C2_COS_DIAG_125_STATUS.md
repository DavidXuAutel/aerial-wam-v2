# C2 ①-eval first-act cos + goal_rel0 (125)

- **status**: **DONE** (2026-08-18)
- **prompt**: `docs/handover/V4_C2_COS_DIAG_125_PROMPT.md`
- **ckpt**: `v4_ac_ckpt_20260818_c2_fromscratch/v4_ac_latest.pt` + RH WM `wm_step_1000.pt`
- **script**: `experiments/aerial/scripts/v4_progress_diag.py` (`--imagine-horizon 15`)
- **renderer**: `127.0.0.1:41451` TCP OK
- **HEAD**: `b35d245f2d6fa32a4d4f35927c68fcfd94162ebf`

Pre-committed: mean cos(first_act, goal_body) **< 0** → 签 §4 In 表；**≥ 0** → 不签（想象-真实倒挂）。实现代码本 job **不写**。

## Verdict

**`do_not_sign_imagine_real_inversion`** — 两跑 mean cos **同号且 ≥ 0**（+0.806 / +0.762），按事前表 **不签** §4 In 表。活假设 = 想象-真实回报倒挂（imagined ΣG ≈ **+85** vs real progress ≈ **−5**；Pearson +0.59 / +0.22 但 mean(real−imag) ≈ **−91**）。

**方向分布退化（事实）**：harness t=0 body `goal_rel0` 全 ep ≈ **`[+30, 0, z]`**，azimuth **|θ| ≤ 0.8°**（7/8 ep ≤ 0.2°）。评测 goal 方向几乎恒定前向（构造，非宽方位抽样）⇒ 正 cos **不能**读成「随 goal 转向」；仍按事前表用 mean cos 签字。

**固定偏置指纹弱**：`first_act_xyz_std_actor` x 维 **0.12 / 0.21**（非 ≈0），且 `n_cos_first_act_lt0=0`（无 ep 负 cos）。`cos_path_goal` 有负 ep（seed=0 3/7），但 first-act cos 全正。

## Step 0 — gate partials on disk

Partial-1 JSON **confirmed missing** `first_act`, `cos_*`, `goal_rel0` (only progress sums + embedded `scan`).

### signals.1.scan (seed=0, dir `v4_gate_r60_20260818_c2`)

- requested **10** → accepted **9** → **n_starts_scored 5** (eval drop 9→5)
- rejections: `open_ahead` **708**, `spawn_collision` 10, `probe_no_hit` 11, `obstacle_ok` 9, `proxy_ok` 20
- probe: hits 9/20, collided 9

### signals.1.scan (seed=1, dir `v4_gate_r60_20260818_c2_n8`)

- requested **8** → accepted **8** → **n_starts_scored 5** (eval drop 8→5)
- rejections: `open_ahead` 15, `spawn_collision` 8, `probe_no_hit` 4, `obstacle_ok` 8, `proxy_ok` 12
- probe: hits 8/12, collided 8

## Summary table

| run | n scored | mean cos actor | n cos<0 | mean ‖a0[:3]‖ | Pearson imagΣG vs real progress | verdict |
|---|---|---|---|---|---|---|
| seed=0 | 7 | **+0.806** | 0 | 0.848 | **+0.588** | do_not_sign |
| seed=1 | 8 | **+0.762** | 0 | 0.829 | **+0.217** | do_not_sign |

Also: mean `cos_path_goal` actor **+0.075 / +0.098**；heur first-act cos **+0.999 / +0.993**。`mean_imagined_sum_progress` **84.9 / 86.5** vs `mean_actor` **−5.94 / −4.48**。

Artifacts: `artifacts/v4_progress_diag_c2_seed0_20260818.json`, `artifacts/v4_progress_diag_c2_seed1_20260818.json`；logs `logs/v4_progress_diag_c2_seed{0,1}_20260818.log`。

## Per-ep (actor)

### seed=0 (n=7; idx 2,5,9 dropped spawn)

| ep | cos_act | cos_heur | cos_path | ‖a0‖ | az° | progress | imagΣG | goal_rel0 (xyz) |
|---|---|---|---|---|---|---|---|---|
| 0 | +0.774 | +0.998 | +0.198 | 0.803 | −0.00 | −3.42 | +84.0 | [30.00, −0.002, 1.04] |
| 1 | +0.845 | +1.000 | +0.287 | 0.897 | +0.01 | −4.15 | +87.8 | [29.99, +0.003, 0.81] |
| 3 | +0.820 | +0.999 | +0.568 | 0.959 | +0.00 | +2.47 | +89.4 | [30.01, +0.002, 0.68] |
| 4 | +0.731 | +1.000 | −0.188 | 0.613 | +0.03 | −10.60 | +81.5 | [30.02, +0.018, 0.18] |
| 6 | +0.850 | +1.000 | +0.081 | 0.956 | +0.01 | −6.36 | +93.8 | [30.00, +0.003, 1.03] |
| 7 | +0.844 | +1.000 | −0.238 | 0.898 | −0.03 | −10.08 | +81.5 | [30.00, −0.016, 0.07] |
| 8 | +0.778 | +0.997 | −0.180 | 0.810 | +0.16 | −9.44 | +76.3 | [30.01, +0.086, 0.11] |

### seed=1 (n=8)

| ep | cos_act | cos_heur | cos_path | ‖a0‖ | az° | progress | imagΣG | goal_rel0 (xyz) |
|---|---|---|---|---|---|---|---|---|
| 0 | +0.750 | +1.000 | +0.593 | 0.775 | −0.00 | +4.41 | +90.3 | [30.00, −0.002, 0.83] |
| 1 | +0.810 | +1.000 | −0.205 | 0.788 | −0.01 | −5.67 | +85.4 | [30.00, −0.004, 0.82] |
| 2 | +0.830 | +0.990 | +0.178 | 0.985 | +0.00 | −3.17 | +91.4 | [30.00, +0.003, 0.85] |
| 3 | +0.720 | +1.000 | +0.140 | 0.718 | +0.05 | −4.79 | +91.0 | [30.01, +0.024, 0.91] |
| 4 | +0.850 | +0.980 | +0.010 | 1.002 | −0.00 | −8.03 | +90.1 | [30.00, −0.001, 0.82] |
| 5 | +0.860 | +1.000 | +0.170 | 0.885 | +0.79 | −3.93 | +89.7 | [30.10, +0.412, −0.04] |
| 6 | +0.410 | +0.990 | −0.210 | 0.480 | +0.02 | −9.87 | +84.3 | [29.98, +0.012, 0.83] |
| 7 | +0.870 | +1.000 | +0.110 | 0.999 | +0.23 | −4.76 | +70.0 | [29.92, +0.122, 0.16] |

## Disposition

- **§4 In 表**：**不签**（签会白训一轮 In-table 实现）。
- **下一件**：活假设 = WM 转移保真 / z0 域差 / 想象-真实倒挂；须另案（非 In 表 goal concat）。全权 ① 仍须解 spawn-in-collision；`enable_policy_update` 仍 false。
