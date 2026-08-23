# V4 RUNBOOK 125 STATUS

- **date**: 2026-08-24
- **state**: **V4 主线** — **6ap 已签（2026-08-24）**；P4.5 / P3 权威 **⓪h primary**（`v4_zero_eval` 已接）；下一发 = 125 hold035 emit
- **enable_policy_update**: false
- **R-16**: **(B)**
- **深度头（部署）**：`depth_ckpt_da3_r60_20260814`；v1–v3 **不部署、不开训**
- **罩子（deploy yaml）**：`safety.kind: three_zone`（P3 **⓪h@12.2m** 对齐；⓪d@3m **legacy 对照**）
- **判据 / 执行**：[`RUNBOOK_v4.md`](../../experiments/aerial/RUNBOOK_v4.md)；[`V4_GATE_STATUS.md`](V4_GATE_STATUS.md)

## V4 主线 — 当前阻塞与下一发（125 / H100）

| 步 | 状态 | 下一发 |
|----|------|--------|
| **P4.5** | 🟡 语料 77ep ✅；re-P1 已跑 | **控制臂 hold035 权威 emit**（⓪h primary；产物见下） |
| **P3 ⓪** | ⏳ **待 6ap 后重 emit** | ⓪d_legacy 预期仍 FAIL（只报）；**merge 看 ⓪h** |
| **P1** | ❌ `p_coll` AUROC 0.549 | P4.5 WM 上已重跑；coll 仍 FAIL |
| **P4 ⓿** | ⚠️ ⓿e `infeasible`（teleport） | 与 P4.5 **正交**；harness 侧并行 |
| **P7 / P8** | ⬜ | **P8 前** ⓪/⓿/P1 须 authoritative |

**125 推荐命令（H100 或 125 CUDA，不重训）**：

```bash
cd ~/aerial-wam-v2 && source experiments/aerial/scripts/env_4090.sh
DATA=experiments/aerial/rl/artifacts/dataset_v0_p45_merged_20260821
OLD=experiments/aerial/rl/artifacts/depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt
TAU=experiments/aerial/rl/artifacts/tau_ckpt_foe_r60_20260815/tau_foe_calibrator.pt
$AERIAL_PY -m experiments.aerial.rl.v4_zero_eval \
  --dataset "$DATA" --depth-ckpt "$OLD" --tau-ckpt "$TAU" --device cuda \
  --heldout-frac 0.35 --split-seed 0 \
  --emit artifacts/v4_zero_p3_oldhead_p45_hold035_20260824.json \
  2>&1 | tee logs/v4_zero_p3_oldhead_hold035_20260824.log
```

- **禁止**：⓪h 权威 FAIL 前开 depth FT；仅为过 ⓪d_legacy depth FT；TZ-3Z 语料训 WM；剥 D̂ OR 腿（`5ao` 挂起）
- **Mac**：只改文档 / handoff；长跑在 **cursor-125**

## TZ-3Z 并行支线（**结案** · 不阻塞 V4 merge）

> 部署路线 = **三线 + D**；离线诊断 `authoritative=false`。详见下方 #27/#28/TZ-3Z 节。

## #26 τ-miss（老头 · 4090 · `authoritative=false` · **挂起**）

> **2026-08-23**：部署路线裁定为 **三线 + D** ⇒ #24 (b) 全面 τ 化 **不推进**；本节 hold035 产物保留作对照，**full77 / T-2 非当前阻塞**。

| 切片 | 状态 | T-1 `p_tau_miss` | T-1 consec | `n_tau_miss_cond` | ⓪d（对照） |
|------|------|------------------|------------|-------------------|------------|
| hold035 | ✅ DONE | **0.6441** | **5** | 59 | miss 0.114, consec 2 |
| full77 | 🟡 同批 job 续跑 | — | — | — | — |

- **产物**：`artifacts/v4_tau_miss_oc_hold035_20260822.json`（full77 → `…_full77_…`）
- **log**：`logs/v4_tau_miss_oc_20260822.log`；**PID** `3998697`（launcher）
- **sync**：2026-08-22 Mac → 125：`v4_zero_eval.py` / `tau_predictor.py` / `depth_geometry.py` + tests
- **B-a**：hold035 `dt_fallback=0`
- **红线**：D̂ OR 腿未动；不发证
- **罩子 v5（2026-08-22）**：`safety.py` 运动学站位 — `min_depth_m` = **3 m 内须稳停** 外边界；`D̂ < 3 + v·min_tau_s` 提前减速（阈值未改）；待 sync 125 后重采/重评

