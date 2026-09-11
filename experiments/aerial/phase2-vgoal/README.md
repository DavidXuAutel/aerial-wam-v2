# Phase-2 + vgoal · 已 close 几何导航 × 视觉目标

> **分支**：`project/phase2-vgoal`（起自 tag `phase2-pass-20260908`）  
> **入口 RUNBOOK**：[`docs/handover/RUNBOOK_phase2_vgoal.md`](../../../docs/handover/RUNBOOK_phase2_vgoal.md)  
> **活页**：[`docs/handover/WAM_PHASE2_VGOAL_STATUS.md`](../../../docs/handover/WAM_PHASE2_VGOAL_STATUS.md)  
> **真机**：[`docs/handover/ORIN_REAL_HARDWARE_RUNBOOK.md`](../../../docs/handover/ORIN_REAL_HARDWARE_RUNBOOK.md)

## 阶段（2026-09-11）

- **仿真**：L1 closed · L2 接线完成 · **L3 paused**（红车/Cart 旁线 archived）
- **真机**：Orin 台架 → 见真机 RUNBOOK

## 一句话

在 **Phase-2 outdoor close**（E2 `toward_g` π · TTI 2.5 · long routes）上，叠 **实时目标识别 + 语义导航**；`aerial-vgoal-wam` 提供检测/跟踪/几何，**主栈与验收以 Phase-2 为准**（旧 Method B `step_e`/m1a20 短评不再作主航道）。

V0 的 `wam_vgoal_eval`（GT 投影 + `toward_g` fallback）仅作接线探针；产品形态为 **YOLO + D̂ 反投影 + `VisualGoalWAMPolicy`** 接入同一 Phase-2 壳。

**不含** Phase-3 室内融合、混采 FT、双尺度 profile。

## 栈对比

| 层 | Phase-2 close（几何） | Phase-2 + vgoal（本 project） |
|----|----------------------|------------------------------|
| 外环 / goal | `clip_toward_goal(G)` → `goal_rel` | `TargetTracker` + detector → `goal_rel` |
| 回落 | — | tracker `SEARCHING` → `toward_g`（默认 ON） |
| 内环 | `step_e` LatentActorDeployPolicy | **同 ckpt** |
| 安全 | TTI `tti_coeff=2.5` | **同** |
| 评测脚本 | `wam_phase2_long_eval.py --subgoal-source toward_g` | `wam_vgoal_eval.py` |
| 兄弟仓 | — | `~/Projects/aerial-vgoal-wam`（`vgoal.*`） |

## 目录

```
experiments/aerial/phase2-vgoal/
├── README.md          # 本文
└── notes/             # 实验一页记录（按需）

experiments/aerial/scripts/
├── wam_phase2_long_eval.py      # 几何主臂（继承 phase2-pass）
├── wam_vgoal_eval.py            # 视觉目标臂（M1–M4）
├── wam_vgoal_deploy.py          # Orin + Pixhawk 真机 deploy
├── camera_yolo_probe.py         # C922 + YOLO 单帧探针
├── pixhawk_offboard_hover.py    # MAVLink / OFFBOARD 烟测
├── vgoal_area_search.py         # M3 AreaSearchPlanner 接线
├── vgoal_dynamic_follow.py      # M4 DynamicTargetTracker 接线
└── vgoal_red_car_*.py           # archived 旁线（sim 红车，勿再投入）

experiments/aerial/deploy/
└── real_camera.py               # V4L2 / C922 采集

experiments/aerial/rl/env/
├── mavlink_bridge.py            # PX4 MAVLink 速度 setpoint
└── pixhawk_env.py               # 真机 env（对齐 AirSim 合同）
```

## 冻结基线

| 项 | 值 |
|----|-----|
| Tag | `phase2-pass-20260908` |
| 几何 close | SR **86.7%** (13/15) · SCR **6.7%** · `toward_g` · cs=10 · tti=2.5 |
| 默认 actor | `v4_ac_ckpt_phase2_toward_g_20260905_112006/v4_ac_latest.pt`（`wam_vgoal_eval` 默认） |
| WM | `wm_ckpt_d_full_20260828/wm_step_3500.pt` |

## 与 Phase-3 的关系

| | `project/phase2-vgoal` | `phase3/unified-outdoor-indoor` |
|--|------------------------|----------------------------------|
| 起点 | `phase2-pass-20260908` | 同 |
| 范围 | 户外 + **视觉目标** | 户外 + **室内 0.x m** 融合训练 |
| vgoal | **本 project 主航道** | 仅带 eval 脚本，非主线 |
| 训练 | 不重训（先 eval 接线） | P1–P3 混采 FT 待签字 |

两线可并行；**不要**把室内合同混进本 project。
