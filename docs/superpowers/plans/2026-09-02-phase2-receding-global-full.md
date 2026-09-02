# Phase-2 Receding Global + Phase-1 Local — Full Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a working **receding global reference** (`P_ref`) + existing Phase-1 WAM tracker so long-horizon eval closes on Euclidean goal `‖p−G‖≤3m`, not arc-length Prog.

**Architecture:** `GlobalRefPlanner` periodically rebuilds a short feasible `P_ref` toward final `G` on a known freefspace proxy; `AdaptiveSubgoalGenerator` takes lookahead carrot `c` on `P_ref` (never require arrive-at-`c`); frozen `step_e` π + short imagination + shield execute. Stop only at `G`.

**Tech Stack:** Python 3, NumPy, existing AirSim eval on `.110`, ckpt `v4_ac_ckpt_step_e_20260828`, YAML `configs/aerial_rl.yaml`.

**Design spec:** [`docs/handover/WAM_PHASE2_HIER_MPC_LOCAL_P1_DESIGN_20260902.md`](../../handover/WAM_PHASE2_HIER_MPC_LOCAL_P1_DESIGN_20260902.md)

## Global Constraints

- **Local π frozen:** do not retrain; do not raise local imagination horizon as a substitute for global planning.
- **Stop contract:** `arrived := rem_dist≤3 ∧ ‖p−G‖≤3`; Prog is diagnostic only (L0 already in `wam_phase2_long_eval.py`).
- **Carrot:** intermediate `c` is lookahead only — never hard-arrive / segment-terminal as mainline default.
- **No pits:** do not open assist, F15 `w_eff` chase, or per-route local forensics as gates for this plan.
- **Naming:** say “receding global reference”, not “MPC done”.
- **Machines:** Mac = docs/unit tests; `.110` = AirSim eval; H100 only if later train (not this plan).
- **Commits:** only when the user explicitly asks.

### Out of mainline (parked)

| Item | Status |
|------|--------|
| R05 / single-route idle forensics | **Parked** — do not block global work |
| L1 `--lookahead-feedback` probe | **Parked** — code may stay default OFF; not a gate |
| True nonlinear MPC @ 5 Hz | L3 later |
| Map-free 300–500 m vision global | L4 later / separate campaign |

### Already done (do not redo)

- [x] L0 honest metrics in `experiments/aerial/scripts/wam_phase2_long_eval.py`
- [x] Design + feasibility review in handover design doc
- [x] Planner goal-aux fix in `experiments/aerial/rl/planner.py` (keep)

---

## File map

| File | Responsibility |
|------|----------------|
| `experiments/aerial/rl/global_ref_planner.py` | **New.** Receding `P_ref` from `(p, G, corridor, feedback)` |
| `experiments/aerial/rl/tests/test_global_ref_planner.py` | **New.** Pure NumPy unit tests |
| `experiments/aerial/rl/subgoal_generator.py` | Unchanged API: still `compute_subgoal(..., global_path=P_ref)` |
| `experiments/aerial/scripts/wam_phase2_long_eval.py` | Wire planner; pass rolling path into subgoal; log replan stats |
| `experiments/aerial/scripts/wam_phase2_offtrack_probes.py` | Optional CLI `--rolling-global` for short checks |
| `docs/handover/WAM_PHASE2_HIER_P0_ROLLING_GLOBAL_DECLARE_*.md` | Gate criteria before default-on |
| `docs/handover/WAM_PHASE2_STATUS_*.md` | Living pointer |

```text
annotation corridor F ──┐
p, ψ, G, stall flags ───┼─► GlobalRefPlanner.step() ─► P_ref (short polyline)
                        │
P_ref ──────────────────┴─► AdaptiveSubgoal.compute_subgoal ─► g_rel
                                                                  │
                                                            Phase-1 π → shield
```

---

### Task 1: `GlobalRefPlanner` core API + unit tests

**Files:**
- Create: `experiments/aerial/rl/global_ref_planner.py`
- Create: `experiments/aerial/rl/tests/test_global_ref_planner.py`

**Interfaces:**
- Consumes: NumPy corridor polyline `F` (N×3), state `p` (3,), yaw, goal `G` (3,)
- Produces:
  - `class GlobalRefPlanner`
  - `def reset(self, corridor: np.ndarray, goal: np.ndarray | None = None) -> None`
  - `def step(self, p: np.ndarray, yaw: float, *, cte_m: float | None = None, progressed_m: float | None = None, force: bool = False) -> np.ndarray`  
    Returns `P_ref` shape `(M, 3)`, `M >= 2`
  - `dataclass GlobalRefConfig` with: `horizon_m`, `replan_period_s`, `step_hz`, `max_point_spacing_m`, `min_progress_m`, `stall_steps_to_replan`, `max_cte_m_to_replan`, `blend_prev: float`

