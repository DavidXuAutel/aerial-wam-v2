# Aerial WAM 阶段 2 执行 Runbook（分层长程 200~800m · 10m/s 高速巡航版）

> **日期**：2026-08-28  
> **本文件是什么**：阶段 2（走廊级/林区长程自主飞行与 10m/s 高速巡航）执行的**唯一日常入口**。  
> **设计规格书**：[`docs/superpowers/specs/2026-08-28-hierarchical-long-horizon-wam-design.md`](../../docs/superpowers/specs/2026-08-28-hierarchical-long-horizon-wam-design.md)  
> **实施计划**：[`docs/superpowers/plans/2026-08-28-hierarchical-long-horizon-10ms-wam.md`](../../docs/superpowers/plans/2026-08-28-hierarchical-long-horizon-10ms-wam.md)  
> **阶段 1 结论**：阶段 1 局部 WAM 5Hz 闭环验收已落地（到达率 93.3%，0 碰撞）。

---

## 核心主线纪律（常驻 · 绝对禁止偏离主航道）

**主线唯一**：单目 RGB + IMU → 潜空间世界模型（RSSM）想象规划 + 分层动态连续前瞻（Adaptive Carrot-on-a-Stick）→ 200~800m 长航程自主高速（最高 10m/s）巡航、避障与入圈。

1. **坚持分层解耦，杜绝单层大尺度漂移**：
   * 上层只负责在 SE(3) 解耦机体系下下发 $20\sim 55\text{m}$ 局域子目标 $g_{\text{rel}}^{\text{body}}$；
   * 底层 5Hz WAM 策略与 ImaginationPlanner 负责近身视觉避障；禁止把 500m 绝对距离直接塞给底层网络。
2. **严守物理速度与转向边界（10m/s 航道准则）**：
   * 开阔直道允许全速 10 m/s 巡航；
   * 密集障碍区（$\hat{D}_{\text{fwd}} \le 3\text{m}$）与急弯（$\ge 60^\circ$）必须通过**净空与曲率减速器**将速度主动压制至 3~5 m/s，禁止为追求时间指标而超机动侧滑撞障。
3. **禁止任何伪创新与旁支偏离**：
   * **禁止**用外部全局路径平滑跟踪器（如纯 Pure Pursuit / MPC）替换底层潜空间策略冒充 WAM；
   * **禁止**关掉安全罩刷到达率；
   * **禁止**在阶段 2 中随意推翻阶段 1 验证通过的底层权重（坚持零重训复用原则）。
4. **机器执行纪律**：
   * **Mac**：仅做代码编写、单元测试、Mock 校验与文档/git 同步；
   * **cursor-125（RTX 4090）**：承接 AirSim 16 路线全量 200~500m 闭环长程评测与视频录制。

---

## 阶段 2 标准执行路线图（步骤 H ~ L）

```
[Phase 2 Mainline Flow]
  Step H: 动态连续前瞻与 10m/s 减速器核心实现 (subgoal_generator.py + 单元测试)
    │
    ▼
  Step I: 200~500m 长路线基准生成 (seen_airsim16_long_routes.json)
    │
    ▼
  Step J: 长程闭环评测调度器 (wam_phase2_long_eval.py + Mock 验证)
    │
    ▼
  Step K: 125 机器 AirSim 全量长程评测 (16 routes, 10m/s cruise, 1000 steps)
    │
    ▼
  Step L: 阶段 2 验收指标签署与产物归档 (SR ≥ 80%, SCR ≤ 10%, SPL ≥ 70%)
```

---

### Step H：前瞻与减速器实现（Mac 本地）

* **目标**：实现 `AdaptiveSubgoalGenerator`，保证单调性锁（Anti-Backtracking）、10m/s 前瞻扩展（$R_{\text{base}}=55\text{m}$）、急弯与低净空收紧。
* **文件**：`experiments/aerial/rl/subgoal_generator.py`
* **测试**：
  ```bash
  pytest experiments/aerial/rl/tests/test_subgoal_generator.py -v
  ```
* **准出条件**：所有几何、单调性与 10m/s 净空测试 100% PASS。

---

### Step I：长路线基准集生成（Mac 本地）

* **目标**：基于 AirSim-16 拓扑生成 16 条 200~500m 连续长路线。
* **执行**：
  ```bash
  python experiments/aerial/scripts/generate_long_routes.py
  ```
* **准出条件**：`artifacts/seen_airsim16_long_routes.json` 产出，包含 8 条中长程（200~300m）与 8 条超长程（300~500m）。

---

### Step J：长程评测脚本与 Mock 验证（Mac 本地）

* **目标**：实现 `wam_phase2_long_eval.py`，集成 Subgoal 动态前瞻与阶段 1 WAM 控制器。
* **执行**：
  ```bash
  python experiments/aerial/scripts/wam_phase2_long_eval.py --mock --episodes 2
  ```
* **准出条件**：Mock 模式下 0 crash，正常输出分步前瞻数据与 JSON 指标。

---

### Step K：125 机器长程实测（cursor-125）

* **目标**：在 4090 真实 AirSim 仿真中评测 16 条长路线。
* **执行命令（125 机器）**：
  ```bash
  cd ~/aerial-wam-v2 && git pull
  source experiments/aerial/scripts/env_4090.sh
  python experiments/aerial/scripts/wam_phase2_long_eval.py \
    --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt \
    --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_step_e_20260828/v4_ac_latest.pt \
    --annotation artifacts/seen_airsim16_long_routes.json \
    --cruise-speed 10.0 \
    --planner --planner-horizon 5 \
    --max-steps 1000 \
    --out artifacts/wam_phase2_accept_result.json
  ```

---

### Step L：阶段 2 验收判定标准

| 核心指标 | 门限要求 | 物理意义 |
| :--- | :--- | :--- |
| **长程到达率 (`arrival_rate`)** | **$\ge 80.0\%$** (13/16 条到达) | 200~500m 长航程全自主完成率 |
| **严重碰撞率 (`severe_collision_rate`)** | **$\le 10.0\%$** ($\le 1$ 条事故) | 高速 10m/s 巡航下的避障安全性 |
| **轨迹加权效率 (`SPL`)** | **$\ge 70.0\%$** | 考核无冗余无序绕远 |
| **全线平均进度比 (`mean_progress_ratio`)** | **$\ge 90.0\%$** | 整体航线推进能力 |
| **安全干预率 (`mean_intervention_rate`)** | **$\le 25.0\%$** | 验证策略自发避障而非依赖硬刹车 |
