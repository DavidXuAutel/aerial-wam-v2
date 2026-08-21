# V4 RUNBOOK 125 STATUS

- **date**: 2026-08-21
- **state**: ACTIVE — **v2 代码已落地**；下一步 = **H100** 按 v2 recipe 开训（不开 4090）
- **enable_policy_update**: false
- **R-16**: **(B)**

## 已实现（declare v2 + #19/#20）

- `experiments/aerial/rl/holdout_split.py` — 训/评同一 seeded 切法  
- `train_depth_head` 写 `holdout_split.json`；`v4_zero_eval --expect-holdout-split` assert  
- `fwd_overread_hinge_weight` + `near_absrel_p90_weight` + early-stop / lr-drop  
- `center_frac=0.5` 冻结（硬 min，无 softmin）

## H100 开训命令（声明 v2）

```bash
# sync repo + dataset_v0_p45_merged_20260821 first
source …  # H100 env
INIT=…/depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt
DATA=…/dataset_v0_p45_merged_20260821
OUT=…/depth_ckpt_p45_v2_fwd_hinge_20260821

python -m experiments.aerial.rl.train_depth_head \
  --dataset "$DATA" --backbone da3 --init-ckpt "$INIT" \
  --steps 800 --holdout-frac 0.2 --split-seed 0 --save-ckpt \
  --checkpoint-dir "$OUT" --overwrite \
  --declare-id v2-20260821 \
  --near-weight 0 \
  --fwd-overread-hinge-weight 3.0 \
  --near-absrel-p90-weight 2.0 --near-absrel-p90-tau 0.9 \
  --early-stop-on-fwd-saturate \
  --device cuda

# 主表 = FT 诚实 holdout（须 MATCH）
python -m experiments.aerial.rl.v4_zero_eval \
  --dataset "$DATA" --depth-ckpt "$OUT/depth_step_800_da3_ft_head.pt" \
  --tau-ckpt …/tau_foe_calibrator.pt \
  --heldout-frac 0.2 --split-seed 0 \
  --expect-holdout-split "$OUT/holdout_split.json" \
  --emit artifacts/v4_zero_p3_v2_holdout_20260821.json

# 附表：全 77（老头权威切片对照时用 heldout-frac=0）
```

**权威过线**：FT 头 → 与训练互斥的 holdout；老头 → 全 77（`heldout-frac=0`）。

## Checklist

- [x] v2 代码（切法 + loss + early-stop）
- [ ] H100：v2 FT + 主表/附表 ⓪
- [ ] 过关后 V0 ④
- [ ] ⓿e fix

## Running jobs

| job | PID | log |
|-----|-----|-----|
| (none) | — | — |