**P0 algorithm (explicit — not “smart later”):**

1. Project `p` onto corridor `F` → `s_true`, `proj`.
2. Build forward window: sample points from `s_true` to `min(s_true + horizon_m, s_end)` along `F` at `max_point_spacing_m`, always append `G` if within horizon else the window end.
3. Replan when: first call; `force`; elapsed ≥ `replan_period_s`; stall (`progressed_m` below `min_progress_m` for `stall_steps_to_replan`); or `cte_m > max_cte_m_to_replan`.
4. Optional blend: if previous `P_ref` exists, linearly blend first waypoint toward previous first waypoint by `blend_prev ∈ [0,1]` to limit carrot jump (then re-sample spacing).
5. Never require the tracker to finish `P_ref` within one period.

- [ ] **Step 1: Write failing tests**

```python
# experiments/aerial/rl/tests/test_global_ref_planner.py
import numpy as np
import pytest
from experiments.aerial.rl.global_ref_planner import GlobalRefPlanner, GlobalRefConfig


def _straight_corridor(length=200.0, z=10.0):
    return np.array([[0.0, 0.0, z], [length, 0.0, z]], dtype=np.float64)


def test_reset_and_first_step_returns_forward_polyline():
    cfg = GlobalRefConfig(horizon_m=40.0, max_point_spacing_m=10.0, replan_period_s=1.0, step_hz=5.0)
    gp = GlobalRefPlanner(cfg)
    F = _straight_corridor()
    gp.reset(F, goal=F[-1])
    Pref = gp.step(np.array([0.0, 0.0, 10.0]), 0.0, force=True)
    assert Pref.ndim == 2 and Pref.shape[1] == 3 and Pref.shape[0] >= 2
    assert Pref[0, 0] == pytest.approx(0.0, abs=1.0)
    assert Pref[-1, 0] <= 40.0 + 1e-6


def test_no_replan_within_period_returns_same_object_or_equal():
    cfg = GlobalRefConfig(horizon_m=40.0, replan_period_s=1.0, step_hz=5.0)
    gp = GlobalRefPlanner(cfg)
    F = _straight_corridor()
    gp.reset(F)
    p = np.array([5.0, 0.0, 10.0])
    a = gp.step(p, 0.0, force=True)
    b = gp.step(p, 0.0)  # ~0.2s later internally once
    np.testing.assert_allclose(a, b)


def test_stall_forces_replan_event():
    cfg = GlobalRefConfig(
        horizon_m=40.0,
        replan_period_s=100.0,
        step_hz=5.0,
        min_progress_m=0.5,
        stall_steps_to_replan=3,
    )
    gp = GlobalRefPlanner(cfg)
    gp.reset(_straight_corridor())
    p = np.array([10.0, 0.0, 10.0])
    gp.step(p, 0.0, force=True, progressed_m=0.0)
    for _ in range(3):
        out = gp.step(p, 0.0, progressed_m=0.0)
    assert gp.last_replan_reason in ("stall", "force", "period", "cte", "init")
    # After enough stalls, reason should be stall at least once
    assert gp.replan_count >= 2
```

- [ ] **Step 2: Run tests — expect FAIL (module missing)**

```bash
python3 -m pytest experiments/aerial/rl/tests/test_global_ref_planner.py -q
```

Expected: `ModuleNotFoundError` or collection error.

- [ ] **Step 3: Implement `global_ref_planner.py`**

Minimal skeleton (implement fully in-repo; keep functions pure NumPy):

```python
@dataclass
class GlobalRefConfig:
    horizon_m: float = 60.0
    replan_period_s: float = 1.0
    step_hz: float = 5.0
    max_point_spacing_m: float = 8.0
    min_progress_m: float = 0.5
    stall_steps_to_replan: int = 25
    max_cte_m_to_replan: float = 12.0
    blend_prev: float = 0.3


class GlobalRefPlanner:
    def __init__(self, cfg: GlobalRefConfig | None = None):
        self.cfg = cfg or GlobalRefConfig()
        self.replan_count = 0
        self.last_replan_reason = "init"
        # internal: corridor, goal, Pref, step_i, stall_i, ...

    def reset(self, corridor: np.ndarray, goal: np.ndarray | None = None) -> None: ...
    def step(self, p, yaw, *, cte_m=None, progressed_m=None, force=False) -> np.ndarray: ...
```

