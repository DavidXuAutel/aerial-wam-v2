# E1 DECLARE — scene fan intent (`--subgoal-source scene`)

> **Status**: **pre-registered, not yet run** (declared 2026-09-03)
> **Prev**: [`WAM_PHASE2_GOAL_SCENE_E0_DECLARE.md`](WAM_PHASE2_GOAL_SCENE_E0_DECLARE.md) — 接线绿灯 / 导航红灯（SR=0，F12 未解）
> **Plan**: [`docs/superpowers/plans/2026-09-03-phase2-goal-scene-nav.md`](../superpowers/plans/2026-09-03-phase2-goal-scene-nav.md) Task 6
> **Spec**: [`docs/superpowers/specs/2026-09-03-phase2-goal-scene-nav-design.md`](../superpowers/specs/2026-09-03-phase2-goal-scene-nav-design.md) §4.1 / §5

**本表阈值在开跑前写定，跑完不得下调。**

## 0. 开跑前的代码改动（必须披露）

E1 开跑前发现 `SceneIntentPlanner` 有一个**使 E1 不可能测出任何东西**的缺陷，已修，测试锁定。

| 项 | 改前 | 改后 |
|----|------|------|
| 前向危险处理 | 打分里 `j += 5.0`（软惩罚），条件 `fwd/horiz > 0.85` ≈ **±31.8° 锥** | `_blocked()` **硬丢弃**（spec §4.1.2「丢弃前方危险锥内的候选」），锥半角随净空收紧：`d_clear` 处不丢，`d_danger` 处丢 **±60°** 内全部 |
| 偏航扇 | `0, ±15, ±30`（最大 **30°**） | `0, ±15, ±30, ±45, ±60, ±75`（最大 **75°**） |

**为什么这是缺陷，不是口味问题**：候选 0 就是 `clip_toward_goal`（= E0 `toward_g` 的那条射线）。旧惩罚锥（±31.8°）**比整个扇面（±30°）还宽**，于是所有候选都吃同一个 `+5.0`，惩罚在比较中直接抵消，进展项永远选中候选 0 ⇒ **`scene` 恒等于 `toward_g`**。E1 会跑出与 E0 主臂逐位相同的数字，却看不出来。

单元测试已锁：`test_scene_tight_depth_peels_off_goal_ray`（挡路时 `chosen_idx != 0`）、`test_scene_fan_reaches_past_danger_cone`（扇面必须够到 ≥60°，否则整扇被丢空）、`test_scene_fan_starved_still_returns_target`。

**未改**：`_should_replan`（`d_fwd < d_clear` 即每步重规划）、`w_g/w_jump`、`r_m`、creep 速度、罩、`step_e` π。

## 1. 可观测性（E1 判定的前提）

E0 的 artifact 无法区分 `scene` 与 `toward_g`。本次为每路加：

| 字段 | 含义 |
|------|------|
| `n_intent_replans` | 外环重选次数 |
| `n_intent_offaxis` | **选中非候选 0** 的次数 ⇒ 真正偏离了对 G 直射线 |
| `mean/max_intent_dev_deg` | `c*` 相对对 G 射线的水平偏角（0 = 纯 `toward_g`） |
| `n_fan_starved` | 整扇被丢空、退化取最侧向候选的次数 |

汇总另加 `intent_offaxis_frac`。**这些是诊断量，不参与 PASS。**

`n_intent_offaxis == 0` ⇒ 本臂事实上就是 E0 主臂，E1 **无效**（不是 FAIL，是没测到东西）。

## 2. Arms

`scene` 只需跑 **1 个新臂**；对照直接用 E0 已有数字（同标注、同 2 路、同 ckpt、同设置）。

| Arm | subgoal_source | 来源 |
|-----|----------------|------|
| **E1 main** | `scene` | **本次新跑** |
| 对照 · E0 main | `toward_g` | E0 DECLARE：closure **0.487** / `d_final` **78.74 m** / SCR 0.0% / IR 0.6% |
| 对照 · waterline | `polyline` | E0 DECLARE：closure **0.370** / `d_final` **96.16 m** / SCR 0.0% / IR 0.1% |
| 对照 · 消融 A | `direct_g` | E0 DECLARE：closure 0.487 / `d_final` **300.72 m** / IR **29.9%** |

