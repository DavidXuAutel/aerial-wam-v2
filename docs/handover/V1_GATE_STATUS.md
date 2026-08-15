# V1 Gate 状态活文档

> **用途**：V1 三信号 merge 进度与待办（镜像 `V0_GATE_STATUS.md` 治理模型）。  
> **前置**：V0 merge PASS — `v0_gate_r60_20260814.json`（2026-08-14）。  
> **设计（re-freeze 草案）**：[V1/V4 设计 §1.2](../design/2026-08-15-v1-v4-design.md#12-v1-三个同权过关信号re-freeze-草案2026-08-15)。

---

## 1. 一句话结论（2026-08-15 晚¹⁴）

**✅ V1 merge PASS** — ① + ② + **③ Phase 2 auth** 齐。  
产物：`v1_gate_r60_20260815.json`（H100 `logs/` + `artifacts/`）。  
**未自动 flip yaml**（`tau_predictor.kind` 仍默认 `gt_proxy`；部署切 `foe_calibrated` 需人工）。

| 主机 | HEAD |
|---|---|
| Mac / 125 / H100 | `e6c144d`+（FOE Phase 2；merge 后状态见本节提交） |

---

## 2. 三信号

| 信号 | 判据 | 结果 |
|---|---|---|
| **V1-①** | 碰撞率相对 V0 ↓20% | ✅ PASS — `tied_zero_collision_bearing` |
| **V1-②** | H=15 想象保真 | ✅ PASS — goalvel `reward_beat_frac=0.93` |
| **V1-③** | FOE τ + D̂_pred；both_fail≤0.20 | ✅ **auth PASS** — `both_fail=0.0013`；τ MAE=`0.93` s；`tau_only=0.010`；`foe_calibrated` |

---

## 3. 待办

- [x] V1a / ① / ② / ③ Phase 2 代码 + auth 实测 + **merge**
- [ ] **人工**：yaml `tau_predictor.kind=foe_calibrated` + `ckpt=.../tau_foe_calibrator.pt`（部署路径）
- [ ] **可选**：P0b cones；V4 讨论（merge 已解锁前置）

---

## 4. V1-③ Phase 2 资产（H100）

| 项 | 路径 / 值 |
|---|---|
| FOE calibrator | `~/aerial-rl-skeleton/.../tau_ckpt_foe_r60_20260815/tau_foe_calibrator.pt` |
| 训 log | `logs/v1_gate_r60_20260815/train_tau_foe_20260815.out`（harvest 46 s + train 5 s） |
| auth partial | `v1_partial_3_auth_r60_20260815.json` |
| **merge** | `v1_gate_r60_20260815.json` — `ok=true` |

### Auth ③ 数字

| 指标 | 值 | 阈 |
|---|---|---|
| `both_fail_frac` | 0.0013 | ≤ 0.20 |
| `tau_only_frac` | 0.010 | ≥ 0.005 |
| `tau_mae_s` | 0.935 | ≤ 2.0 |
| `n` | 1561 held-out frames | |
| `tau_kind` | `foe_calibrated` | 禁 GT depth 推理 |

---

## 5. 复现 merge

```bash
cd ~/aerial-wam-v2 && source .venv/bin/activate && export PYTHONPATH=.
LOG=experiments/aerial/rl/logs/v1_gate_r60_20260815
ART=experiments/aerial/rl/artifacts/v1_gate_r60_20260815
python -m experiments.aerial.rl._v1_gate --merge \
  $ART/v1_partial_1_r60_20260815.json \
  $LOG/v1_partial_2_r60_20260815.json \
  $LOG/v1_partial_3_auth_r60_20260815.json \
  --emit $LOG/v1_gate_r60_20260815.json
```

---

## 6. 变更记录

- **2026-08-15(晚¹⁴)** — Phase 2 FOE 落地；calibrator 训完；**auth ③ PASS**；**V1 merge PASS**；yaml 未 auto-flip。
- **2026-08-15(晚¹³)** — ② goalvel beat=0.93 PASS。
- **2026-08-15(晚¹²…午)** — 见既往。
