# V1 Gate 状态活文档

> **用途**：V1 三信号 merge 进度与待办（镜像 `V0_GATE_STATUS.md` 治理模型）。  
> **前置**：V0 merge PASS — `v0_gate_r60_20260814.json`（2026-08-14）。  
> **设计（re-freeze 草案）**：[V1/V4 设计 §1.2](../design/2026-08-15-v1-v4-design.md#12-v1-三个同权过关信号re-freeze-草案2026-08-15)。

---

## 1. 一句话结论（2026-08-15 晚¹⁰）

**✅ V1a 完成** + **V1b scaffold 已落** + **① PASS**。  
**🟡 V1 partial**：③ proxy PASS；② **仍 FAIL** — 诚实 `beat_frac=0.60`（5k 与 **15k 同值**；需 ≥0.80）。  
**根因**：`step()` +1 对齐 + reward 权重（已修，0→0.60）；**加长训不再涨**。余量在 **h=0..5**：reward≈goal-progress，头 **不见 action**，1-step 难赢 constant。  
**非多日采数阻塞**。**merge 仍 blocked 于 ② + ③ Phase 2**。

产物目录（H100）：`~/aerial-wam-v2/experiments/aerial/rl/artifacts/v1_gate_r60_20260815/`

| 主机 | HEAD |
|---|---|
| Mac / H100 | `3f566af`（对齐+βreward=10；文档晚⁹） |

---

## 2. 三信号：还差什么

| 信号 | 判据（草案） | 最后已知结果（2026-08-15 晚⁹） | **还差什么** |
|---|---|---|---|
| **V1-①** | 碰撞率相对 V0 ↓20% | ✅ **PASS** — `baseline_kind=tied_zero_collision_bearing` | 无（① 已过） |
| **V1-③** | τ / D̂ 双通道独立 | ✅ **Phase 1 proxy PASS**（非 authoritative） | Phase 2：FOE τ + D̂_pred |
| **V1-②** | H=15 想象保真 | ❌ **FAIL**（honest `reward_beat_frac=0.60` @5k**=**15k）；done/recon/latent OK | **action-condition reward 头**（progress 依赖 a）；**勿**下调阈值；加长训已证明平台 |

---

## 3. 待办（按依赖）

- [x] **V1a-1..2** / **V1b scaffold** / **V1-①** — 见既往
- [x] **V1-② 诚实留出重训** — `wm_ckpt_v1_heldout_20260815` → beat≈0
- [x] **V1-② 诊断** — 对齐 bug + reward 权重；**非** Phase-2 FOE / **非** 多日采数阻塞
- [x] **V1-② 最小实验** — 对齐 + `reward: 10` → beat **0.60**（5k）
- [x] **V1-② 15k 对照** — 同设置 15k → beat **仍 0.60**（早 horizon 平台；非步数不够）
- [ ] **V1-② 下一跳** — reward 头 **concat action**（或 post-action feature 监督），因 `NavigationReward`≈Δdist(goal) 强依赖 a；再诚实 5k 复评
- [ ] **V1-merge** — blocked：② FAIL + ③ proxy
- [ ] **P0b**（可选）— shield 消费 `predict_cones()`

---

## 4. V1-② 诊断（2026-08-15 晚⁹）

### 4.1 当前产物（H100）

| 文件 | 要点 |
|---|---|
| `v1_partial_2_r60_20260815.json` | `ok=false`；**honest rew10 15k** `reward_beat_frac=0.60`；done/recon OK |
| `v1_fidelity_r60_20260815.json` | ckpt=`wm_ckpt_v1_heldout_rew10_15k_20260815/wm_step_15000.pt` |
| `v1_fidelity_rew10_20260815.out` | 5k：beat=0.60 |
| `v1_fidelity_rew10_15k_20260815.out` | 15k：beat=0.60（中后程 MAE 更好，h=0..5 仍输） |

### 4.2 根因（已证实）

1. **`step()` +1 偏移（构造 bug）** — `training_loss` 用 **pre-action** `[h_t‖z_t]` 拟合 `reward_t`；旧 `step()` 在 **post-action prior** 上读头再比 `reward_t`。仅改对齐：held-out beat **0→0.27**（仍 FAIL）。
2. **reward 梯度被 recon 淹没** — `loss_pred = recon + reward + …` 无独立权重；jsonl 原先甚至不记 `loss_reward`。设 `loss_scales.reward=10` 后 raw CE **3.58→0.70**（5k）。
3. **非 held-out 泛化主因** — 同旧 ckpt 上 **train 集 open-loop beat_frac 也 ≈0**；teacher-forced 仅弱过 constant（corr≈0.28）。
4. **非阈值/泄漏问题** — 禁止下调 `REWARD_BEAT_FRAC`；泄漏 all-ep 0.53 作废。
5. **非多日数据阻塞** — 36 train ep 即可 0→0.60；15k 不继续涨 → **不是「再采几天」优先**。
6. **早 horizon 结构限** — `NavigationReward` 主项是 goal-progress（依赖 **action**）；reward 头只看 `[h‖z]`，开环用录制 a 时 1-step/h≤5 难赢 near-mean constant。

### 4.3 最小实验结果

| 设置 | `reward_beat_frac` | 备注 |
|---|---|---|
| 旧诚实 5k（错对齐，βreward=1） | ≈0.00–0.07 | `wm_ckpt_v1_heldout_20260815` |
| 仅对齐（诊断脚本） | ≈0.27 | |
| 对齐 + βreward=10，诚实 **5k** | **0.60** | `wm_ckpt_v1_heldout_rew10_20260815` |
| 对齐 + βreward=10，诚实 **15k** | **0.60** | `wm_ckpt_v1_heldout_rew10_15k_20260815`；平台 |

### 4.4 下一跳（仍不改阈值）

1. **最小代码实验**：`reward_head([feature; action])`（train+`step` 一致），诚实 5k 复评 — 优先于再加长训 / 再抬 βreward。
2. 备选：用 post-action prior feature 监督 reward（使头看见 a 的后果）。
3. **禁止**下调阈值 / 泄漏 ckpt；**暂缓** Phase-2 FOE（② 仍有明确单点实验）。

---

## 5. V1 gate partial 跑法

### 5.1 同步

| 主机 | 方式 |
|---|---|
| Mac → origin | `git push` |
| H100 | bastion `cursor-125-public` ProxyJump → `a25689@10.239.121.25:31126`；`git pull` / bundle |

### 5.2 命令

```bash
# H100 — 诚实留出 WM 重训（②；现默认 βreward=10 @ configs/aerial_rl.yaml）
cd ~/aerial-wam-v2 && source .venv/bin/activate && export PYTHONPATH=.
python -m experiments.aerial.rl._wm_train_validate \
  --dataset ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_local_depth_r60_20260814 \
  --steps 5000 --wm-batch 8 --window 8 --horizon 15 \
  --heldout-frac 0.25 --save-ckpt --device cuda \
  --checkpoint-dir ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/wm_ckpt_v1_heldout_rew10_20260815

# H100 — ② fidelity
python -m experiments.aerial.rl._wm_fidelity_eval \
  --dataset ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_local_depth_r60_20260814 \
  --ckpt ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/wm_ckpt_v1_heldout_rew10_20260815/wm_step_5000.pt \
  --config configs/aerial_rl.yaml --heldout-frac 0.25 --horizon 15
```

### 5.3 落盘 partial

| 文件 | 信号 | ok |
|---|---|---|
| `v1_partial_3_r60_20260815.json` | ③ 双通道 | **true**（proxy） |
| `v1_partial_2_r60_20260815.json` | ② fidelity | **false**（rew10 15k beat=0.60） |
| `v1_partial_1_r60_20260815.json` | ① 碰撞率 | **true**（tied-zero） |
| `v1_fidelity_r60_20260815.json` | ② 明细 | reward FAIL @ 0.60（15k ckpt） |

### 5.4 踩坑

1. **H100 wm ckpt 路径** — 权威在 **`aerial-rl-skeleton/artifacts/`**。
2. **② 禁评** all-ep `wm_step_5000.pt` / 未带 `--heldout-frac` 的训产物。
3. **①** 必须用 `configs/aerial_rl_rollout.yaml`（`grab_depth`）。
4. **③ Phase 1 ≠ PASS** — proxy 不得 merge。
5. **Off-site SSH** — Mac→H100 经 **4090 公网** `cursor-125-public` ProxyJump。
6. **coll 标签** — 必须读 post-step `next_obs.collided`。
7. **reward 头** — `step()` 必须在 **pre-action** feature 上读头（与 `training_loss` 一致）。

---

## 6. V1a / ② 资产（H100）

| 项 | 路径 / 值 |
|---|---|
| 语料 | `dataset_v0_local_depth_r60_20260814`（48 usable / 36 train + 12 held @ 0.25） |
| 旧诚实 5k（β=1，错对齐） | `wm_ckpt_v1_heldout_20260815/wm_step_5000.pt` — beat≈0 |
| **当前最佳 ② ckpt** | `wm_ckpt_v1_heldout_rew10_15k_20260815/wm_step_15000.pt` — beat=0.60 |
| 5k rew10（同 beat） | `wm_ckpt_v1_heldout_rew10_20260815/wm_step_5000.pt` |
| r60 all-ep（**非** ②） | `wm_ckpt_r60_20260814/wm_step_5000.pt` |

---

## 7. 诚实留出 + rew10 实验（完成）

| 项 | 值 |
|---|---|
| 代码 | `5d85ca2`：pre-action `step()` + `loss_scales.reward=10` + jsonl `loss_reward` |
| 5k | beat_frac=**0.60**；`loss_reward` 3.58→0.70 |
| 15k | beat_frac=**0.60**（平台）；中后程 MAE↓；entropy_frac min≈0.18 |
| 结论 | 对齐+权重有效；**再加长无效** → 下一跳 action-condition |

---

## 8. 变更记录

- **2026-08-15(晚¹⁰)** — ②：15k 对照仍 beat=0.60；判定早 horizon/action 结构限；下一跳 action-cond reward；未开 FOE / 未改阈值。
- **2026-08-15(晚⁹)** — ②：证实 step/+1 与 reward 权重；rew10 5k → 0.60。
- **2026-08-15(晚⁸…午)** — 诚实留出 FAIL≈0、① PASS、scaffold；见既往。