设置与 E0 逐项一致：assist OFF · `step_e` · no `--rolling-global` · anno `seen_airsim16_long_routes.json` · cruise 10 · planner H=5 · `--max-steps 400` · 同样那 2 路（E0 用 `--episodes 2`，E1 拆成 `--routes 0` + `--routes 1` 并行，选中的路完全相同）。

CLI 默认**仍是 `polyline`**（E0 的默认翻转未做），故必须显式传 `--subgoal-source scene`。

## 3. Gate（开跑前锁定）

| # | 判据 | 阈值 |
|---|------|------|
| **G0** | 有效性：扇面真的动过 | `n_intent_offaxis > 0` 且 `max_intent_dev_deg ≥ 15°`（否则 E1 无效，重设计而非重判） |
| **G1** | 无线臂 closure 不系统性崩（spec §5） | `mean_goal_closure ≥ 0.387`（= E0 `toward_g` 0.487 − 0.10） |
| **G2** | 安全不回退 | `severe_collision_rate ≤ 0.10`；E0 三臂均 0.0，**> 0 即黄灯需逐路看** |
| **G3** | 不散架（对照 `direct_g` 的 F11） | `mean d_final ≤ 150 m`，且无单路 `L_act > 3 × L_ref` |
| **G4** | 干预不失控 | `mean_intervention_rate ≤ 0.25` |
| **G5** | 不得宣称 200–500 m | `d_start` ≈ 151–154 m ⇒ **engineering probe only** |

**明确不作为 E1 判据**：
- **SR** —— E0 已证 SR=0（F12 terminal non-convergence 未解）；E1 不修 F12，SR 大概率仍为 0。**E1 green ≠ 能到达。**
- **Prog / CTE** —— 治理红线，永不参与主线判定。
- `n_intent_replans` / `dev_deg` 的绝对大小 —— 只读，不设阈。

## 4. Run（**110 / 125 并行**，每台一路）

ACCESS.md 里「125 不跑 eval」的限制**已作废**——那条只是因为当时 125 在跑别的 project；现两台空闲，按最大化利用并行。串行 ~1–1.5 h → 并行 **~20–40 min**。

新增 `--routes`（0-based 标注下标，**覆盖 `--episodes`**）。不拆标注文件：一个标注源，输出里的 `route_idx` / `base_route_idx` 不失真，以后每次并行都能复用。

两台都先：

```bash
cd ~/aerial-wam-v2 && git pull && source experiments/aerial/scripts/env_4090.sh
```

Step 0 · mock smoke（Mac 无 torch，只能在远端跑；先确认接线不炸；任一台跑一次即可）：

```bash
python -m experiments.aerial.scripts.wam_phase2_long_eval --mock --routes 0 --max-steps 8 --subgoal-source scene --out $TMPDIR/e1_smoke.json
```

期望：exit 0；JSON `"subgoal_source": "scene"`、`"route_indices": [0]`；`metrics` 含 `n_intent_replans` / `n_intent_offaxis`。

Step 1a · 在 **110** 跑 route 01：

```bash
python -m experiments.aerial.scripts.wam_phase2_long_eval --subgoal-source scene --planner --routes 0 --max-steps 400 --out artifacts/wam_phase2_e1_scene_r01_110.json 2>&1 | tee logs/wam_phase2_e1_scene_r01_110_$(date +%Y%m%d_%H%M%S).log
```

Step 1b · 在 **125** 跑 route 02（与 1a 同时开）：

```bash
python -m experiments.aerial.scripts.wam_phase2_long_eval --subgoal-source scene --planner --routes 1 --max-steps 400 --out artifacts/wam_phase2_e1_scene_r02_125.json 2>&1 | tee logs/wam_phase2_e1_scene_r02_125_$(date +%Y%m%d_%H%M%S).log
```

两台的日志尾部都会打 `PARTIAL RUN: routes [...] of 16 — merge ... before filling any DECLARE row`。**单台的 `Verdict` 是子集上的，无意义，不得填进 §5/§6。**

