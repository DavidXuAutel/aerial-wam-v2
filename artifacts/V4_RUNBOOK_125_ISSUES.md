# V4 RUNBOOK 125 — Issues

## RESOLVED 2026-08-20 | §3 item 11 | spare pool size

**Decision (human, Mac chat):** option **1** — conservative fixed buffer.

- **`--spare-count = 16`** for `target_n = 16` (equal-size spare buffer).
- Timestamp: 2026-08-20.
- Written into `experiments/aerial/RUNBOOK_v4.md` §3 row 11.

**Next:** resume P0c formal verification → continue RUNBOOK §1 through **P8** (stop rules in §6 still apply).

---

## INFO | P3 result | 2026-08-20

**V4-⓪ v2 FAIL** (harness `663d8bb` / fix `8a4e851`). Artifact: `artifacts/v4_zero_p3_20260820.json`.

| sub | result | note |
|-----|--------|------|
| ⓪a | PASS | median AbsRel 0.123 |
| ⓪b | FAIL | 95 frames with near px (<100) |
| ⓪c | FAIL | p90 AbsRel 1.38 |
| ⓪d | PASS | p_miss_trigger 0 |
| ⓪e | PASS | deployment corpus |
| ⓪f | PASS | outer band + sweep; `[lo,hi]` null |

No §6 stop for ⓪ FAIL (R-16) → chain continues at P4.

---

**P3 harness:** `experiments/aerial/rl/v4_zero_eval.py` — offline V4-⓪ v2 (⓪a–⓪f), clearance sweep with `band_lo_hi=null` pre-freeze.

---

## INFO | code update | 2026-08-20 | `4e76865`

**P2 partial + P6:** collector/gate shield path passes `wm_out` (live `p_coll`) to `should_override`; `_build_planner` clips candidates via `body_delta_limits(1/step_hz)`.

Files: `collector.py`, `train_rl.py`, `v0_rollout_eval.py`, `v4_episode_pool.py`, `v4_gate_run_partials.py`, `test_action_space_consistency.py`.

**Remaining P2:** p_coll head AUROC + H100 retrain (if needed) — wiring only on 125 side.

---

## INFO | P4 result | 2026-08-20

**V4-⓿ v2 FAIL** (overall; ⓿a–d PASS). Harness `9f0cc1f` / `experiments/aerial/rl/v4_rho_eval.py`.

| sub | result | note |
|-----|--------|------|
| ⓿a | PASS | median Spearman ρ **0.963** (n_z0=16) |
| ⓿b | PASS | top-1 hit rate **1.0** |
| ⓿c | PASS | Spearman only, H=15 |
| ⓿d | PASS | real=analytic_progress_sum, imag=imagine_reward_sum |
| ⓿e | **FAIL** | double-teleport `median_rel_l2=1.37` (threshold 0.05) |

Artifacts: `artifacts/v4_rho_p4_20260820.json`, `artifacts/v4_rho_p4_z0e_20260820.json`. Log: `logs/v4_p4_full_20260820.log`.

No §6 stop for ⓿ FAIL (R-16) → chain continues at **P4.5**.

---

## BLOCKED | freeze prerequisites | §3 #3 / #7 / #8

**Unsigned human-policy blanks** (agent must not invent):

| item | status |
|------|--------|
| `k` (progress window = C1 window?) | ⬜ unsigned |
| primary/secondary criterion list | ⬜ unsigned |
| OC curves + seed arbitration | ⬜ unsigned |

P7-diag can proceed; **band/θ/k freeze** may BLOCK until human fills these.

---
