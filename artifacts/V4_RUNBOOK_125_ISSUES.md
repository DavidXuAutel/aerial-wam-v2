# V4 RUNBOOK 125 — Issues

## RESOLVED 2026-08-20 | §3 item 11 | spare pool size

**Decision:** `--spare-count = 16` (option 1).

---

## CORRECTION 2026-08-20 | P3 记法 | ⓪b = support 门

**Supersedes** the earlier «P3 FAIL → continue P4» INFO.

- P3 = **`authoritative=false` / near-band `insufficient_support`**, **not** «⓪ FAIL».
- ⓪b triad: `near_px_total=support_px=790055 ≥ 1e4` ✅；`n_frames=95 < 100` ❌；**单帧贡献占比** `max_frame_frac=0.0416 ≤ 0.2` ✅.
- ⓪a/c on same near domain → **neither authoritative** (raw 0.123 / 1.38 not booked).
- Near frames **95/6005 = 1.6%**; outer ⓪f (1)(2) strong → corpus disease, not head.
- **⓪c GT bins（归因）**：`(0,1.5]` p90 AbsRel **1.978** (n=256750)；`(1.5,3]` p90 **0.380** (n=533305) — 坏尾在 <1.5 m。
- ⓪f: (1)(2) reported；(3)/(4) = full `clearance_sweep` in `artifacts/v4_zero_p3_20260820_bins.json` + RUNBOOK §2.1 — D̂ 近 3–4 m 高误触；τ 有条件 bin **全 0.0**；`[lo,hi]=null`，**not a blanket PASS**.
- Fix path: **P4.5 near-band enrichment** → re-P3 (also fixes P1).

Artifacts: `artifacts/v4_zero_p3_20260820.json`；bins `artifacts/v4_zero_p3_20260820_bins.json`.

---

## INFO 2026-08-20 | P1 one_step_ok 补数

Log `artifacts/v4_p1_fidelity_rh_20260820.log` h=0: `wm_mae=0.5817 | mean-base=0.6508` ⇒ **`one_step_ok=True`**. FAIL remains **reward-only** (`beat_frac=0.67`).

---

## RULING 2026-08-20 | R-16 = (B) | Mac chat

**(B) adopted operationally** (formal §5.0 sign-row still owed):

1. Precondition FAIL / `insufficient_support` ≠ V4-MVP premise否证 stop.
2. **R-16 is a gap, not a license** — do not treat «no §6 stop» as permission to certify downstream.
3. **Before P8:** ⓪, ⓿, and P1 must all be **re-run and authoritative**.
4. `enable_policy_update` stays **false**.
5. **No continuous-to-P8 supervisor.**

**(A) not adopted** for now (current P3 is insufficient_support, not FAIL).

**P4 decision:** do **not** continue certifying on current WM. Existing P4 run (`v4_rho_p4_20260820.json`, ⓿e FAIL) is **provisional / non-authoritative** → **re-run after P4.5**.

**Next:** P4.5 only (near-band + 1:1 corpus + WM retrain).

---

## INFO | P4 provisional | 2026-08-20

Harness `9f0cc1f`. ⓿a–d PASS (ρ median 0.963); **⓿e FAIL** (`median_rel_l2=1.37`).  
**Status under ruling (B):** logged only; **must re-run after P4.5**.

---

## BLOCKED | freeze prerequisites | §3 #3 / #7 / #8

Still unsigned: `k`, primary list, OC seed rules. Relevant **after** authoritative ⓪ + P7-diag — not a reason to skip P4.5.

---

## INFO | code update | 2026-08-20 | `4e76865`

P2 wiring + P6 `action_limits` (see prior note).