Step 2 · 合表（把 125 的 JSON 收到同一台，或都收到 Mac 上；合表不需要 torch）：

```bash
python -m experiments.aerial.scripts.merge_phase2_split_eval --out artifacts/wam_phase2_e1_scene_merged.json artifacts/wam_phase2_e1_scene_r01_110.json artifacts/wam_phase2_e1_scene_r02_125.json
```

合表脚本用**与评测器同一个 `aggregate_metrics`** 重算，不是手工平均——`max_intent_dev_deg` 是 max 不是 mean，手算必错。臂身份（`protocol_version` / `subgoal_source` / `goal_feat_mode` / `actor_ckpt` / `cruise_speed_m_s` / `rolling_global`）不一致，或两台 `--routes` 有重叠，**直接 refuse 退出**。

**§5 / §6 只准填 `wam_phase2_e1_scene_merged.json` 的数。**

`EXIT_CODE=1` 是 Verdict=FAIL 判定，**不是 crash**（SR=0 必然触发）。

| Arm | Host | routes | log | out |
|-----|------|--------|-----|-----|
| E1 main · a | **110** | `--routes 0`（route 01） | `logs/wam_phase2_e1_scene_r01_110_<ts>.log` | `artifacts/wam_phase2_e1_scene_r01_110.json` |
| E1 main · b | **125** | `--routes 1`（route 02） | `logs/wam_phase2_e1_scene_r02_125_<ts>.log` | `artifacts/wam_phase2_e1_scene_r02_125.json` |
| E1 main（判定用） | 合表 | 0,1 | — | `artifacts/wam_phase2_e1_scene_merged.json` |

### 4.1 跨机差的处置（开跑前写定）

E0 主臂两路**都在 110**；E1 的 route 02 换到 125，故 route 02 的 E1−E0 差里混了一份机器差。两机一致性有旁证：E0 route 01 `d_min` 110 = **52.28**、125 = **52.25**（Δ 0.03 m）。

**规则**：若合表后 route 02 的 `goal_closure` 落在 G1 阈值 0.387 的 **±0.05**（即 0.337–0.437）内，**先把 route 02 在 110 重跑一遍再判 G1**，不得直接拿跨机数字判绿或判红。落在这个带外则直接判。

## 5. Results (fill when done — 只填合表 JSON 的数)

| Arm | mean d_min | mean d_final | mean closure | SR | SCR | IR | replan | offaxis | dev mean/max |
|-----|------------|--------------|--------------|----|-----|----|--------|---------|--------------|
| E1 `scene` | | | | | | | | | |
| E0 `toward_g` | 78.34 | 78.74 | 0.487 | 0.0% | 0.0% | 0.6% | — | — | 0 / 0 |
| `polyline` | 96.16 | 96.16 | 0.370 | 0.0% | 0.0% | 0.1% | — | — | — |

逐路：

| Route | L_ref | L_act | d_min | d_final | closure | IR | replan | offaxis | max dev |
|-------|-------|-------|-------|---------|---------|----|--------|---------|---------|
| 01 | 168.0 | | | | | | | | |
| 02 | 156.0 | | | | | | | | |

## 6. Gate 判定 (fill when done)

- [ ] **G0** 扇面有效（offaxis > 0 且 max dev ≥ 15°）
- [ ] **G1** closure ≥ 0.387
- [ ] **G2** SCR ≤ 0.10
- [ ] **G3** d_final ≤ 150 m 且无单路 L_act > 3×L_ref
- [ ] **G4** IR ≤ 0.25
- [ ] **G5** 未宣称 200–500 m PASS

## 7. Next（不自动执行）

- E1 green → 才考虑把 CLI 默认改到 `scene`（**独立 commit**，plan Task 4 默认策略表）
- E0 的 `polyline → toward_g` 默认翻转**仍未做**，与本项一并等指令
- **Stop**：不开 E2 动态障碍，不生成 200–500 m 走廊（需另立 plan）
- F12 terminal non-convergence 仍未解 —— E1 不修它，SR 不会因 E1 转正
