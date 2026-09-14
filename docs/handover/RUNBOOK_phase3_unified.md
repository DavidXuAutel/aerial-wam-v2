# Phase-3 RUNBOOK · Unified Outdoor + Indoor Navigation

> **分支**：`project/phase3-unified`（起自 `phase2-pass-20260908`）  
> **模块**：[`experiments/aerial/phase3_unified/README.md`](../../experiments/aerial/phase3_unified/README.md)  
> **父航道**：
>   - [`RUNBOOK_wam_phase2_long_horizon.md`](../../experiments/aerial/RUNBOOK_wam_phase2_long_horizon.md)
>   - [`RUNBOOK_indoor_0xm.md`](../../experiments/aerial/RUNBOOK_indoor_0xm.md)

**不含 vgoal**。视觉目标跟踪见 `project/phase2-vgoal`。

**125 连接**：Mac 一律 `ssh cursor-125-public`（内网 `cursor-125` 易超时；见 [`ACCESS.md`](ACCESS.md)）。

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

### P0 — 骨架 ✅

- [x] `project/phase3-unified` @ `phase2-pass-20260908`
- [x] `scene_profile.py` + collector 接线
- [x] `build_phase3_mixed_annotation.py`
- [x] 双门 eval 脚本

### P1 — 混采语料 + handover 采集 ✅

语料：`experiments/aerial/phase3_unified/annotations/mixed_seen.json`（**16 outdoor_long + 4 indoor_micro**）

```bash
# 再生语料
python -m experiments.aerial.scripts.build_phase3_mixed_annotation \
  --out experiments/aerial/phase3_unified/annotations/mixed_seen.json

# 125 混采采集（scene tag → action_limits / success_dist / shield）
ssh cursor-125-public 'cd ~/aerial-wam-v2 && bash experiments/aerial/scripts/collect_phase3_unified.sh'
```

每 episode 带 `scene` + `pose_source`；collector 按 `scene_profiles` 切换尺度。

签字项（P2 前）：
- [ ] Indoor 阶段 C 签字
- [ ] 混采比例 7:3 签字

### P1b — 室内外交接语料（handover · 双地图）

AirSim **无单图门口**：`env_airsim_16`（户外）与 `building_99`（室内）为**独立 renderer**，采集时按 `map_id` 切换。

主语料：`experiments/aerial/phase3_unified/annotations/handover_seen.json`（15 对 HO + 16 outdoor_long）

```bash
# 再生 handover 语料
python -m experiments.aerial.scripts.build_phase3_handover_annotation \
  --out experiments/aerial/phase3_unified/annotations/handover_seen.json

# 125：探测各 leg 起点是否 spawn-in-collision（Mac 经 public SSH）
ssh cursor-125-public 'cd ~/aerial-wam-v2 && source ~/sim_verify/.venv/bin/activate && \
  python3 -m experiments.aerial.scripts.probe_handover_spawns \
    --handover-only --no-health-check \
    --scene-script ~/aerial-indoor-wam/experiments/aerial/scripts/recover_renderer_scene.sh'

# 过滤无效 approach / B99 段（本地或 125 均可）
python -m experiments.aerial.scripts.build_phase3_handover_annotation \
  --spawn-report experiments/aerial/phase3_unified/annotations/spawn_probe_report.json \
  --out experiments/aerial/phase3_unified/annotations/handover_seen_filtered.json

# 125：全量 handover 采集（outdoor→indoor 成对顺序）
ssh cursor-125-public 'cd ~/aerial-wam-v2 && source ~/sim_verify/.venv/bin/activate && \
  python3 -m experiments.aerial.scripts.collect_phase3_handover \
    --handover-only --spawn-retries 3 \
    --annotation experiments/aerial/phase3_unified/annotations/handover_seen_filtered.json \
    --scene-script ~/aerial-indoor-wam/experiments/aerial/scripts/recover_renderer_scene.sh \
    --out experiments/aerial/rl/artifacts/dataset_phase3_handover_seen'
```

