# DECLARE · P0 Receding Global Reference · 2026-09-02

> **状态**：**码已接线 · 默认 OFF**（`--rolling-global`）· 待 `.110` 评测准出  
> **计划**：[`docs/superpowers/plans/2026-09-02-phase2-receding-global-full.md`](../superpowers/plans/2026-09-02-phase2-receding-global-full.md) Task 4–5  
> **模块**：`experiments/aerial/rl/global_ref_planner.py`  
> **禁止**：assist / F15 / 单路局部坑当门；勿称「已上 MPC」

---

## 1. 行为

| 项 | 值 |
|----|-----|
| 开关 | `--rolling-global`（默认 **False**） |
| 视界 | `--global-horizon-m` 默认 60 |
| 重规划周期 | `--global-replan-period-s` 默认 1.0 |
| 走廊 \(\mathcal{F}\) | 标注折线（与回锚同 annotation） |
| 局部 | 冻结 `step_e` + AdaptiveSubgoal 吃短 `P_ref` |
| 停机 | **仅** `‖p−G‖≤3`（rolling 开时） |
| Ckpt | `v4_ac_ckpt_step_e_20260828` |
| Assist | OFF |

---

## 2. 评测门（`.110`）

对照：`artifacts/wam_phase2_reanchor_stepe_result_20260830.json`（同 annotation 索引）。

| 指标 | 准出 |
|------|------|
| Primary | SR / SPL / SCR / `mean_goal_closure` / `n_monotone_inflate` |
| P0 门 | 相对回锚同路：**mean `goal_closure` ↑** 或 mean `d_min` ↓ ≥5 m，且 SCR 不升；SR 不恶化 |
| 子集 | 先全 16 或固定 8 路均可；**不以单路探针定生死** |
| Fail | 保持默认 OFF；只允平滑/代价修（Task 6），不开 F15 |

```bash
source experiments/aerial/scripts/env_4090.sh
python experiments/aerial/scripts/wam_phase2_long_eval.py \
  --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt \
  --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_step_e_20260828/v4_ac_latest.pt \
  --annotation artifacts/seen_airsim16_long_routes.json \
  --cruise-speed 10.0 --planner --planner-horizon 5 --max-steps 1000 \
  --rolling-global --global-horizon-m 60 --global-replan-period-s 1.0 \
  --out artifacts/wam_phase2_p0_rolling_result.json
```

---

## 3. 结果栏（评测后填）

| 项 | 回锚 | P0 rolling | Δ |
|----|------|------------|---|
| SR | 0 | | |
| mean_goal_closure | ≈0.43 | | |
| n_monotone_inflate | 13/16 | | |
| SCR | 0.125 | | |
| verdict | | | |

---

## 4. 签字

| 项 | 值 |
|----|-----|
| 实现 | Mac / 本会话 Task 1–3 |
| 评测 owner | cursor-125 → `.110` |
| 默认开主航道 | 仅本表 PASS 后 Task 7 |
