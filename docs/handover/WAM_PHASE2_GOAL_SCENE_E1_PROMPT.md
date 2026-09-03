# E1 交接 prompt（给有出网权限的 CLI 会话）

> 用法：在能 ssh 到 110/125 的终端里起 `claude`，把本文件从「## 任务」起整段贴进去（或直接说「读 `docs/handover/WAM_PHASE2_GOAL_SCENE_E1_PROMPT.md` 并执行」）。
> 写于 2026-09-03，仓库状态：分支 `feat/phase2-goal-scene-nav`，HEAD `3848e46`（**本地未推**）。

## 背景（30 秒）

Aerial WAM **Phase-2 主航道**（2026-09-03 重置）：输入只有远目标 G + 当前场景，**无预置折线**；外环 WAM 出近距意图 `c*`，内环冻结的 Phase-1 `step_e` π 执行，安全罩兜底，`‖p−G‖≤3 m` 停机。Phase-1 已通过，不要按 V4-MVP 的框架理解本项目。

- **E0 已判**：接线绿灯（`toward_g` closure 0.487 > `polyline` 0.370；`direct_g` 是干净的 F11 负对照，`d_final` 300.72 m / IR 29.9%），**导航红灯**（SR=0，F12 terminal non-convergence 未解）。见 [`WAM_PHASE2_GOAL_SCENE_E0_DECLARE.md`](WAM_PHASE2_GOAL_SCENE_E0_DECLARE.md)。
- **E1 已预注册、尚未跑**：`--subgoal-source scene`（扇形候选 + 前向危险锥硬丢弃）。阈值在开跑前已写定，见 [`WAM_PHASE2_GOAL_SCENE_E1_DECLARE.md`](WAM_PHASE2_GOAL_SCENE_E1_DECLARE.md) §3。

## 任务

按顺序执行，每步失败就停下报告，不要绕过。

### 1. 先推代码

本地 `3848e46`（`--routes` + 合表脚本）未推，110/125 拉不到就跑不了 E1。两个 remote：`github`（GitHub https）、`origin`（`cursor-125:~/repos/aerial-wam-v2.git`）。

```bash
cd ~/Projects/aerial-wam-v2 && git push github HEAD && git push origin HEAD
```

### 2. 两台各自更新

110：`ssh a26125-110-public`；125：`ssh cursor-125-public`。两台都在 `~/aerial-wam-v2`。先用 `git remote -v` 确认该机跟哪个 remote，再拉。

```bash
cd ~/aerial-wam-v2 && git fetch --all && git checkout feat/phase2-goal-scene-nav && git pull && git log --oneline -1
```

确认 HEAD 是 `3848e46`。然后 `source experiments/aerial/scripts/env_4090.sh`。

### 3. mock smoke（任一台跑一次，先确认接线不炸）

```bash
python -m experiments.aerial.scripts.wam_phase2_long_eval --mock --routes 0 --max-steps 8 --subgoal-source scene --out /tmp/e1_smoke.json
```

期望 exit 0；JSON 里 `"subgoal_source": "scene"`、`"route_indices": [0]`，`metrics` 含 `n_intent_replans` / `n_intent_offaxis`。不符合就停下报告。

### 4. 两机并行跑 E1（**同时开**，各一路，~20–40 min）

110 跑 route 01：

```bash
python -m experiments.aerial.scripts.wam_phase2_long_eval --subgoal-source scene --planner --routes 0 --max-steps 400 --out artifacts/wam_phase2_e1_scene_r01_110.json 2>&1 | tee logs/wam_phase2_e1_scene_r01_110_$(date +%Y%m%d_%H%M%S).log
```

125 跑 route 02：

```bash
python -m experiments.aerial.scripts.wam_phase2_long_eval --subgoal-source scene --planner --routes 1 --max-steps 400 --out artifacts/wam_phase2_e1_scene_r02_125.json 2>&1 | tee logs/wam_phase2_e1_scene_r02_125_$(date +%Y%m%d_%H%M%S).log
```

- `--subgoal-source scene` 必须显式传：CLI 默认仍是 `polyline`。
- **`EXIT_CODE=1` 是 Verdict=FAIL 判定，不是 crash**（SR=0 必然触发）。别把它当报错去「修」。
- 日志尾部会打 `PARTIAL RUN: routes [...] of 16 — merge ...`。**单台 JSON 的 `Verdict` 是子集上的，无意义，不得填进 DECLARE。**

### 5. 合表（把两个 JSON 收到同一台；合表不需要 torch）

