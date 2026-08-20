# V4 RUNBOOK 125 STATUS

- **date**: 2026-08-20
- **state**: **BLOCKED** at freeze — unsigned §3 #3/#7/#8; P7-diag in flight
- **HEAD**: `7b7b367`
- **current step**: freeze BLOCKED → no P7-accept / P8 until human signs `k`, primary list, OC
- **enable_policy_update**: false (must remain)
- **signed**: `--spare-count = 16`

## Checklist

- [x] P0c / P1 FAIL / P2 wiring / P3 FAIL / P6
- [x] **P4** — ⓿a–d PASS / **⓿e FAIL** (teleport z0 repro); harness `9f0cc1f`
- [x] **P4.5 partial** — WM retrain PASS on 4090 (`wm_ckpt_p45_20260820/wm_step_300.pt`); **no new 1:1 corpus** (H100 sync failed)
- [ ] P7-diag (running)
- [ ] freeze / P7-accept / P8 — **BLOCKED**

## Running jobs

| job | PID | log |
|-----|-----|-----|
| P7-diag | see `pgrep -f v4_p7_diag` | `logs/v4_p7_diag_20260820.log` |

## Results summary

| step | verdict | artifact |
|------|---------|----------|
| P4 | FAIL (⓿e) | `artifacts/v4_rho_p4_20260820.json` |
| P4.5 WM | PASS (learning+non-div) | `artifacts/wm_ckpt_p45_20260820/` |
| P7-diag | in progress | `artifacts/v4_p7_diag_20260820.json` (pending) |

## BLOCKED reason

§3 items **#3 `k`**, **#7 primary/secondary list**, **#8 OC curves** are unsigned — agent must not invent. See `artifacts/V4_RUNBOOK_125_ISSUES.md`.

## Notes

- H100 `git fetch cursor125` failed (SSH keys); P4.5 WM retrain ran on **4090** instead.
- P4.5 corpus re-collect (S_open:S_blocked ≈ 1:1) **not done** — WM retrain used existing `dataset_v0_local_depth_r60_20260814`.
- After P7-diag completes: mechanical `[lo,hi]` from P3 ⓪f + `Q_0.25(C_P7)` can be drafted, but **θ/k freeze still BLOCKED**.
