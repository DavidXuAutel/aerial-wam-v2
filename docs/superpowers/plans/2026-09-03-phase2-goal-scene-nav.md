# Phase-2 Goal+Scene Nav Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the D0-locked product stack — input only \(G\) + scene; outer loop proposes Phase-1-scale \(c^*\); inner loop frozen `step_e` π + shield; stop on \(\|p-G\|\le 3\) — with E0 (no polyline on main arm) then E1 (scene fan intent).

**Architecture:** New `SceneIntentPlanner` owns all **non-polyline** \(c^*\) modes. Eval CLI `--subgoal-source` selects `polyline` (waterline/ablation), `toward_g` (E0 main: clip toward \(G\) at \(r\)), `direct_g` (ablation A: raw far \(G\)), `scene` (E1: yaw fan + depth filter + score). Polyline `AdaptiveSubgoalGenerator` / `--rolling-global` stay **opt-in对照**, never flipped back to product default by this plan.

**Tech Stack:** Python 3.10+, NumPy, existing AirSim/mock long_eval, pytest. Mac: code+unit. Long eval: `.110` / `cursor-125` (4090). No Franka / Desk / `10.229.66.70`.

**Spec:** [`../specs/2026-09-03-phase2-goal-scene-nav-design.md`](../specs/2026-09-03-phase2-goal-scene-nav-design.md)

## Global Constraints

- Input contract: **only \(G\) + scene** on main arm; GT polyline is对照 only.
- Success: `arrived := \|p−G\| ≤ success_dist` (default 3 m); **Prog/CTE never gate** mainline PASS.
- Distance waterline: **200–500 m** product scale; current 16-route annos ~110–170 m are **engineering probes**, not 200–500 PASS.
- Inner π: freeze `v4_ac_ckpt_step_e_20260828` + metre `goal_rel`; no F15/assist default ON.
- \(c^*\) scale: ~10–40 m (`r_base` ~20–25 m class); never stuff full 200–500 m into π except ablation `direct_g`.
- `--rolling-global` / `--lookahead-feedback` / heading assist: remain default OFF.
- Eval ops: GPU/AirSim on `.110` or `cursor-125`; Mac agent = docs/wiring/tests only.

## File map

| File | Responsibility |
|------|----------------|
| `experiments/aerial/rl/scene_intent.py` | **Create.** Pure geometry + scene fan outer loop; no GT polyline. |
| `experiments/aerial/rl/tests/test_scene_intent.py` | **Create.** Unit tests for toward_g / direct_g / scene fan. |
| `experiments/aerial/scripts/wam_phase2_long_eval.py` | **Modify.** `--subgoal-source`; Euclidean stop for non-polyline; JSON tags. |
| `experiments/aerial/rl/goal_features.py` | **Reuse** `goal_rel_body` (no change unless missing helper). |
| `experiments/aerial/rl/subgoal_generator.py` | **Unchanged** for product; still used when `polyline`. |
| `docs/handover/WAM_PHASE2_GOAL_SCENE_E0_DECLARE.md` | **Create** after first E0 probe (template in Task 5). |
| STATUS / RUNBOOK / handover stub | Point at this plan; mark E0/E1 progress. |

---

### Task 1: `toward_g` / `direct_g` geometry (no polyline)

**Files:**
- Create: `experiments/aerial/rl/scene_intent.py`
- Create: `experiments/aerial/rl/tests/test_scene_intent.py`

**Interfaces:**
- Produces: `clip_toward_goal(curr_pos, goal, r_m) -> np.ndarray` (world \(c^*\))
- Produces: `body_goal_rel(curr_pos, curr_yaw, target_world) -> np.ndarray` (delegates to `goal_rel_body`)
- Produces: `TowardGoalIntent(r_m=25.0, mode="toward_g"|"direct_g")` with `.reset()` and `.compute(curr_pos, curr_yaw, goal, d_fwd_hat=None) -> (g_rel, info)`