若 outdoor `Approach_Route_*` 持续 collision：用 `spawn_probe_report.json` 过滤，或检查 renderer 是否在 outdoor 图。

### P2 — 融合 FT（H100 · 签字后）

在 **125** 上一键同步语料 + 开训：

```bash
bash experiments/aerial/scripts/train_phase3_unified.sh
```

或 H100 手动（offline replay，warm-start Phase-2 toward_g）：

```bash
python -m experiments.aerial.rl.train_v4_ac \
  --config configs/aerial_rl_phase3_unified.yaml \
  --iters 500 --skip-collect --backend mock --device cuda --dynamics torch \
  --dataset experiments/aerial/rl/artifacts/dataset_phase3_handover_seen \
  --annotation experiments/aerial/phase3_unified/annotations/handover_seen_filtered.json \
  --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt \
  --init-actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_phase2_toward_g_20260905_112006/v4_ac_latest.pt \
  --w-collision 1.0 \
  --ckpt-dir experiments/aerial/rl/artifacts/v4_ac_ckpt_phase3_unified_20260911
```

日志：`artifacts/train_phase3_unified_20260911.log`

### P2b — 室外保持重训（2026-09-12 · P2a 回归后）

**背景**：P2a（44 ep handover、均匀 replay、500 iter）→ outdoor **0/16**，d_min 卡在 ~28m；Phase-2 toward_g 同协议 **13/16（81.2%）**。

| 项 | P2a | P2b |
|----|-----|-----|
| warm-start | Phase-2 toward_g | Phase-2 toward_g（**禁止**从 P2a ckpt 续训） |
| replay 分布 | 44 ep 均匀 | outdoor ×4 + indoor ×1（~**90%** outdoor） |
| iters | 500 | **300** |
| 回归门 | 无 | outdoor SR ≥ baseline − **10pp**（≥ **11/16**） |

```bash
# 125：构建 outdoor-heavy replay + 同步 H100 开训
bash experiments/aerial/scripts/train_phase3_unified_p2b.sh

# 仅重建 replay 数据集（不调 H100）
python3 -m experiments.aerial.scripts.build_phase3_p2b_replay_dataset \
  --mode outdoor_heavy   # 或 outdoor_only

# 125：训后室外回归门（renderer 需在 outdoor）
bash experiments/aerial/scripts/eval_phase3_outdoor_regression_gate.sh \
  experiments/aerial/rl/artifacts/v4_ac_ckpt_phase3_unified_p2b_<STAMP>/v4_ac_latest.pt
```

基线 JSON：`artifacts/phase3_unified_eval_20260911/outdoor_long_eval_phase2_baseline.json`  
配置：`configs/aerial_rl_phase3_unified_p2b.yaml`

### P2c — 室外在线 close 续训（2026-09-13 · P2b 仍 FAIL 后）

**背景**：P2b replay → **0/16**，d_min ~12.6m（优于 P2a 的 ~28m，但仍无法 <3m 到达）。

| 项 | P2b | P2c |
|----|-----|-----|
| 数据 | offline replay（symlink 过采样） | **125 在线采集**（`--phase2 --backend airsim`） |
| 近目标偏置 | 无 | **`--near-goal-frac 0.5`**（5–20m spawn） |
| warm-start | Phase-2 toward_g | Phase-2 toward_g |
| iters | 300（H100 mock） | **48**（125 真机，~3×16 路） |

```bash
# 125：outdoor renderer 就绪后一键开训
bash experiments/aerial/scripts/train_phase3_unified_p2c.sh

# 训后回归门
bash experiments/aerial/scripts/eval_phase3_outdoor_regression_gate.sh \
  experiments/aerial/rl/artifacts/v4_ac_ckpt_phase3_unified_p2c_<STAMP>/v4_ac_latest.pt
```

配置：`configs/aerial_rl_phase3_unified_p2c.yaml`  
语料：`experiments/aerial/phase3_unified/annotations/outdoor_long_only.json`

### P2d — outdoor-only 长训（2026-09-13 · P2b 仍 FAIL）