Reuse projection helpers from `subgoal_generator.py` (`nearest_on_polyline`, `point_at_arc_length`, `compute_polyline_cum_lengths`) — import, do not copy-paste large blocks.

- [ ] **Step 4: Run tests — expect PASS**

```bash
python3 -m pytest experiments/aerial/rl/tests/test_global_ref_planner.py -q
```

Expected: all green.

---

### Task 2: Smoothness / jump bound tests + enforcement

**Files:**
- Modify: `experiments/aerial/rl/global_ref_planner.py`
- Modify: `experiments/aerial/rl/tests/test_global_ref_planner.py`

**Interfaces:**
- Produces: `info` dict optional via `step_with_info(...)` **or** attributes `last_carrot_jump_m`, `last_Pref`
- Constraint: after replan, Euclidean distance between old `P_ref[0]` and new `P_ref[0]` ≤ `max_anchor_jump_m` (add to config, default `8.0`) when `blend_prev` active

- [ ] **Step 1: Failing test**

```python
def test_anchor_jump_bounded_when_blending():
    cfg = GlobalRefConfig(horizon_m=50.0, blend_prev=0.5, max_anchor_jump_m=8.0, replan_period_s=0.0)
    # replan_period_s=0 => every step replans; blend must still bound jump
    ...
    assert gp.last_anchor_jump_m <= 8.0 + 1e-6
```

- [ ] **Step 2: Implement clamp** after blend: if jump > max, scale toward old anchor.
- [ ] **Step 3: pytest PASS**

---

### Task 3: Wire into `wam_phase2_long_eval.py` (opt-in flag)

**Files:**
- Modify: `experiments/aerial/scripts/wam_phase2_long_eval.py`
- Modify: summary JSON schema (episode + aggregate fields)

**Interfaces:**
- CLI: `--rolling-global` (default **False**)
- CLI: `--global-horizon-m` default `60`
- CLI: `--global-replan-period-s` default `1.0`
- Each episode: `global_planner.reset(pts, goal=pts[-1])`
- Each step after subgoal CTE known:  
  `P_ref = global_planner.step(p_curr, curr_yaw, cte_m=..., progressed_m=Δs_true)`  
  then `subgoal_gen.compute_subgoal(..., global_path=P_ref)`  
  **Important:** arrival / `rem_dist` for stop contract must still be vs **route goal G** and full corridor remaining (or Euclidean `‖p−G‖`), not vs short `P_ref` end. If `AdaptiveSubgoal` `rem_dist` is arc-rem on `P_ref`, override success check to use `_goal_dist(p, G)` only when `--rolling-global` (keep rem∧d_goal if rem is computed on full F — prefer computing `rem` on full corridor separately).

**Recommended success path under rolling global:**

```python
d_to_goal = _goal_dist(p_curr, goal_pos)
arrived = d_to_goal <= float(args.success_dist)
# optional: also require nearest-on-full-corridor rem if you keep dual gate
```

Log per episode: `n_global_replans`, `last_replan_reasons` histogram optional.

- [ ] **Step 1: Add argparse flags + construct `GlobalRefPlanner` when enabled**
- [ ] **Step 2: Episode loop uses `P_ref` for carrot; full `pts` for spawn/G/`d_to_goal`**
- [ ] **Step 3: Unit-level smoke** — import main module helpers still pass L0 tests:

```bash
python3 -m pytest experiments/aerial/rl/tests/test_phase2_l0_metrics.py experiments/aerial/rl/tests/test_global_ref_planner.py -q
```

- [ ] **Step 4: Dry `--mock` one episode if mock env supports it; else skip to `.110`**

---

### Task 4: DECLARE for default-off → eval gate

**Files:**
- Create: `docs/handover/WAM_PHASE2_HIER_P0_ROLLING_GLOBAL_DECLARE_20260902.md`
- Update: `docs/handover/WAM_PHASE2_STATUS_20260829.md`
- Update: `experiments/aerial/RUNBOOK_wam_phase2_long_horizon.md` §7

**DECLARE must state:**

