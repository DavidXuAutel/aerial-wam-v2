# V4 RUNBOOK 125 STATUS

- **date**: 2026-08-21
- **state**: ACTIVE — **merge DONE**; depth FT → WM → re-P3/P1 **in flight**
- **HEAD**: `50762a9`
- **enable_policy_update**: false
- **R-16**: **(B)**

## Checklist

- [x] P4.5 v1 + 补采 (open 24 + near 19)
- [x] **merge usable** → `dataset_v0_p45_merged_20260821` (**77** eps；open **35** / blocked **42**)
- [ ] depth FT → `depth_ckpt_p45_merged_20260821`
- [ ] WM train → `wm_ckpt_p45_merged_20260821`
- [ ] re-P3 / re-P1
- [ ] ⓿e fix (orthogonal)
- [ ] freeze / P7-accept / P8

## Running jobs

| job | PID | log |
|-----|-----|-----|
| merge→depth→WM→P3→P1 | **2088190** (`train_depth_head`) | `logs/v4_p45_merge_retrain_eval_20260821.log` |

## Pipeline

`experiments/aerial/scripts/v4_p45_merge_retrain_eval.sh` (`50762a9`)

1. Merge usable-only (skip 1 quarantined)
2. Depth FT 2000 steps from r60 da3 (`--lr 3e-5`)
3. WM 500 steps `--heldout-frac 0.25`
4. P3 → `artifacts/v4_zero_p3_p45_merged_20260821.json`
5. P1 → `logs/v4_p1_p45_merged_20260821.log`

## Notes

- Depth train expected ~1–3 h on 4090; do not interrupt.
- ⓿e not in this pipeline.
