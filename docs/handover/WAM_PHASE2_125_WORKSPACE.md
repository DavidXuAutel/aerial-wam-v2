# Phase-2 125 Agent：独立 Workspace（与 Indoor 隔离）

> **日期**：2026-08-29  
> **目的**：Phase-2 主航道 agent 与 Indoor agent **不得共用**同一个 Cursor `--workspace`。

## 约定

| 战役 | Agent `--workspace` | 运行时评测/AirSim 目录 |
|------|---------------------|------------------------|
| **Phase-2 长程 WAM** | `/home/yao/workspaces/aerial-wam-v2-phase2` | 评测进程仍可在 `/home/yao/aerial-wam-v2`（共享 ckpt/AirSim）；agent 读写本 worktree |
| **Indoor 0.x m** | `/home/yao/aerial-indoor-wam`（或既有 indoor 树） | **禁止**再对 `~/aerial-wam-v2` 开 indoor agent |

## 一次性建树（125）

```bash
mkdir -p ~/workspaces
cd ~/aerial-wam-v2
git worktree add ~/workspaces/aerial-wam-v2-phase2 HEAD
# 共享运行产物（评测日志 / 结果 / 长路由标注）
ln -sfn ~/aerial-wam-v2/artifacts ~/workspaces/aerial-wam-v2-phase2/artifacts
ln -sfn ~/aerial-wam-v2/experiments/aerial/rl/artifacts \
  ~/workspaces/aerial-wam-v2-phase2/experiments/aerial/rl/artifacts
```

## 启动 Phase-2 agent（勿占 aerial-wam-v2 根）

```bash
export PATH="$HOME/.local/bin:$PATH"
cd ~/workspaces/aerial-wam-v2-phase2
# 若旧 phase2 agent 误绑 ~/aerial-wam-v2：先杀该 agent PID，勿杀评测 PID
nohup agent --trust --force \
  --workspace /home/yao/workspaces/aerial-wam-v2-phase2 \
  --model composer-2.5-fast --print \
  "$(cat docs/handover/WAM_PHASE2_MAINLINE_125_PROMPT.md)" \
  > artifacts/wam_phase2_125_agent.log 2>&1 &
```

Indoor agent 必须 `--workspace` 指向 indoor 仓，不得与上表 Phase-2 路径相同。
