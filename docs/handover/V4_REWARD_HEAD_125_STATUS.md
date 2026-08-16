# V4 reward-head fix STATUS (125)

- **status**: **started** — waiting for detached agent Phase 1
- **started**: 2026-08-16T22:02:00+08:00
- **finished**: —
- **agent**: composer-2.5-fast (launch pending PID)
- **PID**: —
- **prompt**: docs/handover/V4_REWARD_HEAD_125_PROMPT.md
- **log**: `~/aerial-wam-v2/logs/v4_reward_head_125_agent.log`
- **HEAD**: (pre-agent; encode-train tip `f3569f0`)
- **sleep-safe**: **yes** (Mac may sleep once PID confirmed)

## Goal checklist
1. ⏳ Phase 1 — finetune reward_head (+ feat_proj) frozen encoder/RSSM; wire imagine aux; `load_skipped` empty for reward_head
2. ⏳ Phase 2 — H100 AC retrain → `v4_ac_ckpt_*_wm_rh/`
3. ⏳ Phase 3 — Gate ①/④ re-run + merge + docs; honest FAIL/PASS
4. ⏳ `enable_policy_update` still **false**

## Phase plan
| Phase | Work | Host |
|---|---|---|
| **1A** | Finetune `reward_feat_proj`+`reward_head` on r60; freeze encoder/RSSM; new WM ckpt; assert `load_skipped` | H100 (prefer) / 125 |
| **1B** | `imagine()` / torch `step` pass `goal_rel`/`body_vel` (or set_goal); cheap tests | 125 code → origin |
| **2** | `train_v4_ac` 300 iters torch WM with rh ckpt → `v4_ac_ckpt_YYYYMMDD_wm_rh/` | H100 via `ssh h100-25` |
| **3** | `v4_gate_run_partials` rollout4090 + merge; update GATE/H100/STATUS | 125 |

## Root cause (from encode-train)
- Legacy `reward_head.0` **(256,1536)** skipped vs new **(256,76)** → random imagination progress
- `imagine()` called `step(z,a)` without aux → zeros into aux-conditioned head
- Gate: ① **−68.88** / ④ **0.143** (see `V4_ENCODE_TRAIN_125_STATUS.md`)

## Chosen fix path
**Finetune** new aux head with frozen backbone (not architecture rollback, not shape-mismatched adapter).

## enable_policy_update
Must remain **false** in `configs/aerial_rl.yaml`.

## How to check on return
```bash
ssh cursor-125-public
cd ~/aerial-wam-v2
cat docs/handover/V4_REWARD_HEAD_125_STATUS.md
tail -80 logs/v4_reward_head_125_agent.log
pgrep -af 'agent --print' || echo no_agent
git log -5 --oneline
```
