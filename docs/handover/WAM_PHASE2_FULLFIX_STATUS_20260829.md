# Phase-2 全修 STATUS（Mac → 125 · 2026-08-29）

> **已 supersede**：活页见 [`WAM_PHASE2_STATUS_20260829.md`](WAM_PHASE2_STATUS_20260829.md)（含全签 R1/R2）。  
> **Workspace**：本地 `aerial-wam-v2`；同步目标 `~/workspaces/aerial-wam-v2-phase2` + `~/aerial-wam-v2`  
> **范围**：审查所列缺陷尽量一次修完（代码层）；actor 重训见全签 R1/R2

---

## 结论

| 缺陷 | 状态 |
|------|------|
| P0 F9 `g_norm` | ✅（自 125 合入） |
| P0 F10 流式 \(z\) | ✅ |
| F5 depth `predict_min` 接线 | ✅ |
| Deploy 读 `obs.info["goal"]` | ✅ |
| F12 终末蠕行 `v_safe(rem)` | ✅ `terminal_creep_rem_m=8` |
| 单调锁 `seg_idx` 重算 | ✅ |
| Planner/actor 限速对齐 `body_delta_limits` | ✅ |
| Eval cones + `wm_out.p_coll` 进罩 | ✅ |
| 去掉 eval 软 `z_err` | ✅ |
| F1 spawn 检测 / z+2 重试 / skip 不计 SCR | ✅ |
| Escape SM 主航道默认关 | ✅ `enable_sustained_escape=False`, `escape_hold_steps=0` |
| Collector Docking | ✅ 125 树已无；cones + ep_info 拷贝恢复 |
| **Actor goal-cond 重训** | ✅ R1 已做 → **FAIL**；**R2** `--w-collision 1.0` 训完、16 路评测中 — [`WAM_PHASE2_STATUS_20260829.md`](WAM_PHASE2_STATUS_20260829.md) |

---

## 单测（Mac）

```bash
python3 -m pytest experiments/aerial/rl/tests/test_subgoal_generator.py \
  experiments/aerial/rl/tests/test_phase2_p0_f9_f10.py \
  experiments/aerial/rl/tests/test_wam_phase2_depth_wiring.py \
  experiments/aerial/rl/tests/test_goal_features.py \
  experiments/aerial/rl/tests/test_three_zone_shield.py \
  experiments/aerial/rl/tests/test_collector_depth_shield.py -q
# 29 passed, 1 skipped（三线动态后 shield 单测已扩）
```

---

## 下一回合（125）

见活页 [`WAM_PHASE2_STATUS_20260829.md`](WAM_PHASE2_STATUS_20260829.md)：等 R2 16 路 → `WAM_PHASE2_SIGNOFF_R2_DECLARE`；禁静默改 yaml `w_collision`。
