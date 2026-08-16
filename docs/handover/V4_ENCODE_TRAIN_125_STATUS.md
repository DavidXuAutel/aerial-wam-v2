# V4 encode + longer train STATUS (125)

- **status**: starting
- **started**: 2026-08-16T16:38:00+08:00
- **handoff**: Mac bootstrap → detached agent on 125
- **prompt**: docs/handover/V4_ENCODE_TRAIN_125_PROMPT.md
- **agent_pid**: (pending launch)
- **log**: ~/aerial-wam-v2/logs/v4_encode_train_125_agent.log
- **sleep-safe**: pending (set yes once PID confirmed)

## Goal
1. Align train + deploy to real torch WM encode (not StubLatentDynamics / proprio4).
2. Longer H100 AC train → `v4_ac_ckpt_20260816_wm/`.
3. Re-run V4 ①/④ on 125; update gate docs. Never flip `enable_policy_update`.

## Context
- M5 merge FAIL: actor_mean −13.54 vs heur 9.71; ④ PASS.
- Prior short train: 10 iters mock/stub → `v4_ac_ckpt_20260816/`.
- WM on H100 (aerial-rl-skeleton): `wm_ckpt_r60_20260814/wm_step_5000.pt` (prefer); also `wm_ckpt_v1a_20260815/`.

## enable_policy_update
**Must stay false** in `configs/aerial_rl.yaml`.

## How to check

```bash
ssh cursor-125-public
cd ~/aerial-wam-v2
cat docs/handover/V4_ENCODE_TRAIN_125_STATUS.md
pgrep -af 'agent --print.*ENCODE|v4_encode_train'
tail -50 logs/v4_encode_train_125_agent.log
```