- [x] **Step 1: Write the failing tests**
- [x] **Step 2: Run tests — expect FAIL (module missing)** *(skipped after impl; suite green)*
- [x] **Step 3: Minimal implementation**
- [x] **Step 4: Run tests — expect PASS** *(6 passed)*
- [x] **Step 5: Commit** *(batched with Tasks 2–4)*

---

### Task 2: Wire E0 into `wam_phase2_long_eval` (`--subgoal-source`)

```python
# experiments/aerial/rl/tests/test_scene_intent.py
import numpy as np
import pytest

from experiments.aerial.rl.scene_intent import TowardGoalIntent, clip_toward_goal


def test_clip_toward_goal_far():
    p = np.array([0.0, 0.0, 10.0])
    g = np.array([100.0, 0.0, 10.0])
    c = clip_toward_goal(p, g, r_m=25.0)
    np.testing.assert_allclose(c, [25.0, 0.0, 10.0], atol=1e-5)


def test_clip_toward_goal_near_returns_g():
    p = np.array([0.0, 0.0, 10.0])
    g = np.array([10.0, 0.0, 10.0])
    c = clip_toward_goal(p, g, r_m=25.0)
    np.testing.assert_allclose(c, g, atol=1e-5)


def test_toward_g_never_uses_polyline_keys():
    intent = TowardGoalIntent(r_m=25.0, mode="toward_g")
    intent.reset()
    g_rel, info = intent.compute(
        curr_pos=np.zeros(3),
        curr_yaw=0.0,
        goal=np.array([80.0, 0.0, 0.0]),
    )
    assert "target_world" in info
    assert info.get("subgoal_source") == "toward_g"
    assert abs(float(g_rel[3]) - 25.0) < 1.0
    assert "cte_m" not in info or info["cte_m"] is None


def test_direct_g_keeps_full_distance():
    intent = TowardGoalIntent(r_m=25.0, mode="direct_g")
    intent.reset()
    g_rel, info = intent.compute(
        curr_pos=np.zeros(3),
        curr_yaw=0.0,
        goal=np.array([80.0, 0.0, 0.0]),
    )
    assert info["subgoal_source"] == "direct_g"
    assert float(g_rel[3]) == pytest.approx(80.0, abs=1e-3)
```

- [ ] **Step 2: Run tests — expect FAIL (module missing)**

```bash
cd /Users/xudazhong/Projects/aerial-wam-v2
python -m pytest experiments/aerial/rl/tests/test_scene_intent.py -v
```

Expected: `ModuleNotFoundError` or import error for `scene_intent`.

- [ ] **Step 3: Minimal implementation**

