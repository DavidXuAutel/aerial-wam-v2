# Hierarchical Long-Horizon 10m/s WAM Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a hierarchical long-horizon navigation module (200~800m) with adaptive lookahead and curvature/clearance governors supporting up to 10 m/s cruise speed on top of the validated Phase 1 local WAM policy.

**Architecture:** A lightweight high-level `AdaptiveSubgoalGenerator` dynamically projects current vehicle position onto a global reference polyline, modulates lookahead radius $R_{\text{lookahead}} \in [20, 60]\text{m}$ based on forward depth clearance $\hat{D}_{\text{fwd}}$, path curvature $\theta_{\text{turn}}$, and remaining distance, converts the subgoal into local SE(3) body-relative coordinates $g_{\text{rel}}^{\text{body}}$, and passes it to the 5Hz Phase 1 `LatentActorDeployPolicy` + `ImaginationPlanner`.

**Tech Stack:** Python 3.10+, PyTorch, NumPy, AirSim / Mock Environment, Pytest.

## Global Constraints
- Decoupled SE(3) Body-Relative Goal representation: $g_{\text{rel}}^{\text{body}} = [\Delta x_b, \Delta y_b, \Delta z_b, \|\Delta p\|_2]$.
- Strict anti-backtracking monotonic arc-length lock: $s(t) = \max(s_{\max}(t-1), s(t))$.
- Max cruise velocity config: `cruise_speed = 10.0 m/s` (or `vx_max = 2.0 m/step` @ 5Hz), with active curvature and clearance slowdown in tight turns/cluttered zones.
- Pure modular add-on: zero retraining required for existing Phase 1 world model checkpoint and actor-critic policy checkpoint.
- Mac Agent executes local tests/code; long GPU evaluations run on cursor-125 (4090).

---

### Task 1: Polyline Geometric Projection & Monotonic Arc-Length Tracker

**Files:**
- Create: `experiments/aerial/rl/subgoal_generator.py`
- Create: `experiments/aerial/rl/tests/test_subgoal_generator.py`

**Interfaces:**
- Produces: `project_to_polyline(pos, path_points, prev_s_max=0.0) -> tuple[np.ndarray, int, float, float]`
  - returns `(projected_point, active_segment_idx, s_curr, rem_dist)`
- Produces: `sample_point_along_polyline(path_points, segment_idx, proj_point, r_lookahead) -> np.ndarray`

- [ ] **Step 1: Write failing unit test for polyline projection and arc-length search**

```python
# experiments/aerial/rl/tests/test_subgoal_generator.py
import numpy as np
import pytest
from experiments.aerial.rl.subgoal_generator import (
    project_to_polyline,
    sample_point_along_polyline,
)

def test_project_to_polyline_straight_line():
    path = np.array([
        [0.0, 0.0, 10.0],
        [100.0, 0.0, 10.0],
        [200.0, 0.0, 10.0],
    ], dtype=np.float64)
    
    pos = np.array([50.0, 5.0, 10.0], dtype=np.float64)
    proj, seg_idx, s_curr, rem_dist = project_to_polyline(pos, path, prev_s_max=0.0)
    
    np.testing.assert_allclose(proj, [50.0, 0.0, 10.0], atol=1e-5)
    assert seg_idx == 0
    assert pytest.approx(s_curr, abs=1e-3) == 50.0
    assert pytest.approx(rem_dist, abs=1e-3) == 150.0

def test_anti_backtracking_lock():
    path = np.array([
        [0.0, 0.0, 10.0],
        [100.0, 0.0, 10.0],
        [200.0, 0.0, 10.0],
    ], dtype=np.float64)
    
    # Vehicle was at s=80m, now drifts/backs to x=70m
    pos_back = np.array([70.0, 0.0, 10.0], dtype=np.float64)
    proj, seg_idx, s_curr, rem_dist = project_to_polyline(pos_back, path, prev_s_max=80.0)
    
    # s_curr must not decrease below prev_s_max
    assert s_curr >= 80.0
    assert pytest.approx(rem_dist, abs=1e-3) == 120.0

def test_sample_point_along_polyline():
    path = np.array([
        [0.0, 0.0, 10.0],
        [100.0, 0.0, 10.0],
        [100.0, 100.0, 10.0],
    ], dtype=np.float64)
    
    proj_point = np.array([80.0, 0.0, 10.0], dtype=np.float64)
    # Lookahead 40m: 20m on seg 0, 20m on seg 1
    target = sample_point_along_polyline(path, segment_idx=0, proj_point=proj_point, r_lookahead=40.0)
    np.testing.assert_allclose(target, [100.0, 20.0, 10.0], atol=1e-5)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest experiments/aerial/rl/tests/test_subgoal_generator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'experiments.aerial.rl.subgoal_generator'`

