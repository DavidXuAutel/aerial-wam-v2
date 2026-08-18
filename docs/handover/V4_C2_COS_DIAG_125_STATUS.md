# C2 ①-eval first-act cos + goal_rel0 (125)

- **status**: running
- **prompt**: `docs/handover/V4_C2_COS_DIAG_125_PROMPT.md`
- **ckpt**: `v4_ac_ckpt_20260818_c2_fromscratch/v4_ac_latest.pt` + RH WM `wm_step_1000.pt`
- **script**: `experiments/aerial/scripts/v4_progress_diag.py`

Pre-committed: mean cos(first_act, goal_body) **< 0** → 签 §4 In 表；**≥ 0** → 不签（想象-真实倒挂）。实现代码本 job **不写**。

## Numbers (fill)

| run | n scored | mean cos actor | n cos<0 | mean ‖a0[:3]‖ | Pearson imagΣG vs real progress | verdict |
|---|---|---|---|---|---|---|
| seed=0 | | | | | | |
| seed=1 | | | | | | |

Per-ep tables + `goal_rel0` / azimuth: _pending_.
