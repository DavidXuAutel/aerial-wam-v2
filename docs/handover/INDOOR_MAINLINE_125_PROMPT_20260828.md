# 125 Agent：室内主航道 · 阶段 A0（合同）→ 再 B

> **日期**：2026-08-29  
> **权威**：`experiments/aerial/RUNBOOK_indoor_0xm.md`（2026-08-29 Stick 主航道修订）  
> **铁律**：所有方案 Stick 主航道。室内 = 阶段 2 同一传感合同的尺度特化。

## 主航道（唯一）

```text
单目 RGB + IMU + 高度计 → \(\hat p\) → WAM → 到点
深度/罩 = 仅安全
```

## 停止 / 作废

- **停止**把未声明 `pose_source` 的跑数当作主航道基线。  
- **不要**开 H100 FT、不要单失败补洞、不要默认 `assist=gt_pd`。

## 阶段 A0（必做 · 阻塞）

1. `goal_rel` 必须由 \(\hat p,\hat\psi\) 接口计算；禁止默许 `obs.position` GT 却不声明。  
2. 报表字段：`pose_source`、`goal_rel_pose_source`、`controller_attribution`、`used_gt_world_pose_for_control`、`sensors_used`。  
3. 默认 `assist=none`；GT-PD 仅对照。  
4. 室内高度：优先 rangefinder 字段（仿真 stub 须在报表声明）。  
5. 更新 `docs/handover/INDOOR_0XM_STATUS.md`：A0 勾选。

## 阶段 B（A0 完成后）

主航道协议重跑 Route 07/10/13/14（或 prompt 原集合），产出：

`artifacts/indoor_mainline_baseline_20260829.json`

须含 `pose_source`；主航道臂不得静默 `gt_proxy`。数字差于夹具账 → 如实写。

## 汇报

A0 改动文件列表；B JSON 路径与四路由摘要；STATUS 摘录；阻塞。
