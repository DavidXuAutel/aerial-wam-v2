# 125 Agent：Phase-2 主航道下一步（P0 F9/F10 + F5 诊断）

> **日期**：2026-08-29  
> **强制 workspace**：`/home/yao/workspaces/aerial-wam-v2-phase2`（与 Indoor `/home/yao/aerial-indoor-wam` **隔离**）  
> **前置**：`WAM_PHASE2_MAINLINE_EVAL_STATUS_20260829.md` — Verdict **FAIL**（SR/SCR 43.8%）  
> **入口**：`experiments/aerial/RUNBOOK_wam_phase2_long_horizon.md` §7  
> **禁止**：Docking / 往返 / 关罩 / 放宽到达 / 改 safety deploy 阈值凑分 / 碰 Franka / 直连 H100 / 动 indoor 仓 / Step M

---

## 目标（本回合只做这些）

按主航道 **先清 P0 代码债**，再做 **F5/F14 只读诊断**（解释 IR≡0 仍 SCR 高）。  
**不**本回合开全量 16 路重评（P0+诊断完成并单测过后再另开评测回合）。

### A. F9 — Actor/Critic `goal_rel` 归一化（P0）

* **现状**：`LatentActorCritic._feat_tensor` 仍 `concat(z, raw metres)`。  
* **动作**：与 `goal_features.reward_aux_features` 对齐的 `g_norm`：  
  \(\mathbf{g}_{norm}=[\hat u_{xyz},\;\log(1+\|g\|)]\)（或仓内已有等价 helper，复用勿另起炉灶）。  
* **训练/部署同一套**；旧 ckpt：加载后行为可能变 — 在 STATUS 写明「需否重训才能宣称 SR 改善」。  
* **单测**：`experiments/aerial/rl/tests/` 增补/扩展，断言 feat 量级稳定（米制 20–55 不冲垮）。

### B. F10 — Planner 使用流式 \(z\)（P0）

* **现状**：`ImaginationPlanner.plan` 内 `dynamics.encode(obs)` 失忆；部署 `observe_and_advance`。  
* **动作**：`plan(obs, base_action, *, latent=...)` 或从 deploy policy 注入当前 \(z\)；**禁止**评分路径单独 encode 重置 GRU。  
* 接好 `wam_phase2_long_eval.py` / deploy 调用链。  
* **单测**：同 obs 连续两步，planner 所用 \(z\) 与 policy 流式 \(z\) 一致（或文档化同一接口）。

### C. F5/F14 — IR≡0 仍硬撞（诊断，本回合以证据为主）

* 读 `artifacts/wam_phase2_accept_result.json` + 日志；抽 1–2 条 SCR episode。  
* 查：`depth_min_pred` 是否写入、`safety.kind`、罩是否 `apply_action`、为何未 intervene。  
* **若是明显接线 bug**（depth 没进 obs / shield 未挂）：**允许最小修复**并单测。  
* **若是阈值/深度质量**：只写诊断进 STATUS，**不要**本回合大改 `safety.py` 阈值刷 IR。

### D. 明确不做

* F1 spawn 全修、F12 终末蠕行大改、全量 16 路重跑、Method B/YOLO、indoor、H100 长训（除非单测证明必须且经 STATUS 声明「下一回合」）。

---

## 准出

1. `pytest` 覆盖 F9/F10 相关单测 **全绿**（在 125 上跑，CPU 即可）。  
2. 短文 STATUS：`docs/handover/WAM_PHASE2_P0_F9F10_STATUS_20260829.md`  
   - 改了哪些文件  
   - 单测命令与结果  
   - F5 诊断结论（接线 bug vs 深度/阈值）  
   - **下一回合建议**（是否可开 mainline 重评 / 是否需 actor 重训）  
3. 代码落在 **phase2 worktree**；需要同步主树时 `cp`/`rsync` 到 `~/aerial-wam-v2` 同路径，并在 STATUS 写明。

---

## 启动检查

```bash
cd /home/yao/workspaces/aerial-wam-v2-phase2
pwd  # 必须是 phase2 worktree
# 禁止 cd ~/aerial-indoor-wam 干活
```
