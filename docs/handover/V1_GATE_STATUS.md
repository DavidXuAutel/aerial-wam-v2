# V1 Gate 状态活文档

> **用途**：V1 三信号 merge 进度与待办（镜像 `V0_GATE_STATUS.md` 治理模型）。  
> **前置**：V0 merge PASS — `v0_gate_r60_20260814.json`（2026-08-14）。  
> **设计（re-freeze 草案）**：[V1/V4 设计 §1.2](../design/2026-08-15-v1-v4-design.md#12-v1-三个同权过关信号re-freeze-草案2026-08-15)。

---

## 1. 一句话结论（2026-08-15 晚¹²）

**✅ V1a 完成** + **V1b scaffold 已落** + **① PASS**。  
**🟡 V1 partial**：③ proxy PASS；② **仍 FAIL** — goal-rel reward 头诚实 5k → `beat_frac=0.53`（与 actrew 持平；**低于** 先前 rew10 的 0.60；需 ≥0.80）。  
**新证据**：goals 已 backfill 51/51；同数据 **kinematic oracle beat=1.0** → 特征在、标签可解，**模型未学会用 `goal_rel`**（raw metre concat 被 1536-D feature 淹没；早 H 指令动作 ≫ 实现位移）。  
**下一跳代码已落**（Mac HEAD `39ead6b`）：`reward_aux(û, log1p(d), body_vel, analytic Δdist)` + feature proj；待 H100 诚实 5k。  
**禁止**下调 `REWARD_BEAT_FRAC`。**未开 FOE**。**merge 仍 blocked 于 ② + ③ Phase 2**。

产物目录（H100）：`~/aerial-wam-v2/experiments/aerial/rl/logs/v1_gate_r60_20260815/`

| 主机 | HEAD |
|---|---|
| Mac | `39ead6b`（body_vel aux；待推 / 待训） |
| H100（最后评测） | `f41bd3b`（goalrel 5k beat=0.53） |

---

## 2. 三信号：还差什么

| 信号 | 判据（草案） | 最后已知结果（2026-08-15 晚¹²） | **还差什么** |
|---|---|---|---|
| **V1-①** | 碰撞率相对 V0 ↓20% | ✅ **PASS** — `baseline_kind=tied_zero_collision_bearing` | 无（① 已过） |
| **V1-③** | τ / D̂ 双通道独立 | ✅ **Phase 1 proxy PASS**（非 authoritative） | Phase 2：FOE τ + D̂_pred |
| **V1-②** | H=15 想象保真 | ❌ **FAIL**（goalrel 5k `reward_beat_frac=0.53`；done/recon OK） | **body_vel × dt analytic aux** 诚实 5k（代码 `39ead6b`）；勿再指望 raw `goal_rel` concat |

---

## 3. 待办（按依赖）

- [x] **V1a-1..2** / **V1b scaffold** / **V1-①** — 见既往
- [x] **V1-② 诚实留出重训** — `wm_ckpt_v1_heldout_20260815` → beat≈0
- [x] **V1-② 诊断** — 对齐 bug + reward 权重；**非** Phase-2 FOE / **非** 多日采数阻塞
- [x] **V1-② 最小实验** — 对齐 + `reward: 10` → beat **0.60**（5k）
- [x] **V1-② 15k 对照** — 同设置 15k → beat **仍 0.60**（早 horizon 平台；非步数不够）
- [x] **V1-② action-cond reward** — `reward_head([feature; a])`；诚实 5k → beat **0.53**（回归；a 近常数）
- [x] **V1-② goal-rel** — backfill goals + `reward_head([feature; a; goal_rel])`；诚实 5k → beat **0.53**（仍 FAIL；oracle=1.0）
- [ ] **V1-② 下一跳** — **body_vel analytic aux**（`39ead6b`）诚实 5k；目标 beat→0.80
- [ ] **V1-merge** — blocked：② FAIL + ③ proxy
- [ ] **P0b**（可选）— shield 消费 `predict_cones()`

---

## 4. V1-② 诊断（累计）

### 4.1 当前产物（H100）

| 文件 | 要点 |
|---|---|
| `v1_partial_2_r60_20260815.json` | `ok=false`；**goalrel 5k** `reward_beat_frac=0.53`；done/recon OK |
| `v1_fidelity_r60_20260815.json` / `v1_fidelity_goalrel_20260815.out` | ckpt=`wm_ckpt_v1_heldout_goalrel_20260815/wm_step_5000.pt`；beat=0.53；h=0..5 仍输 mean-baseline |
| `v1_fidelity_rew10_15k_20260815.out` | 先前最佳对照 beat=0.60 |
| goals | dataset backfill **51/51**；kinematic oracle **beat=1.0** |

### 4.2 根因（已证实）

1. **`step()` +1 偏移（构造 bug）** — 已修；held-out beat **0→0.27**。
2. **reward 梯度被 recon 淹没** — `loss_scales.reward=10` 后 raw CE **3.58→0.70**（5k）；beat **→0.60**。
3. **非 held-out 泛化主因** — 同旧 ckpt 上 train 集 open-loop 也 ≈0。
4. **非阈值/泄漏问题** — 禁止下调 `REWARD_BEAT_FRAC`。
5. **非多日数据阻塞** — 36 train ep 即可 0→0.60；15k 不继续涨。
6. **早 horizon 结构限** — `NavigationReward`≈Δdist(goal)。r60 held-out **动作近常数**（`dx≡1`, std≈0；`dyaw≡0`），a 对 reward 相关 ≈0。
7. **goal-rel 未学会（更新）** — 特征/标签齐全（oracle=1.0），但 raw metre-scale `goal_rel`（4-D）直连 1536-D RSSM feature → 被淹没；且早 H **指令动作 ≫ body_vel×dt 实现位移**（从静止加速），仅 `goal_rel` 无法恢复 progress。需 **scale-stable aux**（unit dir + log dist + body_vel + analytic Δdist）+ **feature proj**。

### 4.3 最小实验结果

| 设置 | `reward_beat_frac` | 备注 |
|---|---|---|
| 旧诚实 5k（错对齐，βreward=1） | ≈0.00–0.07 | `wm_ckpt_v1_heldout_20260815` |
| 仅对齐（诊断脚本） | ≈0.27 | |
| 对齐 + βreward=10，诚实 **5k** | **0.60** | `wm_ckpt_v1_heldout_rew10_20260815` |
| 对齐 + βreward=10，诚实 **15k** | **0.60** | 平台 |
| + action-cond reward，诚实 5k | **0.53** | `wm_ckpt_v1_heldout_actrew_20260815`；回归 |
| **+ goal_rel concat，诚实 5k** | **0.53** | `wm_ckpt_v1_heldout_goalrel_20260815`；**仍 FAIL**；oracle=1.0 |
| + body_vel analytic aux（代码） | **待训** | Mac `39ead6b`；ckpt 名 `wm_ckpt_v1_heldout_bodyvel_20260815` |

### 4.4 下一跳（仍不改阈值）

1. **优先（已实现，待 H100 5k）**：`reward_aux = [û_goal, log1p(d), v_body, analytic]`；`reward_head(proj(feature) ‖ a ‖ aux)`；train+`step` 一致。
2. 备选：若仍 <0.80，再试 supervised aux→reward 直通 / 冻结 RSSM 只训 reward 头。
3. **禁止**下调阈值 / 泄漏 ckpt；**暂缓** Phase-2 FOE。

---

## 5. V1 gate partial 跑法

### 5.1 同步

| 主机 | 方式 |
|---|---|
| Mac → origin / github | `git push` |
| H100 | bastion `cursor-125-public` ProxyJump → `a25689@10.239.121.25:31126`；`git pull` / bundle |

### 5.2 命令

```bash
# H100 — 诚实留出 WM 重训（②；βreward=10；body_vel analytic aux）
cd ~/aerial-wam-v2 && source .venv/bin/activate && export PYTHONPATH=.
python -m experiments.aerial.rl._wm_train_validate \
  --dataset ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_local_depth_r60_20260814 \
  --steps 5000 --wm-batch 8 --window 8 --horizon 15 \
  --heldout-frac 0.25 --save-ckpt --device cuda \
  --checkpoint-dir ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/wm_ckpt_v1_heldout_bodyvel_20260815

# H100 — ② fidelity
python -m experiments.aerial.rl._wm_fidelity_eval \
  --dataset ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_local_depth_r60_20260814 \
  --ckpt ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/wm_ckpt_v1_heldout_bodyvel_20260815/wm_step_5000.pt \
  --config configs/aerial_rl.yaml --heldout-frac 0.25 --horizon 15

# H100 — 刷新 partial_2（指向最新 ckpt）
python experiments/aerial/scripts/v1_gate_run_partials.py h100 \
  --repo ~/aerial-wam-v2 \
  --dataset ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_local_depth_r60_20260814 \
  --wm-ckpt ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/wm_ckpt_v1_heldout_bodyvel_20260815/wm_step_5000.pt \
  --out-dir experiments/aerial/rl/logs/v1_gate_r60_20260815
```

### 5.3 落盘 partial

| 文件 | 信号 | ok |
|---|---|---|
| `v1_partial_3_r60_20260815.json` | ③ 双通道 | **true**（proxy） |
| `v1_partial_2_r60_20260815.json` | ② fidelity | **false**（goalrel 5k beat=0.53；待 bodyvel 刷新） |
| `v1_partial_1_r60_20260815.json` | ① 碰撞率 | **true**（tied-zero） |
| `v1_fidelity_goalrel_20260815.out` | ② 明细 | reward FAIL @ 0.53（goalrel ckpt @ `f41bd3b`） |

### 5.4 踩坑

1. **H100 wm ckpt 路径** — 权威在 **`aerial-rl-skeleton/artifacts/`**。
2. **② 禁评** all-ep `wm_step_5000.pt` / 未带 `--heldout-frac` 的训产物。
3. **①** 必须用 `configs/aerial_rl_rollout.yaml`（`grab_depth`）。
4. **③ Phase 1 ≠ PASS** — proxy 不得 merge。
5. **Off-site SSH** — Mac→H100 经 **4090 公网** `cursor-125-public` ProxyJump；H100 用 `sshpass`。
6. **coll 标签** — 必须读 post-step `next_obs.collided`。
7. **reward 头** — cont/coll 在 **pre-action** `[h‖z]`；reward 在 **`proj(h‖z) ‖ a ‖ reward_aux`**（与 `training_loss` 一致）。旧 ckpt 的 `reward_head` 形状不兼容，须重训。
8. **r60 动作近常数 + 早 H 过冲** — a-concat / raw goal_rel 对早 H 几乎无信息；用 **body_vel×dt analytic**。

---

## 6. V1a / ② 资产（H100）

| 项 | 路径 / 值 |
|---|---|
| 语料 | `dataset_v0_local_depth_r60_20260814`（48 usable / 36 train + 12 held @ 0.25；goals 51/51） |
| 旧诚实 5k（β=1，错对齐） | `wm_ckpt_v1_heldout_20260815/wm_step_5000.pt` — beat≈0 |
| rew10 5k / 15k | beat=**0.60**（平台；仍为对照最佳） |
| actrew 5k | beat=**0.53** |
| **当前 ② ckpt（goalrel）** | `wm_ckpt_v1_heldout_goalrel_20260815/wm_step_5000.pt` — beat=**0.53** |
| 下一跳 ckpt（bodyvel） | `wm_ckpt_v1_heldout_bodyvel_20260815/` — **待训** |
| r60 all-ep（**非** ②） | `wm_ckpt_r60_20260814/wm_step_5000.pt` |

---

## 7. goal-rel 实验（完成；FAIL）

| 项 | 值 |
|---|---|
| 代码 | `1109cbe`/`f41bd3b`：`reward_head([feature; a; goal_rel])` + goal backfill |
| 5k held-out | beat_frac=**0.53**；h=0..5 输 mean-baseline；done/recon OK |
| 诊断 | goals 齐；oracle beat=1.0；raw `goal_rel` 未学到；a 近常数且过冲 |
| 结论 | raw goal concat **不是**升到 0.80 的杠杆；下一跳 **body_vel analytic aux** |

---

## 8. 变更记录

- **2026-08-15(晚¹²)** — ②：goalrel 5k → beat=0.53（与 actrew 持平）；oracle=1.0 证伪「缺特征」；根因=淹没/过冲；代码 `39ead6b` body_vel aux；未开 FOE / 未改阈值。
- **2026-08-15(晚¹¹)** — ②：action-cond reward 诚实 5k → beat=0.53（回归）；证实 a 近常数 + 无 goal；下一跳 goal-rel。
- **2026-08-15(晚¹⁰)** — ②：15k 对照仍 beat=0.60；判定早 horizon/action 结构限；下一跳 action-cond reward。
- **2026-08-15(晚⁹)** — ②：证实 step/+1 与 reward 权重；rew10 5k → 0.60。
- **2026-08-15(晚⁸…午)** — 诚实留出 FAIL≈0、① PASS、scaffold；见既往。
