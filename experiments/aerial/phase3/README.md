# Phase-3 · Unified Outdoor + Indoor（骨架）

> **状态**：骨架期（branch `phase3/unified-outdoor-indoor`，起自 `phase2-pass-20260908`）。
> **入口 RUNBOOK**：[`docs/handover/RUNBOOK_wam_phase3_unified.md`](../../../docs/handover/RUNBOOK_wam_phase3_unified.md)
> **父航道**：[`RUNBOOK_wam_phase2_long_horizon.md`](../RUNBOOK_wam_phase2_long_horizon.md) + [`RUNBOOK_indoor_0xm.md`](../RUNBOOK_indoor_0xm.md)

## 一句话

**同一主航道 × 同一大脑（WAM + π） × 训练分布同时覆盖两种尺度**：
户外长航程（合法折线 + 局部胡萝卜，`success_dist` 米级）与
室内小空间（0.x m 到达 + 微尺度动作限位 + 传感合同 pose_source）。
一次 FT 覆盖二者，避免"室内/室外双 ckpt"分叉。

## 目录

```
experiments/aerial/phase3/
├── __init__.py
├── README.md              # 本文
├── configs/               # 可选：Phase-3 特化实验配置（若与主 configs/ 有交叉，主 configs/ 为准）
├── scripts/               # 混合训练/评测入口（待建）
└── notes/                 # 变更/实验记录（待建）
```

主配置：[`configs/aerial_rl_phase3_unified.yaml`](../../../configs/aerial_rl_phase3_unified.yaml)（融合骨架）。

## 进入准则

启动 Phase-3 训练前必须先满足：

- [ ] Indoor 阶段 C 签字（H100 FT 许可）——见 [`RUNBOOK_indoor_0xm.md`](../RUNBOOK_indoor_0xm.md) §6
- [ ] Phase-2 close 成果冻结（`phase2-pass-20260908`，SR=86.7% SCR=6.7%）
- [ ] 传感合同对齐：`pose_source` 必填；`assist=none` 默认；禁 GT `goal_rel`
- [ ] 混合分布采样比例、双 action-limit profile 切换机制签字

未满足 → 只做骨架/文档，不启动训练。
