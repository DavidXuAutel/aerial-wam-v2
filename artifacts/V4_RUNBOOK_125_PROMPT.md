# V4 RUNBOOK 125 — continue through P8

You are on **4090 host** `cursor-125` / `10.229.20.125`, repo `~/aerial-wam-v2`.

## Mission

1. `git fetch origin && git reset --hard origin/main` (Mac just pushed spare sign-off).
2. `source experiments/aerial/scripts/env_4090.sh` when running Aerial / gate / renderer work.
3. Execute `experiments/aerial/RUNBOOK_v4.md` §1 **in order** from current tip through **P8 inclusive**.
4. Authority = `docs/handover/V4_CRITERIA_REFREEZE_PROPOSAL_20260818.md` §4.6. Do not invent criteria.

## Human decisions already signed (do not re-ask)

- **§3 item 11**: `--spare-count = 16` for `target_n = 16` (option 1, 2026-08-20).
- Use this on all authoritative / formal gate runs that need spare refill.
- P3.5 = N/A. P5 = deferred. `enable_policy_update` stays **false** forever in this mission.
- Do **not** push GitHub. Push **origin only** (`cursor-125` bare).
- Franka / Desk API / `10.229.66.70`: never touch.

## Code-update rule (mandatory — Mac chat is waiting)

Whenever you **change code or docs**:

1. Commit on `main` with a clear message.
2. `git push origin main`.
3. Update `docs/handover/V4_RUNBOOK_125_STATUS.md` (HEAD, step, checklist).
4. If the change is material (behavior / API / gate fields), also append a short note under `artifacts/V4_RUNBOOK_125_ISSUES.md` as `INFO | code update` with commit SHA + files, then push — so the Mac conversation can pull and review.

Do **not** leave code only on the 125 working tree.

## Blocker rule

On any unsigned §3 item, missing machine access, FAIL that hits RUNBOOK §6 stop, or ambiguity you must not invent:

1. Append `artifacts/V4_RUNBOOK_125_ISSUES.md` (severity, evidence, options).
2. Set STATUS **BLOCKED**.
3. Commit + **push origin**.
4. Stop that branch of work; do not guess policy.

## Stop rules (RUNBOOK §6)

- **P7-accept S_blocked FAIL** ⇒ do **not** enter P8; write STATUS + ISSUES; push; stop.
- Never lower n, never flip flags to force PASS, never warm-start failed actor ckpts for P8.

## Machine split

- **125**: renderer / gate / planner / closed-loop / P0c verify / P6 / P7* / P8 gate.
- **H100** (`ssh h100-25` from 125): P1 / P2 training / P3 offline / P4 / P4.5 / P8 actor train.
- Sync H100 via **git bundle from 125**, not ad-hoc scp hot patches.

## Start here

1. Mark §3 #11 resolved in STATUS; close the old ISSUES blocker (already done on tip — verify).
2. Finish **P0c** formal verification with `--spare-count 16` (counters on disk, spare manifest, no n-lowering).
3. Proceed **P1 → P2 → P3 → (skip P3.5) → P4 → P4.5 → (skip/defer P5) → P6 → P7-diag → freeze `[lo,hi]`/θ/k per RUNBOOK → P7-accept → P8**.
4. For §3 blanks that are **data-fill only** after measurement: fill + timestamp. For **human-policy** blanks (`k`, primary list, OC seed rules, freeze-list numerics you cannot derive): **BLOCKED → ISSUES → push**.

## Deliverables continuously

- `docs/handover/V4_RUNBOOK_125_STATUS.md`
- `artifacts/V4_RUNBOOK_125_ISSUES.md` (blockers + INFO code-update notes)
- Commits pushed to **origin** after every meaningful step
