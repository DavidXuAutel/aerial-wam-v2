# V1 Gate 状态活文档

> **用途**：V1 三信号 merge 进度与待办（镜像 `V0_GATE_STATUS.md` 治理模型）。  
> **前置**：V0 merge PASS — `v0_gate_r60_20260814.json`（2026-08-14）。  
> **设计（re-freeze 草案）**：[V1/V4 设计 §1.2](../design/2026-08-15-v1-v4-design.md#12-v1-三个同权过关信号re-freeze-草案2026-08-15)。

---

## 1. 一句话结论（2026-08-15 晚¹³）

**✅ V1a 完成** + **V1b scaffold 已落** + **① PASS** + **② PASS**（goalvel 诚实 5k → `beat_frac=0.93` ≥0.80）。  
**🟡 V1 partial**：③ 仍为 Phase 1 **proxy** PASS（非 authoritative）→ **merge 仍 blocked 于 ③ Phase 2**。  
**路径**：goalrel raw concat 仍 0.53（oracle=1.0 证伪缺特征）→ `reward_aux(û, log1p(d), body_vel, analytic)` + feature proj（`39ead6b`）→ **0.93**。  
**禁止**下调 `REWARD_BEAT_FRAC`。**未开 FOE**。

产物目录（H100）：`~/aerial-wam-v2/experiments/aerial/rl/logs/v1_gate_r60_20260815/`

| 主机 | HEAD |
|---|---|
| Mac / 4090 bare / H100 | `0257b90`+（gate docs；② 代码自 `39ead6b`） |

---

## 2. 三信号：还差什么

| 信号 | 判据（草案） | 最后已知结果（2026-08-15 晚¹³） | **还差什么** |
|---|---|---|---|
| **V1-①** | 碰撞率相对 V0 ↓20% | ✅ **PASS** — `baseline_kind=tied_zero_collision_bearing` | 无（① 已过） |
| **V1-②** | H=15 想象保真 | ✅ **PASS**（goalvel 5k `reward_beat_frac=0.93`；done/recon/coll OK） | 无（② 已过） |
| **V1-③** | τ / D̂ 双通道独立 | ✅ **Phase 1 proxy PASS**（非 authoritative） | Phase 2：FOE τ + D̂_pred |

---

## 3. 待办（按依赖）

- [x] **V1a-1..2** / **V1b scaffold** / **V1-①** — 见既往
- [x] **V1-② 诚实留出重训** — `wm_ckpt_v1_heldout_20260815` → beat≈0
- [x] **V1-② 诊断** — 对齐 bug + reward 权重；**非** Phase-2 FOE / **非** 多日采数阻塞
- [x] **V1-② 最小实验** — 对齐 + `reward: 10` → beat **0.60**（5k）
- [x] **V1-② 15k 对照** — 同设置 15k → beat **仍 0.60**
- [x] **V1-② action-cond reward** — beat **0.53**（回归；a 近常数）
- [x] **V1-② goal-rel** — beat **0.53**（仍 FAIL；oracle=1.0）
- [x] **V1-② body_vel analytic aux** — `39ead6b` / ckpt `goalvel` → beat **0.93** ✅
- [ ] **V1-③ Phase 2** — FOE τ + D̂_pred（**下一阻塞**；现仍禁止为 ② 开 FOE 的旧禁令已随 ② PASS 解除，但启动需单独拍板）
- [ ] **V1-merge** — blocked：**仅** ③ Phase 2
- [ ] **P0b**（可选）— shield 消费 `predict_cones()`

---

## 4. V1-② 诊断（累计）

### 4.1 当前产物（H100）

| 文件 | 要点 |
|---|---|
| `v1_partial_2_r60_20260815.json` | `ok=true`；**goalvel 5k** `reward_beat_frac=0.93` |
| `v1_fidelity_goalvel_20260815.out` | ckpt=`wm_ckpt_v1_heldout_goalvel_20260815/wm_step_5000.pt`；**PASS** |
| `v1_fidelity_goalrel_20260815.out` | 对照：raw goal_rel beat=**0.53** |
| goals | backfill **51/51**；kinematic oracle **beat=1.0** |

### 4.2 根因（已证实）

1. **`step()` +1 偏移** — 已修；beat 0→0.27。
2. **reward 梯度被 recon 淹没** — `loss_scales.reward=10` → beat 0.60。
3. **非 held-out / 非阈值 / 非缺步数** — 见晚⁹–¹⁰。
4. **早 H 动作近常数且过冲** — a-concat / raw `goal_rel` 信息量不足（均 0.53）。
5. **goal-rel 未学会** — 特征齐（oracle=1.0）；raw metre-scale 4-D 被 1536-D feature 淹没；早 H 指令动作 ≫ `body_vel×dt`。
6. **修复（已验证）** — scale-stable `reward_aux` + `reward_feat_proj(64)` → beat **0.93**。

### 4.3 最小实验结果

| 设置 | `reward_beat_frac` | 备注 |
|---|---|---|
| 旧诚实 5k（错对齐，β=1） | ≈0.00–0.07 | |
| 对齐 + βreward=10，5k / 15k | **0.60** | 平台 |
| + action-cond / + raw goal_rel | **0.53** | 回归 |
| **+ body_vel analytic aux，5k** | **0.93** ✅ | `wm_ckpt_v1_heldout_goalvel_20260815` |

### 4.4 下一跳

1. **② 已过** — 勿再改 reward 头阈值。
2. **优先**：V1-③ Phase 2（FOE），单独拍板后启动。
3. **禁止**下调 `REWARD_BEAT_FRAC` / 泄漏 ckpt。

---

## 5. V1 gate partial 跑法

### 5.1 同步

| 主机 | 方式 |
|---|---|
| Mac → 4090 bare | bastion `cursor-125-public` + `git bundle`（直连 22 / GitHub 443 常挂） |
| H100 | 同 bastion → `sshpass` → `a25689@10.239.121.25:31126`；`git fetch` bundle |

### 5.2 命令（② 已过；复现）

```bash
cd ~/aerial-wam-v2 && source .venv/bin/activate && export PYTHONPATH=.
# 已训 ckpt：wm_ckpt_v1_heldout_goalvel_20260815
python -m experiments.aerial.rl._wm_fidelity_eval \
  --dataset ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_local_depth_r60_20260814 \
  --ckpt ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/wm_ckpt_v1_heldout_goalvel_20260815/wm_step_5000.pt \
  --config configs/aerial_rl.yaml --heldout-frac 0.25 --horizon 15

python experiments/aerial/scripts/v1_gate_run_partials.py h100 \
  --repo ~/aerial-wam-v2 \
  --dataset ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_local_depth_r60_20260814 \
  --wm-ckpt ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/wm_ckpt_v1_heldout_goalvel_20260815/wm_step_5000.pt \
  --out-dir experiments/aerial/rl/logs/v1_gate_r60_20260815
```

### 5.3 落盘 partial

| 文件 | 信号 | ok |
|---|---|---|
| `v1_partial_3_r60_20260815.json` | ③ 双通道 | **true**（proxy） |
| `v1_partial_2_r60_20260815.json` | ② fidelity | **true**（goalvel 5k beat=0.93） |
| `v1_partial_1_r60_20260815.json` | ① 碰撞率 | **true**（tied-zero） |
| `v1_fidelity_goalvel_20260815.out` | ② 明细 | **PASS** @ 0.93 |

### 5.4 踩坑

1. **H100 wm ckpt 路径** — 权威在 **`aerial-rl-skeleton/artifacts/`**。
2. **② 禁评** all-ep / 未带 `--heldout-frac` 的训产物。
3. **reward 头** — `proj(h‖z) ‖ a ‖ reward_aux(goal_rel, body_vel, a)`；旧 ckpt 形状不兼容。
4. **Off-site SSH** — Mac→H100 经 `cursor-125-public` + `sshpass`（Cloudflare 偶发 timeout）。

---

## 6. V1a / ② 资产（H100）

| 项 | 路径 / 值 |
|---|---|
| 语料 | `dataset_v0_local_depth_r60_20260814`（goals 51/51） |
| rew10 对照 | beat=**0.60** |
| goalrel 对照 | beat=**0.53** |
| **当前 ② ckpt（PASS）** | `wm_ckpt_v1_heldout_goalvel_20260815/wm_step_5000.pt` — beat=**0.93** |

---

## 7. goalvel 实验（完成；PASS）

| 项 | 值 |
|---|---|
| 代码 | `39ead6b`：`reward_aux` + `reward_feat_proj`；train/`step` 对齐 |
| 5k held-out | beat_frac=**0.93**；learning+non-div PASS；仅 h=4 输 mean-baseline |
| 对照 | goalrel raw concat = 0.53；oracle = 1.0 |
| 结论 | body_vel×dt analytic 是升到 ≥0.80 的杠杆 |

---

## 8. 变更记录

- **2026-08-15(晚¹³)** — ②：**goalvel 5k → beat=0.93 PASS**；partial_2 刷新；merge 仅剩 ③ Phase 2；未开 FOE / 未改阈值。
- **2026-08-15(晚¹²)** — ②：goalrel 5k → 0.53；oracle=1.0；代码 body_vel aux。
- **2026-08-15(晚¹¹…午)** — actrew / rew10 / 对齐诊断；见既往。
