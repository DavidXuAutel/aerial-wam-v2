# V4 M5 STATUS (125 offline)

- **started**: 2026-08-16T10:48:49+08:00
- **finished**: 2026-08-16T11:28:05+08:00
- **agent**: composer-2.5-fast
- **prompt**: docs/handover/V4_M5_125_PROMPT.md
- **HEAD_at_start**: 01ebfa6
- **HEAD_at_finish**: c5823e6
- **renderer**: 127.0.0.1:41451 ✅ (AirSim RPC up)
- **python**: `/home/yao/anaconda3/envs/kairos/bin/python` (airsim + torch + cuda)
- **log**: `artifacts/v4_m5_125_rollout.log`

## enable_policy_update

**Still `false`** in `configs/aerial_rl.yaml` (verified post-run; not flipped per gate rules).

## Commands

```bash
cd ~/aerial-wam-v2

# rollout (4090 local; headon corpus for obstacle-facing scan)
/home/yao/anaconda3/envs/kairos/bin/python experiments/aerial/scripts/v4_gate_run_partials.py rollout4090 \
  --repo ~/aerial-wam-v2 \
  --rollout-dataset ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_headon_20260811 \
  --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_20260816/v4_ac_latest.pt \
  --depth-ckpt experiments/aerial/rl/artifacts/depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt \
  --tau-ckpt experiments/aerial/rl/artifacts/tau_ckpt_foe_r60_20260815/tau_foe_calibrator.pt \
  --env-host 127.0.0.1 \
  --out-dir experiments/aerial/rl/artifacts/v4_gate_r60_20260816 \
  2>&1 | tee artifacts/v4_m5_125_rollout.log

# merge
/home/yao/anaconda3/envs/kairos/bin/python experiments/aerial/scripts/v4_gate_run_partials.py merge \
  --repo ~/aerial-wam-v2 \
  --out-dir experiments/aerial/rl/artifacts/v4_gate_r60_20260816
```

**Note**: first attempt with `anaconda3/bin/python3` (no airsim) → scan `reset_error=1000`.  
**Note**: `dataset_v0_local_depth_r60_20260814` also fails scan on this host; use **headon** corpus.

## M5 results (authoritative partials + merge)

| Signal | Criterion | Result | Numbers |
|---|---|---|---|
| **V4-①** | actor progress ≥ heuristic × 1.10 | ❌ **FAIL** | actor_mean **0.015** vs heur **3.722** (target **4.094**); n=5 scored / 8 scanned |
| **V4-④** | v4 hard coll ≤ v1 baseline; near ratio ≤ 0.80 | ✅ **PASS** | v4_hard **0.00** vs v1_hard **1.00** (remeasured same starts); near_ratio **0.00** |

**Merge**: ❌ **FAIL** (`ok=false`; passed `{1: false, 4: true}`)

Artifacts (gitignored, on disk):

- `experiments/aerial/rl/artifacts/v4_gate_r60_20260816/v4_partial_1_r60_20260816.json`
- `experiments/aerial/rl/artifacts/v4_gate_r60_20260816/v4_partial_4_r60_20260816.json`
- `experiments/aerial/rl/artifacts/v4_gate_r60_20260816/v4_gate_r60_20260816.json`

### V4-④ detail

| Arm | hard coll | near on | near off | near ratio |
|---|---|---|---|---|
| v4 actor shield-on | 0.00 (7 ep) | 0.000 | 0.027 | 0.00 |
| v4 actor shield-off | 0.375 (8 ep) | 0.028 | 0.084 | 0.33 |
| v1 heuristic shield-on (remeasured) | 1.00 (8 ep) | 0.081 | 0.068 | 1.19 |

V1-① authoritative baseline **0.50** documented for reference; comparison used **remeasured** heuristic on same starts (1.00).

## Code delivered

- `experiments/aerial/scripts/v4_gate_run_partials.py` — rollout4090 + merge
- `experiments/aerial/rl/actor_critic.py` — `load_from_checkpoint`, `LatentActorDeployPolicy`

## Next

- M6 flip `enable_policy_update` **blocked** (merge FAIL on ①).
- Actor needs more H100 training or deploy-path fix (negative progress on obstacle-facing starts).
