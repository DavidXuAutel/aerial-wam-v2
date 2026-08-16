# V4 reward-head fix STATUS (125)

- **status**: **in_progress** — Phase 1A code + load_skipped verified
- **started**: 2026-08-16T22:02:00+08:00
- **finished**: —
- **agent**: composer-2.5-fast
- **PID**: **107628** (ppid=1, setsid-detached)
- **prompt**: docs/handover/V4_REWARD_HEAD_125_PROMPT.md
- **log**: `~/aerial-wam-v2/logs/v4_reward_head_125_agent.log`
- **HEAD**: `de928ec` (pre-Phase-1 commit)
- **sleep-safe**: **yes**

## Goal checklist
1. 🔄 Phase 1 — finetune reward_head (+ feat_proj) frozen encoder/RSSM; wire imagine aux; `load_skipped` empty for reward_head
2. ⏳ Phase 2 — H100 AC retrain → `v4_ac_ckpt_*_wm_rh/`
3. ⏳ Phase 3 — Gate ①/④ re-run + merge + docs; honest FAIL/PASS
4. ✅ `enable_policy_update` still **false** (yaml verified)

## Phase 1A — load_skipped baseline (legacy ckpt)
Legacy `wm_ckpt_r60_20260814/wm_step_5000.pt` on 125:
```
load_skipped reward-related: ['reward_head.0.weight: ckpt(256, 1536) vs model(256, 76)']
load_missing reward-related: ['reward_feat_proj.0.weight', 'reward_feat_proj.0.bias', 'reward_head.0.weight']
```
→ random `reward_feat_proj` + `reward_head` after load (root cause confirmed).

## Phase plan
| Phase | Work | Host | Status |
|---|---|---|---|
| **1A** | Finetune RH; new WM ckpt; assert empty load_skipped | H100 | coding → run |
| **1B** | `imagine()` aux pass-through + tests | 125 code | coding |
| **2** | `train_v4_ac` 300 iters → `v4_ac_ckpt_20260816_wm_rh/` | H100 | pending |
| **3** | gate rollout4090 + merge | 125 | pending |

## Commands (planned)
```bash
# Phase 1A (H100)
ssh h100-25
cd ~/aerial-wam-v2 && git pull origin main
source experiments/aerial/scripts/env_h100.sh
python -m experiments.aerial.rl.train_reward_head \
  --dataset /home/a25689/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_local_depth_r60_20260814 \
  --wm-ckpt /home/a25689/aerial-rl-skeleton/experiments/aerial/rl/artifacts/wm_ckpt_r60_20260814/wm_step_5000.pt \
  --config configs/aerial_rl.yaml --steps 1000 --device cuda \
  --checkpoint-dir experiments/aerial/rl/artifacts/wm_ckpt_r60_rh_20260816
```

## enable_policy_update
Must remain **false** in `configs/aerial_rl.yaml`.
