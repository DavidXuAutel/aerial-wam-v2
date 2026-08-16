# V4 H100 train STATUS (encode + longer)

- **date**: 2026-08-16
- **125→H100 key**: `~/.ssh/id_ed25519_h100` / SSH Host `h100-25` → `a25689@10.239.121.25:31126` ✅
- **H100 code sync**: scp (origin-only push; H100 github pull not used)
- **command**:
  ```bash
  python -m experiments.aerial.rl.train_v4_ac \
    --iters 300 --device cuda --imagine-horizon 15 \
    --dynamics torch \
    --wm-ckpt /home/a25689/aerial-rl-skeleton/experiments/aerial/rl/artifacts/wm_ckpt_r60_20260814/wm_step_5000.pt \
    --ckpt-dir experiments/aerial/rl/artifacts/v4_ac_ckpt_20260816_wm
  ```
- **result**: **PASS** (300 iters, all rl=updated)
- **ckpt**: `~/aerial-wam-v2/experiments/aerial/rl/artifacts/v4_ac_ckpt_20260816_wm/v4_ac_latest.pt` (~3.5MB, latent_dim=1536)
- **log**: `~/aerial-wam-v2/artifacts/v4_ac_train_h100_wm.log`
- **metrics**: mean_actor_loss≈**−0.0005**; dynamics_kind=**torch**; wm step=5000; latent_dim=**1536**
- **lr**: actor_lr=1e-4, critic_lr=1e-4 (from `configs/aerial_rl.yaml` v4 block)
- **enable_policy_update**: still **false** (yaml unchanged; train script sets in-memory only)

## Prior short train (stub encode — superseded)

- 10 iters mock/stub → `v4_ac_ckpt_20260816/` (~566KB, latent_dim=8) — **wrong encode path**

## Next (reward-head track — pending)

After Phase 1 RH finetune, retrain AC into **`v4_ac_ckpt_YYYYMMDD_wm_rh/`** with the new WM ckpt (frozen WM). Record command/metrics here when Phase 2 starts. See `V4_REWARD_HEAD_125_STATUS.md`.

## Verification

```bash
ssh h100-25 'ls -la ~/aerial-wam-v2/experiments/aerial/rl/artifacts/v4_ac_ckpt_20260816_wm/v4_ac_latest.pt'
ssh h100-25 'tail -5 ~/aerial-wam-v2/artifacts/v4_ac_train_h100_wm.log'
```