**初读（hold035）**：τ-miss **远高于** ⓪d miss（0.64 vs 0.11），consec 更差（5 vs 2）⇒ 未签 `5ao` 前**不能**据 T-1 单独推 (b)；待 full77 + T-2 φ。

## #27 三线限速 × 深度精度预算（老头 · 4090 · **结案** · `authoritative=false`）

| 方案 | 切片 | 动力学 | 深度 vs 预算 | 总判 |
|------|------|--------|--------------|------|
| **8/5/1.5 @ 2/1**（推荐） | hold035 | ✅ engage≥12.2m | ✅ | **✅** |
| 8/5/1.5 @ 2/1 | full77 | ✅ | ❌ engage p95欠读 3.01m > 预算 3.0m | ❌ 边际 |
| 7/5/1.5 @ 2/1（用户原案） | hold035 | ❌ 余量 0 | — | ❌ |
| **7/5/1.5 @ 2/0.75** | hold035 | ✅ engage≥11.2m | ✅ | **✅** |

- **完整结论**：[`V4_THREE_ZONE_DECLARE_20260823.md`](V4_THREE_ZONE_DECLARE_20260823.md)
- **产物**：`artifacts/v4_three_zone_oldhead_{hold035_8m,full77_8m,hold035_7m,hold035_7m_v075}_20260822.json`
- **harness**：`v4_three_zone_eval.py` + `test_three_zone_eval.py`
- **裁定**：推荐 **8/5/1.5@2/1**；**已接线 deploy**（`safety.kind: three_zone`）；⓪d@3m 退役

## #25 B-2 滞回（老头 · 4090 · 已否定）

| 切片 | consec(δ=0..2) | rate δ0→δ2 | 3–5 m 误触 |
|------|----------------|------------|-----------|
| hold035 | **全 2** | 0.114→0.057 | 0.67→0.95 |
| 全77 | **全 2** | 0.076→0.028 | 0.55→0.87 |

**裁定**：engage/release **压不了 consec**；不升格 B。声明：[`V4_HYSTERESIS_SCAN_DECLARE_20260821.md`](V4_HYSTERESIS_SCAN_DECLARE_20260821.md)

## #28 5 Hz 速度曲线（4090 loopback · **DONE** · `authoritative=false`）

- **harness**：`experiments/aerial/rl/step_hz_velocity_profile.py`
- **产物（open-loop）**：`artifacts/step_hz_profile_5hz_{rgb,depth}_20260823.json`
- **产物（shield-on）**：`artifacts/step_hz_profile_5hz_shield_on_20260823.json`（GT `D̂` proxy + `ThreeZoneSpeedShield`）
- **open-loop**：`achieved_hz≈4.99`；巡航 **~4.85 m/s**；制动 decel p90 **≈3.23 m/s²**（> 三线假设 2.5）；depth 与 RGB **无显著差**
- **shield-on（2026-08-23）**：`achieved_hz≈4.99`；巡航 **~1.0 m/s**（GT 前向 depth 落在 **5 m 带**，`cmd_fwd≈0.2`/step）；制动 p90 **≈3.22 m/s²**；**无额外 observe 税**（复用 `reset`/`step` obs）

## TZ-3Z 支线：老头 · 125 采 + H100 评（`authoritative=false`）

- **声明**：[`V4_THREE_ZONE_BRANCH_125_H100_20260823.md`](V4_THREE_ZONE_BRANCH_125_H100_20260823.md)
- **launcher**：`experiments/aerial/scripts/v4_three_zone_branch.sh`
- **分工**：125 = shield-on collect；H100 = `v4_three_zone_eval`（125 ssh 触发）
- **老头**：`depth_ckpt_da3_r60_20260814`；**不重训**

### 语料与 eval（2026-08-23 **DONE**）

| 语料 | ep | path/ep | 评价 |
|------|-----|---------|------|
| `…_20260823`（无 annotation） | 22 | ~0.3 m | **废弃** |
| `…_20260823b` / `c` | 21+21 | ~11 m | 开阔远距；annotation OK |
| `…_20260823_merged` | 42 | mean **11.0 m** | 开阔主集；gt_fwd min **9.3 m**；L 带 **0 帧** |
| `…_near_20260823f` / `g` | 9 + 3 | ~10 m | blocked 近障；`topup_near` 补采 |
| **`…_near_20260823fg`** | **12** | — | **P1 目标达成**（f+g merge） |
| **`…_oldhead_20260823_full`** | **54** | — | **42 open + 12 near**；TZ-3Z eval 主语料 |

