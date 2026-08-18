# Reopen RH progress head — R1 analytic Δ‖g‖ in imagine (125)

- **status**: **IN PROGRESS**
- **prompt**: `docs/handover/V4_RH_REOPEN_125_PROMPT.md`
- **started**: 2026-08-18
- **agent**: composer-2.5-fast on 125
- **renderer**: `127.0.0.1:41451` (Phase 4 only)
- **enable_policy_update**: must stay **false**

Pre-committed: sign §5 「重开 RH progress 头」= **R1** (`imagine` aux progress = `analytic_progress(g, a[:3])`, keep RH `p_coll` / z). **Not** RH retrain. **Not** yaw rotation. **Not** §4 In-table. **Not** warm-start C2 π.

Calib accept (old C2 ckpt, measures imagine not π): arm (b) \|ΣG/ΣΔ‖g‖\| ∈ **[0.8, 1.2]** and arm (c) **same sign**. Else stop.

## Phase 0 — sign

- **DONE** 2026-08-18 — §5 「重开 RH progress 头」= **[x]**，裁定 **重开并落地 R1**；HEAD `7883b89`；`advance_goal_rel_body` yaw **unchecked**。

## Phase 1 — code

- (pending)

## Phase 2 — calib on R1

- (pending)

## Phase 3 — H100 from-scratch AC

- (pending)

## Phase 4 — ① re-gate

- (pending)

## enable_policy_update

**false** (must remain).
