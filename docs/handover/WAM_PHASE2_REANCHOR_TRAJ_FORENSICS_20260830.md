# Phase-2 回锚 16 路航迹法医（2026-08-30）

> 协议：`step_e` + `goal_feat_mode=meter` + AdaptiveSubgoal + planner H=5 + ThreeZone · cruise=10

## 标签计数

| tag | n |
|-----|---|
| `F_MONOTONE_INFLATE` | 12 |
| `F_OFFTRACK` | 2 |
| `F_SCR` | 2 |

## 逐路

| 路 | tag | prog | d_min | d_final | maxCTE | earlyCTE | lock_gap | IR | plot |
|----|-----|------|-------|---------|--------|----------|----------|----|------|
| R01 | `F_MONOTONE_INFLATE` | 98% | 63.5 | 66.65 | 73.06 | 4.68 | 29.17 | 0.10 | `R01_traj_xy.png` |
| R02 | `F_MONOTONE_INFLATE` | 100% | 54.02 | 54.01 | 66.12 | 8.65 | 0.19 | 0.12 | `R02_traj_xy.png` |
| R03 | `F_MONOTONE_INFLATE` | 100% | 68.02 | 68.01 | 76.87 | 8.11 | 0.0 | 0.07 | `R03_traj_xy.png` |
| R04 | `F_SCR` | 0% | 142.94 | 171.47 | 48.75 | 2.92 | 0.0 | 1.00 | `R04_traj_xy.png` |
| R05 | `F_MONOTONE_INFLATE` | 100% | 68.59 | 68.58 | 76.61 | 8.63 | 0.36 | 0.08 | `R05_traj_xy.png` |
| R06 | `F_MONOTONE_INFLATE` | 100% | 61.57 | 61.56 | 72.21 | 7.91 | 0.2 | 0.07 | `R06_traj_xy.png` |
| R07 | `F_MONOTONE_INFLATE` | 98% | 59.85 | 71.46 | 73.0 | 7.57 | 18.0 | 0.11 | `R07_traj_xy.png` |
| R08 | `F_OFFTRACK` | 0% | 104.6 | 166.43 | 62.06 | 3.77 | 0.0 | 1.00 | `R08_traj_xy.png` |
| R09 | `F_MONOTONE_INFLATE` | 100% | 61.84 | 61.82 | 71.51 | 7.54 | 0.07 | 0.07 | `R09_traj_xy.png` |
| R10 | `F_MONOTONE_INFLATE` | 100% | 63.85 | 63.84 | 70.76 | 8.04 | 0.05 | 0.09 | `R10_traj_xy.png` |
| R11 | `F_MONOTONE_INFLATE` | 92% | 57.63 | 76.31 | 74.99 | 8.74 | 20.49 | 0.10 | `R11_traj_xy.png` |
| R12 | `F_MONOTONE_INFLATE` | 100% | 61.8 | 61.79 | 71.71 | 7.77 | 1.11 | 0.09 | `R12_traj_xy.png` |
| R13 | `F_OFFTRACK` | 25% | 112.68 | 116.03 | 56.29 | 7.02 | 0.04 | 0.94 | `R13_traj_xy.png` |
| R14 | `F_MONOTONE_INFLATE` | 97% | 57.99 | 58.38 | 70.02 | 7.21 | 17.75 | 0.09 | `R14_traj_xy.png` |
| R15 | `F_MONOTONE_INFLATE` | 100% | 57.95 | 57.93 | 68.96 | 7.31 | 0.0 | 0.08 | `R15_traj_xy.png` |
| R16 | `F_SCR` | 2% | 105.67 | 105.67 | 1.5 | 1.5 | 0.0 | 0.00 | `R16_traj_xy.png` |

## 读数

- `F_OFFTRACK_EARLY`：前 50 步 CTE≥15.0m → **方向性失败**，汇总 Prog 无意义。
- `F_MONOTONE_INFLATE`：高 Prog + 大 CTE/`d_min` → **单调锁虚高进度**。
- `F_TERMINAL_GAP`：走廊进度高但从未进到达邻域。
- `F_SCR`：严重碰撞。

产物目录：`/home/yao/aerial-wam-v2/artifacts/videos/wam_phase2_pcoll_veto_forensics_20260831_outdoor`
