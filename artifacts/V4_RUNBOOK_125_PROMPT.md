# V4 RUNBOOK 125 — 主线 handoff（2026-08-24 · 6ap 已签）

You are on **4090** `cursor-125`, repo `~/aerial-wam-v2`.

## 优先级

1. **V4 主线** — P4.5 控制臂 **⓪h 权威 emit**（见下）
2. **TZ-3Z** — **不要新开**（并行支线已结案；除非用户点名）

`enable_policy_update` = **false**。R-16 = **(B)**。**不要**跑 P8 / supervisor / 降 `n`。

## 6ap 已签（2026-08-24）

[`V4_ZERO_PRIMARY_MIGRATION_REFREEZE_20260824.md`](../docs/handover/V4_ZERO_PRIMARY_MIGRATION_REFREEZE_20260824.md) **12/12**：

- **P3 primary** = `⓪a∧⓪b∧⓪c∧⓪h∧⓪e`（**⓪h** @ engage_outer **12.2 m**）
- **⓪d@3m** → JSON `0d_legacy` **report-only**（FAIL 不阻塞 merge）
- **禁止**仅为过 ⓪d_legacy 开 depth FT

`v4_zero_eval.py` 已接 ⓪h（Mac sync 后确认 `aggregate_verdict` keys 含 `0h`）。

## 当前事实

- P4.5 语料 **DONE**：`dataset_v0_p45_merged_20260821`（77 ep，近带 315 帧）
- 旧控制臂 `oldhead_merged_20260821`：**⓪d_legacy FAIL**（`consec=2`）— **不再 gate**
- TZ 诊断：同老头 ⓪h hold035/full77 **双 PASS**（先验，非 p45 证书）
- Deploy = `three_zone` 8/5/1.5 @ 2/1

## 你的下一发（只做这个，除非 BLOCKED）

```bash
cd ~/aerial-wam-v2
git pull   # 须含 6ap harness + runbook
source experiments/aerial/scripts/env_4090.sh
DATA=experiments/aerial/rl/artifacts/dataset_v0_p45_merged_20260821
OLD=experiments/aerial/rl/artifacts/depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt
TAU=experiments/aerial/rl/artifacts/tau_ckpt_foe_r60_20260815/tau_foe_calibrator.pt
$AERIAL_PY -m experiments.aerial.rl.v4_zero_eval \
  --dataset "$DATA" --depth-ckpt "$OLD" --tau-ckpt "$TAU" --device cuda \
  --heldout-frac 0.35 --split-seed 0 \
  --emit artifacts/v4_zero_p3_oldhead_p45_hold035_20260824.json \
  2>&1 | tee logs/v4_zero_p3_oldhead_hold035_20260824.log
```

**通过标准（汇报用）**：

- `verdict.ok` = **⓪h primary 合取**（看 `sub.0h`，不是 `0d_legacy`）
- ⓪b support 仍 PASS
- 落盘 `0d_legacy` + `clearance_sweep` + `n_near_forward_frames` + `n_tau_cond`
- ⓪c / ⓪f 按 RUNBOOK §2.1 读（**不改阈值**）

**若 ⓪h PASS**：P4.5 深度项结案；更新 handoff。**若 ⓪h FAIL**：R-16 (B) 下车站；**不要**自动 depth FT。

**可选同轮**：P1 coll 复评 on `wm_ckpt_p45_merged_20260821/wm_step_500.pt`。

## 禁止

- P7-accept / P8 / 连续 supervisor
- 仅为过 ⓪d_legacy depth FT
- `#26` / `5ao` 摘 D̂ OR 腿
- 把 TZ ⓪h 当 p45 权威证书

## 交付

1. 跑完上表 eval（或 BLOCKED 原因）
2. 更新 `docs/handover/V4_RUNBOOK_125_STATUS.md` 主线表
3. `artifacts/V4_RUNBOOK_125_ISSUES.md` 若有新阻塞
4. commit + push（125 侧）
