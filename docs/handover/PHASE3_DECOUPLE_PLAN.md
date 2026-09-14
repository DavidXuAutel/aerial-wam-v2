# Phase-3 Decouple 方案 · 室外冻结 + 室内增量 + Scene Router

> **日期**：2026-09-14  
> **状态**：草案（P2a–P2e 室外 FT 结案后）  
> **关联**：[`RUNBOOK_phase3_unified.md`](RUNBOOK_phase3_unified.md)、[`WAM_PHASE3_UNIFIED_STATUS.md`](WAM_PHASE3_UNIFIED_STATUS.md)

---

## 0. 一句话

**室外 π 冻结为 Phase-2 toward_g；室内单独训练/部署；运行时由任务级 Scene Router 选择策略与 profile，不由 RGB π 猜测室内外。**

---

## 1. 背景与结论（P2a–P2e）

### 1.1 已验证事实

| 实验 | 室外回归门 | 结论 |
|------|------------|------|
| Phase-2 toward_g | **13/16** | 唯一可用 outdoor baseline |
| P2a 均匀 handover replay | 0/16 | FAIL |
| P2b outdoor-heavy replay | 0/16 | FAIL（d_min ~12.6m） |
| P2c 在线 near-goal 48 iter | 0/16 | FAIL（d_min ~43m） |
| P2d outdoor-only 500 iter | 1/16 | FAIL |
| P2e Phase-2 expert close-tail 80 iter | **0/8**（中止） | FAIL，且劣于 P2d |

**P2e 关键对照**（同协议、同 Phase-2 ckpt）：

- Expert 采集（未 FT）：**14/16 到达**，min_d ~2.7m  
- Close-tail 微训后：R01 min_d **19.6m**，全面退化  

→ **数据与采集栈正确；imagination replay 微调 Phase-2 π 必然破坏 outdoor close。**

### 1.2 战略调整

| 原 Phase-3 目标 | 调整后 |
|-----------------|--------|
| 单 ckpt、7:3 混采、一次 FT | **室外冻结 + 室内增量** |
| π 从分布学会两种尺度 | **Router 显式切换 scene + 双策略** |
| outdoor 回归门作为 FT 副产品 | outdoor 门仅作 **不退化验收**（≥11/16） |

原「单 ckpt 双门」目标 **暂停**，直至有证据表明不损伤 Phase-2 的融合路径（例如 frozen-trunk adapter）。

---

## 2. 架构总览

```
                    ┌─────────────────────────┐
                    │   Mission / GCS         │
                    │   (waypoints, segments) │
                    └───────────┬─────────────┘
                                │
                    ┌───────────▼─────────────┐
                    │   Handover FSM          │
                    │   OUTDOOR|APPROACH|INDOOR│
                    └───────────┬─────────────┘
                                │ scene_id, profile
              ┌─────────────────┴─────────────────┐
              ▼                                   ▼
    ┌──────────────────┐              ┌──────────────────┐
    │ OutdoorPolicy    │              │ IndoorPolicy     │
    │ Phase-2 ckpt     │              │ P3-indoor ckpt   │
    │ (frozen)         │              │ (trainable)      │
    └────────┬─────────┘              └────────┬─────────┘
              │                                   │
              └─────────────────┬─────────────────┘
                                ▼
                    ┌─────────────────────────┐
                    │ WAM + shield + planner  │
                    │ (scene_profile 切换)    │
                    └─────────────────────────┘
```

**原则**：π 只负责「当前 scene 内怎么飞」；**scene 由 FSM + 任务元数据决定**，不是 RGB 端到端分类。

---

## 3. Scene Router：如何判断室内 / 室外

### 3.1 仿真（与现有语料一致）

| 字段 | 户外 | 室内 |
|------|------|------|
| `map_id` | `env_airsim_16` | `building_99` |
| `scene` | `outdoor_long` / `outdoor_approach` | `indoor_micro` |
| 切换方式 | `recover_renderer_scene.sh outdoor\|building99` | 采集/评估脚本显式调用 |

仿真 **无单图门口**；handover = 户外腿结束 → **换 renderer** → 室内腿开始。Router 在仿真里等价于：**episode 元数据 + FSM 状态**。

### 3.2 真机 / 部署（推荐优先级）