| Field | Value |
|-------|--------|
| Default | `--rolling-global` OFF until gate |
| Ckpt | `v4_ac_ckpt_step_e_20260828` |
| Assist | OFF |
| Compare | same annotation vs reanchor JSON waterline |
| Primary metrics | SR, SPL, SCR, `mean_goal_closure`, `n_monotone_inflate` |
| Gate (P0) | On a **fixed 8-route subset** (not R05 theater): mean `goal_closure` ↑ vs reanchor same indices **or** mean `d_min` ↓ by ≥5 m without SCR↑; SR non-worsening |
| Fail → | keep flag OFF; diagnose jump/OOD; do not open F15 |

- [ ] **Step 1: Write DECLARE**
- [ ] **Step 2: Point STATUS/RUNBOOK “下一步” only at P0 rolling global `.110` eval**

---

### Task 5: `.110` P0 eval (execution, not Mac)

**Files:** artifacts under `artifacts/wam_phase2_p0_rolling_*`

**Commands (on `.110` after sync):**

```bash
source experiments/aerial/scripts/env_4090.sh
# baseline (flag off) optional if reanchor JSON trusted
python experiments/aerial/scripts/wam_phase2_long_eval.py \
  --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt \
  --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_step_e_20260828/v4_ac_latest.pt \
  --annotation artifacts/seen_airsim16_long_routes.json \
  --cruise-speed 10.0 --planner --planner-horizon 5 --max-steps 1000 \
  --rolling-global \
  --global-horizon-m 60 --global-replan-period-s 1.0 \
  --out artifacts/wam_phase2_p0_rolling_result.json
```

- [ ] **Step 1: Sync tree to `.110`**
- [ ] **Step 2: Run P0 eval**
- [ ] **Step 3: Fill DECLARE results table; PASS/FAIL**
- [ ] **Step 4: If PASS → Task 6; if FAIL → Task 6 still allowed only as cost/smoothness fix, not local reward chase**

---

### Task 6: P1 — explicit global cost (still receding reference)

**Files:**
- Modify: `experiments/aerial/rl/global_ref_planner.py`
- Modify: tests

**P1 behavior:** when replanning, generate **K** candidate forward windows (e.g. stay on corridor; lateral ±offset samples if corridor has width; or skip-ahead shortcuts if segment chord is free — P0 corridor-only may only vary horizon / start s). Score:

```text
J = w_progress * (-Δs_to_G) + w_curv * κ + w_clear * clearance_pen + w_consist * ‖P_new - P_old‖
```

Pick argmin. Depth clearance optional: if `d_fwd_hat` passed into `step`, penalize candidates whose first chord points into danger.

- [ ] **Step 1: Tests for cost prefers higher progress when clearance equal**
- [ ] **Step 2: Implement candidate scoring**
- [ ] **Step 3: `.110` compare P0 vs P1 same seed routes**

---

### Task 7: Mainline default decision

**Only after Task 5 PASS (and preferably Task 6 non-regress):**

- [ ] Flip docs: mainline long_eval recommends `--rolling-global`
- [ ] Keep default False in argparse until product sign-off, **or** default True behind protocol_version bump — record choice in STATUS
- [ ] Do **not** delete fixed-path mode (ablation)

---

## Execution order (locked)

```text
Task1 API → Task2 jump bound → Task3 long_eval wire → Task4 DECLARE/docs
    → Task5 .110 P0 eval → Task6 P1 cost → Task7 default decision
```

**Do not insert:** R05 probes, L1 feedback gates, F15 FT, assist A/B, segment-terminal default-on.

---

## Task checklist

- [x] Task 1 `GlobalRefPlanner` + tests
- [x] Task 2 jump bound
- [x] Task 3 long_eval `--rolling-global`
- [x] Task 4 P0 DECLARE + STATUS/RUNBOOK
- [ ] Task 5 `.110` P0 eval
- [ ] Task 6 P1 cost
- [ ] Task 7 default decision
- [x] L0 metrics (prior)
- [x] No assist / F15 / segment-terminal as mainline

---

## Spec coverage (self-check)

| Spec item | Task |
|-----------|------|
| Receding `P_ref` | 1–3 |
| Lookahead not arrive-at-c | unchanged subgoal + Task 3 success on G |
| Local = Phase-1 frozen | constraint |
| Only G hard stop | Task 3 |
| Honest metrics | L0 done |
| Known `F` for P0 | corridor = annotation |
| Replan rate ≪ 5 Hz | config `replan_period_s` |
| c jump limit | Task 2 |
| No oversell “MPC done” | docs wording |
| Park R05 / L1 pits | Global Constraints |

**Plan complete.** Next: choose execution mode and start Task 1.
