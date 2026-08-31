# Indoor WAM — STATUS（主航道）

> **权威**：[`experiments/aerial/RUNBOOK_indoor_0xm.md`](../../experiments/aerial/RUNBOOK_indoor_0xm.md)（2026-08-29 Stick 主航道）  
> **125 prompt**：[`INDOOR_MAINLINE_125_PROMPT_20260828.md`](INDOOR_MAINLINE_125_PROMPT_20260828.md)

## 一句话

**所有方案 Stick 主航道。** 阶段 **A0** 合同已落地（`goal_rel`←\(\hat p\)，`pose_source` 落盘，禁静默 GT）。  
阶段 **B** 诚实基线已重跑：**arrival_rate_hat = 0/4 @ 0.2m**（`odom_from_imu_rgb` + `assist=none`）— 显著差于夹具账，符合预期。  
**下一步 = 阶段 C（H100 FT · 签字后）**。

## 勾选

| 项 | 状态 |
|----|------|
| Stick 主航道 + 传感合同写入 runbook | ✅ 2026-08-29 |
| 阶段 **A0**：`goal_rel`←\(\hat p\)；`pose_source` 落盘；禁静默 GT | ✅ 2026-08-29 |
| 阶段 A：默认仅 WAM（`assist=none`） | ✅ |
| 阶段 B：合同化主航道基线 | ✅ [`artifacts/indoor_mainline_baseline_20260829.json`](../../artifacts/indoor_mainline_baseline_20260829.json) |
| 阶段 C：H100 FT | ⬜ 签字后 |
| 阶段 D：held-out 验收 | ⬜ |

## 阶段 A0 改动文件（125 · 2026-08-29）

| 文件 | 内容 |
|------|------|
| `experiments/aerial/rl/pose_estimate.py` | **新**：`PoseEstimate`、`OdomFromImuRgbPoseEstimator`、`GtProxyPoseEstimator`；`pose_source` 合同 |
| `experiments/aerial/rl/goal_features.py` | `goal_rel_from_obs` 必须走 `pose_estimate` 或显式 `gt_proxy` |
| `experiments/aerial/rl/indoor_controller.py` | 高度优先 rangefinder/AGL；`mainline_sensors_used` 含 `pose:*` |
| `experiments/aerial/rl/collector.py` | 默认 `pose_source=gt_proxy`（仿真训练显式声明）；`act_delta` 传 `nav_pos` |
| `experiments/aerial/rl/env/obs.py` | `PolicyObservation.nav_pos/nav_yaw/goal` |
| `experiments/aerial/rl/wm_data.py` | WM 训练路径显式 `gt_proxy` stamp |
| `experiments/aerial/scripts/indoor_mainline_baseline_eval.py` | **新**：阶段 B 协议 runner |
| `experiments/aerial/rl/tests/test_pose_estimate.py` | **新**：A0 合同单测 |

## 阶段 B 基线摘要（合同 · 2026-08-29）

协议：`pose_source=odom_from_imu_rgb`，`assist=none`，`forbid_gt_world_pose_control=true`，`success_dist=0.20m`。

| Route | d_end_hat (m) | d_end_gt (m) | arrived_hat | attribution | pose_source |
|-------|---------------|--------------|-------------|-------------|-------------|
| 07 | 1032.1 | 89.7 | ❌ | wam | odom_from_imu_rgb |
| 10 | 218.5 | 105.2 | ❌ | wam | odom_from_imu_rgb |
| 13 | 873.4 | 131.0 | ❌ | wam | odom_from_imu_rgb |
| 14 | 693.6 | 88.8 | ❌ | wam | odom_from_imu_rgb |

**作废**（未声明 `pose_source` / GT `goal_rel`）：  
`indoor_lossless_eval_20260828.json`、`indoor_odom_alt_eval_20260828.json`、`indoor_two_phase_eval_20260828.json`、`indoor_mainline_baseline_20260828.json`。

## 阻塞 / 下一步

1. **VIO 前端**：当前 `odom_from_imu_rgb` 为动作积分 stub，漂移极大 → 阶段 C FT 前须签字 + 真实 \(\hat p\) 或仿真 VIO stub 升级。  
2. 签字后 **阶段 C**：H100 室内全分布 FT（禁单失败补洞）。  
3. **阶段 D**：held-out；`attribution=wam`；`pose_source`≠未声明 gt。

禁止：H100 FT（未签字）、单失败补洞、夹具成绩写完成态、默认 `assist=gt_pd`。

**汇报**：[`/tmp/indoor_mainline_125_report.md`](/tmp/indoor_mainline_125_report.md)
