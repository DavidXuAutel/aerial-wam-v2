# V4 RUNBOOK 125 STATUS

- **date**: 2026-08-21
- **state**: ACTIVE — merge+retrain+re-eval **DONE**; ⓪/P1 still not fully PASS
- **HEAD**: `8062b40`
- **enable_policy_update**: false
- **R-16**: **(B)**

## Checklist

- [x] P4.5 v1 + 补采
- [x] merge usable → `dataset_v0_p45_merged_20260821` (**77**；open 35 / blocked 42)
- [x] depth FT → `depth_ckpt_p45_merged_20260821/depth_step_2000_da3_ft_head.pt`（holdout AbsRel **0.113**)
- [x] WM → `wm_ckpt_p45_merged_20260821/wm_step_500.pt`（①a–c PASS）
- [x] re-P3 / re-P1（见下）
- [ ] ⓪c/⓪d/⓪f + P1 coll 仍 FAIL → 下一治
- [ ] ⓿e fix（orthogonal）
- [ ] freeze / P7-accept / P8

## re-P3 (`artifacts/v4_zero_p3_p45_merged_20260821.json`)

| 子项 | 结果 | 数 |
|------|------|-----|
| ⓪a | PASS | median AbsRel **0.144** |
| ⓪b | PASS | near frames **315**；`max_frame_frac=0.024`；px 1.54e6 |
| ⓪c | **FAIL** | p90 AbsRel **0.792** > 0.50 |
| ⓪d | **FAIL** | miss **0.142** > 0.05；max_consec_miss=4 |
| ⓪e | PASS | deployment corpus |
| ⓪f | **FAIL** | outer p90 **0.504** >（外带精度/误触合取未过） |

## re-P1 (`logs/v4_p1_p45_merged_20260821.log`)

- **reward PASS**：`beat_frac=0.93`（was 0.67）；`growth_ok=True`；h=0 `0.330 < 0.907` → **`one_step_ok=True`**
- **p_coll FAIL（claimed）**：pos=**3** (≥3) AUROC **0.549**
- done vacuous OK；recon OK（latent_norm_max 21.85）
- ⇒ overall **FAIL** 现由 **coll** 支撑（reward 已修好）

## Running jobs

| job | PID | log |
|-----|-----|-----|
| (none) | — | — |

## Notes

- Launch SSH 曾 exit 1；流水线实际跑完 depth/WM/P3；P3 `set -e` 曾跳过 P1 → 已补跑 P1（`8062b40` 修脚本）。
- 相对 P4.5 v1：reward 过了；近带 support 更强；**精度尾（⓪c）与漏触发（⓪d）变差/仍挂**；⓪f 新 FAIL。
- 下一步候选：针对 <1.5 m / 漏触发再治 depth（或语料），**不动阈值**；coll 头需更多正例或重训。
