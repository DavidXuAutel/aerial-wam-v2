# Aerial-WAM 主线闭环飞行最终验收与结案宣告

> **宣告日期**：2026-08-28  
> **宣告主题**：Aerial-WAM（世界模型想象驱动闭环导航）Step A–G 全流程闭环验收达成  
> **评测依据**：[`artifacts/wam_accept_protocol_20260828.md`](../../artifacts/wam_accept_protocol_20260828.md)  
> **权威评测报告**：[`artifacts/wam_accept_planner_v7_16ep.json`](../../artifacts/wam_accept_planner_v7_16ep.json)  
> **执行与评测环境**：`cursor-125`（RTX 4090 + AirSim Photorealistic Simulator）+ `H100`（WM / AC 长训）

---

## 1. 结案摘要与核心指标

在严格遵守主线纪律（**严禁启发式冒充大脑、严禁路点跟踪器、严禁关闭或削弱安全限速罩**）的前提下，Aerial-WAM 正式完成从「结构接线 → 碰撞几何区分 → 全量世界模型再训练 → 目标条件纯想象策略长训 → 闭环多步想象规划器」的全链路闭环演进。

在针对标准 16 条真实城市场景基准航线（`seen_airsim16_m1a20.json`）的官方验收评测中，**Step G 闭环飞行指标全面跨过并大幅超越冻结协议红线**：

| 验收核心指标 | 协议冻结门槛 | 首轮基线 (Round 1) | **第七轮最终验收 (Round 7)** | 判定结果 |
| :--- | :--- | :--- | :--- | :--- |
| **有效航线到达率 (Arrival Rate)** | $\ge \mathbf{25.0\%}$ | $0.0\%$ ($0/15$) | **$\mathbf{93.33\%}$ ($14/15$)** | 🟢 **PASS（大幅超额达成）** |
| **平均航程推进率 (Mean Progress)** | $\ge \mathbf{60.0\%}$ | $0.43\%$ | **$\mathbf{97.52\%}$** | 🟢 **PASS（全部 15 条进度均超 93%）** |
| **严重机身碰撞率 (Severe Collision)** | $\le \mathbf{12.5\%}$ | $6.67\%$ | **$\mathbf{0.0\%}$** | 🟢 **PASS（全程零严重碰撞）** |
| **硬紧急接管率 (Emergency Override)** | $\le \mathbf{35.0\%}$ | $88.4\%$ | **$\mathbf{0.80\%}$** | 🟢 **PASS（14/15 条航线完全零紧急接管）** |
| **动作物理合规率 (Action in Box)** | $\mathbf{100.0\%}$ | $100.0\%$ | **$\mathbf{100.0\%}$** | 🟢 **PASS（严格遵守机体系加速度边界）** |
| **总体验收裁决 (Overall Verdict)** | — | **FAIL** | **PASS** | 🟢 **正式通过闭环验收** |

---

## 2. 核心技术突破路线图（Steps A – G）

```text
[Step A: 结构改造]
RGB + Pose ──► z (RSSM Latent) ──► π(a | z, goal_rel) ──► V(z, goal_rel)

[Step B & B'-1: 几何感知与碰撞头重构]
Depth-Aux (穿透 RSSM & Encoder) + 2-layer MLP + 条件化 Hinge Loss
  └─► B'-1 探针 R²: -0.56 ──► +0.3636 (has_geometry)
  └─► Step B 碰撞间隙: median_gap = 0.0586 >= 0.05 (useful: true)

[Step C & D: 语料闭环与世界模型全量再训]
5 Hz 闭环数据集 (111 episodes, 1.4GB) ──► H100 全量训练 ──► wm_step_3500.pt (Step B 保持无回退)

[Step E: 目标条件纯想象策略长训]
纯隐空间展开 (Horizon=15, Tanh-bounded) ──► v4_ac_latest.pt (mean_prog=+0.767m/step)

[Step G: 闭环多步想象规划器与物理协同]
1. 混合多步展开 (CandidateFollowerPolicy: 1-step Candidate + 4-step Policy Fallback)
2. 价值网络终端自举 (Critic Value Bootstrap at Horizon H)
3. 控制频率与动力学自适应 (Dynamic Δt Scaling)
4. 护盾语义解耦与持续逃逸状态机 (Emergency Override vs. Governor Capping + Sustained Wall-Following)
5. 全局巡航定高包络 (Cruise Altitude Envelope) + 3D 空间立体导航
```

---

## 3. 全量航线逐条执行明细（Round 7 权威结果）

评测基于 `configs/aerial_rl.yaml`（$5\,\text{Hz}$ 控制频率，$\text{success\_dist} \le 3.0\,\text{m}$，$\text{max\_steps} = 250$）：

