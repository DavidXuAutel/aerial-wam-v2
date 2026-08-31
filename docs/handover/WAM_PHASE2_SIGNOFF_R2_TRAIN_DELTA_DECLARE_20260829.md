# Phase-2 全签 R2 · 训程 delta 声明（2026-08-29）

> **性质**：**训程对照声明**（改 imagination `w_collision`，不改门限 / 不改 yaml 默认）。  
> **纪律检讨**：本应在开训**前**落盘；实际是 Mac 为赶 H100 3h 窗口先开训后补文书 — **违规**，本文补账，不追溯改写 R1。  
> **上游**：[`WAM_PHASE2_SIGNOFF_DECLARE_20260829.md`](WAM_PHASE2_SIGNOFF_DECLARE_20260829.md)（R1 FAIL）。  
> **执行**：[`WAM_PHASE2_SIGNOFF_R2_125_PROMPT.md`](WAM_PHASE2_SIGNOFF_R2_125_PROMPT.md)。

---

## 0. 为什么改方案（相对 R1）

| 项 | R1 | 观测 |
|----|-----|------|
| 配方 | g_norm + `w_collision=10`（yaml 默认）· 500 iter · 同 WM/语料 | 想象 `mean_return≈−63`（Step E 同语料曾 **+10.79**） |
| 闭环 | 16 路 native · cruise=10 | **SR=0%** · SCR=25% · ρ̄=56.6% |
| 归因（R1 DECLARE） | π 弱为主 | 假设：**近恒定 `p_coll≈0.5` × 10 → 每步 −5 税淹没 progress** |

**禁止**：无 delta 复跑 R1；回退 `step_e`；关罩 / Docking 凑 PASS。

---

## 1. 冻结的唯一训程 delta

| 项 | 值 |
|----|-----|
| **唯一变更** | CLI `--w-collision 1.0`（覆盖 yaml `reward.w_collision: 10.0`，**不改仓库默认 yaml**） |
| 其余 | 同 R1：g_norm · `condition_on_goal=True` · 从零 · 500 iter · `dataset_v0_d_full_20260828` · `wm_step_3500` |
| H100 | `a25689@10.239.121.22:31126`（经 125；旧 `.25` Host 勿依赖） |
| ckpt-dir | **`v4_ac_ckpt_phase2_gnorm_r2_20260829`**（勿覆盖 R1） |
| 评测协议 | 同 R1：16 路 · cruise=**10** · planner H=5 · 门限不变 |

**读法**：R2 是 **coll 税权重 ablation**，不是新主航道默认。若 PASS，须另开声明才允许把 yaml 默认改成 1.0。

---

## 2. 训后已测（开训后补记）

| 项 | 值 |
|----|-----|
| 完成 | 500/500 · `v4_ac_latest.pt` @ 2026-08-29 ~15:02 UTC |
| 想象 `mean_return` | 末次汇总 **≈ +3.68**（R1 **−63**；符号已回正） |
| 想象 `mean_progress` | 末 iter 量级 **~0.67–0.79 m/step** |
| 闭环 | 125 16 路 **进行中** → 结果进 [`WAM_PHASE2_SIGNOFF_R2_DECLARE_20260829.md`](WAM_PHASE2_SIGNOFF_R2_DECLARE_20260829.md)（评完由 125 写） |

---

## 3. 红线

- 不得把 R2 结果写成「yaml 已改 w_collision=1」  
- 不得把「想象 return 回正」写成「全签 PASS」——须过 16 路门限  
- 动态三线罩 25 m/s / `v_ref` 是**另一声明**（[`V4_THREE_ZONE_25MS_DECLARE_20260829.md`](V4_THREE_ZONE_25MS_DECLARE_20260829.md)）；本 R2 评测仍 **cruise=10** 与 R1 可比
