# V1 Gate 状态活文档

> **用途**：V1 三信号 merge 进度与待办（镜像 `V0_GATE_STATUS.md` 治理模型）。  
> **前置**：V0 merge PASS — `v0_gate_r60_20260814.json`（2026-08-14）。  
> **设计**：[V1/V4 设计](../design/2026-08-15-v1-v4-design.md)。

---

## 1. 一句话结论（2026-08-15）

**✅ V1a 完成（H100 `.25`）**：`_wm_train_validate` PASS + flags 已翻 + corrector smoke **3/3 `wm=updated`**。  
**V1b 未开始**（τ + 想象规划 + 双通道罩 + `_v1_gate` 三信号）。

---

## 2. 三信号：还差什么

| 信号 | 判据（草案） | 最后已知结果 | **还差什么** |
|---|---|---|---|
| **V1-①** | 碰撞率相对 V0 ↓ | — | 4090 rollout + V1 罩/规划器（V1b） |
| **V1-②** | H=15 想象保真 / 非发散 | ✅ **V1a floor PASS**：loss 14.03→2.10；recon↓；min_ent 0.46；H=15 max norm **17.33** | 正式 `_v1_gate` + 留出 ckpt fidelity 评 |
| **V1-③** | τ / D̂ 双通道独立验证 | — | τ 头未实现；D̂ 沿用 V0 ③ |

---

## 3. 待办（按依赖）

- [x] **V1a-1** — H100 `_wm_train_validate` on `dataset_v0_local_depth_r60_20260814` → **`wm_ckpt_v1a_20260815/wm_step_500.pt`** PASS
- [x] **V1a-2** — flip `dynamics.kind=torch`、`enable_wm_update=true`；corrector smoke **SMOKE_WM_UPDATED=OK**（mock 3 iter）
- [ ] **V1b-1** — `tau_predictor.py` + collector 接线 — 🟡 **scaffold 已落**（GT depth+vel proxy；单测 3/3）；待光流 FOE + 训练头
- [ ] **V1b-2** — `DepthTauShield` + 想象规划器
- [ ] **V1b-3** — `_v1_gate` 三 partial merge
- [ ] **P0b**（可选）— shield 消费 `predict_cones()`

---

## 4. V1a 资产与命令（H100）

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
```

---

## 5. 变更记录

- **2026-08-15(午²)** — **V1b-1 scaffold**：`tau_predictor.py`（GT depth+closing-vel τ）；collector `tau_predictor` 接线 → `obs.info['tau_pred']`；单测 3/3 pass。
- **2026-08-15(午)** — **V1a 执行完成**：
  1. `_wm_train_validate` 500 steps PASS（learning + non-divergence H=15）
  2. `configs/aerial_rl.yaml`：`kind=torch`、`enable_wm_update=true`、`checkpoint_dir=wm_ckpt_v1a_20260815`
  3. `v1a_corrector_smoke.py`：3 iter mock，`wm=updated` ×3，`rl=skipped`（V4 仍 OFF）
- **2026-08-15** — 建本文件；V0 合拢后 V1 起步状态。
