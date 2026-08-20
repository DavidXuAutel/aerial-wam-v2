# V4 RUNBOOK 125 — Issues

## RESOLVED 2026-08-20 | §3 item 11 | spare pool size

**Decision (human, Mac chat):** option **1** — conservative fixed buffer.

- **`--spare-count = 16`** for `target_n = 16` (equal-size spare buffer).
- Timestamp: 2026-08-20.
- Written into `experiments/aerial/RUNBOOK_v4.md` §3 row 11.

**Next:** resume P0c formal verification → continue RUNBOOK §1 through **P8** (stop rules in §6 still apply).

---

## Open

_(none at sign-off time; agent appends new blockers below)_

---

## INFO | code update | 2026-08-20 | `4e76865`

**P2 partial + P6:** collector/gate shield path passes `wm_out` (live `p_coll`) to `should_override`; `_build_planner` clips candidates via `body_delta_limits(1/step_hz)`.

Files: `collector.py`, `train_rl.py`, `v0_rollout_eval.py`, `v4_episode_pool.py`, `v4_gate_run_partials.py`, `test_action_space_consistency.py`.

**Remaining P2:** p_coll head AUROC + H100 retrain (if needed) — wiring only on 125 side.