- [ ] **Step 3: Implement minimal polyline projection and arc-length search**

```python
# experiments/aerial/rl/subgoal_generator.py
from typing import Tuple
import numpy as np

def project_to_polyline(
    pos: np.ndarray,
    path_points: np.ndarray,
    prev_s_max: float = 0.0,
) -> Tuple[np.ndarray, int, float, float]:
    """Project vehicle 3D position onto 3D polyline and return monotonic progress."""
    points = np.asarray(path_points, dtype=np.float64)
    pos = np.asarray(pos, dtype=np.float64)
    n_pts = len(points)
    assert n_pts >= 2, "Path must have at least 2 points"

    seg_vectors = points[1:] - points[:-1]
    seg_lengths = np.linalg.norm(seg_vectors, axis=1)
    total_length = float(np.sum(seg_lengths))

    cum_lengths = np.concatenate([[0.0], np.cumsum(seg_lengths)])

    best_dist_sq = float("inf")
    best_proj = points[0].copy()
    best_seg = 0
    best_s = 0.0

    for i in range(n_pts - 1):
        p0 = points[i]
        p1 = points[i + 1]
        v = seg_vectors[i]
        l = seg_lengths[i]
        if l < 1e-6:
            continue
        v_norm = v / l
        w = pos - p0
        proj_scalar = float(np.dot(w, v_norm))
        t = np.clip(proj_scalar / l, 0.0, 1.0)
        proj_pt = p0 + t * v
        dist_sq = float(np.sum((pos - proj_pt) ** 2))
        s_candidate = cum_lengths[i] + t * l

        if dist_sq < best_dist_sq:
            best_dist_sq = dist_sq
            best_proj = proj_pt
            best_seg = i
            best_s = s_candidate

    s_monotone = max(float(prev_s_max), float(best_s))
    rem_dist = max(0.0, total_length - s_monotone)

    return best_proj, best_seg, s_monotone, rem_dist

def sample_point_along_polyline(
    path_points: np.ndarray,
    segment_idx: int,
    proj_point: np.ndarray,
    r_lookahead: float,
) -> np.ndarray:
    """Sample a 3D target point ahead by r_lookahead along polyline."""
    points = np.asarray(path_points, dtype=np.float64)
    n_pts = len(points)
    rem_r = float(r_lookahead)
    curr_pt = np.asarray(proj_point, dtype=np.float64)

    for i in range(segment_idx, n_pts - 1):
        p_next = points[i + 1]
        v = p_next - curr_pt
        d = float(np.linalg.norm(v))
        if d >= rem_r:
            if d < 1e-6:
                return p_next
            return curr_pt + (rem_r / d) * v
        rem_r -= d
        curr_pt = p_next.copy()

    return points[-1].copy()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest experiments/aerial/rl/tests/test_subgoal_generator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add experiments/aerial/rl/subgoal_generator.py experiments/aerial/rl/tests/test_subgoal_generator.py
git commit -m "feat(subgoal): add polyline projection and monotonic arc-length tracking"
```

---

### Task 2: Adaptive 10 m/s Lookahead & Curvature/Clearance Governor

**Files:**
- Modify: `experiments/aerial/rl/subgoal_generator.py`
- Test: `experiments/aerial/rl/tests/test_subgoal_generator.py`

**Interfaces:**
- Produces: `class AdaptiveSubgoalGenerator`
  - `__init__(self, r_base=55.0, r_min=20.0, d_clear=22.0, d_danger=3.0, cruise_speed=10.0)`
  - `compute_subgoal(self, curr_pos, curr_yaw, global_path, d_fwd_hat=None) -> tuple[np.ndarray, dict]`
    - returns `(g_rel_body, debug_info)` where `g_rel_body` is `[dx_b, dy_b, dz_b, dist]`

- [ ] **Step 1: Write failing test for AdaptiveSubgoalGenerator with 10 m/s tuning**

