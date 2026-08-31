# Phase-2 全修 / 全签 STATUS（活页 · 2026-08-30）

> **Workspace**：Mac `aerial-wam-v2` → 125 `~/workspaces/aerial-wam-v2-phase2` + `~/aerial-wam-v2`  
> **AirSim**：`10.229.20.110:41451`（迁中，见 [`AIRSIM_MIGRATE_110_20260831.md`](AIRSIM_MIGRATE_110_20260831.md)）  
> **H100**：`a25689@10.239.121.26:31126`（经 125；`ssh h100-26`）

---

## 一句话

**主航道回锚**：默认 = AdaptiveSubgoal + **`step_e` + `goal_feat_mode=meter`**（零重训合同）。  
F9 `g_norm` / R1/R2 重训 = **ablation**。对照评测待 125 跑。

---

## 全签 / 分叉账

| 轮 | 内容 | 结果 |
|----|------|------|
| R1 | g_norm 重训 · w_coll=10 | **FAIL** SR=0% |
| R2 | w_coll=1 重训 | 想象 return↑；闭环 IR≈1 / prog≈0（评测收尾中） |
| **回锚** | **step_e + meter** · 不开训 | **FAIL 已出** — Prog=85.7% IR=17.7% SR=0 SCR=12.5%；[`DECLARE`](WAM_PHASE2_REANCHOR_STEPE_DECLARE_20260830.md) / `artifacts/wam_phase2_reanchor_stepe_result_20260830.json` |

---

## 航迹法医（2026-08-30）

16 路逐条 XY + CTE + fail tag 已跑完：[`WAM_PHASE2_REANCHOR_TRAJ_FORENSICS_20260830.md`](WAM_PHASE2_REANCHOR_TRAJ_FORENSICS_20260830.md)  
图集：`artifacts/videos/wam_phase2_reanchor_forensics_20260830/`

| tag | n |
|-----|---|
| `F_OFFTRACK` | **14** |
| `F_SCR` | **2**（R04/R16） |
| 到点 | **0** |

结论：主失败是**假 p_coll 紧急体轴 −x 回退**（前方开敞仍 latch），不是「差一点进 3m」。汇总 Prog 不能当完成度。

### 假 p_coll 紧急回退 — 已修（2026-08-30）

- **根因**：`ThreeZoneSpeedShield` 在 `p_coll>max` 时无条件 body −x emergency；侧向 clutter 可抬高 WM `p_coll`，而 `d_fwd` 仍 ≫ L1。
- **修法**：`safety.py` — 当 `d_fwd > L1`（`p_coll_clearance_veto_m`，默认=L1）时 **veto** `p_coll` 通道；前方近距仍 latch。
- **测**：`test_p_coll_emergency_vetoed_when_forward_clear` / `_latches_when_forward_near`（本地+125 绿）。
- **125 短探 R01×50**：`emerg_steps=0` · `along_disp=+7.64m`（修前同场景沿路负向/回退）。已 sync `safety.py`+`three_zone.py`。

下一刀：短评测确认 IR/Prog；若仍偏 CTE → CTE 门控单调锁 + 真实投影胡萝卜（零重训）。

## 评测纪律（永久）

**先看场景，再信汇总。** 每轮 16 路评测准出前必须：逐路扫标注几何 → 跑 `wam_phase2_traj_forensics`（XY+CTE+tag）→ 再读 SR/Prog。只贴 mean 指标开修 = 浪费时间（见 Runbook Step K 硬门）。

## 下一回合（125）— **Subgoal 真投影已修 · 待 Outdoor 复测**

**2026-08-31**：零重训修 `subgoal_generator`：
- CTE / 胡萝卜 ← **真正交投影**（`nearest_on_polyline`）
- CTE>`cte_lock_freeze_m`（默认 5 m）→ **回滚** `s_progress` 到真弧长（禁 Prog 虚涨）
- 单测 11 passed（含 freeze / true-CTE）

**下一步**：125 client → `10.229.20.110:41451` Outdoor 16 路法医复测（p_coll veto + 本修）。  
禁止 g_norm / Docking / 关罩；勿连 125 本机 Building_99。
