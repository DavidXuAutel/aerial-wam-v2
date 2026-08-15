# V1 Gate 状态活文档

> **用途**：V1 三信号 merge 进度与待办（镜像 `V0_GATE_STATUS.md` 治理模型）。  
> **前置**：V0 merge PASS — `v0_gate_r60_20260814.json`（2026-08-14）。  
> **设计（re-freeze 草案）**：[V1/V4 设计 §1.2](../design/2026-08-15-v1-v4-design.md#12-v1-三个同权过关信号re-freeze-草案2026-08-15)。

---

## 1. 一句话结论（2026-08-15 晚¹¹）

**✅ V1a 完成** + **V1b scaffold 已落** + **① PASS**。  
**🟡 V1 partial**：③ proxy PASS；② **仍 FAIL** — action-cond reward 头诚实 5k → `beat_frac=0.53`（**低于** 先前 rew10 的 0.60；需 ≥0.80）。  
**新证据**：held-out 动作几乎常数（`dx≡1`，`dyaw≡0`），`[feature; a]` 对早 horizon 信息量极低；goal 未进 WM / 数据集。  
**禁止**下调 `REWARD_BEAT_FRAC`。**未开 FOE**。**merge 仍 blocked 于 ② + ③ Phase 2**。

产物目录（H100）：`~/aerial-wam-v2/experiments/aerial/rl/artifacts/v1_gate_r60_20260815/`

| 主机 | HEAD |
|---|---|
| Mac / H100 | `96daacd`（action-cond + 文档晚¹¹） |

---

## 2. 三信号：还差什么

| 信号 | 判据（草案） | 最后已知结果（2026-08-15 晚¹¹） | **还差什么** |
|---|---|---|---|
| **V1-①** | 碰撞率相对 V0 ↓20% | ✅ **PASS** — `baseline_kind=tied_zero_collision_bearing` | 无（① 已过） |
| **V1-③** | τ / D̂ 双通道独立 | ✅ **Phase 1 proxy PASS**（非 authoritative） | Phase 2：FOE τ + D̂_pred |
| **V1-②** | H=15 想象保真 | ❌ **FAIL**（actrew 5k `reward_beat_frac=0.53`；done/recon OK） | **goal-rel reward 特征**（或存 goal 进 npz）；勿再指望 a-concat / 加长训 |

---

## 3. 待办（按依赖）

- [x] **V1a-1..2** / **V1b scaffold** / **V1-①** — 见既往
- [x] **V1-② 诚实留出重训** — `wm_ckpt_v1_heldout_20260815` → beat≈0
- [x] **V1-② 诊断** — 对齐 bug + reward 权重；**非** Phase-2 FOE / **非** 多日采数阻塞
- [x] **V1-② 最小实验** — 对齐 + `reward: 10` → beat **0.60**（5k）
- [x] **V1-② 15k 对照** — 同设置 15k → beat **仍 0.60**（早 horizon 平台；非步数不够）
- [x] **V1-② action-cond reward** — `reward_head([feature; a])` train+`step` 对齐；诚实 5k → beat **0.53**（回归；a 近常数）
- [ ] **V1-② 下一跳** — **goal-relative** 输入（数据集写 goal / 或 episode 末位恢复）；或 post-action feature 监督；再诚实 5k
- [ ] **V1-merge** — blocked：② FAIL + ③ proxy
- [ ] **P0b**（可选）— shield 消费 `predict_cones()`

---

## 4. V1-② 诊断（累计）

### 4.1 当前产物（H100）

| 文件 | 要点 |
|---|---|
| `v1_partial_2_r60_20260815.json` | `ok=false`；**actrew 5k** `reward_beat_frac=0.53`；done/recon OK |
| `v1_fidelity_r60_20260815.json` | ckpt=`wm_ckpt_v1_heldout_actrew_20260815/wm_step_5000.pt` |
| `v1_fidelity_actrew_20260815.out` | beat=0.53；h=0..5 仍输 mean-baseline |
| `v1_fidelity_rew10_15k_20260815.out` | 先前最佳对照 beat=0.60 |

### 4.2 根因（已证实）

1. **`step()` +1 偏移（构造 bug）** — 已修；held-out beat **0→0.27**。
2. **reward 梯度被 recon 淹没** — `loss_scales.reward=10` 后 raw CE **3.58→0.70**（5k）；beat **→0.60**。
3. **非 held-out 泛化主因** — 同旧 ckpt 上 train 集 open-loop 也 ≈0。
4. **非阈值/泄漏问题** — 禁止下调 `REWARD_BEAT_FRAC`。
5. **非多日数据阻塞** — 36 train ep 即可 0→0.60；15k 不继续涨。
6. **早 horizon 结构限（更新）** — `NavigationReward`≈Δdist(goal)。`[feature; a]` **已实现**，但 r60 held-out **动作近常数**（`dx≡1`, std≈0；`dyaw≡0`），a 对 reward 相关 ≈0；**goal 不在** `episode_*.npz` / WM 输入 → 早 H 难赢 near-mean constant。

### 4.3 最小实验结果

| 设置 | `reward_beat_frac` | 备注 |
|---|---|---|
| 旧诚实 5k（错对齐，βreward=1） | ≈0.00–0.07 | `wm_ckpt_v1_heldout_20260815` |
| 仅对齐（诊断脚本） | ≈0.27 | |
| 对齐 + βreward=10，诚实 **5k** | **0.60** | `wm_ckpt_v1_heldout_rew10_20260815` |
| 对齐 + βreward=10，诚实 **15k** | **0.60** | 平台 |
| **+ action-cond reward，诚实 5k** | **0.53** | `wm_ckpt_v1_heldout_actrew_20260815`；回归 |

### 4.4 下一跳（仍不改阈值）

1. **优先**：reward 头加 **goal-relative**（采集写 `goal` 进 npz，或用 episode 末 proprio 作 proxy），train+`step` 一致；诚实 5k。
2. 备选：post-action prior feature 监督 reward。
3. **禁止**下调阈值 / 泄漏 ckpt；**暂缓** Phase-2 FOE（② 仍有明确单点实验）。a-concat 可保留（无害于 done/coll；动作多样时仍有用）。

---

## 5. V1 gate partial 跑法

### 5.1 同步

| 主机 | 方式 |
|---|---|
| Mac → origin | `git push` |
| H100 | bastion `cursor-125-public` ProxyJump → `a25689@10.239.121.25:31126`；`git pull` / bundle |

### 5.2 命令

```bash
# H100 — 诚实留出 WM 重训（②；βreward=10；现 reward_head=[feature;a]）
cd ~/aerial-wam-v2 && source .venv/bin/activate && export PYTHONPATH=.
python -m experiments.aerial.rl._wm_train_validate \
  --dataset ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_local_depth_r60_20260814 \
  --steps 5000 --wm-batch 8 --window 8 --horizon 15 \
  --heldout-frac 0.25 --save-ckpt --device cuda \
  --checkpoint-dir ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/wm_ckpt_v1_heldout_actrew_20260815

# H100 — ② fidelity
python -m experiments.aerial.rl._wm_fidelity_eval \
  --dataset ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_local_depth_r60_20260814 \
  --ckpt ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/wm_ckpt_v1_heldout_actrew_20260815/wm_step_5000.pt \
  --config configs/aerial_rl.yaml --heldout-frac 0.25 --horizon 15
```

### 5.3 落盘 partial

| 文件 | 信号 | ok |
|---|---|---|
| `v1_partial_3_r60_20260815.json` | ③ 双通道 | **true**（proxy） |
| `v1_partial_2_r60_20260815.json` | ② fidelity | **false**（actrew 5k beat=0.53） |
| `v1_partial_1_r60_20260815.json` | ① 碰撞率 | **true**（tied-zero） |
| `v1_fidelity_r60_20260815.json` | ② 明细 | reward FAIL @ 0.53（actrew ckpt） |

### 5.4 踩坑

1. **H100 wm ckpt 路径** — 权威在 **`aerial-rl-skeleton/artifacts/`**。
2. **② 禁评** all-ep `wm_step_5000.pt` / 未带 `--heldout-frac` 的训产物。
3. **①** 必须用 `configs/aerial_rl_rollout.yaml`（`grab_depth`）。
4. **③ Phase 1 ≠ PASS** — proxy 不得 merge。
5. **Off-site SSH** — Mac→H100 经 **4090 公网** `cursor-125-public` ProxyJump。
6. **coll 标签** — 必须读 post-step `next_obs.collided`。
7. **reward 头** — cont/coll 在 **pre-action** `[h‖z]`；reward 在 **`[h‖z‖a]`**（与 `training_loss` 一致）。旧 ckpt 的 `reward_head` 形状不兼容，须重训。
8. **r60 动作近常数** — a-concat 对早 H 几乎无信息；下一跳看 **goal**。

---

## 6. V1a / ② 资产（H100）

| 项 | 路径 / 值 |
|---|---|
| 语料 | `dataset_v0_local_depth_r60_20260814`（48 usable / 36 train + 12 held @ 0.25） |
| 旧诚实 5k（β=1，错对齐） | `wm_ckpt_v1_heldout_20260815/wm_step_5000.pt` — beat≈0 |
| rew10 5k / 15k | beat=**0.60**（平台；仍为对照最佳） |
| **当前 ② ckpt（actrew）** | `wm_ckpt_v1_heldout_actrew_20260815/wm_step_5000.pt` — beat=**0.53** |
| r60 all-ep（**非** ②） | `wm_ckpt_r60_20260814/wm_step_5000.pt` |

---

## 7. action-cond 实验（完成）

| 项 | 值 |
|---|---|
| 代码 | `477de66`：`reward_head([feature; action])` train + `step` |
| 5k held-out | beat_frac=**0.53**；`loss_reward` 5.53→0.61；learning+non-div PASS |
| 诊断 | held-out `action`：`dx` std=0、`dyaw` std=0；corr(a,r)≈0；goal 未存 npz |
| 结论 | a-concat **不是**升到 0.80 的杠杆；下一跳 **goal-rel** |

---

## 8. 变更记录

- **2026-08-15(晚¹¹)** — ②：action-cond reward 诚实 5k → beat=0.53（回归）；证实 a 近常数 + 无 goal；下一跳 goal-rel；未开 FOE / 未改阈值。
- **2026-08-15(晚¹⁰)** — ②：15k 对照仍 beat=0.60；判定早 horizon/action 结构限；下一跳 action-cond reward。
- **2026-08-15(晚⁹)** — ②：证实 step/+1 与 reward 权重；rew10 5k → 0.60。
- **2026-08-15(晚⁸…午)** — 诚实留出 FAIL≈0、① PASS、scaffold；见既往。
