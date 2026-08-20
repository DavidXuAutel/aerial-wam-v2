# V4 RUNBOOK 125 STATUS

- **date**: 2026-08-20
- **state**: ACTIVE — P4 done; P4.5 in progress
- **HEAD**: `9f0cc1f` (+ local P4 artifacts)
- **current step**: P4.5 corpus + WM retrain
- **P4 result**: **FAIL** — `artifacts/v4_rho_p4_20260820.json`（⓿a/b/c/d PASS；⓿e FAIL teleport z0 repro；harness `9f0cc1f`）
- **enable_policy_update**: false (must remain)
- **signed**: `--spare-count = 16`

## Checklist

- [x] P0c / P1 FAIL / P2 wiring / P3 FAIL / P6
- [x] **P4** V4-⓿ v2 — ⓿a median ρ **0.963** / top-1 **1.0** / ⓿c/d PASS；**⓿e FAIL** (`median_rel_l2=1.37`); no §6 stop (R-16)
- [ ] P4.5 → P7* → P8

## Running jobs

| job | PID | log |
|-----|-----|-----|
| (none yet) | — | — |

## Notes

- P4 harness: `experiments/aerial/rl/v4_rho_eval.py`; ⓿e artifact `artifacts/v4_rho_p4_z0e_20260820.json`.
- ⓿e: double-teleport latent rel-L2 >> threshold (render/encode non-determinism); ranking used offline dataset z0 (valid for ⓿a–d).
- Next: P4.5 H100 WM retrain + P7-diag harness; freeze may BLOCK on unsigned `k` / primary list / OC (§3 #3/#7/#8).
