# Phase-3 Unified Navigation · STATUS

> **分支**：`project/phase3-unified`  
> **RUNBOOK**：[`RUNBOOK_phase3_unified.md`](RUNBOOK_phase3_unified.md)  
> **起点**：`phase2-pass-20260908`（Phase-2 outdoor close，SR 86.7%）

## 一句话

同一 WAM + π 覆盖户外长航程 + 室内 0.x m。**与 vgoal 无关。**

## 阶段

| 阶段 | 状态 | 说明 |
|------|------|------|
| **P0** 骨架 + 接线 | 🟡 in progress | branch、scene_profile、混采脚本、双门 eval shell |
| **P1** 混采语料 | ⬜ | 签字后 125 采集 |
| **P2** 融合 FT | ⬜ | 签字后 H100 |
| **P3** 双门验收 | ⬜ | 同一 ckpt outdoor + indoor |

## P0 checklist

- [x] `project/phase3-unified` from `phase2-pass-20260908`
- [x] `configs/aerial_rl_phase3_unified.yaml`
- [x] `experiments/aerial/rl/scene_profile.py` + collector 接线
- [x] `build_phase3_mixed_annotation.py`
- [x] `eval_phase3_unified.sh`
- [ ] Indoor 阶段 C 签字
- [ ] 混采 7:3 签字
- [ ] `train_v4_ac --config` 读 phase3 yaml（当前仍默认 aerial_rl.yaml）

## 阻塞

1. Indoor `odom_from_imu_rgb` 仍为积分 stub（阶段 B 0/4 @ 0.2m）
2. Indoor 阶段 C 未签字 → H100 FT 禁止
3. `train_v4_ac` 尚未接受 `--config configs/aerial_rl_phase3_unified.yaml` 作为默认

## 与 phase2-vgoal 关系

并行、不合并。vgoal / Orin / 红车旁线留在 `project/phase2-vgoal`。
