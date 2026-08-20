# V4 RUNBOOK 125 STATUS

- **date**: 2026-08-20
- **state**: **BLOCKED** — §3 item 11 spare pool size unsigned (`--spare-count` required)
- **HEAD**: pending commit (base `a961979`)
- **current step**: P0c harness **DONE** (code + unit tests); formal gate run **blocked** on spare-count sign-off
- **enable_policy_update**: false (must remain)

## RUNBOOK review (2026-08-20)

- **P0 DONE** ✅ — R1 landed; calib ratio 1.00 PASS (`30b9ff8` / `d96da1d`)
- **Next in chain**: P0c (implemented) → **P1** (blocked until spare-count signed for any authoritative gate)
- **§3 items still ⬜ that block P0c formal verification vs can wait**:
  - **Blocks P0c gate run**: #11 spare pool size (this BLOCKED state)
  - **Can wait (later steps)**: #1 `[lo,hi]`, #2 `θ`, #3 `k`, #4 `Q_0.25(C_P7)`, #7 primary list, #8 OC curves/seeds, #9 spacing check, #12 freeze list numerics, #15 blind-arm implementation
  - **Already signed**: #5 5ab fork, #6 band vs P2, #10 start-set relations, #13 R≥3, #14 Δ=0, #16 arrival def

## Checklist

- [x] Reviewed `experiments/aerial/RUNBOOK_v4.md`
- [x] P0c harness: `v4_episode_pool.py` + `v4_gate_run_partials.py` integration
- [x] P0c unit tests (`test_v4_episode_pool.py`)
- [x] P0c renderer self-check (`target-n=2 --spare-count=2`, stub dynamics; counters + spare refill verified)
- [ ] P1 …

## P0c deliverables

| Item | Status |
|------|--------|
| `n_invalid_spawn` / `n_none_returned` / `n_pair_broken` counters | ✅ `EpisodeDropCounters` |
| Spare manifest frozen before run | ✅ `p0c_spare_manifest.json` |
| Refill to `target_n=16` without lowering n | ✅ `fill_to_target_n` |
| `authoritative=false` + counters when short | ✅ in partial JSON |
| `--spare-count` required CLI | ✅ exit 2 if missing |
| Spare pool size policy | ⬜ **ISSUE filed** → `artifacts/V4_RUNBOOK_125_ISSUES.md` |
