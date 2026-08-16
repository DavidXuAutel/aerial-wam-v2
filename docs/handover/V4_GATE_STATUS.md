# V4 Gate 状态活文档

> **用途**：V4-MVP merge 进度（镜像 V1 活文档）。  
> **设计**：[V4-MVP 规格](../superpowers/specs/2026-08-16-v4-mvp-design.md)（方案 1）。  
> **前置**：V1 merge PASS + `tau_predictor.kind=foe_calibrated`。

---

## 1. 一句话结论（2026-08-16）

**V4 encode-train re-gate：merge FAIL（① −68.88 / ④ 0.143）** — encode path OK；根因是 reward_head 旧形 (256,1536) 跳过加载 + imagine 缺 `goal_rel`。  
**Follow-on 已启动**：reward-head finetune → AC retrain → re-gate（`V4_REWARD_HEAD_125_STATUS.md`）。  
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
| M5b | 4090 ①④ re-gate (torch WM) | ❌ merge FAIL — ① −68.88 vs heur 10.66; ④ v4_hard 0.143 |
| M5c | reward-head finetune + AC `*_wm_rh` + re-gate | ⏳ in progress — see `V4_REWARD_HEAD_125_STATUS.md` |
| M6 | flip yaml | **禁止**（merge 未 PASS） |

---

## 3. 变更记录

- **2026-08-16** — 规格落地；125 agent 接手 M0–M4。
- **2026-08-16 晚** — M1–M4 代码入库；`_v4_gate --self-check` PASS；`v4_ac_smoke` OK。
- **2026-08-16(M3)** — 125→H100 SSH key; H100 `train_v4_ac` 10 iters PASS (stub).
- **2026-08-16(M5)** — 125 4090 rollout (stub encode): ① FAIL / ④ PASS; yaml 未翻。
- **2026-08-16(encode-train)** — Align train+deploy to torch WM encode; H100 300 iters; re-gate `v4_gate_r60_20260816_wm`: ① FAIL, ④ FAIL; merge FAIL; yaml 未翻.
- **2026-08-16(reward-head)** — Start M5c: finetune RH (frozen encoder/RSSM) + imagine aux + H100 `v4_ac_ckpt_*_wm_rh` + re-gate; yaml 未翻.

---

## 4. Latest gate numbers (torch WM, 2026-08-16)

| Signal | Criterion | Result | Numbers |
|---|---|---|---|
| **V4-①** | actor ≥ heur × 1.10 | ❌ | actor_mean **−68.88** vs heur **10.66** (target **11.72**); n=6 |
| **V4-④** | v4_hard ≤ v1_hard | ❌ | v4_hard **0.143** vs v1 **0.00** (remeasured same starts) |
| **Merge** | both pass | ❌ | `ok=false` |

Artifacts: `experiments/aerial/rl/artifacts/v4_gate_r60_20260816_wm/v4_gate_r60_20260816.json`
