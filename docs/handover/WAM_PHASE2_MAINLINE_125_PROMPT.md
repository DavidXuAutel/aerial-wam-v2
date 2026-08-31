# 125 Agent：Phase-2 诚实主航道评测（立即执行）

> **日期**：2026-08-29  
> **机器**：cursor-125 only（4090 / AirSim）  
> **Agent workspace（强制）**：`/home/yao/workspaces/aerial-wam-v2-phase2`（与 Indoor **隔离**；见 [`WAM_PHASE2_125_WORKSPACE.md`](WAM_PHASE2_125_WORKSPACE.md)）  
> **入口**：[`experiments/aerial/RUNBOOK_wam_phase2_long_horizon.md`](../../experiments/aerial/RUNBOOK_wam_phase2_long_horizon.md)  
> **禁止**：往返/bridge 刷分、Docking、关罩、放宽到达、改 safety deploy、碰 Franka / H100 直连；**禁止**占用 `~/aerial-wam-v2` 作为 Cursor workspace（留给评测进程 / 勿与 indoor 抢）

---

## 目标

按 **当前诚实主航道**（合法原生折线 + AdaptiveSubgoal + 阶段 1 WAM + ThreeZone）跑完 `mainline_native` 闭环评测，产出 JSON，并按 F1–F14 归类失败。

**不做**：修 F9/F10 代码债、开 Method B/YOLO、跨区 200–500 m Step M（除非本评测已过门且用户另令）。

**若评测已在跑**（常见 PID + `artifacts/eval_phase2_long.log`）：**禁止杀进程重开**；监控至写出 `artifacts/wam_phase2_accept_result.json` 后做 Step L。

---

## 步骤（按序）

### 0. 环境

```bash
cd ~/aerial-wam-v2
source experiments/aerial/scripts/env_4090.sh
# 确认无残留长评测
pgrep -af 'wam_phase2_long_eval|AirSim' || true
```

若 AirSim 未起：按本机既有 `RUNBOOK` / `env_4090` 惯例拉起后再评；不要在 Mac 侧猜命令。

### 1. 单测（准出才继续）

```bash
pytest experiments/aerial/rl/tests/test_subgoal_generator.py -v
```

### 2. 再生原生基准

```bash
python experiments/aerial/scripts/generate_long_routes.py
python -c "import json; d=json.load(open('artifacts/seen_airsim16_long_routes.json')); print(d['version'], d['n_routes']); assert 'mainline_native' in d['version']"
```

### 3. 主航道闭环（强制 planner + 默认 three_zone 栈）

```bash
mkdir -p artifacts
nohup python experiments/aerial/scripts/wam_phase2_long_eval.py \
  --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt \
  --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_step_e_20260828/v4_ac_latest.pt \
  --annotation artifacts/seen_airsim16_long_routes.json \
  --cruise-speed 10.0 \
  --planner --planner-horizon 5 \
  --max-steps 1000 \
  --out artifacts/wam_phase2_accept_result.json \
  > artifacts/wam_phase2_accept.log 2>&1 &
echo "PID=$!"
```

确认：`wam_phase2_long_eval.py` 主栈为 Subgoal → π → Planner → Shield；**无** Docking / escape / roundtrip。

### 4. 监控至结束

```bash
tail -f artifacts/wam_phase2_accept.log
# 结束后：
python -c "import json; r=json.load(open('artifacts/wam_phase2_accept_result.json')); print({k:r.get(k) for k in r if k in ('sr','arrival_rate','scr','severe_collision_rate','spl','mean_progress','ir','intervention_rate','n_episodes') or True}); print('keys', sorted(r.keys())[:40])"
```

### 5. 报告（写回短 STATUS 即可）

在 `docs/handover/` 或 `artifacts/` 写一页：

* SR / SCR / SPL / mean_progress / IR  
* 对照门限：SR≥80%, SCR≤10%, SPL≥70%, ρ̄≥90%, IR≤25%  
* 每条失败标 **F1–F14** 之一  
* 禁止用「再加启发式」关失败  

完成后把 JSON 路径与关键数字贴在回复里。

---

## 偏离即停

见 Phase-2 runbook §6。尤其禁止：往返、Docking、关罩、假到达、把结果写成视觉认目标。
