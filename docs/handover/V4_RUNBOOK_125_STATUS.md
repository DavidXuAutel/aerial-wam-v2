# V4 RUNBOOK 125 STATUS

- **date**: 2026-08-21
- **state**: ACTIVE — **hinge+pinball FT 进行中**
- **HEAD**: `5831c1f`
- **enable_policy_update**: false
- **R-16**: **(B)**

## Running jobs

| job | PID | log |
|-----|-----|-----|
| depth hinge+pinball FT → held-out ⓪ | **3410479** (train **3410491**) | `logs/v4_depth_hinge_pinball_20260821.log` |

Recipe（已声明）：`near_weight=0` / hinge=3 / pinball=2@0.9；init=r60 老头；`holdout-frac=0.2`；训完自动 eval emit `artifacts/v4_zero_p3_hinge_pinball_holdout_20260821.json`。

## Checklist

- [x] 跑前声明 + 代码 `5831c1f`
- [ ] 125 FT + held-out ⓪（进行中）
- [ ] 过关后重跑 V0 ④
- [ ] ⓿e fix

## Artifacts

- 声明：`docs/handover/V4_DEPTH_LOSS_DECLARE_20260821.md`
- 控制臂：`artifacts/v4_zero_p3_oldhead_merged_20260821.json`
- 本轮 OUT：`experiments/aerial/rl/artifacts/depth_ckpt_p45_hinge_pinball_20260821/`
