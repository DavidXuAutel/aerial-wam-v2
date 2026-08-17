# V4 Gate 状态活文档

> **用途**：V4-MVP merge 进度（镜像 V1 活文档）。  
> **设计**：[V4-MVP 规格](../superpowers/specs/2026-08-16-v4-mvp-design.md)（方案 1）。  
> **前置**：V1 merge PASS + `tau_predictor.kind=foe_calibrated`。

---

## 1. 一句话结论（2026-08-17）

**Goal+z0 track done — merge FAIL（① −8.74 / ④ PASS）** — goal inject + headon RGB z0 fixed train conditioning (goal_rel 0→3.05) but ① **regressed** vs RH-only (−3.17→−8.74); ④ still beats remeasured v1 (0.000 vs 0.429).  
Prior V4 reward-head re-gate：merge FAIL（① −3.17 / ④ PASS）.  
`enable_policy_update` **仍 false**。

---

## 2. 里程碑

| 步 | 内容 | 状态 |
|---|---|---|
| M0 | 设计规格入库 | ✅ |
| M1 | actor_critic + 单测 | ✅ |
| M2 | corrector 接线 + smoke | ✅ `v4_ac_smoke.py` |
| M3 | H100 短训 ckpt | ✅ PASS — `v4_ac_ckpt_20260816/` (stub, superseded) |
| M3b | H100 WM encode 300-iter train | ✅ — `v4_ac_ckpt_20260816_wm/` latent_dim=1536 |
| M4 | `_v4_gate` self-check | ✅ |
| M5 | 4090 ①④ eval (stub) | ❌ merge FAIL — ① −13.54 vs heur 9.71; ④ PASS |
| M5b | 4090 ①④ re-gate (torch WM, legacy RH) | ❌ merge FAIL — ① −68.88; ④ v4_hard 0.143 vs v1 0.00 |
| M5c | reward-head finetune + AC `*_wm_rh` + re-gate | ❌ merge FAIL — ① −3.17 vs heur 7.44; ④ **PASS** (0.143 vs v1 0.25) |
| M5d | goal inject + real RGB z0 + re-gate | ❌ merge FAIL — ① −8.74 vs heur 8.42; ④ **PASS** (0.000 vs v1 0.429) |
| M6 | flip yaml | **禁止**（merge 未 PASS） |

---

## 3. 变更记录

- **2026-08-16** — 规格落地；125 agent 接手 M0–M4。
- **2026-08-16 晚** — M1–M4 代码入库；`_v4_gate --self-check` PASS；`v4_ac_smoke` OK。
- **2026-08-16(M3)** — 125→H100 SSH key; H100 `train_v4_ac` 10 iters PASS (stub).
- **2026-08-16(M5)** — 125 4090 rollout (stub encode): ① FAIL / ④ PASS; yaml 未翻。
- **2026-08-16(encode-train)** — Align train+deploy to torch WM encode; H100 300 iters; re-gate `v4_gate_r60_20260816_wm`: ① FAIL, ④ FAIL; merge FAIL; yaml 未翻.
- **2026-08-16(reward-head)** — M5c done: RH finetune 1000 steps (`wm_ckpt_r60_rh_20260816`); AC 300 iters; re-gate `v4_gate_r60_20260816_wm_rh`: ① FAIL, ④ PASS; merge FAIL; yaml 未翻.
- **2026-08-17(goal+z0)** — M5d done: goal inject + headon RGB z0 AC 300 iters (`v4_ac_ckpt_20260817_wm_rh_goal_rgb`); re-gate `v4_gate_r60_20260817_wm_rh_goal`: ① FAIL (−8.74), ④ PASS; merge FAIL; yaml 未翻.

---

## 4. Latest gate numbers (goal+RGB z0, 2026-08-17)

| Signal | Criterion | Result | Numbers |
|---|---|---|---|
| **V4-①** | actor ≥ heur × 1.10 | ❌ | actor_mean **−8.74** vs heur **8.42** (target **9.26**); n=7 |
| **V4-④** | v4_hard ≤ v1_hard | ✅ | v4_hard **0.000** vs v1 **0.429** (remeasured same starts) |
| **Merge** | both pass | ❌ | `ok=false` `{1: false, 4: true}` |

Artifacts: `experiments/aerial/rl/artifacts/v4_gate_r60_20260817_wm_rh_goal/v4_gate_r60_20260816.json`

### Prior (reward-head WM, 2026-08-16 — superseded)

| Signal | Criterion | Result | Numbers |
|---|---|---|---|
| **V4-①** | actor ≥ heur × 1.10 | ❌ | actor_mean **−3.17** vs heur **7.44** (target **8.18**); n=5 |
| **V4-④** | v4_hard ≤ v1_hard | ✅ | v4_hard **0.143** vs v1 **0.25** (remeasured same starts) |
| **Merge** | both pass | ❌ | `ok=false` `{1: false, 4: true}` |

Artifacts: `experiments/aerial/rl/artifacts/v4_gate_r60_20260816_wm_rh/v4_gate_r60_20260816.json`

### Prior (encode-train, legacy RH skipped — superseded)
| **V4-①** | ❌ | actor_mean **−68.88** vs heur **10.66** |
| **V4-④** | ❌ | v4_hard **0.143** vs v1 **0.00** |

Artifacts: `experiments/aerial/rl/artifacts/v4_gate_r60_20260816_wm/v4_gate_r60_20260816.json`
