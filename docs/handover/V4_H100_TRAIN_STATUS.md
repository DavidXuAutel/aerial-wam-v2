# V4 H100 short train STATUS (M3)

- **date**: 2026-08-16
- **125→H100 key**: `~/.ssh/id_ed25519_h100` / SSH Host `h100-25` → `a25689@10.239.121.25:31126` ✅
- **H100 HEAD**: `793d124`
- **command**:
  ```bash
  python -m experiments.aerial.rl.train_v4_ac --iters 10 --device cuda \
    --imagine-horizon 15 --ckpt-dir experiments/aerial/rl/artifacts/v4_ac_ckpt_20260816
  ```
- **result**: **PASS**
- **ckpt**: `~/aerial-wam-v2/experiments/aerial/rl/artifacts/v4_ac_ckpt_20260816/v4_ac_latest.pt` (~566KB)
- **log**: `~/aerial-wam-v2/artifacts/v4_ac_train_h100.log`
- **metrics**: mean_actor_loss≈-0.043; critic_loss~0.02; entropy~3.67; device=cuda
- **enable_policy_update**: still **false** (not flipped)

## Verification (2026-08-16, local via `ssh h100-25`)

- **ckpt present**: ✅ `~/aerial-wam-v2/experiments/aerial/rl/artifacts/v4_ac_ckpt_20260816/v4_ac_latest.pt`
- **size**: 565931 bytes (553K on disk; matches ~566KB in doc)
- **mtime**: 2026-08-16 02:44:54 UTC
- **enable_policy_update**: unchanged (**false**)