```python
# experiments/aerial/rl/scene_intent.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np

from experiments.aerial.rl.goal_features import goal_rel_body


def clip_toward_goal(
    curr_pos: np.ndarray,
    goal: np.ndarray,
    r_m: float,
) -> np.ndarray:
    """World-frame c*: at most r_m along the vector to G (or G if closer)."""
    p = np.asarray(curr_pos, dtype=np.float64).reshape(3)
    g = np.asarray(goal, dtype=np.float64).reshape(3)
    delta = g - p
    dist = float(np.linalg.norm(delta))
    r = float(max(1e-3, r_m))
    if dist <= r or dist < 1e-9:
        return g.copy()
    return p + delta * (r / dist)


@dataclass
class TowardGoalIntent:
    """E0 outer stub: no GT polyline; modes toward_g | direct_g."""

    r_m: float = 25.0
    mode: str = "toward_g"  # or "direct_g"
    cruise_speed: float = 10.0
    d_danger: float = 3.0
    d_clear: float = 22.0
    min_creep_speed: float = 1.0

    def reset(self) -> None:
        return None

    def compute(
        self,
        curr_pos: np.ndarray,
        curr_yaw: float,
        goal: np.ndarray,
        d_fwd_hat: Optional[float] = None,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        mode = str(self.mode)
        if mode not in ("toward_g", "direct_g"):
            raise ValueError(f"unknown TowardGoalIntent.mode={mode!r}")
        p = np.asarray(curr_pos, dtype=np.float64).reshape(3)
        g = np.asarray(goal, dtype=np.float64).reshape(3)
        if mode == "direct_g":
            target = g.copy()
        else:
            # Optional: shrink r when forward depth is tight (same α idea as AdaptiveSubgoal).
            r = float(self.r_m)
            if d_fwd_hat is not None and np.isfinite(float(d_fwd_hat)):
                alpha = float(
                    np.clip(
                        (float(d_fwd_hat) - self.d_danger)
                        / max(1e-6, self.d_clear - self.d_danger),
                        0.4,
                        1.0,
                    )
                )
                r = max(12.0, r * alpha)
            target = clip_toward_goal(p, g, r_m=r)

        g_rel = goal_rel_body(p, float(curr_yaw), target)
        d_to_g = float(np.linalg.norm(g - p))
        # Speed bleed near Euclidean arrival (no polyline rem).
        v_safe = float(self.cruise_speed)
        if d_fwd_hat is not None and np.isfinite(float(d_fwd_hat)):
            if float(d_fwd_hat) <= self.d_danger:
                v_safe = float(self.min_creep_speed)
            elif float(d_fwd_hat) < self.d_clear:
                t = (float(d_fwd_hat) - self.d_danger) / max(
                    1e-6, self.d_clear - self.d_danger
                )
                v_safe = self.min_creep_speed + t * (
                    self.cruise_speed - self.min_creep_speed
                )
        if d_to_g <= 8.0:
            t_term = float(np.clip(d_to_g / 8.0, 0.0, 1.0))
            v_term = self.min_creep_speed + t_term * (
                self.cruise_speed - self.min_creep_speed
            )
            v_safe = float(min(v_safe, v_term))

        info: Dict[str, Any] = {
            "subgoal_source": mode,
            "target_world": target.tolist(),
            "rem_dist": d_to_g,  # Euclidean remaining to G (not arc-s)
            "s_progress": 0.0,  # unused for PASS; keep key for JSON compat
            "safe_speed_limit": v_safe,
            "cte_m": None,
            "r_lookahead": float(np.linalg.norm(target - p)),
            "seg_idx": 0,
        }
        return g_rel, info
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
python -m pytest experiments/aerial/rl/tests/test_scene_intent.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add experiments/aerial/rl/scene_intent.py experiments/aerial/rl/tests/test_scene_intent.py
git commit -m "$(cat <<'EOF'
feat(phase2): add toward_g/direct_g intent without GT polyline

EOF
)"
```

---

### Task 2: Wire E0 into `wam_phase2_long_eval` (`--subgoal-source`)

**Files:**
- Modify: `experiments/aerial/scripts/wam_phase2_long_eval.py`
- Test: extend `experiments/aerial/rl/tests/test_scene_intent.py` **or** add a thin mock smoke if one already exists for long_eval; prefer not to import full AirSim in unit tests — assert argparse choices via a small helper if needed.

**Interfaces:**
- Consumes: `TowardGoalIntent` from Task 1
- Produces: CLI `--subgoal-source {polyline,toward_g,direct_g}` (default **`polyline`** until E0 DECLARE; E0 runs force `toward_g`)
- Produces: for non-polyline sources: `arrived` iff Euclidean \(\|p-G\|\le success_dist\) (segment-crossing same as rolling_global path)
- Produces: JSON meta key `"subgoal_source"`

- [ ] **Step 1: Add argparse**

In `build_argparser` / `main` args (alongside `--rolling-global`):

```python
p.add_argument(
    "--subgoal-source",
    type=str,
    default="polyline",
    choices=("polyline", "toward_g", "direct_g", "scene"),
    help="E0/E1: polyline=waterline; toward_g=main E0; direct_g=ablation A; scene=E1",
)
```

- [ ] **Step 2: Construct intent vs AdaptiveSubgoal**

After existing `subgoal_gen = AdaptiveSubgoalGenerator(...)` block:

