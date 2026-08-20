# V4 RUNBOOK 125 STATUS

- **date**: 2026-08-20
- **state**: ACTIVE — spare signed; resume through P8
- **HEAD**: (agent fills after pull)
- **current step**: P0c formal verify → … → P8
- **enable_policy_update**: false (must remain)
- **signed**: `--spare-count = 16` (§3 item 11, option 1)

## Checklist

- [x] Reviewed `experiments/aerial/RUNBOOK_v4.md`
- [x] P0c harness + unit tests
- [ ] P0c formal / authoritative path with `--spare-count 16`
- [ ] P1 … through P8 (see RUNBOOK §1; P3.5 N/A; P5 deferred)

## Notes for agent

Update this file at every step boundary. On blocker: append `artifacts/V4_RUNBOOK_125_ISSUES.md`, set **BLOCKED**, commit + **push origin**.