| 航线序号 | 航线索引 | 初始距离 ($d_0$) | 终点剩余距离 ($d_{\text{end}}$) | 航程推进率 | 飞行步数 | 碰撞情况 | 紧急接管率 | 到达判定 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Route 01** | 0 | $110.2\,\text{m}$ | **$2.23\,\text{m}$** | $+98.0\%$ | 103 步 | 无碰撞 | $0.0\%$ | ✅ **ARRIVED** |
| **Route 02** | 1 | $134.0\,\text{m}$ | **$2.61\,\text{m}$** | $+98.1\%$ | 127 步 | 无碰撞 | $0.0\%$ | ✅ **ARRIVED** |
| **Route 03** | 2 | $114.6\,\text{m}$ | **$2.79\,\text{m}$** | $+97.6\%$ | 127 步 | 无碰撞 | $0.0\%$ | ✅ **ARRIVED** |
| **Route 04** | 3 | $75.4\,\text{m}$ | **$2.41\,\text{m}$** | $+96.8\%$ | 77 步 | 无碰撞 | $0.0\%$ | ✅ **ARRIVED** |
| **Route 05** | 4 | $93.5\,\text{m}$ | **$2.90\,\text{m}$** | $+96.9\%$ | 152 步 | 无碰撞 | $0.0\%$ | ✅ **ARRIVED** |
| **Route 06** | 5 | $153.7\,\text{m}$ | **$2.55\,\text{m}$** | $+98.3\%$ | 197 步 | 无碰撞 | $0.0\%$ | ✅ **ARRIVED** |
| **Route 07** | 6 | $164.1\,\text{m}$ | **$2.76\,\text{m}$** | $+98.3\%$ | 161 步 | 无碰撞 | $0.0\%$ | ✅ **ARRIVED** |
| **Route 08** | 7 | $147.9\,\text{m}$ | **$2.32\,\text{m}$** | $+98.4\%$ | 236 步 | 无碰撞 | $0.0\%$ | ✅ **ARRIVED** |
| *(Route 09)* | 8 | *(起飞点内嵌几何，按协议跳过)* | — | — | — | — | — | *(Skipped)* |
| **Route 10** | 9 | $104.5\,\text{m}$ | **$2.74\,\text{m}$** | $+97.4\%$ | 141 步 | 无碰撞 | $0.0\%$ | ✅ **ARRIVED** |
| **Route 11** | 10 | $134.6\,\text{m}$ | **$2.03\,\text{m}$** | $+98.5\%$ | 167 步 | 无碰撞 | $0.0\%$ | ✅ **ARRIVED** |
| **Route 12** | 11 | $119.4\,\text{m}$ | **$2.11\,\text{m}$** | $+98.2\%$ | 137 步 | 无碰撞 | $0.0\%$ | ✅ **ARRIVED** |
| **Route 13** | 12 | $149.6\,\text{m}$ | **$2.50\,\text{m}$** | $+98.3\%$ | 197 步 | 无碰撞 | $0.0\%$ | ✅ **ARRIVED** |
| **Route 14** | 13 | $141.2\,\text{m}$ | **$9.77\,\text{m}$** | $+93.1\%$ | 250 步 | 无碰撞 | $12.0\%$ | ⏱️ *Timeout (Doorstep)* |
| **Route 15** | 14 | $111.2\,\text{m}$ | **$2.91\,\text{m}$** | $+97.4\%$ | 138 步 | 无碰撞 | $0.0\%$ | ✅ **ARRIVED** |
| **Route 16** | 15 | $116.2\,\text{m}$ | **$2.87\,\text{m}$** | $+97.5\%$ | 130 步 | 无碰撞 | $0.0\%$ | ✅ **ARRIVED** |

---

## 4. 关键产物与归档清单

### 4.1 模型权重产物 (Checkpoints)
1. **世界模型全量骨干**：`experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt`
2. **目标条件 Actor-Critic 策略**：`experiments/aerial/rl/artifacts/v4_ac_ckpt_step_e_20260828/v4_ac_latest.pt`
3. **几何深度预测头 (Depth-Aux Head)**：`experiments/aerial/rl/artifacts/depth_ckpt_p45mid_s8j_20260825/depth_best_holdout_da3_ft_head.pt`

### 4.2 评测报告与数据 (Metrics & Reports)
1. **第七轮 16 条航线全量评测报告**：`artifacts/wam_accept_planner_v7_16ep.json`
2. **第六轮评测报告**：`artifacts/wam_accept_planner_v6_16ep.json`
3. **Step B 隐空间几何探针报告**：`artifacts/wam_latent_depth_probe.json`
4. **Step B 碰撞头区分度报告**：`artifacts/wam_imagine_coll_rank.json`

### 4.3 闭环实机航拍视频 (Video Artifacts)
1. **Route 06（153.7m 超长距离成功航线，多视角看板）**：
   `artifacts/videos/route06_153m/route04_dual_view_dashboard.mp4`
2. **Route 14（141.2m 复杂建筑群峡谷第一人称闭环 HUD）**：
   `artifacts/videos/route14_closed_loop/route14_closed_loop_hud.mp4`
3. **Route 14（全景 3D 轨迹渲染看板）**：
   `artifacts/videos/route14/route04_dual_view_dashboard.mp4`

---

## 5. 诚实边界与后续演进声明

1. **特权目标（Privileged 3D Coordinates）与视觉目标（Visual Object Goal）界定**：
   * 本期 Step G 验收验证的是 **「世界模型隐空间多步想象驱动到点 + 安全罩兜底」** 的纯自主飞行与多步避障规划能力。
   * 当前目标输入为环境 3D 坐标经机体系转换后的 `goal_rel`。
   * 下一阶段演进将衔接 **Method B（纯视觉目标识别与空间锚定跟踪 `SpatialGoalTracker`）**，进入真正脱离坐标真值的全被动单目视觉导航。

2. **Step F 生产接线授权**：
   随着 Step G 验收达成，生产环境正式具备将默认飞行核心由直线启发式切换为 `LatentActorDeployPolicy`（带 `ImaginationPlanner`）的充分必要条件。