```python
from experiments.aerial.rl.scene_intent import TowardGoalIntent, SceneIntentPlanner

subgoal_source = str(args.subgoal_source)
intent = None
if subgoal_source in ("toward_g", "direct_g"):
    intent = TowardGoalIntent(
        r_m=25.0 if args.cruise_speed >= 8.0 else 20.0,
        mode=subgoal_source,
        cruise_speed=float(args.cruise_speed),
    )
elif subgoal_source == "scene":
    intent = SceneIntentPlanner(  # Task 3; until then raise clear error
        r_m=25.0 if args.cruise_speed >= 8.0 else 20.0,
        cruise_speed=float(args.cruise_speed),
    )
if intent is not None and bool(args.rolling_global):
    raise SystemExit("refuse: --rolling-global incompatible with non-polyline --subgoal-source")
logger.info("subgoal_source=%s", subgoal_source)
```

Until Task 3 lands, either omit `"scene"` from choices temporarily **or** stub `SceneIntentPlanner` that raises `NotImplementedError` — prefer: Task 2 choices = `polyline,toward_g,direct_g` only; Task 4 adds `scene`.

- [ ] **Step 3: Per-step branch (replace unconditional AdaptiveSubgoal call)**

```python
if intent is not None:
    g_rel_body, s_info = intent.compute(
        curr_pos=p_curr,
        curr_yaw=curr_yaw,
        goal=goal_pos,
        d_fwd_hat=d_fwd,
    )
    target_world = np.array(s_info["target_world"], dtype=np.float64)
    rem_dist = float(s_info["rem_dist"])  # Euclidean to G
    s_prog = 0.0
    safe_v = float(s_info.get("safe_speed_limit", args.cruise_speed))
else:
    # existing polyline / rolling_global path unchanged
    ...
```

- [ ] **Step 4: Euclidean-only stop for non-polyline**

Unify stop predicate:

```python
euclid_only = intent is not None or bool(args.rolling_global)
if euclid_only:
    if d_to_goal <= float(args.success_dist):
        arrived = True
        break
else:
    if rem_dist <= float(args.success_dist) and d_to_goal <= float(args.success_dist):
        arrived = True
        break
```

Same for post-step `seg_d` gate.

- [ ] **Step 5: JSON summary**

Add `"subgoal_source": subgoal_source` next to `"rolling_global"`. Do **not** require `mean_progress` for PASS messaging; keep logging Prog as diagnostic only.

- [ ] **Step 6: Mock smoke (no AirSim)**

```bash
python -m experiments.aerial.scripts.wam_phase2_long_eval \
  --mock --routes 0 --max-steps 5 \
  --subgoal-source toward_g \
  --annotation artifacts/seen_airsim16_m1a20.json \
  # plus existing required ckpt / wm flags used by the script
```

Expected: exits 0; JSON has `"subgoal_source": "toward_g"`; no traceback referencing `nearest_on_polyline` on the intent path.

- [ ] **Step 7: Commit**

```bash
git add experiments/aerial/scripts/wam_phase2_long_eval.py
git commit -m "$(cat <<'EOF'
feat(phase2): E0 --subgoal-source toward_g/direct_g in long_eval

EOF
)"
```

---

### Task 3: `SceneIntentPlanner` (E1 outer loop)

**Files:**
- Modify: `experiments/aerial/rl/scene_intent.py`
- Modify: `experiments/aerial/rl/tests/test_scene_intent.py`

**Interfaces:**
- Consumes: `clip_toward_goal`, `goal_rel_body`
- Produces: `SceneIntentPlanner.compute(...)` → `(g_rel, info)` with `info["subgoal_source"]=="scene"`, `info["n_candidates"]`, `info["replan"]=bool`

Candidate generation (P0, no polyline):

1. Yaw offsets \(\{0,\pm15^\circ,\pm30^\circ\}\) in body/world horizontal; place point at distance `r_m` from `curr_pos` at current altitude (or blend z toward \(G\)).
2. Always include `clip_toward_goal(p, G, r_m)` as a candidate.
3. Drop candidates whose bearing falls in a dangerous forward cone when `d_fwd_hat < d_danger` (keep lateral candidates).
4. Score: \(J = -w_g \cdot (d_{\mathrm{before}}-d_{\mathrm{after}}) + w_{\mathrm{jump}}\cdot\|c-c_{\mathrm{prev}}\|\) with optional collision prior `+ w_coll * 1[d_fwd small and candidate nearly forward]`.
5. Replan every `replan_period_s` **or** when `d_fwd_hat < d_clear` **or** Euclidean progress over last window \(< \epsilon\).

