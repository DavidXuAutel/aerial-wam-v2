# V1 collision-rich held-out collect STATUS (125 / 4090)

- **status**: **running**
- **started**: 2026-08-17T16:05:40+08:00 (restart; see aborted attempt below)
- **host**: `cursor-125` / `10.229.20.125` (4090)
- **HEAD at launch**: `0541c74` (STATUS commits may be ahead)
- **PID**: `1146088` (`logs/v1_coll_heldout_collect_20260817.pid`)
- **log**: `logs/v1_coll_heldout_collect_20260817.log`
- **dataset**: `experiments/aerial/rl/artifacts/dataset_v1_coll_heldout_20260817`
- **purpose**: WM-unseen collision-rich held-out for cleaner V1-②-coll claim (unique collision episodes **≥3**; r60 diagnostic had unique held-out coll ep=2). Does **not** rewrite 08-15 merge; `enable_policy_update` stays **false**.

## Command (current)

```bash
cd ~/aerial-wam-v2
source experiments/aerial/scripts/env_4090.sh
OUT=experiments/aerial/rl/artifacts/dataset_v1_coll_heldout_20260817
nohup "$PYTHON_BIN" -m experiments.aerial.rl.collect_dataset \
  --backend airsim --host 127.0.0.1 --port 41451 \
  --camera front_custom --vehicle drone_1 \
  --annotation "$ANNOTATION" \
  --episodes 80 --max-steps 200 --step-hz 5.0 \
  --grab-depth \
  --out "$OUT" \
  > logs/v1_coll_heldout_collect_20260817.log 2>&1 &
```

## Design notes

| Choice | Why |
|---|---|
| **no** `--approach-bias` | Abort of approach-d18 (below) got only **1/22** coll — early goal success. Plain r60 recipe historically **9/51** coll |
| `--episodes 80` | Margin over r60’s 60 so unique coll ep≥3 is realistic |
| `--grab-depth --step-hz 5.0` | Schema-v2 / `_refuse_v0` / fidelity-eval compatible |
| manifest via `collect_dataset` | Avoid approach_merged / near_merged “no manifest” failure mode |

## Aborted attempt (same day)

- PID `1134097`, `--approach-bias --approach-dist-m 18 --episodes 60`
- Early sample **1/22** coll; episodes ~17–26 steps (goal reached before obstacles)
- Artifacts kept under `dataset_v1_coll_heldout_20260817_abort_approach_d18_*` + matching log

## Unchanged (do not flip)

- `enable_policy_update: false`
- 08-15 V1 merge JSON / yaml gate flags
- No Desk API / Franka network changes

## Immediate health (restart)

- Renderer `:41451` up (`AirVLN-Linux-Shipping`)
- `ep 0: 116 steps @ 5.0 Hz | path 108.49 m | OK`
- Longer flights vs approach-d18 (as expected for far annotation goals)

## Next (after collect finishes — do not start until then)

1. Confirm `manifest.json` + usable collision count (`count_dataset_collisions.py` / load skip-quarantined); need unique coll ep **≥3**.
2. Tar+ssh dataset to H100 `.25` under `~/aerial-rl-skeleton/.../artifacts/`.
3. On H100: WM fidelity / V1-②-coll diagnostic on this held-out — **not** rewrite 08-15 merge unless unique coll ep≥3 and protocol agreed.
