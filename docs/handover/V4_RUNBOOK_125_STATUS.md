# V4 RUNBOOK 125 STATUS

- **date**: 2026-08-21
- **state**: ACTIVE — loss 改法**已声明**；下一步 = 按声明 FT + held-out 验 ⓪
- **HEAD**: (pending push)
- **enable_policy_update**: false
- **R-16**: **(B)**

## 权威结论（不变）

控制臂 = ⓪ 首个权威 FAIL。稳固支点 = ⓪d **consec≥2**。V0 ④ 低功效待重跑。

## 跑前声明（已落盘）

[`V4_DEPTH_LOSS_DECLARE_20260821.md`](V4_DEPTH_LOSS_DECLARE_20260821.md)

| # | 改法 | 本轮 |
|---|------|------|
| A | 近带单侧 over-read hinge | weight **3.0** |
| B | 近带 pinball τ=0.9 | weight **2.0** |
| C | consec | 指望 A/B；**不做** shield 滞回 |
| — | 对称 `near_weight` | 本轮 **0** |

验收：`v4_zero_eval --heldout-frac 0.2`；过 ⓪c/d 且 ①d≤0.30。

## 125 上怎么跑（声明 recipe）

```bash
source experiments/aerial/scripts/env_4090.sh
INIT=experiments/aerial/rl/artifacts/depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt
DATA=experiments/aerial/rl/artifacts/dataset_v0_p45_merged_20260821
OUT=experiments/aerial/rl/artifacts/depth_ckpt_p45_hinge_pinball_20260821

python -m experiments.aerial.rl.train_depth_head \
  --dataset "$DATA" --backbone da3 --init-ckpt "$INIT" \
  --steps 2000 --holdout-frac 0.2 --save-ckpt \
  --checkpoint-dir "$OUT" --overwrite \
  --near-weight 0 \
  --near-overread-hinge-weight 3.0 \
  --near-absrel-pinball-weight 2.0 \
  --near-absrel-pinball-tau 0.9

python -m experiments.aerial.rl.v4_zero_eval \
  --dataset "$DATA" \
  --depth-ckpt "$OUT/depth_step_2000_da3_ft_head.pt" \
  --tau-ckpt experiments/aerial/rl/artifacts/tau_ckpt_foe_r60_20260815/tau_foe_calibrator.pt \
  --heldout-frac 0.2 \
  --emit artifacts/v4_zero_p3_hinge_pinball_holdout_20260821.json
```

## Checklist

- [x] 控制臂权威 FAIL / V0 ④ supersede
- [x] `--heldout-frac` + `n_near_forward_frames`
- [x] 跑前声明 + loss 代码（默认关，CLI 开）
- [ ] 125：声明 recipe FT + held-out ⓪
- [ ] 过关后才重跑 V0 ④
- [ ] ⓿e fix

## Artifacts

- 声明：`docs/handover/V4_DEPTH_LOSS_DECLARE_20260821.md`
- 控制臂：`artifacts/v4_zero_p3_oldhead_merged_20260821.json`
