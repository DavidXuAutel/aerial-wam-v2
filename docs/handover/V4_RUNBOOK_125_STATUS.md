# V4 RUNBOOK 125 STATUS

- **date**: 2026-08-20
- **state**: ACTIVE — restarted for P4
- **HEAD**: (agent fills after pull)
- **current step**: P4 V4-⓿ v2
- **P3 result**: **FAIL** — `artifacts/v4_zero_p3_20260820.json`（⓪b/⓪c FAIL；⓪a/d/e/f PASS；`[lo,hi]` null）
- **enable_policy_update**: false (must remain)
- **signed**: `--spare-count = 16`

## Checklist

- [x] P0c / P1 FAIL / P2 wiring / P3 FAIL / P6
- [ ] **P4** V4-⓿ v2（含 ⓿d analytic G、⓿e teleport z0 实测）
- [ ] P4.5 → P7* → P8

## Notes

- Living docs synced: next = P4. No §6 stop on P3 FAIL (R-16).
- Do not invent `[lo,hi]` from P3 diag hint (lo≈4.5 is diagnostic only).