```python
@dataclass
class SceneIntentPlanner:
    r_m: float = 25.0
    cruise_speed: float = 10.0
    yaw_offsets_deg: tuple = (0.0, -15.0, 15.0, -30.0, 30.0)
    replan_period_s: float = 2.0
    step_hz: float = 5.0
    w_g: float = 1.0
    w_jump: float = 0.05
    d_danger: float = 3.0
    d_clear: float = 22.0
    min_creep_speed: float = 1.0

    def reset(self) -> None:
        self._c_prev: Optional[np.ndarray] = None
        self._steps_since_replan: int = 10**9
        self._last_d_to_g: Optional[float] = None
        self._stall_steps: int = 0

    def _candidates(self, p: np.ndarray, yaw: float, goal: np.ndarray) -> list[np.ndarray]:
        out = [clip_toward_goal(p, goal, self.r_m)]
        r = float(self.r_m)
        for deg in self.yaw_offsets_deg:
            psi = float(yaw) + np.deg2rad(float(deg))
            c = p + np.array(
                [r * np.cos(psi), r * np.sin(psi), 0.0], dtype=np.float64
            )
            # pull z gently toward G
            c[2] = p[2] + 0.3 * (goal[2] - p[2])
            out.append(c)
        return out

    def compute(...):  # select min J; hold c* between replans
        ...
```

- [ ] **Step 1: Failing tests**

```python
def test_scene_planner_picks_forward_when_clear():
    pl = SceneIntentPlanner(r_m=25.0)
    pl.reset()
    g_rel, info = pl.compute(
        curr_pos=np.zeros(3),
        curr_yaw=0.0,
        goal=np.array([100.0, 0.0, 0.0]),
        d_fwd_hat=40.0,
    )
    assert info["subgoal_source"] == "scene"
    assert info["n_candidates"] >= 2
    tw = np.array(info["target_world"])
    assert tw[0] > 0.0  # progresses +x toward G


def test_scene_planner_holds_between_replans():
    pl = SceneIntentPlanner(r_m=25.0, replan_period_s=2.0, step_hz=5.0)
    pl.reset()
    _, info0 = pl.compute(np.zeros(3), 0.0, np.array([100.0, 0.0, 0.0]), 40.0)
    t0 = info0["target_world"]
    _, info1 = pl.compute(np.array([1.0, 0.0, 0.0]), 0.0, np.array([100.0, 0.0, 0.0]), 40.0)
    assert info1.get("replan") is False
    np.testing.assert_allclose(info1["target_world"], t0, atol=1e-6)
```

- [ ] **Step 2: Implement until PASS**

- [ ] **Step 3: Commit**

```bash
git add experiments/aerial/rl/scene_intent.py experiments/aerial/rl/tests/test_scene_intent.py
git commit -m "$(cat <<'EOF'
feat(phase2): SceneIntentPlanner fan candidates without GT polyline

EOF
)"
```

---

### Task 4: Wire `--subgoal-source=scene` + docs defaults

**Files:**
- Modify: `experiments/aerial/scripts/wam_phase2_long_eval.py` (add `scene` choice; construct `SceneIntentPlanner`)
- Modify: `docs/handover/WAM_PHASE2_STATUS_20260829.md`
- Modify: `experiments/aerial/RUNBOOK_wam_phase2_long_horizon.md` §7
- Modify: `docs/handover/WAM_PHASE2_GOAL_SCENE_NAV_DESIGN_20260903.md`
- Modify: spec §5 E0/E1 rows if needed

**Default policy (explicit):**

| Phase | `--subgoal-source` default in CLI | Product meaning |
|-------|-----------------------------------|-----------------|
| After Task 2 | `polyline` | waterline unbroken |
| After E0 DECLARE green | change default → `toward_g` | E0 main |
| After E1 DECLARE green | change default → `scene` | E1 main |

