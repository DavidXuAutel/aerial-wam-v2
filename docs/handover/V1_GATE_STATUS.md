# V1 Gate 状态活文档

> **用途**：V1 三信号 merge 进度与待办（镜像 `V0_GATE_STATUS.md` 治理模型）。  
> **前置**：V0 merge PASS — `v0_gate_r60_20260814.json`（2026-08-14）。  
> **设计**：[V1/V4 设计](../design/2026-08-15-v1-v4-design.md)。

---

## 1. 一句话结论（2026-08-15 晚）

**✅ V1a 完成** + **V1b scaffold 已落**（代码 @ `f0b74d9`）。  
**🟡 首次 V1 partial 跑通（H100 `.25`）**：**V1-③ PASS**；**V1-② FAIL**（fidelity）；**V1-① FAIL**（rollout scan 0/8）。**merge 未做**。

产物目录（H100）：`~/aerial-wam-v2/experiments/aerial/rl/artifacts/v1_gate_r60_20260815/`

---

## 2. 三信号：还差什么

| 信号 | 判据（草案） | 最后已知结果（2026-08-15 晚） | **还差什么** |
|---|---|---|---|
| **V1-①** | 碰撞率相对 V0 ↓20% | ❌ **FAIL** — scan **0/8** accepted；spawn_collision 主导（H100→4090 headon：630/738；4090 local r60：406/1000+594 too_close） | 修复 cross-net spawn / 复用 V0 ②④ 已接受 starts；再跑 `v1_partial_1` |
| **V1-②** | H=15 想象保真（留出 ckpt） | ❌ **FAIL** — `wm_step_5000.pt` held-out 25%（12 ep）：`reward_beat_frac=0.53`（需≥0.8）、`coll_auroc=NaN`（held-out **0** 碰撞轨）；`done_ok=true`，`recon_growth_ok=true`，`latent_norm_max=19.85` | 增采含碰撞 held-out / 长训 WM；或评 V1a ckpt + 诚实留出重训 |
| **V1-③** | τ / D̂ 双通道独立 | ✅ **PASS** — r60 5000 frames：`both_fail_frac=**0.002**`（≪0.35）；`tau_only=0.94%`；`depth_only=0%`（GT depth proxy） | 无 — partial 已落盘；待 D̂ 预测头接入 ③ 正式版 |

---

## 3. 待办（按依赖）

- [x] **V1a-1** — H100 `_wm_train_validate` on `dataset_v0_local_depth_r60_20260814` → **`wm_ckpt_v1a_20260815/wm_step_500.pt`** PASS
- [x] **V1a-2** — flip `dynamics.kind=torch`、`enable_wm_update=true`；corrector smoke **SMOKE_WM_UPDATED=OK**（mock 3 iter）
- [x] **V1b-1** — `tau_predictor.py` + 接线 — GT depth+vel proxy；`v1b_tau_smoke.py` OK；**待**光流 FOE 训练头
- [x] **V1b-2** — `DepthTauShield` + `ImaginationPlanner` + collector/`train_rl` 接线 — 单测 + `v1b_planner_smoke.py` OK
- [x] **V1b-3** — `_v1_gate.py` + `v1_gate_run_partials.py` — partial **已跑**（③ PASS / ②① FAIL）；merge 待三信号齐
- [ ] **V1-merge** — `--merge` 三 partial → `v1_gate_r60_20260815.json`（**blocked**）
- [ ] **V1-① 复跑** — 解决 rollout scan spawn_collision；4090 缺 `depth_ckpt_da3_r60`（仅 skeleton 有 near head）
- [ ] **V1-② 复跑** — fidelity 需碰撞轨 + reward beat baseline；首跑 ckpt=`wm_ckpt_r60_20260814/wm_step_5000.pt`
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
| `v1_partial_3_r60_20260815.json` | ③ 双通道 | **true** |
| `v1_partial_2_r60_20260815.json` | ② fidelity | **false** |
| `v1_partial_1_r60_20260815.json` | ① 碰撞率 | **false**（无 starts） |
| `v1_fidelity_r60_20260815.json` | ② 明细 | reward/coll FAIL |

### 4.4 踩坑

1. **H100 wm ckpt 路径** — `wm_ckpt_v1a_20260815` 在 **`aerial-rl-skeleton/artifacts/`**，不在 `~/aerial-wam-v2/artifacts/`。
2. **4090 无 r60 depth ckpt** — 本地仅有 `aerial-rl-skeleton/.../depth_ckpt_da3_near_20260811/`；① 应走 **H100→4090**（yaml `env.host=10.229.20.125`）。
3. **① scan 全拒** — `spawn_collision` 暴增（738 扫 630 拒）；与 V0 partial_24（10/16 accepted）对比需查 renderer / 出生高度 / cross-net 健康。
4. **② coll_auroc=NaN** — held-out 12 ep 无碰撞轨 → p_coll 分离不可评（非 WM 发散）。

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

- **2026-08-15(晚²)** — **首次 V1 partial 执行**（H100 `.25` + 4090 RPC OK）：
  - 跑 `v1_gate_run_partials.py`；bundle 同步 H100
  - **V1-③ PASS**：`both_fail_frac=0.002`，`n=5000`
  - **V1-② FAIL**：`wm_step_5000` held-out；`reward_beat_frac=0.53`；`coll_traj_pos=0`
  - **V1-① FAIL**：obstacle scan 0/8（spawn_collision）
  - merge **未执行**
- **2026-08-15(晚)** — **V1b scaffold 合拢**：`DepthTauShield`、`planner.py`、`ImaginationPlanner`、`_v1_gate.py`、`v1_metrics.py`；yaml `safety.kind=depth_tau`；单测 + smoke PASS（Mac）。
- **2026-08-15(午³)** — **V1b-1 接线**：`train_rl` 构建 `tau_predictor`/`depth_predictor`；yaml `tau_predictor.enable=true`；`v1b_tau_smoke.py`。
- **2026-08-15(午²)** — **V1b-1 scaffold**：`tau_predictor.py`（GT depth+closing-vel τ）；collector `tau_predictor` 接线 → `obs.info['tau_pred']`；单测 3/3 pass。
- **2026-08-15(午)** — **V1a 执行完成**：
  1. `_wm_train_validate` 500 steps PASS（learning + non-divergence H=15）
  2. `configs/aerial_rl.yaml`：`kind=torch`、`enable_wm_update=true`、`checkpoint_dir=wm_ckpt_v1a_20260815`
  3. `v1a_corrector_smoke.py`：3 iter mock，`wm=updated` ×3，`rl=skipped`（V4 仍 OFF）
- **2026-08-15** — 建本文件；V0 合拢后 V1 起步状态。
