# C2 ①-eval first-act cos + goal_rel0 (125)

- **status**: running
- **prompt**: `docs/handover/V4_C2_COS_DIAG_125_PROMPT.md`
- **ckpt**: `v4_ac_ckpt_20260818_c2_fromscratch/v4_ac_latest.pt` + RH WM `wm_step_1000.pt`
- **script**: `experiments/aerial/scripts/v4_progress_diag.py`

Pre-committed: mean cos(first_act, goal_body) **< 0** → 签 §4 In 表；**≥ 0** → 不签（想象-真实倒挂）。实现代码本 job **不写**。

> **收紧（08-18 洞 4，见 PROMPT 事后注记 / `V4_GATE_STATUS.md` §1 洞 4）**：评测 `goal_body0` 由构造 **≡ `[+30,0,0]`** 恒定 ⇒ 首动作 cos 退化为 `sign(a0_x)`，`first_act_xyz_std≈0` 不是 goal-blind 指纹，且 §4 In 表在 t=0 信息量为 0。故 **`cos ≥ 0` → 仍不签**（不变）；**`cos < 0` → 「待签」**，须同时落轨迹级 `cos_path_goal` / `cos_mean10_act_xy_goal_body_xy`（t=0 正、沿 t 翻负 ⇒ 可签；全程正而 progress 负 ⇒ 倒挂，不签）。本 job **不**签 §5。
>
> 另：`signals.1.scan` 的键是 **`rejections`**（不是 `rej`）；`rejections["spawn_collision"]` 是扫描期被拒 ≠ 评测期 `_run_one_resilient→None` 丢局，须分开写。

## Numbers (fill)

| run | n scored | mean cos actor | n cos<0 | mean ‖a0[:3]‖ | Pearson imagΣG vs real progress | verdict |
|---|---|---|---|---|---|---|
| seed=0 | | | | | | |
| seed=1 | | | | | | |

Per-ep tables + `goal_rel0` / azimuth: _pending_.
