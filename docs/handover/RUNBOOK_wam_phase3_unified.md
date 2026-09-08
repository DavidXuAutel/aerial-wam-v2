# Phase-3 RUNBOOK · Unified Outdoor + Indoor

> **日期**：2026-09-08 建立骨架（branch `phase3/unified-outdoor-indoor`，起自 `phase2-pass-20260908`）
> **本文件是什么**：户外长航程与室内小空间**融合训练**的唯一执行入口。
> **父航道**：
>   - [`experiments/aerial/RUNBOOK_wam_phase2_long_horizon.md`](../../experiments/aerial/RUNBOOK_wam_phase2_long_horizon.md)（Phase-2 长航程）
>   - [`experiments/aerial/RUNBOOK_indoor_0xm.md`](../../experiments/aerial/RUNBOOK_indoor_0xm.md)（Indoor 0.x m）
> **冲突裁决**：两父 runbook 冲突 → 传感合同以 Indoor §0.1 为准；长航程规划/罩以 Phase-2 为准；大脑（WAM+π）三方共同。本 runbook 只在**融合层**新增约束，不重写父约束。

---

## 0. 一句话

**同一主航道 × 同一大脑 × 训练分布同时覆盖两种尺度**。

- 户外长航程：合法折线 + 局部胡萝卜 + 米级到达
- 室内小空间：0.x m 到达 + 微尺度动作限位 + 传感合同 `pose_source`
- **一次 FT 覆盖二者**，避免"室内/室外双 ckpt"分叉与"室内借户外 ckpt + 缩盒"假进度。

## 1. 为什么合并

| 现状 | 合并的必要性 |
|------|-------------|
| Phase-2 已 close（SR=86.7% SCR=6.7% @ `phase2-pass-20260908`）；策略在户外分布内成熟 | 保住户外能力，同时把 0.x m 能力**训进同一策略** |
| Indoor 阶段 B 诚实基线：`arrival_rate_hat=0/4 @ 0.2m`（`odom_from_imu_rgb` + `assist=none`） | 单独 FT 室内 ckpt 会与户外分叉；Stick 主航道 = 同一策略 × 双尺度 |
| Indoor 阶段 C（H100 FT）待签字 | Phase-3 直接把"阶段 C"扩为"双分布 FT"，一次落地 |

## 2. 硬约束（继承 + 融合）

### 2.1 继承 Phase-2

- 大脑 = WAM（RSSM 32×32）+ π；深度/τ 罩仅安全。
- 户外动作限位 `[1.0, 0.4, 0.4, 0.314]` m/step @ 5 Hz。
- 三区罩户外剖面（L1=8 / L2=5 / L3=1.5，v_cruise=25 m/s）。
- 报表字段：`controller_attribution` / `sensors_used`。

### 2.2 继承 Indoor A0 传感合同

- `pose_source ∈ {vio_est, odom_from_imu_rgb, gt_proxy}` **必填**。
- `goal_rel` **必须**由 `\(\hat p,\hat\psi\)` 与目标算出；**禁**默许 `obs.position`（AirSim GT）却报表写"未用 GT"。
- 训练期允许 `gt_proxy`（stamp 落盘），**验收禁默认 `gt_proxy`**。
- 高度：室内优先 rangefinder/AGL；baro 辅助不替代水平定位。
- `assist=gt_pd` 默认 off，仅对照。

### 2.3 融合新增（Phase-3 专属）

| 项 | 规则 |
|----|------|
| **场景切换**：单 episode 只属一个 `scene ∈ {outdoor_long, indoor_micro}` | episode 元数据必带 `scene` tag；`cross_scene_in_episode=false` |
| **action_limits** | 按 `scene` 走 `configs/aerial_rl_phase3_unified.yaml` §`scene_profiles`；训练/评测/部署三处统一 |
| **success_dist** | outdoor 3.0 m，indoor 0.5 m（或 0.2 m 严门，见阶段 D） |
| **三区罩剖面** | 按 `scene` 切；不允许 outdoor 剖面用于 indoor 或反之 |
| **混采比例** | 默认 `outdoor:indoor = 7:3`；签字前禁改 |
| **报表强制** | 除 §2.1/§2.2 字段外，必须落盘 `scene` |

