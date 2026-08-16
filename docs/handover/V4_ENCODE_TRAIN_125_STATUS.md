# V4 encode + longer train STATUS (125)

- **status**: in_progress — Phase B H100 300-iter train running
- **started**: 2026-08-16T16:38:00+08:00
- **agent_confirmed**: 2026-08-16T16:41:30+08:00
- **updated**: 2026-08-16T17:00:00+08:00
- **handoff**: Mac bootstrap → detached agent on 125
- **prompt**: docs/handover/V4_ENCODE_TRAIN_125_PROMPT.md
- **agent_pid**: **2749229**
- **log**: `~/aerial-wam-v2/logs/v4_encode_train_125_agent.log`
- **sleep-safe**: **yes**

## Goal
1. Align train + deploy to real torch WM encode (not StubLatentDynamics / proprio4).
2. Longer H100 AC train → `v4_ac_ckpt_20260816_wm/`.
3. Re-run V4 ①/④ on 125; update gate docs. Never flip `enable_policy_update`.

## Phase A — encode path (code) ✅
- [x] `load_torch_dynamics()` shared train + deploy
- [x] `train_v4_ac.py` `--dynamics torch` + `--wm-ckpt`
- [x] `v4_gate_run_partials.py` `--dynamics-kind torch` + `--wm-ckpt`
- [x] tests PASSED; legacy ckpt load fix (shape filter + optimizer skip)
- [x] HEAD `8692475` pushed origin; H100 synced via scp

## Phase B — H100 longer train
- **status**: **running** (nohup on H100)
- **WM ckpt**: `/home/a25689/aerial-rl-skeleton/experiments/aerial/rl/artifacts/wm_ckpt_r60_20260814/wm_step_5000.pt`
- **target ckpt dir**: `experiments/aerial/rl/artifacts/v4_ac_ckpt_20260816_wm/`
- **iters**: 300, horizon 15, latent_dim=1536
- **smoke**: 2 iters OK, mean_actor_loss≈0.20
- **log**: `~/aerial-wam-v2/artifacts/v4_ac_train_h100_wm.log`
- **H100 HEAD**: synced files (not git pull — origin-only push policy)

## Phase C — gate on 125
- **pending** — after Phase B; stage actor ckpt from H100
- **out dir**: `experiments/aerial/rl/artifacts/v4_gate_r60_20260816_wm/`
- **renderer**: `127.0.0.1:41451`

## enable_policy_update
**Must stay false** in `configs/aerial_rl.yaml` (verified unchanged).

## Context
- M5 FAIL: actor_mean −13.54 vs heur 9.71 (stub encode); ④ PASS.
- Fixed: r60 ckpt reward-head shape mismatch; encoder/RSSM load, latent_dim=1536.

## How to check

```bash
ssh h100-25 'tail -30 ~/aerial-wam-v2/artifacts/v4_ac_train_h100_wm.log; pgrep -af train_v4_ac'
ls -la experiments/aerial/rl/artifacts/v4_ac_ckpt_20260816_wm/ 2>/dev/null
```