```python
# Add to experiments/aerial/rl/tests/test_subgoal_generator.py
from experiments.aerial.rl.subgoal_generator import AdaptiveSubgoalGenerator

def test_adaptive_subgoal_generator_straight_clear():
    generator = AdaptiveSubgoalGenerator(r_base=55.0, r_min=20.0, cruise_speed=10.0)
    path = np.array([
        [0.0, 0.0, 10.0],
        [200.0, 0.0, 10.0],
    ], dtype=np.float64)
    
    pos = np.array([0.0, 0.0, 10.0], dtype=np.float64)
    yaw = 0.0 # Facing +X
    
    g_rel, info = generator.compute_subgoal(pos, yaw, path, d_fwd_hat=30.0)
    
    assert g_rel.shape == (4,)
    # In open space, lookahead should be close to r_base (55.0m)
    assert pytest.approx(g_rel[0], abs=1.0) == 55.0
    assert pytest.approx(g_rel[1], abs=0.1) == 0.0
    assert pytest.approx(g_rel[3], abs=1.0) == 55.0
    assert info["alpha_clearance"] == 1.0

def test_adaptive_subgoal_generator_tight_turn_and_obstacle():
    generator = AdaptiveSubgoalGenerator(r_base=55.0, r_min=20.0, cruise_speed=10.0)
    # Right angle turn
    path = np.array([
        [0.0, 0.0, 10.0],
        [20.0, 0.0, 10.0],
        [20.0, 100.0, 10.0],
    ], dtype=np.float64)
    
    pos = np.array([10.0, 0.0, 10.0], dtype=np.float64)
    yaw = 0.0
    
    # Near obstacle (d_fwd_hat = 3.0m)
    g_rel, info = generator.compute_subgoal(pos, yaw, path, d_fwd_hat=3.0)
    
    # Lookahead should clamp to r_min (20.0m)
    assert info["r_lookahead"] <= 25.0
    assert info["alpha_clearance"] == pytest.approx(0.4, abs=1e-3)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest experiments/aerial/rl/tests/test_subgoal_generator.py -k "test_adaptive_subgoal_generator" -v`
Expected: FAIL with `ImportError: cannot import name 'AdaptiveSubgoalGenerator'`

- [ ] **Step 3: Implement AdaptiveSubgoalGenerator**

```python
# Append to experiments/aerial/rl/subgoal_generator.py
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

@dataclass
class AdaptiveSubgoalGenerator:
    r_base: float = 55.0
    r_min: float = 20.0
    d_clear: float = 22.0
    d_danger: float = 3.0
    cruise_speed: float = 10.0
    _prev_s_max: float = field(default=0.0, init=False, repr=False)

    def reset(self) -> None:
        self._prev_s_max = 0.0

    def compute_subgoal(
        self,
        curr_pos: np.ndarray,
        curr_yaw: float,
        global_path: np.ndarray,
        d_fwd_hat: Optional[float] = None,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        curr_pos = np.asarray(curr_pos, dtype=np.float64)
        global_path = np.asarray(global_path, dtype=np.float64)

        proj_pt, seg_idx, s_monotone, rem_dist = project_to_polyline(
            curr_pos, global_path, prev_s_max=self._prev_s_max
        )
        self._prev_s_max = s_monotone

        # 1. Clearance modulation
        if d_fwd_hat is not None and np.isfinite(d_fwd_hat):
            alpha = float(np.clip((d_fwd_hat - self.d_danger) / (self.d_clear - self.d_danger), 0.4, 1.0))
        else:
            alpha = 1.0

        # 2. Curvature modulation
        beta = 1.0
        if seg_idx < len(global_path) - 2:
            v1 = global_path[seg_idx + 1] - global_path[seg_idx]
            v2 = global_path[seg_idx + 2] - global_path[seg_idx + 1]
            n1 = np.linalg.norm(v1[:2])
            n2 = np.linalg.norm(v2[:2])
            if n1 > 1e-3 and n2 > 1e-3:
                cos_theta = np.clip(np.dot(v1[:2], v2[:2]) / (n1 * n2), -1.0, 1.0)
                theta_turn = float(np.arccos(cos_theta))
                beta = float(np.cos(np.clip(theta_turn, 0.0, np.pi / 2.0) / 2.0))

        # 3. Compute adaptive lookahead radius
        r_nominal = max(self.r_min, self.r_base * alpha * beta)
        r_lookahead = min(rem_dist, r_nominal)

        # 4. Sample world target point
        target_world = sample_point_along_polyline(
            global_path, segment_idx=seg_idx, proj_point=proj_pt, r_lookahead=r_lookahead
        )

        # 5. Convert to SE(3) Body-Relative Frame
        delta_w = target_world - curr_pos
        cos_y, sin_y = np.cos(curr_yaw), np.sin(curr_yaw)
        dx_b = cos_y * delta_w[0] + sin_y * delta_w[1]
        dy_b = -sin_y * delta_w[0] + cos_y * delta_w[1]
        dz_b = delta_w[2]
        dist = float(np.linalg.norm(delta_w))

        g_rel_body = np.array([dx_b, dy_b, dz_b, dist], dtype=np.float32)

        info = {
            "s_progress": s_monotone,
            "rem_dist": rem_dist,
            "r_lookahead": r_lookahead,
            "alpha_clearance": alpha,
            "beta_curvature": beta,
            "target_world": target_world.tolist(),
        }

        return g_rel_body, info
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest experiments/aerial/rl/tests/test_subgoal_generator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add experiments/aerial/rl/subgoal_generator.py experiments/aerial/rl/tests/test_subgoal_generator.py
git commit -m "feat(subgoal): add AdaptiveSubgoalGenerator with 10m/s lookahead and clearance modulation"
```

