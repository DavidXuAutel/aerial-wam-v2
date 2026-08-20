# V4 RUNBOOK 125 STATUS

- **date**: 2026-08-20
- **state**: ACTIVE — P0c formal run in flight; P1 FAIL logged; P2/P6 code pushed
- **HEAD**: `e183a26`
- **current step**: P0c formal verify (running) → P1 **FAIL** (logged) → P2 wiring done → …
- **enable_policy_update**: false (must remain)
- **signed**: `--spare-count = 16` (§3 item 11, option 1)

## Checklist

- [x] Reviewed `experiments/aerial/RUNBOOK_v4.md`
- [x] P0c harness + unit tests
- [ ] P0c formal / authoritative path with `--spare-count 16` (run in progress)
- [x] P1 V1-② on RH WM — **FAIL** (`reward beat_frac=0.67`, `p_coll AUROC=0.091`); log `artifacts/v4_p1_fidelity_rh_20260820.log`. No RUNBOOK §6 stop rule for P1; continue chain, WM weakness noted.
- [x] P2 partial: collector + gate pass `wm_out` to `should_override` (code; p_coll head still FAIL per P1)
- [ ] P3 … P4.5
- [x] P6: `_build_planner` sets `action_limits = body_delta_limits(1/step_hz)`
- [ ] P7-diag → freeze → P7-accept → P8

## In-flight jobs (2026-08-20)

| Job | Host | Log |
|---|---|---|
| P0c formal `--target-n 16 --spare-count 16` | 125 | `logs/v4_p0c_formal_20260820.log` (running) |
| P1 V1-② fidelity RH WM | H100 | `artifacts/v4_p1_fidelity_rh_20260820.log` (**FAIL**, done) |

## Notes

- H100 synced via git bundle `22bb986`.
- §3 item 11 resolved; spare-count=16 signed.
- Human-policy blanks still open: `k`, primary list, OC seed rules, freeze-list numerics (see RUNBOOK §3).