| 项 | P2b | P2d |
|----|-----|-----|
| warm-start | Phase-2 toward_g | **P2b ckpt** |
| replay | outdoor-heavy handover | **100% outdoor** handover ×6 |
| iters | 300 | **500**，lr **5e-5** |

**结果（2026-09-14）**：**1/16**，d_min median ~11.4m → **FAIL**（门槛 ≥11/16）。  
JSON：`artifacts/phase3_unified_eval_20260914/outdoor_long_eval_p2b_candidate.json`

### P2e — Phase-2 close-tail micro-FT（2026-09-14 · P2d FAIL 后）

**根因**：P1 handover 语料用 **HeuristicPolicy** 采集，非 Phase-2 π；对非 expert 轨迹做 imagination replay 会把 IR 从 ~0.76 拉到 ~0.25，close 能力持续丢失。

| 项 | P2b–P2d | P2e |
|----|---------|-----|
| 数据来源 | handover npz（heuristic） | **Phase-2 toward_g expert** 16 路 rollout |
| replay 范围 | 全 episode | **close-tail only**（d_goal ∈ [3, 18] m） |
| warm-start | Phase-2 或 P2b | **仅 Phase-2 toward_g** |
| iters / lr | 300–500 / 1e-4–5e-5 | **80 / 2e-5**，entropy **1e-4** |
| 在线 FT | P2c（已放弃） | **不做**（P2c 48 iter → d_min ~43m） |

```bash
# 125：采集 expert → 切 close-tail → 同步 H100 微训
bash experiments/aerial/scripts/train_phase3_unified_p2e.sh

# 仅重建 close-tail（已有 expert npz）
SKIP_COLLECT=1 bash experiments/aerial/scripts/train_phase3_unified_p2e.sh

# 训后回归门
bash experiments/aerial/scripts/eval_phase3_outdoor_regression_gate.sh \
  experiments/aerial/rl/artifacts/v4_ac_ckpt_phase3_unified_p2e_<STAMP>/v4_ac_latest.pt
```

配置：`configs/aerial_rl_phase3_unified_p2e.yaml`  
脚本：`collect_phase3_p2e_phase2_expert.py`、`build_phase3_p2e_close_tail_dataset.py`

**放弃路径（勿重复）**：从 P2b/P2d ckpt 续训；handover 全段 replay；P2c 式 48 iter 在线 near-goal。

**P2e 结果（2026-09-14）**：Expert 14/16 到达，但 close-tail 80 iter 后回归门 **0/8** → **FAIL**。统一 FT 路线结案。

### P3 — Decouple（室外冻结 + 室内增量）

> 完整方案：[`PHASE3_DECOUPLE_PLAN.md`](PHASE3_DECOUPLE_PLAN.md)

- **室外**：冻结 `v4_ac_ckpt_phase2_toward_g_20260905_112006`，禁止 replay FT  
- **室内**：独立 `P3-indoor` ckpt（方案 B：双 ckpt + Router）  
- **室内外判断**：任务级 Handover FSM + waypoint/围栏/GCS，**不由 RGB π 分类**

```bash
# P3-indoor：语料 + 采集（125 · 必须 building99 renderer）
python -m experiments.aerial.scripts.build_phase3_indoor_annotation
bash experiments/aerial/scripts/collect_phase3_indoor.sh

# H100 训练（室内 npz only；可选 warm-start Phase-2）
bash experiments/aerial/scripts/train_phase3_indoor.sh

# 训后：indoor ckpt 评室内；outdoor 门只跑 Phase-2 ckpt
bash experiments/aerial/scripts/eval_phase3_handover_decouple.sh \
  experiments/aerial/rl/artifacts/v4_ac_ckpt_phase2_toward_g_20260905_112006/v4_ac_latest.pt \
  experiments/aerial/rl/artifacts/v4_ac_ckpt_phase3_indoor_<STAMP>/v4_ac_latest.pt
```

配置：`configs/aerial_rl_phase3_indoor.yaml` · 语料：`phase3_indoor_seen.json`（`scene=indoor_micro`, `map_id=building_99`）

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
