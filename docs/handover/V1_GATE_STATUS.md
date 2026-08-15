# V1 Gate 状态活文档

> **用途**：V1 三信号 merge 进度与待办（镜像 `V0_GATE_STATUS.md` 治理模型）。  
> **前置**：V0 merge PASS — `v0_gate_r60_20260814.json`（2026-08-14）。  
> **设计（re-freeze 草案）**：[V1/V4 设计 §1.2](../design/2026-08-15-v1-v4-design.md#12-v1-三个同权过关信号re-freeze-草案2026-08-15)。

---

## 1. 一句话结论（2026-08-15 晚⁷）

**✅ V1a 完成** + **V1b scaffold 已落**。  
**🟡 V1 partial**：③ proxy PASS；② FAIL（reward）；① **PASS**（`tied_zero_collision_bearing`：scan 8/8 collision-bearing，`off_hard=1.0`，V0/V1 shield-on hard=near_ep=0）。**merge 仍 blocked 于 ② + ③ Phase 2**。

产物目录（H100）：`~/aerial-wam-v2/experiments/aerial/rl/artifacts/v1_gate_r60_20260815/`

---

## 2. 三信号：还差什么

| 信号 | 判据（草案） | 最后已知结果（2026-08-15 晚⁷） | **还差什么** |
|---|---|---|---|
| **V1-①** | 碰撞率相对 V0 ↓20% | ✅ **PASS** — `baseline_kind=tied_zero_collision_bearing`；hard v0/v1=0；`off_hard=1.0`；scan 8/8 probe coll=8 | 无（① 已过） |
| **V1-③** | τ / D̂ 双通道独立 | ✅ **Phase 1 proxy PASS**（非 authoritative） | Phase 2：FOE τ + D̂_pred |
| **V1-②** | H=15 想象保真 | ❌ **FAIL**（`reward_beat_frac=0.53`）；**coll_ok=N/A** | 增采碰撞 held-out；诚实留出 ckpt 重训 |

---

## 3. 待办（按依赖）

- [x] **V1a-1** — H100 `_wm_train_validate` on `dataset_v0_local_depth_r60_20260814` → **`wm_ckpt_v1a_20260815/wm_step_500.pt`** PASS
- [x] **V1a-2** — flip `dynamics.kind=torch`、`enable_wm_update=true`；corrector smoke **SMOKE_WM_UPDATED=OK**（mock 3 iter）
- [x] **V1b-1** — `tau_predictor.py` + 接线 — GT depth+vel proxy；`v1b_tau_smoke.py` OK；**待**光流 FOE 训练头
- [x] **V1b-2** — `DepthTauShield` + `ImaginationPlanner` + collector/`train_rl` 接线 — 单测 + `v1b_planner_smoke.py` OK
- [x] **V1b-3** — `_v1_gate.py` + `v1_gate_run_partials.py` — partial **已跑**（③ PASS / ② FAIL / ① PASS）
- [ ] **V1-merge** — `--merge` 三 partial → `v1_gate_r60_20260815.json`（**blocked**：② FAIL + ③ proxy）
- [x] **V1-① 复跑** — `aerial_rl_rollout.yaml` + tied-zero 规则 → PASS @ `8d2eb71`+rescored
- [ ] **V1-② 复跑** — fidelity 需碰撞轨 + reward beat baseline
- [ ] **P0b**（可选）— shield 消费 `predict_cones()`

---

## 4. V1 gate partial 跑法（2026-08-15 实测）

### 4.1 同步

| 主机 | 方式 | 结果 |
|---|---|---|
| Mac → github/origin | `git push` | `f0b74d9` |
| H100 | `git bundle` → `git pull /tmp/aerial-wam-v2-main.bundle main` | `4a6f606`→`f0b74d9`（需 `git reset --hard` 清本地 yaml 脏改） |
| 4090 | `git pull origin main` | OK |

### 4.2 命令

```bash
# H100 — offline ② + ③
cd ~/aerial-wam-v2 && source .venv/bin/activate && export PYTHONPATH=.
python experiments/aerial/scripts/v1_gate_run_partials.py h100 \
  --dataset ~/aerial-rl-skeleton/.../dataset_v0_local_depth_r60_20260814 \
  --wm-ckpt ~/aerial-rl-skeleton/.../wm_ckpt_r60_20260814/wm_step_5000.pt \
  --out-dir experiments/aerial/rl/artifacts/v1_gate_r60_20260815

# H100 → 4090 renderer — ①（与 V0 ②④ 同 harness）
python experiments/aerial/scripts/v1_gate_run_partials.py rollout4090 \
  --rollout-dataset ~/aerial-rl-skeleton/.../dataset_v0_headon_20260811 \
  --depth-ckpt ~/aerial-rl-skeleton/.../depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt \
  --n-episodes 8 --device cuda

# merge（三 partial ok 后）
python -m experiments.aerial.rl._v1_gate --merge \
  v1_partial_1_r60_20260815.json v1_partial_2_r60_20260815.json v1_partial_3_r60_20260815.json
```

### 4.3 落盘 partial

| 文件 | 信号 | ok |
|---|---|---|
| `v1_partial_3_r60_20260815.json` | ③ 双通道 | **true**（proxy） |
| `v1_partial_2_r60_20260815.json` | ② fidelity | **false**（reward） |
| `v1_partial_1_r60_20260815.json` | ① 碰撞率 | **true**（tied-zero；`off_hard=1.0`） |
| `v1_fidelity_r60_20260815.json` | ② 明细 | reward/coll FAIL |

### 4.4 踩坑

1. **H100 wm ckpt 路径** — `wm_ckpt_v1a_20260815` 在 **`aerial-rl-skeleton/artifacts/`**，不在 `~/aerial-wam-v2/artifacts/`。
2. **4090 无 r60 depth ckpt** — ① 应走 **H100→4090**（`aerial_rl_rollout.yaml` `env.host=10.229.20.125`）。
3. **① 必须用 `configs/aerial_rl_rollout.yaml`** — `aerial_rl.yaml` 的 `grab_depth=false` 只在 reset 强制抓深，probe 全程 fwd 冻在 reset 帧（≡18.1 m）→ 假 0 碰撞。
4. **① scan 全拒（2026-08-15 晚⁴）** — 曾 630 spawn_collision + full-field too_close；对比 V0 partial_24 `spawn=6`。晚⁷ 用 rollout yaml 后 scan **8/8**（spawn=7，probe coll=8）。
5. **② coll_ok** — re-score 后应为 **N/A**（`coll_traj_pos=0`）；② 仍 FAIL 于 reward。
6. **③ Phase 1 ≠ PASS** — proxy ③ 不得 merge。
7. **Off-site SSH** — Mac→H100 经 **4090 公网** `cursor-125-public`（`ssh-125.david-x.com` / cloudflared）ProxyJump → `a25689@10.239.121.25:31126`。

---

## 5. V1a 资产与命令（H100）

| 项 | 路径 / 值 |
|---|---|
| 语料 | `~/aerial-rl-skeleton/.../dataset_v0_local_depth_r60_20260814` |
| V1a ckpt | `.../wm_ckpt_v1a_20260815/wm_step_500.pt` |
| 训练日志 | `.../wm_ckpt_v1a_20260815/wm_train.jsonl` |
| meta | `.../wm_ckpt_v1a_20260815/wm_train_meta.json`（authoritative=true） |
| yaml | `dynamics.kind=torch`, `enable_wm_update=true`, `checkpoint_dir=wm_ckpt_v1a_20260815` |

```bash
# 复现 V1a validate
python -m experiments.aerial.rl._wm_train_validate \
  --dataset ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_local_depth_r60_20260814 \
  --steps 500 --wm-batch 8 --window 8 --horizon 15 \
  --checkpoint-dir experiments/aerial/rl/artifacts/wm_ckpt_v1a_20260815 \
  --save-ckpt --device cuda

# corrector smoke（无 Hydra）
python experiments/aerial/scripts/v1a_corrector_smoke.py

# V1b τ 通道 smoke（mock，须 repo 根目录）
python experiments/aerial/scripts/v1b_tau_smoke.py

# V1b 想象规划 smoke（mock + dynamics.kind=stub override）
python experiments/aerial/scripts/v1b_planner_smoke.py

# V1 gate self-check
python -m experiments.aerial.rl._v1_gate --self-check
```

---

## 6. 变更记录

- **2026-08-15(晚⁷)** — ① 真因：`grab_depth=false`（训用 yaml）冻 probe 深度；改 `aerial_rl_rollout.yaml` 后 scan 8/8、probe coll=8、`off_hard=1.0`、双臂 shield-on hard/near=0 → **tied-zero PASS**。未开 Phase 2 FOE / WM 重训。
- **2026-08-15(晚⁶)** — 诊断 V1-①：`v1_partial_1` probe coll=0 / fwd≡18 m / full≡1.0（地面误收）；V0 `v0_partial_24` 同协议 hard `n_contact=0`、near_coll on/off=0.0044/0.0388。修复：probe=forward∨collided、候选 forward 排序、① standoff=3.0、hard=0 时 `near_coll_episode` 回退。
- **2026-08-15(晚⁵)** — harness @ `9875b1a`：V1-① scan **8/8**；rollout 双臂 coll=0 → ① FAIL（baseline 无效）；② re-score `coll_ok=null`。
- **2026-08-15(晚⁴)** — V1-① 复跑 ×2 仍 0/8；根因诊断 + harness 补丁；4090 `recover_renderer.sh`。
- **2026-08-15(晚³)** — **§1.2 re-freeze 草案**写入设计 doc；`v1_metrics` 对齐 coll N/A + Phase 标记。
- **2026-08-15(晚²)** — 首次 V1 partial 执行（③ proxy PASS / ②① FAIL）；见 §4。
- **2026-08-15(晚)** — **V1b scaffold 合拢**：`DepthTauShield`、`planner.py`、`ImaginationPlanner`、`_v1_gate.py`、`v1_metrics.py`；yaml `safety.kind=depth_tau`；单测 + smoke PASS（Mac）。
- **2026-08-15(午³)** — **V1b-1 接线**：`train_rl` 构建 `tau_predictor`/`depth_predictor`；yaml `tau_predictor.enable=true`；`v1b_tau_smoke.py`。
- **2026-08-15(午²)** — **V1b-1 scaffold**：`tau_predictor.py`（GT depth+closing-vel τ）；collector `tau_predictor` 接线 → `obs.info['tau_pred']`；单测 3/3 pass。
- **2026-08-15(午)** — **V1a 执行完成**：
  1. `_wm_train_validate` 500 steps PASS（learning + non-divergence H=15）
  2. `configs/aerial_rl.yaml`：`kind=torch`、`enable_wm_update=true`、`checkpoint_dir=wm_ckpt_v1a_20260815`
  3. `v1a_corrector_smoke.py`：3 iter mock，`wm=updated` ×3，`rl=skipped`（V4 仍 OFF）
- **2026-08-15** — 建本文件；V0 合拢后 V1 起步状态。
