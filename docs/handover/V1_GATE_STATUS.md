# V1 Gate 状态活文档

> **用途**：V1 三信号 merge 进度与待办（镜像 `V0_GATE_STATUS.md` 治理模型）。  
> **前置**：V0 merge PASS — `v0_gate_r60_20260814.json`（2026-08-14）。  
> **设计（re-freeze 草案）**：[V1/V4 设计 §1.2](../design/2026-08-15-v1-v4-design.md#12-v1-三个同权过关信号re-freeze-草案2026-08-15)。

---

## 1. 一句话结论（2026-08-15 晚¹⁴）

**✅ V1a 完成** + **① PASS** + **② PASS**（goalvel `beat_frac=0.93`）。  
**🟡 V1-③**：Phase 1 proxy PASS 仍在；**Phase 2 代码已落**（FOE τ + auth gate path）— **authoritative ③ 尚未跑通** → **merge 仍 blocked**。  
**禁止**凭 proxy ③ / 未过 auth ③ 做 `--merge` PASS。

产物目录（H100）：`~/aerial-wam-v2/experiments/aerial/rl/logs/v1_gate_r60_20260815/`

| 主机 | HEAD |
|---|---|
| Mac / H100 | 见本节提交后 SHA（FOE Phase 2 scaffold） |

---

## 2. 三信号：还差什么

| 信号 | 判据（草案） | 最后已知结果（2026-08-15 晚¹⁴） | **还差什么** |
|---|---|---|---|
| **V1-①** | 碰撞率相对 V0 ↓20% | ✅ **PASS** — `baseline_kind=tied_zero_collision_bearing` | 无 |
| **V1-②** | H=15 想象保真 | ✅ **PASS**（goalvel 5k `reward_beat_frac=0.93`） | 无 |
| **V1-③** | τ / D̂ 双通道独立 | proxy PASS；**auth 未评** | H100：训 calibrator（可选）→ `--phase3 auth` 评 FOE+D̂_pred |

---

## 3. 待办（按依赖）

- [x] **V1a / V1b scaffold / ① / ②** — 见既往
- [x] **V1-③ Phase 2 代码** — FOE Farneback + τ；`phase=auth` gate；`train_tau_foe`；单测
- [ ] **V1-③ Phase 2 实测** — H100 auth partial（`both_fail≤0.20`、τ MAE≤2.0、`tau_only≥0.005`）
- [ ] **V1-merge** — blocked：**仅** auth ③
- [ ] **P0b**（可选）— shield 消费 `predict_cones()`

---

## 4. V1-③ Phase 2（本轮）

### 4.1 已落代码

| 项 | 路径 |
|---|---|
| FOE τ | `tau_predictor.py` — `kind=foe` / `foe_calibrated`；**推理禁 GT depth** |
| 伪标签训 | `train_tau_foe.py` — r60 GT τ → MLP calibrator |
| auth ③ | `_v1_gate --phase3 auth --depth-ckpt ... [--tau-ckpt ...]` |
| 阈值 | `v1_metrics`：auth both_fail≤0.20；τ MAE≤2.0；tau_only≥0.005 |
| yaml | `tau_predictor.kind` 仍默认 `gt_proxy`（**未 flip**） |

### 4.2 H100 下一步（auth 实测）

```bash
cd ~/aerial-wam-v2 && source .venv/bin/activate && export PYTHONPATH=.

# 可选：calibrator（伪标签；古典 FOE 也可先盲跑 auth）
python -m experiments.aerial.rl.train_tau_foe \
  --dataset ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_local_depth_r60_20260814 \
  --out-dir ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/tau_ckpt_foe_r60_20260815 \
  --steps 2000 --device cuda
# ETA：harvest ~数分钟（Farneback 全语料）+ train 2000 step ≪5 min on H100

# auth ③（古典 FOE 或 +calibrator）
python -m experiments.aerial.rl._v1_gate --signals 3 \
  --phase3 auth --device cuda \
  --dataset ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_local_depth_r60_20260814 \
  --depth-ckpt ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt \
  --tau-kind foe \
  --emit experiments/aerial/rl/logs/v1_gate_r60_20260815/v1_partial_3_auth_r60_20260815.json
```

**未 flip merge**：auth JSON `ok=true` 且 `authoritative=true` 后才可与 ①② 合并。

---

## 5. V1-② 资产（仍有效）

| 项 | 路径 / 值 |
|---|---|
| **② ckpt** | `wm_ckpt_v1_heldout_goalvel_20260815/wm_step_5000.pt` — beat=**0.93** |
| partial_2 | `v1_partial_2_r60_20260815.json` `ok=true` |

---

## 6. 变更记录

- **2026-08-15(晚¹⁴)** — V1-③ Phase 2：**FOE τ + auth gate + train_tau_foe 落地**；Mac 单测 PASS；**未**跑 auth 实测 / **未** merge。
- **2026-08-15(晚¹³)** — ②：goalvel 5k → beat=0.93 PASS；merge 仅剩 ③ Phase 2。
- **2026-08-15(晚¹²…午)** — 见既往。
