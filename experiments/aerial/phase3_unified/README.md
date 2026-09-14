# Phase-3 · Unified Outdoor + Indoor Navigation

> **分支**：`project/phase3-unified`（起自 tag `phase2-pass-20260908`）  
> **入口 RUNBOOK**：[`docs/handover/RUNBOOK_phase3_unified.md`](../../../docs/handover/RUNBOOK_phase3_unified.md)  
> **活页**：[`docs/handover/WAM_PHASE3_UNIFIED_STATUS.md`](../../../docs/handover/WAM_PHASE3_UNIFIED_STATUS.md)

## 一句话

**同一 WAM + π**，训练分布同时覆盖户外长航程（米级到达）与室内小空间（0.x m 到达 + 微尺度动作盒）。  
**不含** vgoal / YOLO / 视觉目标跟踪 — 那是 `project/phase2-vgoal` 旁线。

## 与相邻 project 的分工

| Project | 范围 |
|---------|------|
| **Phase-2 close** (`phase2-pass-20260908`) | 户外几何导航 closed |
| **`project/phase2-vgoal`** | 户外 + 视觉目标（vgoal） |
| **`project/phase3-unified`（本 project）** | 户外 + 室内 **融合导航** |

## 目录

```
experiments/aerial/phase3_unified/
├── README.md           # 本文
├── mixed_corpus.py     # 混采 annotation 构建
└── notes/              # 实验一页记录（按需）

experiments/aerial/rl/scene_profile.py   # 按 episode.scene 切 profile（collector 已接线）

configs/aerial_rl_phase3_unified.yaml

experiments/aerial/scripts/
├── build_phase3_mixed_annotation.py
└── eval_phase3_unified.sh
```

## 工作区

**当前主 project**：`project/phase3-unified`（起自 `phase2-pass`，不含 vgoal）。

```bash
git checkout project/phase3-unified
```

## 快速开始

```bash
# 混采语料（已生成：16 outdoor + 4 indoor）
python -m experiments.aerial.scripts.build_phase3_mixed_annotation \
  --out experiments/aerial/phase3_unified/annotations/mixed_seen.json

# P1 采集（125 · AirSim；Mac 经 `ssh cursor-125-public`）
ssh cursor-125-public 'cd ~/aerial-wam-v2 && bash experiments/aerial/scripts/collect_phase3_unified.sh'

# 训练入口（P2 签字后）
python -m experiments.aerial.rl.train_v4_ac \
  --config configs/aerial_rl_phase3_unified.yaml \
  --backend airsim --dynamics torch --phase2 \
  --init-actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_phase2_toward_g_20260905_112006/v4_ac_latest.pt

# 双门验收
bash experiments/aerial/scripts/eval_phase3_unified.sh <actor_ckpt>
```

## 进入训练前必满足

- [ ] Indoor 阶段 C 签字（见 `RUNBOOK_indoor_0xm.md` §6）
- [ ] 混采比例 7:3 签字
- [ ] `pose_source` / VIO stub 升级计划签字

未满足 → 只做语料/接线/双门 eval 脚手架，不启动 H100 FT。
