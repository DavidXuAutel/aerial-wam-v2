# V4 RUNBOOK 125 STATUS

- **date**: 2026-08-20
- **state**: ACTIVE — agent restarted; resume at P3
- **HEAD**: 663d8bb
- **current step**: P3 in flight (H100 offline eval)
- **P3 job**: H100 pid=39936; log `~/aerial-wam-v2/logs/v4_p3_zero_20260820.log`; emit `artifacts/v4_zero_p3_20260820.json`
- **enable_policy_update**: false (must remain)
- **signed**: `--spare-count = 16` (§3 item 11, option 1)

## Checklist

- [x] Reviewed `experiments/aerial/RUNBOOK_v4.md`
- [x] P0c harness + unit tests
- [x] P0c formal `--target-n 16 --spare-count 16` — DONE (`v4_gate_p0c_formal_20260820/`; n=16 authoritative; counters present). ①/④ signal ok=False on old actor is expected.
- [x] P1 V1-② on RH WM — **FAIL** (logged; no §6 stop)
- [x] P2 partial wiring (`4e76865`)
- [ ] P3 V4-⓪ v2 (⓪a–⓪f)
- [ ] P4 V4-⓿ v2
- [ ] P4.5 corpus + WM retrain + re-run P1/P4
- [x] P6 action_limits
- [ ] P7-diag → freeze → P7-accept → P8

## Notes

- Previous agent died with stale “P0c in flight”; Mac restart 2026-08-20 ~20:35.
- Human-policy blanks still open: `k`, primary list, OC seed rules, freeze-list numerics.
