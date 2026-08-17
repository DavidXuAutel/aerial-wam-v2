# V1 collision-rich held-out collect STATUS (125 / 4090)

- **status**: **running**
- **started**: 2026-08-17T16:03:00+08:00
- **host**: `cursor-125` / `10.229.20.125` (4090)
- **HEAD**: `0541c74`
- **PID**: `1134097` (also `logs/v1_coll_heldout_collect_20260817.pid`)
- **log**: `logs/v1_coll_heldout_collect_20260817.log`
- **dataset**: `experiments/aerial/rl/artifacts/dataset_v1_coll_heldout_20260817`
- **purpose**: collision-rich **WM-unseen held-out** for a cleaner V1-②-coll claim (unique collision episodes **≥3**; r60 diagnostic had unique held-out coll ep=2). Does **not** rewrite 08-15 merge; `enable_policy_update` stays **false**.

## Command

```bash
cd ~/aerial-wam-v2
source experiments/aerial/scripts/env_4090.sh
OUT=experiments/aerial/rl/artifacts/dataset_v1_coll_heldout_20260817
nohup "$PYTHON_BIN" -m experiments.aerial.rl.collect_dataset \
  --backend airsim --host 127.0.0.1 --port 41451 \
  --camera front_custom --vehicle drone_1 \
  --annotation "$ANNOTATION" \
  --episodes 60 --max-steps 200 --step-hz 5.0 \
  --grab-depth --approach-bias --approach-dist-m 18 \
  --out "$OUT" \
  > logs/v1_coll_heldout_collect_20260817.log 2>&1 &
```

## Design notes

| Choice | Why |
|---|---|
| `--approach-bias --approach-dist-m 18` | Historical approach/near corpora produced more collisions than plain r60 / headon (headon coll=0 for ②-coll) |
| `--episodes 60` | Same volume as r60 collect; annotation cycles (`seen_airsim16_m1a20`, 20 starts) |
| `--grab-depth --step-hz 5.0` | Schema-v2 / `_refuse_v0` / fidelity-eval compatible (r60 practice) |
| manifest via `collect_dataset` | Avoid approach_merged / near_merged “no manifest” failure mode |

## Unchanged (do not flip)

- `enable_policy_update: false`
- 08-15 V1 merge JSON / yaml gate flags
- No Desk API / Franka network changes

## Immediate health (start)

- Renderer `:41451` up (`AirVLN-Linux-Shipping`)
- `approach-bias ON: goals -> start + 18.0 m along start yaw (20 eps)`
- `ep 0: 20 steps @ 5.0 Hz | path 15.32 m | OK`

## Next (after collect finishes — do not start until then)

1. Confirm `manifest.json` + usable collision count (`count_dataset_collisions.py` / load skip-quarantined).
2. Tar+ssh dataset to H100 `.25` under `~/aerial-rl-skeleton/.../artifacts/`.
3. On H100: WM fidelity / V1-②-coll diagnostic on this held-out (new ckpt or held-out split) — **not** rewrite 08-15 merge unless unique coll ep≥3 and protocol agreed.
