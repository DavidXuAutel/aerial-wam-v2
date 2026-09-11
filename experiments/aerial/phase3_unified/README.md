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

## 快速开始（P0 骨架）

```bash
git checkout project/phase3-unified

# 生成混采语料（7:3 outdoor:indoor）
python -m experiments.aerial.scripts.build_phase3_mixed_annotation \
  --out artifacts/phase3_unified_mixed_seen.json

# 双门验收（签字后，同一 ckpt）
bash experiments/aerial/scripts/eval_phase3_unified.sh <actor_ckpt>
```

## 进入训练前必满足

- [ ] Indoor 阶段 C 签字（见 `RUNBOOK_indoor_0xm.md` §6）
- [ ] 混采比例 7:3 签字
- [ ] `pose_source` / VIO stub 升级计划签字

未满足 → 只做语料/接线/双门 eval 脚手架，不启动 H100 FT。
