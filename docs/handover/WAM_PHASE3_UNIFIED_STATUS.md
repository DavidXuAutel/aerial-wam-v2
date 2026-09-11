# Phase-3 Unified Navigation · STATUS

> **分支**：`project/phase3-unified`（**当前工作区**）  
> **RUNBOOK**：[`RUNBOOK_phase3_unified.md`](RUNBOOK_phase3_unified.md)  
> **起点**：`phase2-pass-20260908`（Phase-2 outdoor close，SR 86.7%）

## 一句话

同一 WAM + π 覆盖户外长航程 + 室内 0.x m。**与 vgoal 无关。**

## 阶段

| 阶段 | 状态 | 说明 |
|------|------|------|
| **P0** 骨架 + 接线 | ✅ | branch、scene_profile、config、双门 eval |
| **P1** 混采语料 + 采集接线 | ✅ | 20 eps（16 outdoor + 4 indoor），collector 按 scene 切 profile |
| **P2** 融合 FT | ⬜ | 签字后 H100 |
| **P3** 双门验收 | ⬜ | 同一 ckpt outdoor + indoor |

## P1 产物

| 文件 | 内容 |
|------|------|
| `experiments/aerial/phase3_unified/annotations/mixed_seen.json` | 混采 annotation（`scene` + `pose_source`） |
| `configs/aerial_rl_phase3_unified.yaml` | 默认指向混采语料 + `scene_profiles` |
| `experiments/aerial/scripts/collect_phase3_unified.sh` | 125 混采采集入口 |

场景分布：**16 × `outdoor_long` + 4 × `indoor_micro`**（seen pool；FT 目标混采 7:3）。

## 125 采集（P1）

```bash
git checkout project/phase3-unified
bash experiments/aerial/scripts/collect_phase3_unified.sh
```

## 阻塞（P2 前）

1. Indoor 阶段 C 签字
2. `odom_from_imu_rgb` VIO stub 升级（eval 诚实基线）
3. H100 融合 FT 签字

## 与 phase2-vgoal 关系

并行、不合并。vgoal / Orin 留在 `project/phase2-vgoal`（HJ 相机 WIP 在 stash）。