## 3. 目录 / 骨架

```
experiments/aerial/phase3/
├── __init__.py
├── README.md
├── configs/          # 空,若未来需要 sub-config
├── scripts/          # train_phase3.py / eval_phase3.py (待建)
└── notes/            # 每次实验的一页记录
configs/aerial_rl_phase3_unified.yaml   # 主配置骨架
docs/handover/RUNBOOK_wam_phase3_unified.md   # 本文
```

## 4. 阶段（Phase-3 只走一次，覆盖两种尺度）

### P0 — 骨架 / 合同（本 branch 骨架完成即完成）

- [x] branch `phase3/unified-outdoor-indoor` 起自 `phase2-pass-20260908`
- [x] 目录骨架 + 融合 config + 统一 RUNBOOK
- [ ] Indoor 阶段 C 签字（父 runbook §6 阶段 C）
- [ ] 混采比例、双 profile 切换机制签字
- [ ] Phase-2 close ckpt 路径写入 `world_model.checkpoint_dir`（等签字）

### P1 — 融合数据收集（125 · 签字后）

- 分场景采集：户外 seen 长航程 + 室内 seen 微空间。
- 每 episode 元数据必带 `scene` + `pose_source`。
- 户外沿用 Phase-2 seen16 长路由；室内沿用 Indoor 阶段 B held-out。
- 采集脚本：`experiments/aerial/rl/collector.py`（透传 `scene_profiles`）。

### P2 — 融合 FT（H100 · 经 125 · 签字后）

- 起点 ckpt：Phase-2 close。
- 混采：`outdoor:indoor = 7:3`（初值，签字后允许调）。
- **禁**单失败补洞；**禁**单尺度专用 FT 分支。
- 每轮以 P3 验收协议回归户外 + 室内两条曲线。

### P3 — 验收（125）

**双回归门**（同一 ckpt 同时过）：

| 门 | 户外（seen 长航程） | 室内（seen 微空间） |
|----|--------------------|--------------------|
| SR | ≥ Phase-2 close 值（SR=86.7% ± 阶段公差） | ≥ 阶段 B 诚实基线 + 明确提升幅度（签字前定） |
| 到点门槛 | `success_dist=3.0 m` | `success_dist=0.5 m`；严门再看 0.2 m |
| `pose_source` | 户外允许 `gt_proxy`（历史一致，验收 stamp） | ≠ 未声明 `gt_proxy`；`attribution=wam` |
| SCR | ≤ Phase-2 close 值 | 报表齐全（无硬阈值前先看曲线） |

任一门未过 → **不 close Phase-3**；禁"户外过、室内没过就宣称阶段成功"。

## 5. 假进度清单（Phase-3 特化 · 继承父项外新增）

| 假进度 | 为何假 |
|--------|--------|
| 双 ckpt（室内一个、户外一个）拼进度 | 违反 Stick 主航道 = 同一大脑 |
| 混采比例未签字就跑训练 | 决策绕过 |
| 用户外三区罩剖面跑 indoor 评测 | 剖面错配；safety 参数不服务导航 |
| indoor 用户外 `success_dist=3.0m` 门 | 门错配；不达 0.x m 就不是 Indoor |
| P2 中途按单尺度失败率过采样 | 单失败补洞 |
| P3 只报单尺度回归 | 双门未双验 |

## 6. 变更记录

| 日期 | 内容 |
|------|------|
| 2026-09-08 | 建立 Phase-3 骨架：branch/目录/统一 config/本 runbook（起自 `phase2-pass-20260908`） |