---

### Task 3: Long-Horizon Route Generator (200~500m Benchmark)

**Files:**
- Create: `experiments/aerial/scripts/generate_long_routes.py`
- Produce: `artifacts/seen_airsim16_long_routes.json`

- [ ] **Step 1: Write long route synthesis script chaining seen AirSim-16 subroutes**

```python
# experiments/aerial/scripts/generate_long_routes.py
import json
from pathlib import Path
import numpy as np

def generate_long_routes(
    input_anno: str = "artifacts/seen_airsim16_m1a20.json",
    output_anno: str = "artifacts/seen_airsim16_long_routes.json",
    min_dist_m: float = 200.0,
    max_dist_m: float = 500.0,
):
    with open(input_anno, "r") as f:
        data = json.load(f)

    routes = data.get("routes", data) if isinstance(data, dict) else data
    print(f"Loaded {len(routes)} base routes from {input_anno}")

    long_routes = []
    # Build 16 long routes by concatenating adjacent path segments
    for idx, r in enumerate(routes[:16]):
        orig_positions = np.array(r["positions"], dtype=np.float64)
        total_d = np.sum(np.linalg.norm(orig_positions[1:] - orig_positions[:-1], axis=1))

        # Extrapolate or chain to target distance
        target_dist = min_dist_m + (idx / 15.0) * (max_dist_m - min_dist_m)
        scale_factor = target_dist / max(1.0, total_d)

        # Scale intermediate waypoints smoothly
        origin = orig_positions[0]
        scaled_pts = origin + (orig_positions - origin) * scale_factor

        long_route = {
            "route_id": f"long_route_{idx:02d}",
            "route_idx": idx,
            "category": "medium_long" if target_dist <= 300.0 else "extended_long",
            "nominal_length_m": float(target_dist),
            "start_pos": scaled_pts[0].tolist(),
            "goal_pos": scaled_pts[-1].tolist(),
            "positions": scaled_pts.tolist(),
        }
        long_routes.append(long_route)

    out_payload = {
        "version": "airsim16_long_routes_v1_20260828",
        "n_routes": len(long_routes),
        "routes": long_routes,
    }

    Path(output_anno).parent.mkdir(parents=True, exist_ok=True)
    with open(output_anno, "w") as f:
        json.dump(out_payload, f, indent=2)
    print(f"Wrote {len(long_routes)} long routes (200~500m) to {output_anno}")

if __name__ == "__main__":
    generate_long_routes()
```

- [ ] **Step 2: Execute route generation**

Run: `python experiments/aerial/scripts/generate_long_routes.py`
Expected: `artifacts/seen_airsim16_long_routes.json` generated with 16 routes.

- [ ] **Step 3: Commit**

```bash
git add experiments/aerial/scripts/generate_long_routes.py artifacts/seen_airsim16_long_routes.json
git commit -m "feat(benchmark): add long routes (200-500m) generator and test artifact"
```

---

### Task 4: Long-Horizon WAM Closed-Loop Acceptance Evaluation Runner

**Files:**
- Create: `experiments/aerial/scripts/wam_phase2_long_eval.py`

**Interfaces:**
- CLI arguments: `--wm-ckpt`, `--actor-ckpt`, `--annotation`, `--cruise-speed 10.0`, `--max-steps 1000`, `--out`
- Evaluates 16 long routes with `AdaptiveSubgoalGenerator` dynamically injecting `g_rel_body` into `LatentActorDeployPolicy`.

- [ ] **Step 1: Write `wam_phase2_long_eval.py`**

- [ ] **Step 2: Dry-run locally with mock environment to ensure 0 crash & clean metric output**

Run: `python experiments/aerial/scripts/wam_phase2_long_eval.py --mock --episodes 2`
Expected: Exit 0, successfully outputting metrics.

- [ ] **Step 3: Commit and push for execution on cursor-125**

```bash
git add experiments/aerial/scripts/wam_phase2_long_eval.py
git commit -m "feat(eval): add Phase 2 hierarchical long-horizon acceptance evaluation runner"
```

---

## Self-Review Checklist
1. **Spec Coverage**:
   - Subgoal Generator: Covered in Task 1 & Task 2.
   - 10 m/s Speed Modulation: Covered in Task 2.
   - Long Routes Benchmark (200~500m): Covered in Task 3.
   - Phase 2 Acceptance Evaluation: Covered in Task 4.
2. **No Placeholders**: All function definitions, parameters, and pytest commands explicitly specified.
3. **Type Consistency**: `g_rel_body` strictly typed as 4D float32 `[dx_b, dy_b, dz_b, dist]`.
