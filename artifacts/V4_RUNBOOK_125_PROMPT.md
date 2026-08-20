# V4 RUNBOOK 125 — RESUME through P8 (restart 2026-08-20 evening)

You are on **4090 host** `cursor-125` / `10.229.20.125`, repo `~/aerial-wam-v2`.

## Why restart

Previous agent exited ~15:59 while STATUS still said “P0c formal running”.
**P0c formal actually finished ~16:51** and left artifacts. No new commits after `0c37bad`. Chain stalled. You must resume and **not re-do finished work** unless verification fails.

## Mission

1. `git fetch origin && git reset --hard origin/main` (then continue from tip).
2. `source experiments/aerial/scripts/env_4090.sh` for Aerial / gate / renderer.
3. Execute `experiments/aerial/RUNBOOK_v4.md` §1 **in order through P8 inclusive**.
4. Authority = `docs/handover/V4_CRITERIA_REFREEZE_PROPOSAL_20260818.md` §4.6. Do not invent criteria.

## Already done (verify, then mark DONE in STATUS — do not re-run unless broken)

| Step | Evidence |
|---|---|
| **P0c harness** | commits `e28baa9` + tests |
| **P0c formal** `--target-n 16 --spare-count 16` | `experiments/aerial/rl/artifacts/v4_gate_p0c_formal_20260820/` — spare manifest; `v4_partial_{1,4}_*.json` with `n_scored=16`, `authoritative=true`, counters `n_invalid_spawn` / `n_none_returned` / `n_pair_broken`. Log: `logs/v4_p0c_formal_20260820.log` (ended ~16:51). Signal ①/④ `ok=False` is **expected** on old actor — does **not** undo P0c PASS. |
| **P1** V1-② RH WM | **FAIL** logged (`reward beat_frac=0.67`, `p_coll AUROC=0.091`); no §6 stop → continue |
| **P2 wiring** | `4e76865` — `wm_out` into `should_override` (head still weak) |
| **P6** | `4e76865` — planner `action_limits = body_delta_limits(1/step_hz)` |
| **§3 #11** | `--spare-count=16` signed |

## First actions after start

1. Update `docs/handover/V4_RUNBOOK_125_STATUS.md`: P0c formal **DONE**; clear stale “in flight”; set **current step = P3** (next unfinished).
2. Commit + **push origin** that STATUS fix immediately (Mac chat is watching).
3. Proceed: **P3 → (skip P3.5) → P4 → P4.5 → (defer P5) → P7-diag → freeze → P7-accept → P8**.
4. Stay alive across long jobs: if you start a long H100/125 job, write STATUS with PID/log path, push, then wait/monitor; on completion update STATUS again and push. **Do not exit** while the chain is unfinished unless **BLOCKED**.

## Signed / fixed rules

- `--spare-count = 16` for `target_n = 16`.
- P3.5 = N/A. P5 = deferred. `enable_policy_update` = **false** always.
- Push **origin only** (no GitHub). No Franka / Desk / `10.229.66.70`.
- Code/docs changes → commit + push origin + STATUS; material changes also `INFO | code update` in `artifacts/V4_RUNBOOK_125_ISSUES.md`.
- Blockers → ISSUES + STATUS **BLOCKED** + push + stop (no inventing `k` / primary list / OC rules / freeze numerics).
- **P7-accept S_blocked FAIL** ⇒ do not enter P8; ISSUES + push + stop (§6).

## Machine split

- **125**: gate / planner / closed-loop / P7* / P8 gate.
- **H100** (`ssh h100-25`): P3 offline / P4 / P4.5 / P8 train. Sync via **git bundle from 125**.

## Deliverables

- Continuous STATUS + ISSUES updates pushed to origin after every step boundary.
