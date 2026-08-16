# V4 encode + longer train STATUS (125)

- **status**: in_progress — Phase B H100 longer train (legacy ckpt load fix pushed)
- **started**: 2026-08-16T16:38:00+08:00
- **agent_confirmed**: 2026-08-16T16:41:30+08:00
- **updated**: 2026-08-16T16:55:00+08:00
- **handoff**: Mac bootstrap → detached agent on 125
- **prompt**: docs/handover/V4_ENCODE_TRAIN_125_PROMPT.md
- **agent_pid**: **2749229**
- **agent_bin**: `/home/yao/.local/bin/agent` (composer-2.5-fast)
- **log**: `~/aerial-wam-v2/logs/v4_encode_train_125_agent.log`
- **HEAD_at_launch**: `e1ff47f`
- **sleep-safe**: **yes** — Mac may sleep; work runs on 125 (+ H100 via ssh h100-25)

## Goal
1. Align train + deploy to real torch WM encode (not StubLatentDynamics / proprio4).
2. Longer H100 AC train → `v4_ac_ckpt_20260816_wm/`.
3. Re-run V4 ①/④ on 125; update gate docs. Never flip `enable_policy_update`.

## Phase A — encode path (code)
- [x] `load_torch_dynamics()` in `train_rl.py` (shared train + deploy)
- [x] `train_v4_ac.py`: `--dynamics torch`, `--wm-ckpt`; no mock→stub forced when torch
- [x] `v4_gate_run_partials.py`: `--dynamics-kind torch`, `--wm-ckpt`; removes hardcoded stub default for actor
- [x] `test_torch_encode_differs_from_stub_proprio4` in `test_dynamics_torch.py` — **PASSED**
- [x] legacy WM ckpt load: `_filter_compatible_state_dict` (reward-head shape skip)
- [x] commit + `git push origin main`
- [ ] sync H100 → start Phase B

## Phase B — H100 longer train
- **status**: starting (after H100 sync)
- **WM ckpt on H100**: `/home/a25689/aerial-rl-skeleton/experiments/aerial/rl/artifacts/wm_ckpt_r60_20260814/wm_step_5000.pt`
- **target ckpt dir**: `experiments/aerial/rl/artifacts/v4_ac_ckpt_20260816_wm/`
- **planned iters**: 300 (≈1–3h wall)
- **command**:
  ```bash
  ssh h100-25
  cd ~/aerial-wam-v2
  source experiments/aerial/scripts/env_h100.sh
  export PYTHONPATH=$PWD
  python -m experiments.aerial.rl.train_v4_ac \
    --iters 300 --device cuda --imagine-horizon 15 \
    --dynamics torch \
    --wm-ckpt /home/a25689/aerial-rl-skeleton/experiments/aerial/rl/artifacts/wm_ckpt_r60_20260814/wm_step_5000.pt \
    --ckpt-dir experiments/aerial/rl/artifacts/v4_ac_ckpt_20260816_wm \
    2>&1 | tee artifacts/v4_ac_train_h100_wm.log
  ```

## Phase C — gate on 125
- **pending** — stage WM + actor ckpt from H100; renderer `127.0.0.1:41451`
- **out dir**: `experiments/aerial/rl/artifacts/v4_gate_r60_20260816_wm/`
- **dataset**: `~/aerial-rl-skeleton/.../dataset_v0_headon_20260811` (headon fallback)

## enable_policy_update
**Must stay false** in `configs/aerial_rl.yaml` (verified unchanged).

## Context
- M5 merge FAIL: actor_mean −13.54 vs heur 9.71; ④ PASS.
- Prior short train: 10 iters mock/stub → `v4_ac_ckpt_20260816/` (latent_dim=8, wrong encode).
- Blocker fixed: r60 ckpt reward_head.0 shape [256,1536] vs new [256,76]; encoder/RSSM now load.

## How to check

```bash
ssh cursor-125-public
cd ~/aerial-wam-v2
cat docs/handover/V4_ENCODE_TRAIN_125_STATUS.md
ps aux | grep -F V4_ENCODE_TRAIN_125_PROMPT | grep -v grep
pgrep -af 'train_v4_ac|v4_gate_run_partials|v4_encode'
tail -50 logs/v4_encode_train_125_agent.log
ssh h100-25 'tail -20 ~/aerial-wam-v2/artifacts/v4_ac_train_h100_wm.log'
```