```bash
python -m experiments.aerial.scripts.merge_phase2_split_eval --out artifacts/wam_phase2_e1_scene_merged.json artifacts/wam_phase2_e1_scene_r01_110.json artifacts/wam_phase2_e1_scene_r02_125.json
```

用评测器同一个 `aggregate_metrics` 重算。**禁止手工平均**——`max_intent_dev_deg` 是 max 不是 mean。臂身份不一致或两台 `--routes` 重叠会 refuse 退出，那种情况直接报告，别改脚本绕过。

### 6. 判 Gate 并填 DECLARE

**只准填 `wam_phase2_e1_scene_merged.json` 的数**，填 E1 DECLARE §5（总表 + 逐路表）和 §6（勾选框）。

| # | 判据 | 阈值 |
|---|------|------|
| **G0** | 有效性：扇面真的动过 | `n_intent_offaxis > 0` 且 `max_intent_dev_deg ≥ 15°` |
| **G1** | closure 不系统性崩 | `mean_goal_closure ≥ 0.387`（= E0 `toward_g` 0.487 − 0.10） |
| **G2** | 安全不回退 | `severe_collision_rate ≤ 0.10`（E0 三臂均 0.0，>0 即黄灯需逐路看） |
| **G3** | 不散架 | `mean d_final ≤ 150 m` 且无单路 `L_act > 3 × L_ref`（L_ref：route 01 = 168.0，route 02 = 156.0） |
| **G4** | 干预不失控 | `mean_intervention_rate ≤ 0.25` |
| **G5** | 不得宣称 200–500 m | `d_start` ≈ 151–154 m ⇒ engineering probe only |

**明确不作为判据**：SR（E0 已证 SR=0，F12 未解，E1 不修它，**E1 green ≠ 能到达**）、Prog/CTE（治理红线）、`n_intent_replans` / `dev_deg` 的绝对大小（只读）。

两条特殊处置：

- **G0 不过** ⇒ E1 **无效**（不是 FAIL，是没测到东西：`scene` 事实上退化成了 E0 主臂）。此时**停下报告，等重设计指令**，不要改 `SceneIntentPlanner` 参数重跑。
- **跨机差**（E1 DECLARE §4.1，开跑前已写定）：E0 主臂两路都在 110，route 02 换到 125 混了一份机器差。若合表后 **route 02 的 `goal_closure` 落在 0.337–0.437**（G1 阈值 0.387 ±0.05），**先把 route 02 在 110 重跑一遍再判 G1**。带外直接判。旁证：E0 route 01 `d_min` 110 = 52.28 / 125 = 52.25。

填完提交（DECLARE 单独一个 commit），然后**停下报告**。

## 治理红线（违反即停）

1. 阈值开跑前已冻结，**跑完不得下调**，不得事后改判据措辞。
2. **不得为刷到达率关安全罩**，不得开 F15 效率权重 / path heading assist / `--lookahead-feedback` / `--rolling-global`。
3. **不得翻 CLI 默认**（`polyline → toward_g` 或 `→ scene`）。默认翻转只能在 DECLARE 绿灯后的**独立 commit** 里做，且要等人类指令。E0 的默认翻转也仍未做。
4. **不得宣称 200–500 m 过门**——本次是 ~151–154 m。
5. **不开 E2 动态障碍、不生成 200–500 m 走廊**（需另立 plan）。
6. 代码只走 git，**不许 scp 热补丁**到 110/125；Mac 只做代码/单测/文档，GPU/AirSim 只在远端。
7. 汇报要诚实：FAIL 就写 FAIL 并附数字，跳过的步骤要说明。**报完停下等指令，不要自作主张提行动方案。**

## 参考

- E1 DECLARE（阈值 + 运行命令 + 跨机规则）：[`WAM_PHASE2_GOAL_SCENE_E1_DECLARE.md`](WAM_PHASE2_GOAL_SCENE_E1_DECLARE.md)
- E0 DECLARE（对照数字）：[`WAM_PHASE2_GOAL_SCENE_E0_DECLARE.md`](WAM_PHASE2_GOAL_SCENE_E0_DECLARE.md)
- Runbook（§7.1 = 多机并行纪律，F1–F15 失败归类）：[`experiments/aerial/RUNBOOK_wam_phase2_long_horizon.md`](../../experiments/aerial/RUNBOOK_wam_phase2_long_horizon.md)
- 机器/网络：[`ACCESS.md`](ACCESS.md)
- spec / plan：`docs/superpowers/specs/2026-09-03-phase2-goal-scene-nav-design.md` §4.1/§5、`docs/superpowers/plans/2026-09-03-phase2-goal-scene-nav.md` Task 6
