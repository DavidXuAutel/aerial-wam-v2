# V4 RUNBOOK 125 STATUS

- **date**: 2026-08-20
- **state**: ACTIVE — P3 in flight; living docs synced
- **HEAD**: (after Mac docs merge)
- **current step**: P3 in flight (H100 offline eval, retry after broadcast fix)
- **P3 job**: H100 pid=40433; log `~/aerial-wam-v2/logs/v4_p3_zero_20260820.log`; emit `artifacts/v4_zero_p3_20260820.json`
- **enable_policy_update**: false (must remain)
- **signed**: `--spare-count = 16` (§3 item 11, option 1)

## Checklist

- [x] Reviewed `experiments/aerial/RUNBOOK_v4.md`
- [x] P0c harness + unit tests (`e28baa9`)
- [x] P0c formal `--target-n 16 --spare-count 16` — DONE (`v4_gate_p0c_formal_20260820/`; counters in RUNBOOK §1)
- [x] P1 V1-② — **FAIL** (reward only per §1.2.2; log `artifacts/v4_p1_fidelity_rh_20260820.log`)
- [x] P2 wiring (`4e76865`) — head AUROC claimed still open
- [ ] P3 V4-⓪ v2 (⓪a–⓪f) — harness `663d8bb`; H100 retry after `8a4e851` broadcast fix
- [ ] P4 / P4.5
- [x] P6 action_limits (`4e76865`)
- [ ] P7-diag → freeze → P7-accept → P8

## Notes

- Living docs (Mac): RUNBOOK / V4_GATE_STATUS / LIVING_DOCS / PROJECT_STATUS record P0c–P6 progress; **下一步 = P3**.
- Human-policy blanks still open: `k`, primary list, OC seed rules, freeze-list numerics.