| 优先级 | 机制 | 说明 |
|--------|------|------|
| **P0** | **任务段 `scene` 字段** | 航点序列每段标注 `outdoor` / `indoor`；与 handover 语料同构 |
| **P0** | **Handover waypoint** | 楼门口坐标 + 半径 R（如 5–10m）；进入 `APPROACH` |
| **P1** | **室内地理围栏** | 建筑 footprint 多边形 + \(\hat p\) 在内 → `INDOOR`（依赖 VIO/地图） |
| **P1** | **GCS 确认** | `SWITCH_INDOOR` / `SWITCH_OUTDOOR` 指令（人工兜底） |
| **P2** | GNSS 质量 | 丢星 + 已在 approach 区 → 辅证切 indoor |
| **P2** | 高度 AGL / 气压 | 辅证，不单独硬切 |
| **P3** | RGB 场景分类器 | **第一版不做**；门口/玻璃易误报，且与导航目标解耦 |

### 3.3 Handover FSM（建议状态机）

```
OUTDOOR ──(距 handover_wp < R)──► APPROACH ──(触发 indoor)──► INDOOR
   ▲                              │                            │
   └────────(任务结束/出围栏)──────┴────────────────────────────┘
```

| 状态 | 使用策略 | scene_profile | 进入条件 |
|------|----------|---------------|----------|
| `OUTDOOR` | Phase-2 ckpt | `outdoor_long` | 默认；在户外走廊/围栏外 |
| `APPROACH` | Phase-2 ckpt | `outdoor_approach`（可选） | 距 handover waypoint < R m |
| `INDOOR` | Indoor ckpt | `indoor_micro` | 满足 **任一**：① GCS 确认 ② \(\hat p\) 进室内围栏 ③（仿真）`map_id=building_99` |

**迟滞**： indoor 切换需连续 N 帧（如 5）满足条件；outdoor 回切需出围栏 + M 帧，防抖动。

**接口草案**（实现时放 `experiments/aerial/phase3_unified/handover_router.py`）：

```python
@dataclass
class RouterInput:
    mission_segment: str          # "outdoor" | "indoor" | "approach"
    p_hat: np.ndarray             # [3] world
    handover_wp: np.ndarray | None
    gnss_ok: bool | None = None
    gcs_command: str | None = None  # "switch_indoor" | "switch_outdoor"

@dataclass
class RouterOutput:
    fsm_state: str                # OUTDOOR | APPROACH | INDOOR
    scene: str                    # outdoor_long | indoor_micro | ...
    policy_id: str                # "phase2_outdoor" | "phase3_indoor"
    scene_profile: SceneProfile
```

Eval / 闭环先 **直接用 `episode["scene"]` 喂 Router**（oracle router），与真机 FSM 同接口。

---

## 4. 策略与训练：P3-indoor

### 4.1 室外（冻结）

| 项 | 值 |
|----|-----|
| ckpt | `v4_ac_ckpt_phase2_toward_g_20260905_112006/v4_ac_latest.pt` |
| 训练 | **禁止** imagination replay / 在线 FT |
| 验收 | 回归门 **≥11/16**（建议先跑 sanity 签字） |

### 4.2 室内（增量）— 两档方案

#### 方案 A：Frozen trunk + indoor adapter（中期目标）

- Phase-2 actor trunk **冻结**
- 仅训 indoor head / LoRA + indoor critic
- 部署：单包，Router 选 head
- 风险：需改 `train_v4_ac` / deploy 路径；需证明 adapter 不拖累 outdoor 推理路径

#### 方案 B：双 ckpt + Router（**第一版推荐**）

- `outdoor_ckpt` = Phase-2（不变）
- `indoor_ckpt` = 新训，仅 indoor 数据
- Router 按 FSM 加载/切换推理图
- 优点：**与仿真 handover 完全一致**；室外零风险；实现快

**第一版采用方案 B**；A 作为合并部署的后续优化。

### 4.3 P3-indoor 训练约束（方案 B）

| 项 | 规则 |
|----|------|
| 数据 | handover 室内腿 + B99 短路由；**不用** Heuristic 户外段训 indoor π |
| warm-start | 可选 Phase-2（仅作初始化）；或 scratch 小网络 |
| **禁止** | imagination replay 混合 outdoor npz；禁止动 Phase-2 权重文件 |
| 方法 | BC / 短 offline；或 indoor-only 在线 collect（小 iter） |
| profile | `indoor_micro`：success 0.5m（严门 0.2m），动作盒 `[0.15,0.08,0.08,0.10]` |

