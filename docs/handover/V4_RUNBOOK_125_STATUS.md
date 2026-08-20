# V4 RUNBOOK 125 STATUS

- **date**: 2026-08-20
- **state**: **BLOCKED at freeze** — `lo>hi` conflict + §3 #3/#7/#8 unsigned
- **HEAD**: `c45e781` (+ `fed447c` pending)
- **current step**: freeze BLOCKED → **no P7-accept / P8**
- **P3 (post-P4.5)**: ⓪b **PASS** (150 frames); ⓪c/⓪d FAIL; `[lo,hi]=null` — `artifacts/v4_zero_p3_p45_20260820.json`
- **P1 (post-P4.5)**: **FAIL** reward `beat_frac=0.67`; `one_step_ok=True` — `logs/v4_p1_p45_20260820.log`
- **P4 (post-P4.5)**: ⓿a–d PASS; **⓿e FAIL** (`rel_l2=1.39`) — `artifacts/v4_rho_p4_p45_balanced_20260820.json`
- **enable_policy_update**: false
- **R-16**: **(B)** — none of ⓪/⓿/P1 fully authoritative PASS
- **signed**: `--spare-count=16`

## Checklist

- [x] P0c / P2 wiring / P6
- [x] **P4.5** — corpus 34 eps + WM `wm_step_500.pt` PASS
- [x] re-P3 / re-P1 / re-P4
- [x] **P7-diag** — `C_P7.p25=4.859 m`, n_scored=16
- [ ] freeze — **BLOCKED** (`lo≈5.25` > `Q_0.25=4.86`; `k`/primary/OC unsigned)
- [ ] P7-accept / P8 — not started

## Running jobs

| job | PID | log |
|-----|-----|-----|
| (none) | — | — |

## Key artifacts

| step | path |
|------|------|
| P4.5 corpus | `experiments/aerial/rl/artifacts/dataset_v0_p45_balanced_20260820/` |
| WM | `experiments/aerial/rl/artifacts/wm_ckpt_p45_balanced_20260820/wm_step_500.pt` |
| P3 | `artifacts/v4_zero_p3_p45_20260820.json` |
| P4 | `artifacts/v4_rho_p4_p45_balanced_20260820.json` |
| P7-diag | `artifacts/v4_p7_diag_p45_20260820.json` |

## Freeze blocker (mechanical)

- `Q_0.25(C_P7)` = **4.859 m**
- ⓪f `suggested_lo_clearance_m` = **5.25 m** (diagnostic only in P3; not frozen)
- ⇒ **`lo > hi`** under §4.6 rules — human re-freeze or sign required

## Notes

- P7-diag planner arrival **0/16** on S_blocked diag set — if unblocked, P7-accept likely §6 stop.
- Open corpus layer 11/24 (not 1:1); ⓪b support gate cleared (150 near frames).
