# V1 Gate 状态活文档

> **用途**：V1 三信号 merge 进度与待办（镜像 `V0_GATE_STATUS.md` 治理模型）。  
> **前置**：V0 merge PASS — `v0_gate_r60_20260814.json`（2026-08-14）。  
> **设计（re-freeze 草案）**：[V1/V4 设计 §1.2](../design/2026-08-15-v1-v4-design.md#12-v1-三个同权过关信号re-freeze-草案2026-08-15)。

---

## 1. 一句话结论（2026-08-15 晚⁸）

**✅ V1a 完成** + **V1b scaffold 已落** + **① PASS**。  
**🟡 V1 partial**：③ proxy PASS；② **仍 FAIL**（`reward_beat_frac≈0.53`，需 ≥0.80）；**coll_ok=N/A**（`coll_traj_pos` 曾被 pre-step 标签误计为 0）。  
**merge 仍 blocked 于 ② + ③ Phase 2**。诚实留出 WM 重训已开跑（见 §7）。

产物目录（H100）：`~/aerial-wam-v2/experiments/aerial/rl/artifacts/v1_gate_r60_20260815/`

| 主机 | HEAD |
|---|---|
| Mac | `00a1e4b`+（本轮 held-out train / coll-label 修补） |
| H100 | 同步至同 SHA（via bastion ProxyJump） |

---

## 2. 三信号：还差什么

| 信号 | 判据（草案） | 最后已知结果（2026-08-15 晚⁸） | **还差什么** |
|---|---|---|---|
| **V1-①** | 碰撞率相对 V0 ↓20% | ✅ **PASS** — `baseline_kind=tied_zero_collision_bearing` | 无（① 已过） |
| **V1-③** | τ / D̂ 双通道独立 | ✅ **Phase 1 proxy PASS**（非 authoritative） | Phase 2：FOE τ + D̂_pred |
| **V1-②** | H=15 想象保真 | ❌ **FAIL**（`reward_beat_frac=0.53`）；**coll_ok=N/A** | 诚实留出 ckpt 重训 + 复评；**勿**再评 all-ep `wm_step_5000` |

---

## 3. 待办（按依赖）

- [x] **V1a-1** — H100 `_wm_train_validate` on `dataset_v0_local_depth_r60_20260814` → **`wm_ckpt_v1a_20260815/wm_step_500.pt`** PASS
- [x] **V1a-2** — flip `dynamics.kind=torch`、`enable_wm_update=true`；corrector smoke **SMOKE_WM_UPDATED=OK**
- [x] **V1b-1..3** — τ / shield / planner / `_v1_gate` scaffold + partial 首跑
- [x] **V1-①** — tied-zero PASS @ `00a1e4b`
- [ ] **V1-② 诚实留出重训** — `_wm_train_validate --heldout-frac 0.25 --steps 5000` → `wm_ckpt_v1_heldout_20260815/`（进行中，见 §7）
- [ ] **V1-② 复评** — `_wm_fidelity_eval` / partial_2 对上新 ckpt；目标 `reward_beat_frac≥0.80`
- [ ] **V1-merge** — `--merge` 三 partial（**blocked**：② FAIL + ③ proxy）
- [ ] **P0b**（可选）— shield 消费 `predict_cones()`

---

## 4. V1-② 诊断（2026-08-15 晚⁸）

### 4.1 当前产物（H100）

| 文件 | 要点 |
|---|---|
| `v1_partial_2_r60_20260815.json` | `ok=false`；`reward_beat_frac=0.533…`；`reward_growth_ok=true`；`done_ok`/`latent_ok`/`recon_growth_ok`=true；`coll_ok=null`（N/A） |
| `v1_fidelity_r60_20260815.json` | **ckpt=`wm_ckpt_r60_20260814/wm_step_5000.pt`**；`heldout_frac=0.25`；`n_traj=12`；`coll_traj_pos=0` |

### 4.2 根因（按优先级）

1. **错误 ckpt / 无诚实留出** — `wm_step_5000` 与 `wm_ckpt_v1a` 均在 **全部 48 ep** 上训（`heldout_frac` 未写入 meta / 未排除尾部）。设计 §1.2.2 **禁止**用该 ckpt 做 authoritative ②。首跑 summary 也曾因错误路径找不到 `wm_ckpt_v1a` 而回落到 r60-5000。
2. **模型在短程 reward 上弱于 constant-mean** — 即便存在泄漏（ckpt 见过 held-out），`reward_beat_frac` 仍仅 **0.53**；h0–h5 的 WM MAE **高于** baseline（1-step `0.86` vs base `0.65` → `one_step_ok` 亦 FAIL）。done/recon/latent 已过 → **不是** eval 整体坏掉，而是 **reward 头开环跟踪不够**。诚实留出重训不会「靠去掉泄漏 magically 过线」；需要在 **未见过尾部** 的数据上认真训够（默认 5000 step，与 r60 同量级）。
3. **coll 标签 bug（已修，非 ② 主阻塞）** — r60 碰撞只在 **`next_obs.collided`**；`wm_eval` / `wm_data` 曾读 **`obs.collided`** → held-out 实际有 2 条碰撞 ep，但 fidelity 记 `coll_traj_pos=0`。已改为 post-step（与 `v0_rollout_eval` / `dataset` 一致）。N/A 规则下 1–2 条仍不单独 FAIL；② 仍由 reward 决定。
4. **非 Phase-2 FOE 阻塞** — ② 不依赖 τ FOE。

### 4.3 最小诚实路径（不改阈值）

1. `_wm_train_validate --heldout-frac 0.25 --steps 5000 --save-ckpt` → dated dir `wm_ckpt_v1_heldout_20260815`（**禁止** warm-start 自曾见过 held-out 的 ckpt）。
2. 用同一 `heldout_frac=0.25` 复跑 fidelity → 写 `v1_partial_2` / `v1_fidelity`。
3. 若 reward 仍 <0.80：加长 steps / 查 reward 头与对齐，**不得**下调 `REWARD_BEAT_FRAC`。

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
| `v1_partial_2_r60_20260815.json` | ② fidelity | **false**（reward；待诚实 ckpt 复评） |
| `v1_partial_1_r60_20260815.json` | ① 碰撞率 | **true**（tied-zero） |
| `v1_fidelity_r60_20260815.json` | ② 明细 | reward FAIL；coll N/A |

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

## 7. 诚实留出重训（进行中）

| 项 | 值 |
|---|---|
| 命令 | §5.2 `_wm_train_validate --heldout-frac 0.25 --steps 5000` |
| 输出 | `wm_ckpt_v1_heldout_20260815/`（jsonl + meta + `wm_step_5000.pt`） |
| ETA | 约 **5–15 min**（既往 r60 5000-step ≈ meta→ckpt ~5 min；H100 空闲） |
| 完成后 | 立即 `_wm_fidelity_eval` / 刷新 `v1_partial_2`；更新本文件 §1–2 |

---

## 8. 变更记录

- **2026-08-15(晚⁸)** — ② 诊断：all-ep `wm_step_5000` + 泄漏评仍 `reward_beat_frac=0.53`（短程弱于 mean baseline）；修 `wm_eval`/`wm_data` post-step coll；`_wm_train_validate --heldout-frac`；启动诚实留出 5000-step 重训。未开 Phase 2 FOE。
- **2026-08-15(晚⁷)** — ① tied-zero PASS（`grab_depth`/rollout yaml）。
- **2026-08-15(晚⁶…午)** — ① harness 诊断、§1.2 re-freeze、V1b scaffold、V1a 执行；见既往条目。
