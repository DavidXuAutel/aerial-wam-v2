# V4 RUNBOOK 125 — RESUME at P4 (restart 2026-08-20 ~21:30)

You are on **4090** `cursor-125` / `10.229.20.125`, repo `~/aerial-wam-v2`.

## Mission

1. `git fetch origin && git reset --hard origin/main`
2. Execute `experiments/aerial/RUNBOOK_v4.md` from **P4 through P8** (skip finished steps).
3. Authority = proposal §4.6. Do not invent criteria or freeze `[lo,hi]` from P3 hints.

## Already done (do not re-run)

| Step | Result |
|---|---|
| P0 / P0c / P2 wiring / P6 | DONE |
| P1 | FAIL (reward only) |
| **P3** | **FAIL** — `artifacts/v4_zero_p3_20260820.json`: ⓪a/d/e/f PASS; ⓪b FAIL (95<100 frames); ⓪c FAIL (p90 AbsRel 1.38). `[lo,hi]` **null**. No §6 stop → continue |

## Start: P4 = V4-⓿ v2

Requirements (RUNBOOK §2.2 / §4):
- ⓿a/b/c: Spearman ρ median ≥ 0.50 (`n_z0 ≥ 8`), top-1 ≥ 0.50; **no Pearson**; **no mixed horizon**
- ⓿d: real-side G **hardcoded analytic** (position geometry); imagine side = model
- ⓿e: **measure** whether AirSim teleport can reproduce the same `z0` — do not assume

Machine split: H100 for offline / train pieces; 125 for any renderer / teleport checks. Sync H100 via **git bundle from 125**.

## After P4

Continue in order: **P4.5 → (defer P5) → P7-diag → freeze (needs human `k` if unsigned) → P7-accept → P8**.  
P7-accept S_blocked FAIL ⇒ stop (§6), no P8.  
`enable_policy_update` stays **false**. Push **origin only**.

## Mandatory reporting

- Update `docs/handover/V4_RUNBOOK_125_STATUS.md` at every step; commit + **push origin**.
- Code changes → commit + push + `INFO | code update` in `artifacts/V4_RUNBOOK_125_ISSUES.md`.
- Blockers (unsigned §3 policy blanks you cannot derive) → ISSUES + STATUS **BLOCKED** + push + stop.
- Stay alive across long jobs: write PID/log in STATUS, push, monitor, then continue. **Do not exit** while P4–P8 unfinished unless BLOCKED.