Do **not** flip default in the same commit as first wiring; flip only in a dedicated docs+CLI commit after DECLARE.

- [ ] **Step 1: Enable `scene` in argparse + constructor**

- [ ] **Step 2: RUNBOOK one-liner for E0/E1**

```text
# E0 main (no polyline):
python -m experiments.aerial.scripts.wam_phase2_long_eval \
  --subgoal-source toward_g --routes 0,4 --max-steps 400 ...

# E0 ablation A:
  --subgoal-source direct_g ...

# Waterline对照:
  --subgoal-source polyline   # optional --rolling-global

# E1:
  --subgoal-source scene ...
```

- [ ] **Step 3: Commit**

```bash
git add experiments/aerial/scripts/wam_phase2_long_eval.py \
  docs/handover/WAM_PHASE2_STATUS_20260829.md \
  experiments/aerial/RUNBOOK_wam_phase2_long_horizon.md \
  docs/handover/WAM_PHASE2_GOAL_SCENE_NAV_DESIGN_20260903.md
git commit -m "$(cat <<'EOF'
docs(phase2): wire scene intent CLI and E0/E1 runbook

EOF
)"
```

---

### Task 5: E0 probe on `.110` / `125` + DECLARE

**Files:**
- Create: `docs/handover/WAM_PHASE2_GOAL_SCENE_E0_DECLARE.md`

**Ops (not Mac GPU):**

- [ ] **Step 1: Short probe** — routes `0,4` (or R05/R01), `max-steps` enough for ~local behavior, `--subgoal-source toward_g`, shield ON, `step_e` ckpt, assist OFF.

- [ ] **Step 2: Ablation** — same routes `direct_g` and `polyline` for对照 table (3 arms).

- [ ] **Step 3: Fill DECLARE**

```markdown
# E0 DECLARE — goal+scene / no polyline main arm

| Arm | subgoal_source | routes | mean d_min | mean d_final | mean closure | SR | SCR |
|-----|----------------|--------|------------|--------------|--------------|----|-----|
| main | toward_g | | | | | | |
| A | direct_g | | | | | | |
| waterline | polyline | | | | | | |

Gate: runs complete; SCR not worse than chaotic baseline; **not** claiming 200–500 PASS.
JSON paths: ...
```

- [ ] **Step 4: If E0 gate OK, flip CLI default to `toward_g` (separate commit)**

- [ ] **Step 5: Update STATUS** — E0 done / E1 next

---

### Task 6: E1 scene probe (after Task 3–5)

- [ ] **Step 1:** Same short routes with `--subgoal-source scene`; log `n_candidates` / `replan` counts if added to episode JSON.

- [ ] **Step 2:** Qualitative: when forward depth is low, chosen \(c^*\) should not stay pure nose-in (unit test already; AirSim should show lateral peel in logs).

- [ ] **Step 3:** E1 DECLARE; only then consider default → `scene`.

- [ ] **Step 4:** **Stop.** Do not start E2 dynamic obstacles or 200–500 corridor generation in this plan unless a new plan is written. Do not claim 200–500 m PASS on 110–170 m annos.

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| Input only G+scene on main | 2, 4 |
| Scheme B outer c* | 3, 4 |
| Ablation A `direct_g` | 1, 2, 5 |
| Euclidean stop 3 m | 2 |
| Polyline / rolling-global demoted | 2 (refuse combo), 4 docs |
| No Prog/CTE PASS | 2, 5 DECLARE |
| c* ~10–40 m | 1 (`r_m`), 3 |
| No long H as fake global | (not added) |
| 200–500 scale honesty | Global Constraints + Task 6 stop |
| D0 already signed | — |
| E0 / E1 ladder | 5 / 6 |
| E2 dynamic | **out of scope** (next plan) |

## Placeholder / consistency scan

- Mode name: always `toward_g` | `direct_g` | `scene` | `polyline` (CLI = `info["subgoal_source"]`).
- `SceneIntentPlanner` introduced in Task 3; Task 2 must not require it.
- Default flip only after DECLARE (Task 5/6), not at first wire.
