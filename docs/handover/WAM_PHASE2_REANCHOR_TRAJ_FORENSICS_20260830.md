# Phase-2 回锚 16 路航迹法医（2026-08-30）

> 协议：`step_e` + `goal_feat_mode=meter` + AdaptiveSubgoal + planner H=5 + ThreeZone · cruise=10

## 标签计数

| tag | n |
|-----|---|
| `F_OFFTRACK` | 2 |

## 逐路

| 路 | tag | prog | d_min | d_final | maxCTE | earlyCTE | lock_gap | IR | plot |
|----|-----|------|-------|---------|--------|----------|----------|----|------|
| R03 | `F_OFFTRACK` | 23% | 118.67 | 118.4 | 48.8 | 6.52 | 0.89 | 0.02 | `R03_traj_xy.png` |
| R05 | `F_OFFTRACK` | 0% | 133.84 | 149.91 | 40.27 | 4.97 | 0.35 | 0.02 | `R05_traj_xy.png` |

## 读数

- `F_OFFTRACK_EARLY`：前 50 步 CTE≥15.0m → **方向性失败**，汇总 Prog 无意义。
- `F_MONOTONE_INFLATE`：高 Prog + 大 CTE/`d_min` → **单调锁虚高进度**。
- `F_TERMINAL_GAP`：走廊进度高但从未进到达邻域。
- `F_SCR`：严重碰撞。

产物目录：`artifacts/videos/wam_phase2_conesfix_forensics_20260901`
