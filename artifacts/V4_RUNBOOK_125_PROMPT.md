# V4 RUNBOOK 125 — P4.5 only (NO continuous P8)

You are on **4090** `cursor-125`, repo `~/aerial-wam-v2`.

## HARD STOP on previous “run to P8” order

Mac chat **revoked** continuous-to-P8 / supervisor relaunch.

**Only allowed work now:** **P4.5** (near-band corpus enrichment + `S_open:S_blocked ≈ 1:1` + WM retrain), then stop and update STATUS/ISSUES + push.

**Do not:** run P7-accept / P8; relaunch supervisor; treat current P3 as ⓪ FAIL; treat current P4 as authoritative; freeze `[lo,hi]` from diag.

## Corrected facts (must obey)

- P3 = **`insufficient_support` / `authoritative=false`** because ⓪b support gate failed (`n_frames=95<100`). ⓪a/c not bookable.
- R-16 ruling **(B):** no premise-否证 stop, but **P8 blocked until ⓪/⓿/P1 all re-pass authoritative**; `enable_policy_update=false`.
- Existing P4 JSON is provisional → re-run after P4.5.

## Deliverables

1. Pull `origin/main`.
2. Plan + start P4.5 with **explicit near-band frame share target** (must clear ⓪b: ≥100 near frames / support gates).
3. STATUS + ISSUES + commit + push.
4. **Exit** when P4.5 job is launched or BLOCKED on a real human blank — do not continue the chain past P4.5 in this session.
