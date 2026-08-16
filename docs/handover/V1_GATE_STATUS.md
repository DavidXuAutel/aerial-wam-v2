# V1 Gate 状态活文档

> **用途**：V1 三信号 merge 进度与待办（镜像 `V0_GATE_STATUS.md` 治理模型）。  
> **前置**：V0 merge PASS — `v0_gate_r60_20260814.json`（2026-08-14）。  
> **设计（re-freeze 草案）**：[V1/V4 设计 §1.2](../design/2026-08-15-v1-v4-design.md#12-v1-三个同权过关信号re-freeze-草案2026-08-15)。

---

## 1. 一句话结论（2026-08-15 晚¹⁵ · rigor）

**✅ V1 merge PASS（严谨口径）** — ① **δ 实证** + ② honest held-out + ③ Phase 2 auth（含 V0 ③ reproj 证据绑定）。

| 主机 | HEAD |
|---|---|
| Mac / 125 bare / H100 | `86dd457`+（① 拒 tied-zero；晚¹⁵ 实测后文档提交） |

**yaml 已 flip**（`tau_predictor.kind=foe_calibrated`；`planner.enable`/`enable_policy_update` 仍 false）。  
**下一步**：[V4-MVP](../superpowers/specs/2026-08-16-v4-mvp-design.md) — V4 scaffold M1–M4 完成，见 [V4_GATE_STATUS](V4_GATE_STATUS.md)。

产物（H100）：

- merge：`experiments/aerial/rl/logs/v1_gate_r60_20260815/v1_gate_r60_20260815.json`（`ok=true`）
- ①：`artifacts/v1_gate_r60_20260815/v1_partial_1_r60_20260815.json`
- ②：`logs/.../v1_partial_2_r60_20260815.json`
- ③：`logs/.../v1_partial_3_auth_r60_20260815.json`

---

## 2. 三信号（严谨复核后）

| 信号 | 判据 | 结果 |
|---|---|---|
| **V1-①** | `v0>0` 且 `v1 ≤ 0.8×v0`；V1=`foe_calibrated`；trigger=1.5 | ✅ **auth PASS** — `delta_reduction`；hard **v0=0.75 → v1=0.50**（target≤0.60）；off_hard=1.0 |
| **V1-②** | honest held-out；beat≥0.80；coll N/A if pos&lt;3 | ✅ PASS — goalvel beat=**0.93**；`coll_ok=null`（pos=1，不足 3）；done/recon/latent OK |
| **V1-③** | FOE+D̂；both_fail≤0.20；τ MAE≤2；**V0 ③ reproj≤0.25 同 ckpt** | ✅ auth PASS — both_fail=0.0013；MAE=0.935；`v0_reproj_evidence.median=0.212`（`v0_partial_3_r60_20260814.json`） |

### 软过 → 严谨（晚¹⁵）

| 信号 | 曾软过 | 问题 | 晚¹⁵ 处置 |
|---|---|---|---|
| **①** | `tied_zero_collision_bearing`（hard 双 0，trigger=3.0，τ=`gt_proxy`） | δ 未测；V1 非产品 τ | 代码默认拒 tied-zero；trigger=**1.5** + **foe_calibrated** 重跑 → **δ PASS** |
| **②** | merge JSON `coll_ok=true` | fidelity 仅 **+1/−11** 碰撞轨，AUROC 不应 authoritative | 按 §1.2.2 重记 **`coll_ok=null`**；overall 仍由 reward 等 PASS |
| **③** | `v0_reproj_note` 口头引用 | 未绑定数字/路径 | 写入 **`v0_reproj_evidence`**（median 0.212，n=90，同 r60 ft-head） |

---

## 3. 待办

- [x] V1a / 严谨 ① δ / ② honest / ③ Phase 2 auth + **merge**
- [x] **人工**：yaml `tau_predictor.kind=foe_calibrated` + `ckpt=.../tau_foe_calibrator.pt` (**flipped 2026-08-15 on 125**)
- [ ] **可选**：增采含碰撞 held-out（使 ② `coll_traj_pos≥3` 可评 AUROC）；P0b cones；V4

---

## 4. 资产与数字

### ① authoritative（H100→4090，晚¹⁵）

| 项 | 值 |
|---|---|
| τ | `foe_calibrated` + `tau_ckpt_foe_r60_20260815/tau_foe_calibrator.pt` |
| trigger | **1.5 m**（metric band；非 3.0 standoff） |
| hard v0 / v1 / off | **0.75 / 0.50 / 1.0** |
| target_max | 0.60（δ=0.20） |
| near_ep v0 / v1 | 0.625 / 0.875（hard 为主判据；near 未单独 gate） |
| scan | 8/8；probe collided=8 |
| log | `artifacts/v1_partial1_auth_rerun.log` |

### ② goalvel

| 项 | 值 |
|---|---|
| ckpt | `wm_ckpt_v1_heldout_goalvel_20260815/wm_step_5000.pt` |
| meta | `heldout_frac=0.25`，train eps=**36**/48，`authoritative=true` |
| fidelity | held-out 12 ep；beat=**0.933**；latent_norm_max=21.3 |
| coll | pos=**1** → N/A；log AUROC=0.909 仅诊断 |
| out | `artifacts/v1_fidelity_goalvel_20260815.out` |

### ③ auth FOE

| 指标 | 值 | 阈 |
|---|---|---|
| both_fail_frac | 0.0013 | ≤0.20 |
| tau_only_frac | 0.010 | ≥0.005 |
| tau_mae_s | 0.935 | ≤2.0 |
| depth_pred_vs_gt_both_fail | 0.0045 | ≤0.35（设计） |
| V0 ③ reproj median | **0.212**（n=90） | ≤0.25 |

---

## 5. 复现 merge

```bash
cd ~/aerial-wam-v2 && source experiments/aerial/scripts/env_h100.sh && export PYTHONPATH=$PWD
LOG=experiments/aerial/rl/logs/v1_gate_r60_20260815
ART=experiments/aerial/rl/artifacts/v1_gate_r60_20260815
python -m experiments.aerial.rl._v1_gate --merge \
  $ART/v1_partial_1_r60_20260815.json \
  $LOG/v1_partial_2_r60_20260815.json \
  $LOG/v1_partial_3_auth_r60_20260815.json \
  --emit $LOG/v1_gate_r60_20260815.json
```

严谨 ① 重跑：

```bash
python experiments/aerial/scripts/v1_gate_run_partials.py rollout4090 \
  --rollout-dataset ~/aerial-rl-skeleton/.../dataset_v0_headon_20260811 \
  --depth-ckpt ~/aerial-rl-skeleton/.../depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt \
  --tau-kind foe_calibrated \
  --tau-ckpt ~/aerial-rl-skeleton/.../tau_ckpt_foe_r60_20260815/tau_foe_calibrator.pt \
  --shield-trigger-m 1.5 \
  --n-episodes 8 --device cuda
# 禁止 --allow-tied-zero
```

---

## 6. 变更记录

- **2026-08-15(晚¹⁵)** — **严谨复核**：① 拒 tied-zero 并 δ 重跑 PASS（0.75→0.50）；② `coll_ok` 改 N/A；③ 绑定 V0 reproj 证据；**merge 重出 ok=true**。代码 `86dd457`。
- **2026-08-15(晚¹⁴)** — Phase 2 FOE；auth ③；曾 merge（① 为 soft tied-zero，后撤销权威性）。
- **2026-08-15(晚¹³)** — ② goalvel beat=0.93。
- **2026-08-15(晚¹²…午)** — scaffold / 首跑 partial / harness 修复等（见 git log）。

---

## Deploy flip (follow-up 2026-08-15)

**Done on 125:** `tau_predictor.kind=foe_calibrated`, `use_gt_depth=false`, ckpt=`/home/a25689/aerial-rl-skeleton/experiments/aerial/rl/checkpoints/tau_ckpt_foe_r60_20260815/tau_foe_calibrator.pt`.

- `planner.enable` remains **false**
- `enable_policy_update` remains **false** (needs V4 gate re-freeze — do not flip)
- Next focus: **V4** entry (re-freeze checklist below)
- Ops: commit on 125 → push local bare `origin` → sync H100; Mac may sleep

### V4 entry checklist (do not start training update yet)

- [ ] Re-freeze V4 gate criteria in design doc
- [ ] Confirm imagination / actor-critic eval harness
- [ ] Only then consider flipping `enable_policy_update: true`
- [ ] Keep planner.enable policy separate from V4 AC update

