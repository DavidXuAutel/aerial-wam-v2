# V4 RUNBOOK 125 — P4→P8 NO EARLY EXIT

You are on **4090** `cursor-125`, repo `~/aerial-wam-v2`.

## HARD RULE (human 2026-08-20): do not stop until P8

**Forbidden:** exiting after finishing only P4 / P4.5 / P7 / docs / one FAIL log.
**Allowed exit conditions (only these):**
1. **P8 complete** (actor train + gate ①′/④′ attempted; STATUS checklist P8 checked; commit+push), OR
2. **BLOCKED** with ISSUES pushed (unsigned human-policy blank you must not invent), OR
3. **RUNBOOK §6 stop** (P7-accept S_blocked FAIL → no P8).

If a long job is running: write PID/log to STATUS, push, **wait/poll until done**, then continue the next step in the **same session**. Prefer `nohup` + polling over exiting.

After any step FAIL that has **no §6 stop** (P1/P3 style, R-16): **log and continue** — do not exit.

## Mission

1. `git fetch origin && git reset --hard origin/main` (unless you have unpushed WIP — then commit+push first).
2. Read `docs/handover/V4_RUNBOOK_125_STATUS.md` for `current step`; resume there.
3. Run `experiments/aerial/RUNBOOK_v4.md` through **P8 inclusive**.
4. Authority = proposal §4.6. Never invent criteria. Never freeze `[lo,hi]` from P3 diag hints alone. Never flip `enable_policy_update`. Origin-only push.

## Done already

- P0 / P0c / P2 wiring / P6 DONE
- P1 FAIL (reward only)
- P3 FAIL (⓪b/⓪c; ⓪f PASS; `[lo,hi]` null) — continue

## Chain

**P4** (⓿a–e; ⓿e teleport z0 measured) → **P4.5** → defer P5 → **P7-diag** → freeze (BLOCKED if `k`/primary/OC need human) → **P7-accept** → **P8**.

## Reporting

STATUS + ISSUES + commit + push origin at every step boundary and before any wait.