### 4.4 明确放弃的路径

- P2a–P2e 式 **统一 replay FT**
- 从 P2b/P2d/P2e ckpt 续训
- 7:3 混采单次 FT「一个 ckpt 通吃」
- 靠 RGB 分类器自动切 scene（第一版）

---

## 5. 验收（双门，decouple 版）

| 门 | 策略 | 脚本 | 门槛 |
|----|------|------|------|
| **Outdoor 不退化** | Phase-2 ckpt | `eval_phase3_outdoor_regression_gate.sh` | **≥11/16** |
| **Indoor 能力** | indoor ckpt + oracle router | `indoor_mainline_baseline_eval.py` / B99 fixture | 签字前定基线（如 mainline >0/4，B99 逐步提升） |
| **Handover 端到端** | Router + 双 ckpt | 新建 `eval_phase3_handover_decouple.sh` | outdoor approach 不撞 + indoor 段到达率 |

Outdoor 门在 **每次 indoor 训练后** 只跑 Phase-2 ckpt（确认无人误覆盖权重）。

---

## 6. 执行计划

### Phase 0 — 结案与冻结（1 天）

- [ ] STATUS 记入 P2a–P2e FAIL 与根因
- [ ] 室外 ckpt 冻结路径写入 RUNBOOK
- [ ] （建议）Phase-2 outdoor sanity 回归门一次

### Phase 1 — Router + eval 骨架（3–5 天）

- [x] `handover_router.py`：FSM + oracle 模式（`episode["scene"]`）
- [x] `eval_phase3_handover_decouple.sh`：按 scene 切 ckpt 跑 handover 语料
- [x] 文档化 handover waypoint / 围栏 JSON 格式（`handover_geofence_example.json`）

### Phase 2 — P3-indoor 训练（1–2 周）

- [x] `configs/aerial_rl_phase3_indoor.yaml`（`indoor_micro` only，`map_id=building_99`）
- [x] `train_phase3_indoor.sh` + `collect_phase3_indoor.sh`（125 Building_99 collect + H100 train，**不碰** Phase-2 文件）
- [x] `build_phase3_indoor_annotation.py` / `indoor_corpus.py`（采集前强制 scene 校验）
- [x] P3-indoor v0 采集 14 ep + H100 200 iter（ckpt `phase3_indoor_20260914`）
- [x] decouple eval：approach **11/14**（phase2 协议）；indoor **0/8**
- [ ] 室内门验收迭代（v1+）

### Phase 3 — Handover 集成（1 周）

- [x] 仿真 decouple eval（oracle router + 双 ckpt；approach 用 phase2 协议 **11/14**）
- [ ] GCS 切换命令桩（可选）
- [x] STATUS / decouple plan 记入 2026-09-14 结果
- [ ] 签字文档

---

## 7. 文件与命名（拟新增）

| 路径 | 用途 |
|------|------|
| `docs/handover/PHASE3_DECOUPLE_PLAN.md` | 本文 |
| `experiments/aerial/phase3_unified/handover_router.py` | FSM + Router I/O |
| `configs/aerial_rl_phase3_indoor.yaml` | 室内训练配置 |
| `experiments/aerial/scripts/train_phase3_indoor.sh` | 室内训练入口 |
| `experiments/aerial/scripts/eval_phase3_handover_decouple.sh` | 双 ckpt handover eval |

---

## 8. 开放问题（签字前）

1. Indoor 严门幅度：mainline 0.2m vs B99 gt_proxy 协议是否拆分验收？  
2. `APPROACH` 是否单独 ckpt，还是继续用 Phase-2？（默认：Phase-2）  
3. 真机第一版是否强制 GCS 确认进 indoor？（建议：仿真 oracle，真机 P0 强制确认）  
4. adapter（方案 A）何时启动：室内门初步通过后。

---

## 9. 变更记录

| 日期 | 内容 |
|------|------|
| 2026-09-14 | 初版：P2e 失败后 decouple + Scene Router + P3-indoor（方案 B） |
