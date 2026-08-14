# Aerial WAM v2

Pure-vision aerial world model (DreamerV3 RSSM) for OpenFly/AirSim, gated by the **V0 four-signal contract** before any production flags flip.

This repository is a **clean extraction** from the `aerial-rl-skeleton` worktree of `robomaster-tt-control`. It contains only V0 bring-up code, specs, and runbooks — no FastWAM training stack, no B0/B1 orchestration, no Tello flight control.

## Quick links

| Doc | Purpose |
|---|---|
| [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md) | **Current state, formulas, blockers, next steps** |
| [experiments/aerial/RUNBOOK_v0.md](experiments/aerial/RUNBOOK_v0.md) | Top-level V0 runbook (living doc) |
| [docs/handover/V0_GATE_STATUS.md](docs/handover/V0_GATE_STATUS.md) | Gate merge gap + todo list |
| [docs/superpowers/specs/2026-08-04-aerial-wam-v2-frozen-spec.md](docs/superpowers/specs/2026-08-04-aerial-wam-v2-frozen-spec.md) | Frozen thresholds (§4.1) |
| [experiments/aerial/scripts/RUNBOOK_sync_and_env.md](experiments/aerial/scripts/RUNBOOK_sync_and_env.md) | Mac / H100 / 4090 sync & env |

## Machines

| Role | Host |
|---|---|
| Dev (Mac) | This repo |
| Train + offline gate (①③) + rollout client (②④) | `a25689@10.239.121.22:31126` |
| AirSim renderer | `10.229.20.125:41451` |

Artifacts (checkpoints, datasets) live on H100 under `~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/` — **not in git**.

## Minimal setup (H100)

```bash
INSTALL=1 source experiments/aerial/scripts/env_h100.sh
source experiments/aerial/scripts/env_h100.sh
```

## V0 gate (after all four partial JSONs exist)

```bash
python -m experiments.aerial.rl._v0_gate --merge \
  artifacts/v0_partial_1.json \
  artifacts/v0_partial_3.json \
  artifacts/v0_partial_24.json
```

Exit 0 → only then flip `depth_head.enable`, `safety.kind`, `corrector.enable_wm_update` in `configs/aerial_rl.yaml`.

## Provenance

Migrated from git branch `aerial-rl-skeleton` @ `8a063be` (2026-08-12).
