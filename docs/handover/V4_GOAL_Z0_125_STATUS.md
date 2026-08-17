# V4 goal + z0 alignment STATUS (125)

- **status**: **started** — waiting for detached agent Phase 0
- **started**: 2026-08-17T08:59:00+08:00
- **finished**: —
- **agent**: composer-2.5-fast (launch pending PID)
- **PID**: —
- **prompt**: docs/handover/V4_GOAL_Z0_125_PROMPT.md
- **log**: `~/aerial-wam-v2/logs/v4_goal_z0_125_agent.log`
- **HEAD**: (pre-agent; tip after handoff commit)
- **sleep-safe**: **yes** (Mac may sleep once PID confirmed)
- **access**: `cursor-125` direct LAN — see `ACCESS.md` (NOT `cursor-125-public`)

## Goal checklist
1. ⏳ Phase 0 — diagnose: log mean|goal_rel|, mean imagined progress, mean_return (expect ≈0 under mock+null)
2. ⏳ Phase 1 — inject goals into train_v4_ac; H100 AC retrain → `v4_ac_ckpt_*_wm_rh_goal/`
3. ⏳ Phase 2 — align z0 with real RGB (offline encode or short 4090 collect)
4. ⏳ Phase 3 — re-gate ①/④ on 125; honest FAIL/PASS; update V4_GATE_STATUS
5. ⏳ Phase 4 — only if still short: longer train / RH fidelity / vel=0 / actor concat goal_rel
6. ⏳ `enable_policy_update` still **false**

## Phase plan
| Phase | Work | Host |
|---|---|---|
| **0** | Probe train_v4_ac metrics under current mock+annotation:null | 125 or H100 |
| **1** | Goal inject + H100 AC w/ frozen `wm_ckpt_r60_rh_20260816/wm_step_1000.pt` | H100 |
| **2** | Real-RGB z0 (r60/headon encode or 4090 collect buffer) | 125 + H100 |
| **3** | Gate ①/④ + merge | 125 renderer :41451 |
| **4** | Escalations only if ① still short | as needed |

## Phase 0 — diagnose
| Metric | Value | Notes |
|---|---|---|
| mean\|goal_rel\| | — | expect ≈0 |
| mean imagined progress | — | expect ≈0 |
| mean_return | — | — |

## Phase 1 — goal inject + AC
| Field | Value |
|---|---|
| goal source | — (mock episode / annotation / approach-bias) |
| wm ckpt | `wm_ckpt_r60_rh_20260816/wm_step_1000.pt` |
| actor ckpt | — |
| iters | — |
| post-fix mean\|goal_rel\| | — |
| log | — |

## Phase 2 — z0 RGB align
| Field | Value |
|---|---|
| method | — (offline encode / 4090 collect) |
| dataset / buffer | — |
| actor ckpt | — |

## Phase 3 — gate
| Signal | Result | Numbers |
|---|---|---|
| **V4-①** | — | — |
| **V4-④** | — | — |
| **Merge** | — | — |

Artifacts: —

## Prior baseline (reward-head, 2026-08-16)
| Signal | Result |
|---|---|
| ① | ❌ actor −3.17 vs heur 7.44 |
| ④ | ✅ 0.143 ≤ v1 0.25 |
| merge | ❌ |

## enable_policy_update
**false** in `configs/aerial_rl.yaml` (must remain).

## How to check on return
```bash
ssh cursor-125
cd ~/aerial-wam-v2
cat docs/handover/V4_GOAL_Z0_125_STATUS.md
tail -50 logs/v4_goal_z0_125_agent.log
pgrep -af 'agent --print.*V4_GOAL_Z0'
grep enable_policy_update configs/aerial_rl.yaml
```
