# V4 RUNBOOK 125 STATUS

- **date**: 2026-08-20
- **state**: ACTIVE — P0c formal run in flight; P1 on H100
- **HEAD**: (pending commit for P2/P6)
- **current step**: P0c formal verify (running) → P1 (H100) → … → P8
- **enable_policy_update**: false (must remain)
- **signed**: `--spare-count = 16` (§3 item 11, option 1)

## Checklist

- [x] Reviewed `experiments/aerial/RUNBOOK_v4.md`
- [x] P0c harness + unit tests
- [ ] P0c formal / authoritative path with `--spare-count 16` (run in progress)
- [ ] P1 V1-② on RH WM (H100 `_wm_fidelity_eval` running)
- [x] P2 partial: collector + gate pass `wm_out` to `should_override` (code; AUROC train TBD)
- [ ] P3 … P4.5
- [x] P6: `_build_planner` sets `action_limits = body_delta_limits(1/step_hz)`
- [ ] P7-diag → freeze → P7-accept → P8

## In-flight jobs (2026-08-20)

| Job | Host | Log |
|---|---|---|
| P0c formal `--target-n 16 --spare-count 16` | 125 | `logs/v4_p0c_formal_20260820.log` |
| P1 V1-② fidelity RH WM | H100 | `~/aerial-wam-v2/artifacts/v4_p1_fidelity_rh_20260820.log` |

## Notes

- H100 synced via git bundle `22bb986`.
- §3 item 11 resolved; spare-count=16 signed.
- Human-policy blanks still open: `k`, primary list, OC seed rules, freeze-list numerics (see RUNBOOK §3).
