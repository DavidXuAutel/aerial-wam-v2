# 125 Agent：Phase-2 回锚对照（`step_e` + 米制 goal · 不开训）

> **日期**：2026-08-30  
> **强制 workspace**：`/home/yao/workspaces/aerial-wam-v2-phase2`  
> **Indoor**：禁止动  
> **声明**：[`WAM_PHASE2_REANCHOR_STEPE_DECLARE_20260830.md`](WAM_PHASE2_REANCHOR_STEPE_DECLARE_20260830.md)  
> **禁止**：H100 重训、Docking、关罩、escape、放宽到达、用 R1/R2 g_norm ckpt 冒充回锚

---

## 目标

按规格原意跑一轮诚实主航道对照：

**AdaptiveSubgoal → `step_e` π（`goal_feat_mode=meter`）→ Planner → ThreeZone**

验证：在 **不换基线权** 时，Phase-2 长廊能否恢复可用能力；结果与 R1/R2 对照写入 DECLARE。

---

## 0. 同步代码（Mac 已改）

至少拉取 / 覆盖：

* `experiments/aerial/rl/actor_critic.py`（`goal_feat_mode`）  
* `experiments/aerial/scripts/wam_phase2_long_eval.py`（`--goal-feat-mode`）  
* `experiments/aerial/rl/tests/test_phase2_p0_f9_f10.py`  
* 本 prompt + `WAM_PHASE2_REANCHOR_STEPE_DECLARE_20260830.md`  
* 活页 `WAM_PHASE2_STATUS_20260829.md` / phase2 runbook §7  

同步到：`~/workspaces/aerial-wam-v2-phase2` **与** `~/aerial-wam-v2`（评测跑主树）。

### R2 评测若仍在跑

**勿杀**；让其写完 JSON 即可（作负对照）。回锚评测等 GPU/AirSim 空闲再开，或 R2 结束后立刻开。

---

## 1. 单测

```bash
cd ~/aerial-wam-v2
source experiments/aerial/scripts/env_4090.sh
pytest experiments/aerial/rl/tests/test_phase2_p0_f9_f10.py \
  experiments/aerial/rl/tests/test_actor_goal_cond.py \
  experiments/aerial/rl/tests/test_subgoal_generator.py -q
```

确认：`test_feat_tensor_meter_mode_keeps_raw_metres` 绿。

---

## 2. 确认 ckpt / 模式

```bash
ls -lh experiments/aerial/rl/artifacts/v4_ac_ckpt_step_e_20260828/v4_ac_latest.pt
$PYTHON_BIN - <<'PY'
import torch
from experiments.aerial.rl.actor_critic import LatentActorCritic
ac = LatentActorCritic.load_from_checkpoint(
    "experiments/aerial/rl/artifacts/v4_ac_ckpt_step_e_20260828/v4_ac_latest.pt",
    device="cpu",
)
print("condition_on_goal", ac.config.condition_on_goal)
print("goal_feat_mode(default load)", ac.config.goal_feat_mode)
assert ac.config.condition_on_goal is True
assert ac.config.goal_feat_mode == "meter"
PY
```

---

## 3. 16 路回锚评测

```bash
cd ~/aerial-wam-v2
source experiments/aerial/scripts/env_4090.sh
# AirSim :41451 就绪；无冲突 long_eval
nohup $PYTHON_BIN experiments/aerial/scripts/wam_phase2_long_eval.py \
  --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt \
  --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_step_e_20260828/v4_ac_latest.pt \
  --goal-feat-mode meter \
  --annotation artifacts/seen_airsim16_long_routes.json \
  --cruise-speed 10.0 \
  --planner --planner-horizon 5 \
  --max-steps 1000 \
  --out artifacts/wam_phase2_reanchor_stepe_result_20260830.json \
  > artifacts/wam_phase2_reanchor_stepe_20260830.log 2>&1 &
echo EVAL_PID=$!
```

日志须含：`goal_feat_mode=meter`。

---

## 4. 写评完 DECLARE

路径（WT + 主树副本）：

`docs/handover/WAM_PHASE2_REANCHOR_STEPE_DECLARE_20260830.md`

（可在跑前声明文末追加 §「评测结果」）至少含：

| 项 | 要求 |
|----|------|
| 协议 | step_e · meter · cruise=10 · planner H=5 |
| 指标 | SR/SCR/SPL/ρ̄/IR vs 门限 |
| 对照 | vs R1（g_norm 重训 FAIL）与 R2（若已有 JSON） |
| 失败条 | F1–F14 |
| 下一刀 | 一句；**禁止**默认建议「再开 g_norm 重训」除非对照证明 meter+step_e 已到顶且缺口在特征尺度 |

同步 `WAM_PHASE2_STATUS_20260829.md`「下一步」。

---

## 5. 完成回复

- goal_feat_mode 确认 meter + step_e 路径  
- 16 路指标 + verdict  
- vs R1/R2 一句  
- DECLARE 路径  

---

## 停止条件

- 无 `step_e` ckpt / 单测红 → 停，写 blocker  
- 误用 `phase2_gnorm*` ckpt → 作废重跑  
- 评测崩 → 修接线重跑，勿改门限
