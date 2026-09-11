# Phase-3 RUNBOOK · Unified Outdoor + Indoor Navigation

> **分支**：`project/phase3-unified`（起自 `phase2-pass-20260908`）  
> **模块**：[`experiments/aerial/phase3_unified/README.md`](../../experiments/aerial/phase3_unified/README.md)  
> **父航道**：
>   - [`RUNBOOK_wam_phase2_long_horizon.md`](../../experiments/aerial/RUNBOOK_wam_phase2_long_horizon.md)
>   - [`RUNBOOK_indoor_0xm.md`](../../experiments/aerial/RUNBOOK_indoor_0xm.md)

**不含 vgoal**。视觉目标跟踪见 `project/phase2-vgoal`。

---

## 0. 一句话

**同一主航道 × 同一大脑（WAM + π） × 训练分布覆盖户外 + 室内两种尺度**，一次 FT 产出一份 ckpt，双门验收。

## 1. 硬约束

### 继承 Phase-2（户外）

- 大脑 = WAM + π；深度/τ 罩仅安全
- 户外 `success_dist = 3.0 m`，动作盒 `[1.0, 0.4, 0.4, 0.314]`
- 三区罩户外剖面 L1/L2/L3 = 8/5/1.5 m

### 继承 Indoor A0（室内）

- `pose_source` 必填；`goal_rel` 由 \(\hat p\) 算出
- 室内 `success_dist = 0.5 m`（严门 0.2 m），动作盒 `[0.15, 0.08, 0.08, 0.10]`
- 三区罩室内剖面 L1/L2/L3 = 1.5/0.8/0.4 m

### Phase-3 融合规则

| 项 | 规则 |
|----|------|
| 单 episode 单 scene | `scene ∈ {outdoor_long, indoor_micro}` |
| 混采比例 | 默认 7:3（签字前禁改） |
| 双 ckpt | **禁止**（室内一个、户外一个） |
| P3 验收 | **同一 ckpt** 户外 + 室内双门同时过 |

配置：`configs/aerial_rl_phase3_unified.yaml`

## 2. 阶段

### P0 — 骨架（当前）

- [x] `project/phase3-unified` @ `phase2-pass-20260908`
- [x] `scene_profile.py` + collector 接线
- [x] `build_phase3_mixed_annotation.py`
- [x] 双门 eval 脚本
- [ ] Indoor 阶段 C 签字
- [ ] 混采比例签字

### P1 — 混采语料（125）

```bash
python -m experiments.aerial.scripts.build_phase3_mixed_annotation \
  --outdoor artifacts/seen_airsim16_long_routes.json \
  --out artifacts/phase3_unified_mixed_seen.json \
  --outdoor-prob 0.7
```

每 episode 带 `scene` + `pose_source`。

### P2 — 融合 FT（H100 · 签字后）

起点：`v4_ac_ckpt_phase2_toward_g_20260905_112006`

```bash
python -m experiments.aerial.rl.train_v4_ac \
  --config configs/aerial_rl_phase3_unified.yaml \
  --annotation artifacts/phase3_unified_mixed_seen.json \
  --phase2 --r-m 25 \
  --init-actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_phase2_toward_g_20260905_112006/v4_ac_latest.pt
```

### P3 — 双门验收（125）

```bash
bash experiments/aerial/scripts/eval_phase3_unified.sh <actor_ckpt>
```

| 门 | 脚本 | 门槛 |
|----|------|------|
| Outdoor | `wam_phase2_long_eval.py --subgoal-source toward_g` | SR ≥ Phase-2 close |
| Indoor | `indoor_mainline_baseline_eval.py` | 诚实基线之上（签字前定幅度） |

## 3. 假进度清单

| 假进度 | 为何假 |
|--------|--------|
| 双 ckpt 拼进度 | 违反 Stick 主航道 |
| 户外 profile 跑 indoor eval | 门错配 |
| indoor 用 3.0 m 成功门 | 不是室内能力 |
| 只报单尺度回归 | 双门未双验 |
| 混入 vgoal 训练 | 本 project 范围外 |

## 4. 变更记录

| 日期 | 内容 |
|------|------|
| 2026-09-08 | 初版骨架（旧 branch `phase3/unified-outdoor-indoor`） |
| 2026-09-11 | 新建 `project/phase3-unified`；接线 scene_profile + 混采脚本；与 vgoal 脱钩 |
