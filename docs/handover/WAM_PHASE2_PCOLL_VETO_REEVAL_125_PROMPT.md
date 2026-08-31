# 125 Agent：p_coll veto 修后 · 16 路跟折线复评 + 法医

> **日期**：2026-08-30  
> **强制 workspace**：`/home/yao/workspaces/aerial-wam-v2-phase2`  
> **评测主树**：`/home/yao/aerial-wam-v2`（AirSim / ckpt）  
> **Indoor**：禁止动  
> **活页**：[`WAM_PHASE2_STATUS_20260829.md`](WAM_PHASE2_STATUS_20260829.md)  
> **禁止**：H100 重训、g_norm、Docking、关罩、escape、放宽到达、只报 mean Prog 当结论

---

## 目标（唯一问题）

假 `p_coll` 紧急回退已修（`d_fwd > L1` veto）。**飞迹是否贴合法折线？**

交付顺序硬门：

1. **先**逐路表（tag / maxCTE / earlyCTE / prog / d_min）+ XY 图  
2. **再**汇总 SR/Prog/IR  
3. 一句结论：跟折线是否好转；若否 → 下一刀指向 Subgoal 真投影/冻结单调锁（**零重训**）

对照基线：[`WAM_PHASE2_REANCHOR_TRAJ_FORENSICS_20260830.md`](WAM_PHASE2_REANCHOR_TRAJ_FORENSICS_20260830.md)（修前 14×`F_OFFTRACK` / 2×`F_SCR`）。

---

## 0. 同步（Mac → 125 两棵树）

覆盖到 **主树** `~/aerial-wam-v2` **与** worktree `~/workspaces/aerial-wam-v2-phase2`：

| 文件 | 为何 |
|------|------|
| `experiments/aerial/rl/safety.py` | p_coll clearance veto |
| `experiments/aerial/rl/three_zone.py` | `engage_outer_for_speed` 等依赖 |
| `experiments/aerial/rl/tests/test_three_zone_shield.py` | veto 单测 |
| `experiments/aerial/scripts/wam_phase2_traj_forensics.py` | 法医 |
| `experiments/aerial/scripts/wam_phase2_long_eval.py` | 可选汇总 |
| 本 prompt + STATUS + phase2 runbook §7 / Step K |

可用 `scp`/`cat>`；勿 `git reset --hard`。

确认主树含 veto：

```bash
grep -n p_coll_clearance_veto ~/aerial-wam-v2/experiments/aerial/rl/safety.py | head
```

---

## 1. 单测 + AirSim

```bash
cd ~/aerial-wam-v2
source experiments/aerial/scripts/env_4090.sh
$PYTHON_BIN -m pytest experiments/aerial/rl/tests/test_three_zone_shield.py::test_p_coll_emergency_vetoed_when_forward_clear \
  experiments/aerial/rl/tests/test_three_zone_shield.py::test_p__coll_emergency_latches_when_forward_near -q --tb=line
```

（第二测名以文件为准：`test_p_coll_emergency_latches_when_forward_near`。）

AirSim `:41451`：若无客户端可连，跑 `~/aerial_airsim_persistent/recover_renderer.sh`。  
**勿杀**无关 Indoor / 正在下的 Blocks curl（除非占死 41451）。  
**勿并行**第二个 long_eval/forensics。

---

## 2. 主任务：16 路法医（够用，不必再跑一遍 long_eval）

同栈：`step_e` + `meter` + Subgoal + planner H=5 + ThreeZone · cruise=10。

```bash
cd ~/aerial-wam-v2
source experiments/aerial/scripts/env_4090.sh
OUT=artifacts/videos/wam_phase2_pcoll_veto_forensics_20260830
nohup $PYTHON_BIN experiments/aerial/scripts/wam_phase2_traj_forensics.py \
  --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt \
  --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_step_e_20260828/v4_ac_latest.pt \
  --goal-feat-mode meter \
  --annotation artifacts/seen_airsim16_long_routes.json \
  --cruise-speed 10.0 \
  --planner-horizon 5 \
  --max-steps 1000 \
  --out-dir "$OUT" \
  > artifacts/wam_phase2_pcoll_veto_forensics_20260830.log 2>&1 &
echo FORENSICS_PID=$!
```

等跑完。产物：`$OUT/forensics_summary.json`、`$OUT/R##_traj_xy.png`、`$OUT/forensics_report.md`（若脚本写出）。

从 summary 自算：`SR = mean(arrived)`、`mean_prog`、`mean_IR`、`SCR`、各 `fail_tag` 计数。  
**可选**：另跑 `wam_phase2_long_eval.py` → `artifacts/wam_phase2_pcoll_veto_result_20260830.json`（仅当 GPU/AirSim 空且需要官方 JSON；否则 forensics 足够）。

---

## 3. 写 DECLARE + 更新 STATUS

新建：`docs/handover/WAM_PHASE2_PCOLL_VETO_FORENSICS_DECLARE_20260830.md`

必须含：

| 节 | 内容 |
|----|------|
| 协议 | step_e · meter · cruise=10 · planner H=5 · **p_coll veto on** |
| **逐路表** | R01–R16：tag / prog / d_min / maxCTE / earlyCTE / IR（**放在汇总前面**） |
| vs 修前 | OFFTRACK/SCR 计数对比；earlyCTE/maxCTE 是否下降 |
| 汇总 | SR/SCR/Prog/IR（附表） |
| 结论 | 跟折线是否改善；若否 → Subgoal 真投影 + CTE 冻结单调锁（零重训） |
| 禁止句 | 不得建议默认 g_norm 重训 |

同步活页 `WAM_PHASE2_STATUS_20260829.md`「下一回合」。两棵树都写。

---

## 4. 完成回复（给用户）

1. 逐路 tag 表（可压缩）  
2. vs 修前：OFFTRACK 数量 / 典型 maxCTE  
3. 一句：是否跟得上折线  
4. 下一刀一句（仅当仍离线）  
5. 产物路径

---

## 偏离即停

* 只贴 mean Prog/SR、无逐路  
* 换 ckpt / 关罩 / Docking  
* 未确认 `p_coll_clearance_veto` 已在主树就开飞  
* Indoor workspace  
