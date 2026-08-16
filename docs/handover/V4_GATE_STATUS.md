# V4 Gate 状态活文档

> **用途**：V4-MVP merge 进度（镜像 V1 活文档）。  
> **设计**：[V4-MVP 规格](../superpowers/specs/2026-08-16-v4-mvp-design.md)（方案 1）。  
> **前置**：V1 merge PASS + `tau_predictor.kind=foe_calibrated`。

---

## 1. 一句话结论（2026-08-16）

**V4-MVP scaffold 由 125 离线 agent 执行中（M0–M4）**。  
`enable_policy_update` **仍 false**。验收见 `artifacts/V4_125_AGENT_STATUS.md`。

---

## 2. 里程碑

| 步 | 内容 | 状态 |
|---|---|---|
| M0 | 设计规格入库 | 进行中 / 见 125 STATUS |
| M1 | actor_critic + 单测 | 待 |
| M2 | corrector 接线 + smoke | 待 |
| M3 | H100 短训 ckpt | 待 |
| M4 | `_v4_gate` self-check | 待 |
| M5 | 4090 ①④ eval | 待用户验收后 |
| M6 | flip yaml | **禁止**直至 merge PASS |

---

## 3. 变更记录

- **2026-08-16** — 规格落地；125 agent 接手 M0–M4。
