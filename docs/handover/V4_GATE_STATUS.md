# V4 Gate 状态活文档

> **用途**：V4-MVP merge 进度（镜像 V1 活文档）。  
> **设计**：[V4-MVP 规格](../superpowers/specs/2026-08-16-v4-mvp-design.md)（方案 1）。  
> **前置**：V1 merge PASS + `tau_predictor.kind=foe_calibrated`。

---

## 1. 一句话结论（2026-08-16）

**V4-MVP M5 4090 eval 完成：merge FAIL（① progress 未达标，④ 安全 PASS）**。  
`enable_policy_update` **仍 false**（生产 yaml 未翻；M6 禁止）。  
细节见 `docs/handover/V4_M5_125_STATUS.md`。

---

## 2. 里程碑

| 步 | 内容 | 状态 |
|---|---|---|
| M0 | 设计规格入库 | ✅ |
| M1 | actor_critic + 单测 | ✅ |
| M2 | corrector 接线 + smoke | ✅ `v4_ac_smoke.py` |
| M3 | H100 短训 ckpt | ✅ PASS — `v4_ac_ckpt_20260816/v4_ac_latest.pt` |
| M4 | `_v4_gate` self-check | ✅ |
| M5 | 4090 ①④ eval | ❌ merge **FAIL** — ① actor_mean=0.015 vs heur=3.72; ④ v4_hard=0.0≤v1=1.0 ✅ |
| M6 | flip yaml | **禁止**（merge 未 PASS） |

---

## 3. 变更记录

- **2026-08-16** — 规格落地；125 agent 接手 M0–M4。
- **2026-08-16 晚** — M1–M4 代码入库；`_v4_gate --self-check` PASS；`v4_ac_smoke` OK。

- **2026-08-16(M3)** — 125→H100 SSH key; H100 `train_v4_ac` 10 iters PASS.
- **2026-08-16(M5)** — 125 4090 rollout: `v4_gate_run_partials.py rollout4090` + merge; ① FAIL / ④ PASS; yaml 未翻。