| eval（H100 · merged 42） | engage_outer | L1/L2/L3 | 总判 |
|--------------------------|--------------|----------|------|
| hold035 | n=30，p95 **0.95 m** | no support | ✅ engage only |
| full77 | n=59，p95 **0.99 m** | no support | ✅ engage only |

| eval（H100 · **full 54** · `20260823_full`） | engage_outer | cap_l1 | cap_l2 | cap_l3 | **⓪h** | 总判 |
|-----------------------------------------------|--------------|--------|--------|--------|--------|------|
| hold035 | n=32，p95 **0.95 m** | n=21 | n=40，p95 **0.63 m** | n=32，p95 **1.37 m** | n=473，p=**0.017**，consec=**3** | **✅** |
| full77 | n=97，p95 **0.99 m** | n=46 | n=93，p95 **1.33 m** | n=32，p95 **1.37 m** | n=1552，p=**0.010**，consec=**3** | **✅** |

- **产物**：`artifacts/v4_three_zone_branch_{hold035,full77}_20260823_{merged,full}.json`
- **log**：`logs/v4_three_zone_supp_20260823.log`（b/c）；`logs/v4_three_zone_topup_20260823g.log`（P1 f→g→fg→full）
- **P1 排障**：`v4_p45_collect` 扫层误用 `aerial_rl.yaml` 默认 `backend:mock` → 已修强制 `airsim`；launcher 增 `MODE=topup_near`

### 部署路线：三线 + D（2026-08-23）

| 层 | 量 | 角色 |
|----|-----|------|
| 主控 | `D̂` → `planned_speed(d)` | 8/5/1.5 m 分级限速 |
| 应急 | `τ`、`p_coll` | latch + 后退（不改） |
| 离线 primary | **⓪h** engage-miss | **已冻结**（DECLARE §4c；`20260823_full` H100 **PASS**） |
| **不做** | #24 (b) 摘 D OR 腿 | `5ao` 挂起 |

### P1 近障补采（**DONE** · `MODE=topup_near`）

```bash
# 首轮（9 ep）+ 补采（3 ep）示例
STAMP=20260823_full NEAR_STAMP=20260823g PRIOR_NEAR_STAMP=20260823f \
  NEAR_COMBINED_STAMP=20260823fg PER_LAYER=4 BLOCKED_SEED=101 MODE=topup_near \
  bash experiments/aerial/scripts/v4_three_zone_branch.sh
```

- `collect_near`：`v4_p45_collect` + `three_zone` yaml；`goal-dist-m 30` / `probe-near-m 1.5` / `p45_balanced` pool
- `merge_near`：f(9) + g(3) → **fg(12)**；`merge_full`：merged(42) + fg(12) → **full(54)**

## Checklist

- [x] 深度头冻结老头
- [x] K-min B-1 否定
- [x] B-2 Phase C 否定（不升格）
- [x] `#27` 三线结案（declare 20260823）
- [x] harness sync + `#26` 开跑（hold035 DONE）
- [x] `#28` 5 Hz 速度曲线（rgb + depth）→ `a_max` 实测 ~3.23，设计保留 2.5
- [x] TZ-3Z：merged 42 ep + H100 eval **DONE**（engage ✅）
- [x] TZ-3Z P1：近障 **12 ep** → `20260823_full` **54 ep** + hold035/full77 **双 PASS**
- [x] ⓪h engage-miss re-freeze + harness（`v4_three_zone_eval` §0h）
- [x] ⓪h 入账 H100 eval（`20260823_full` hold035+full77 **双 PASS**）
- [x] shield-on 5 Hz 速度曲线（#28 后续 · P3）
- [x] Mac 合入 + sync 125（`44d7c78`）
- [ ] **V4 主线**：控制臂 hold035 重评（`v4_zero_eval` on `p45_merged`）
- [ ] **V4 主线**：⓪ 权威 FAIL 归因 → 是否开 depth loss 声明（**须 FAIL 后**）
- [ ] **V4 主线**：P1 `p_coll` 复测 / P4 ⓿e harness

## Running jobs

| job | PID | log |
|-----|-----|-----|
| — | — | （无） |
