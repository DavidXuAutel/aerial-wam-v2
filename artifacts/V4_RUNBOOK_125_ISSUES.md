# V4 RUNBOOK 125 — Issues

## 2026-08-20 | §3 item 11 | blocker | spare pool size undetermined

**Step:** P0c (pre-freeze)

**Severity:** blocker (for formal gate runs; harness code is implemented)

**Evidence:**
- `experiments/aerial/RUNBOOK_v4.md` §3 row 11: spare pool size **⬜ 待定量**
- `docs/handover/V4_CRITERIA_REFREEZE_PROPOSAL_20260818.md` §4.6.10 V5: "P0c spare 池大小未定量"
- Empirical eval-period drop (not scan): gate `accepted` 9→`scored` 5 (~44%) per `LIVING_DOCS.md` / `V4_GATE_STATUS.md` (seed=0); cos diag same construct n=7/8 (seed=1, zero drops)

**Implemented (not blocked):**
- `experiments/aerial/rl/v4_episode_pool.py` — three counters + spare manifest + refill
- `experiments/aerial/scripts/v4_gate_run_partials.py` — wired P0c; **`--spare-count` required** (no default)

**Proposed human decision:**
Choose and timestamp `--spare-count` before any authoritative gate run. Options to sign:
1. **Conservative fixed buffer** (e.g. 16 spares for n=16) — simple, may overscan
2. **Empirical upper bound** from P0c diag runs at `--target-n 16` with increasing spare until 0 drops in R≥3 seeds
3. **Formula** tied to observed eval drop rate p: spare ≥ ceil(n × p / (1−p)) at chosen confidence (needs p measured on target construct)

Until signed, rollout4090 exits 2 without `--spare-count`; do not treat gate output as authoritative.
