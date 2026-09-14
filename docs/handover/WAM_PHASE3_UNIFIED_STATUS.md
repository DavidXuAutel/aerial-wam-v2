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
| **P1** 混采语料 + 采集接线 | ✅ | **44/44 ep**（28 handover + 16 outdoor_long，0 skip） |
| **P2** 融合 FT | 🔴 | P2a–P2d FAIL；**P2e FAIL**（0/8 中止）；统一 replay FT **结案** |
| **P3** decouple | 🟡 | Router + dual-ckpt eval 已接线；P3-indoor v0 训完（200 iter） |
| **P3** 双门验收 | 🟡 | **decouple approach 11/14**（Phase-2 协议）；**indoor 0/8**（P3-indoor v0）；outdoor long 门仍用 Phase-2 单独跑 |

## P1 产物

| 文件 | 内容 |
|------|------|
| `experiments/aerial/phase3_unified/annotations/handover_seen_filtered.json` | **14 对**有效 handover（spawn 过滤后） |
| `experiments/aerial/phase3_unified/annotations/spawn_probe_report.json` | 125 spawn 探测（14/15 outdoor + 14/15 indoor OK） |
| `experiments/aerial/phase3_unified/annotations/building99_indoor_short_routes.json` | Building_99 真室内 8 条 |
| `experiments/aerial/scripts/collect_phase3_handover.py` | 按 `map_id` 切 renderer 采集 |
| `configs/aerial_rl_phase3_unified.yaml` | 默认指向混采语料 + `scene_profiles` |
| `experiments/aerial/scripts/collect_phase3_unified.sh` | 125 混采采集入口 |

场景分布：**16 × `outdoor_long` + 4 × `indoor_micro`**（seen pool；FT 目标混采 7:3）。

## 125 采集（P1）

连接：**`ssh cursor-125-public`**（不用内网 `cursor-125`）。

```bash
ssh cursor-125-public 'cd ~/aerial-wam-v2 && git checkout project/phase3-unified && \
  source ~/sim_verify/.venv/bin/activate && \
  python3 -m experiments.aerial.scripts.collect_phase3_handover \
    --handover-only --spawn-retries 3 \
    --annotation experiments/aerial/phase3_unified/annotations/handover_seen_filtered.json \
    --scene-script ~/aerial-indoor-wam/experiments/aerial/scripts/recover_renderer_scene.sh \
    --out experiments/aerial/rl/artifacts/dataset_phase3_handover_seen'
```

## P3 decouple 验收（2026-09-14）

| 门 | 结果 | 协议 / ckpt |
|----|------|-------------|
| Outdoor approach | **11/14（78.6%）** | Phase-2 toward_g+planner+shield；裸 actor 对照 0/14 |
| Indoor B99 | **0/8** | P3-indoor `v4_ac_ckpt_phase3_indoor_20260914` |
| Outdoor long 不退化 | 待签字 | 仅跑 Phase-2 ckpt 回归门 |

产物：`artifacts/phase3_unified_eval_decouple_20260914_p2protocol/`

## 阻塞（P3-indoor 迭代）

1. Indoor 0/8 — 需更多数据 / iter / pose 协议对齐
2. `odom_from_imu_rgb` VIO stub（eval 诚实基线，可选）
3. 统一 replay FT **已结案** — 勿再试 P2a–P2e

## 与 phase2-vgoal 关系

并行、不合并。vgoal / Orin 留在 `project/phase2-vgoal`（HJ 相机 WIP 在 stash）。
