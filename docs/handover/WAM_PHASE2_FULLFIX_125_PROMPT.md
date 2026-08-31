# 125 Agent：Phase-2 全修同步 + 单测 + SCR smoke

> **强制 workspace**：`/home/yao/workspaces/aerial-wam-v2-phase2`  
> **禁止**：动 indoor 仓、Docking、往返、关罩、开 escape、H100 直连、全量 16 路（本回合仅 smoke）

## 任务

1. 确认下列文件已与 Mac 全修对齐（若 `/tmp/phase2_fullfix.tgz` 已解压则跳过）：  
   `subgoal_generator.py`, `safety.py`, `collector.py`, `wam_phase2_long_eval.py`, 相关 tests, STATUS。  
2. 同步同路径到 `~/aerial-wam-v2`。  
3. 跑：
   ```bash
   cd /home/yao/workspaces/aerial-wam-v2-phase2
   python -m pytest experiments/aerial/rl/tests/ -q --tb=line
   ```
4. 若 AirSim 空闲：smoke **最多 3 条**原 SCR 路由（annotation 里 route 对应 base 曾 SCR 的），确认日志出现非零 IR 或 depth_min_pred；**不要**全 16 路。  
5. 更新/确认 `docs/handover/WAM_PHASE2_FULLFIX_STATUS_20260829.md` 写上 125 单测结果与 smoke 数字。  
6. 明确写下：**actor 重训未做**，下一战役经 125→H100。
