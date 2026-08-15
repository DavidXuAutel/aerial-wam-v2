# V1 Gate 状态活文档

> **用途**：V1 三信号 merge 进度与待办（镜像 `V0_GATE_STATUS.md` 治理模型）。  
> **前置**：V0 merge PASS — `v0_gate_r60_20260814.json`（2026-08-14）。  
> **设计（re-freeze 草案）**：[V1/V4 设计 §1.2](../design/2026-08-15-v1-v4-design.md#12-v1-三个同权过关信号re-freeze-草案2026-08-15)。

---

## 1. 一句话结论（2026-08-15 晚⁸）

**✅ V1a 完成** + **V1b scaffold 已落** + **① PASS**。  
**🟡 V1 partial**：③ proxy PASS；② **仍 FAIL** — 诚实留出 ckpt 复评后 `reward_beat_frac≈0.00–0.07`（需 ≥0.80）；**coll_ok=N/A**（`coll_traj_pos=1`）。  
**merge 仍 blocked 于 ② + ③ Phase 2**。泄漏评 0.53 是虚高；真实短板是 reward 开环跟踪。

产物目录（H100）：`~/aerial-wam-v2/experiments/aerial/rl/artifacts/v1_gate_r60_20260815/`

| 主机 | HEAD |
|---|---|
| Mac / H100 | `08dc2c7`（held-out train + post-step coll） |

---

## 2. 三信号：还差什么

| 信号 | 判据（草案） | 最后已知结果（2026-08-15 晚⁸） | **还差什么** |
|---|---|---|---|
| **V1-①** | 碰撞率相对 V0 ↓20% | ✅ **PASS** — `baseline_kind=tied_zero_collision_bearing` | 无（① 已过） |
| **V1-③** | τ / D̂ 双通道独立 | ✅ **Phase 1 proxy PASS**（非 authoritative） | Phase 2：FOE τ + D̂_pred |
| **V1-②** | H=15 想象保真 | ❌ **FAIL**（honest `reward_beat_frac≈0.0–0.07`）；**coll_ok=N/A**（pos=1） | 加长/加碰撞语料 + reward 头改进；**勿**下调阈值 |

---

## 3. 待办（按依赖）

- [x] **V1a-1** — H100 `_wm_train_validate` on `dataset_v0_local_depth_r60_20260814` → **`wm_ckpt_v1a_20260815/wm_step_500.pt`** PASS
- [x] **V1a-2** — flip `dynamics.kind=torch`、`enable_wm_update=true`；corrector smoke **SMOKE_WM_UPDATED=OK**
- [x] **V1b-1..3** — τ / shield / planner / `_v1_gate` scaffold + partial 首跑
- [x] **V1-①** — tied-zero PASS @ `00a1e4b`
- [x] **V1-② 诚实留出重训** — `wm_ckpt_v1_heldout_20260815/wm_step_5000.pt`（36 train eps，PASS learning+non-div）
- [x] **V1-② 复评** — FAIL：`reward_beat_frac≈0.0–0.07`（见 §7）
- [ ] **V1-② 下一跳** — 更长训 / 更多含碰撞 held-out / reward 头对齐诊断（**不**改 `REWARD_BEAT_FRAC`）
- [ ] **V1-merge** — `--merge` 三 partial（**blocked**：② FAIL + ③ proxy）
- [ ] **P0b**（可选）— shield 消费 `predict_cones()`

---

## 4. V1-② 诊断（2026-08-15 晚⁸）

### 4.1 当前产物（H100）

| 文件 | 要点 |
|---|---|
| `v1_partial_2_r60_20260815.json` | `ok=false`；**honest** `reward_beat_frac=0.0`；done/recon/latent OK；`coll_ok=null`（pos=1） |
| `v1_fidelity_r60_20260815.json` | **ckpt=`wm_ckpt_v1_heldout_20260815/wm_step_5000.pt`**；`heldout_frac=0.25`；`coll_traj_pos=1`；`coll_auroc=1.0` |

### 4.2 根因（按优先级）— 已用诚实 ckpt 证实

1. **模型弱点（主因）** — 诚实留出 5000-step 训完后，held-out `reward_beat_frac` **跌至 ~0.0–0.07**（泄漏 all-ep 评曾虚高至 0.53）。几乎所有 horizon 的 WM MAE **高于** constant-mean；done/recon/latent 仍过 → **reward 开环跟踪不够**，不是 harness 整坏。
2. **曾用错误 ckpt** — 首跑评的是 all-ep `wm_ckpt_r60_20260814/wm_step_5000.pt`（设计禁止作 authoritative ②）。已替换。
3. **coll 标签 bug（已修）** — 曾读 pre-step `obs.collided` → 假 `coll_traj_pos=0`。现 `pos=1`；N/A（<3）不单独 FAIL。
4. **非 Phase-2 FOE 阻塞**。

### 4.3 下一跳（仍不改阈值）

1. 诊断 reward 头：1-step MAE vs mean baseline 差距、训练 `loss_reward` 曲线、±1 对齐。
2. 更长诚实留出训（e.g. 15k–50k）或增采含碰撞 / 多样 reward 的 held-out 语料后再训。
3. **禁止**下调 `REWARD_BEAT_FRAC` / 改用泄漏 ckpt 过门。

---

## 5. V1 gate partial 跑法

### 5.1 同步

| 主机 | 方式 |
|---|---|
| Mac → origin | `git push` |
| H100 | bastion `cursor-125-public` ProxyJump → `a25689@10.239.121.25:31126`；`git pull` / bundle |

### 5.2 命令

```bash
# H100 — 诚实留出 WM 重训（② 前置）
cd ~/aerial-wam-v2 && source .venv/bin/activate && export PYTHONPATH=.
python -m experiments.aerial.rl._wm_train_validate \
  --dataset ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_local_depth_r60_20260814 \
  --steps 5000 --wm-batch 8 --window 8 --horizon 15 \
  --heldout-frac 0.25 --save-ckpt --device cuda \
  --checkpoint-dir ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/wm_ckpt_v1_heldout_20260815

# H100 — ② fidelity（同一 heldout_frac）
python -m experiments.aerial.rl._wm_fidelity_eval \
  --dataset ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_local_depth_r60_20260814 \
  --ckpt ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/wm_ckpt_v1_heldout_20260815/wm_step_5000.pt \
  --config configs/aerial_rl.yaml --heldout-frac 0.25 --horizon 15

# 或 partials runner
python experiments/aerial/scripts/v1_gate_run_partials.py h100 \
  --dataset ~/aerial-rl-skeleton/.../dataset_v0_local_depth_r60_20260814 \
  --wm-ckpt ~/aerial-rl-skeleton/.../wm_ckpt_v1_heldout_20260815/wm_step_5000.pt \
  --out-dir experiments/aerial/rl/artifacts/v1_gate_r60_20260815
```

### 5.3 落盘 partial

| 文件 | 信号 | ok |
|---|---|---|
| `v1_partial_3_r60_20260815.json` | ③ 双通道 | **true**（proxy） |
| `v1_partial_2_r60_20260815.json` | ② fidelity | **false**（honest reward≈0） |
| `v1_partial_1_r60_20260815.json` | ① 碰撞率 | **true**（tied-zero） |
| `v1_fidelity_r60_20260815.json` | ② 明细 | reward FAIL；coll N/A（pos=1） |

### 5.4 踩坑

1. **H100 wm ckpt 路径** — 权威在 **`aerial-rl-skeleton/artifacts/`**，不在 `~/aerial-wam-v2/artifacts/`。
2. **② 禁评** all-ep `wm_step_5000.pt` / 未带 `--heldout-frac` 的训产物。
3. **①** 必须用 `configs/aerial_rl_rollout.yaml`（`grab_depth`）。
4. **③ Phase 1 ≠ PASS** — proxy 不得 merge。
5. **Off-site SSH** — Mac→H100 经 **4090 公网** `cursor-125-public` ProxyJump。
6. **coll 标签** — 必须读 post-step `next_obs.collided`。

---

## 6. V1a 资产与命令（H100）

| 项 | 路径 / 值 |
|---|---|
| 语料 | `~/aerial-rl-skeleton/.../dataset_v0_local_depth_r60_20260814`（48 usable / 36 train + 12 held @ 0.25） |
| V1a ckpt（地板，非 ②） | `.../wm_ckpt_v1a_20260815/wm_step_500.pt` |
| r60 all-ep ckpt（**非** ②） | `.../wm_ckpt_r60_20260814/wm_step_5000.pt` |
| ② 目标 ckpt | `.../wm_ckpt_v1_heldout_20260815/wm_step_5000.pt` |

---

## 7. 诚实留出重训 + 复评（完成）

| 项 | 值 |
|---|---|
| 训 | `heldout_frac=0.25` → 36/48 train；`steps=5000`；wall ~5 min；**PASS** learning+non-div |
| ckpt | `~/aerial-rl-skeleton/.../wm_ckpt_v1_heldout_20260815/wm_step_5000.pt` |
| meta | `heldout_frac=0.25`，`episodes=36`，`git_sha=08dc2c7`，`authoritative=true` |
| 复评 | `reward_beat_frac≈0.0–0.07` → **② FAIL**；`coll_traj_pos=1` → N/A；done/recon/latent OK |
| 对照 | 旧泄漏评 all-ep ckpt：`reward_beat_frac=0.53`（虚高，不可作 gate） |

---

## 8. 变更记录

- **2026-08-15(晚⁸)** — ②：修 coll 标签 + `--heldout-frac` 训；诚实 5000-step PASS 后 fidelity 仍 FAIL（reward≈0）；确认泄漏 0.53 虚高。未开 Phase 2 FOE / 未改阈值。
- **2026-08-15(晚⁷)** — ① tied-zero PASS（`grab_depth`/rollout yaml）。
- **2026-08-15(晚⁶…午)** — ① harness 诊断、§1.2 re-freeze、V1b scaffold、V1a 执行；见既往条目。
