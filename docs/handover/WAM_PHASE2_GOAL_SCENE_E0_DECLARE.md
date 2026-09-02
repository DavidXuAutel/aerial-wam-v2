# E0 DECLARE — goal+scene / no polyline main arm

> **Status**: template — fill after `.110` / `cursor-125` probe  
> **Plan**: [`docs/superpowers/plans/2026-09-03-phase2-goal-scene-nav.md`](../superpowers/plans/2026-09-03-phase2-goal-scene-nav.md)  
> **Spec**: [`docs/superpowers/specs/2026-09-03-phase2-goal-scene-nav-design.md`](../superpowers/specs/2026-09-03-phase2-goal-scene-nav-design.md)

## Command sketch (4090)

```bash
# main E0
python -m experiments.aerial.scripts.wam_phase2_long_eval \
  --subgoal-source toward_g --planner \
  --episodes 2 --max-steps 400 \
  --out artifacts/wam_phase2_e0_toward_g_probe.json

# ablation A
python -m experiments.aerial.scripts.wam_phase2_long_eval \
  --subgoal-source direct_g --planner --episodes 2 --max-steps 400 \
  --out artifacts/wam_phase2_e0_direct_g_probe.json

# waterline对照
python -m experiments.aerial.scripts.wam_phase2_long_eval \
  --subgoal-source polyline --planner --episodes 2 --max-steps 400 \
  --out artifacts/wam_phase2_e0_polyline_probe.json
```

Assist OFF. `step_e` ckpt. No `--rolling-global` on toward_g/direct_g/scene.

## Results (fill)

| Arm | subgoal_source | routes | mean d_min | mean d_final | mean closure | SR | SCR | JSON |
|-----|----------------|--------|------------|--------------|--------------|----|-----|------|
| main | toward_g | | | | | | | |
| A | direct_g | | | | | | | |
| waterline | polyline | | | | | | | |

## Gate

- [ ] Runs complete (no wiring crash)
- [ ] SCR not worse than chaotic / waterline baseline in a scary way
- [ ] **Not** claiming 200–500 m PASS (annos ~110–170 m = engineering probe only)

## Next

- E0 green → flip CLI default `polyline` → `toward_g` (dedicated commit)
- Then E1 `--subgoal-source scene` probe + DECLARE
