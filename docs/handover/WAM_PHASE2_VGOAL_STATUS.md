# Phase-2 + vgoal · 活页 STATUS

> **分支**：`project/phase2-vgoal`  
> **RUNBOOK**：[`RUNBOOK_phase2_vgoal.md`](RUNBOOK_phase2_vgoal.md)  
> **模块 README**：[`experiments/aerial/phase2-vgoal/README.md`](../../experiments/aerial/phase2-vgoal/README.md)

---

## 一句话

**几何 Phase-2 已 close**（`phase2-pass-20260908`）；本线在同一 π/罩上叠 **视觉 goal 来源**（`aerial-vgoal-wam`），与 Phase-3 室内融合 **无关**。

## 进度

| 项 | 状态 |
|----|------|
| 分支 `project/phase2-vgoal` | **已推** `github` + `origin`（125 bare） |
| RUNBOOK / 模块 README | **已写** |
| 125 手递 | [`WAM_PHASE2_VGOAL_125_PROMPT.md`](WAM_PHASE2_VGOAL_125_PROMPT.md) |
| vgoal 4 路探针 | **完成** · `artifacts/wam_vgoal_probe2_4routes.json`（SR 50% · det 8%） |
| 几何对照 4 路（同 routes 0–3） | **125 运行中** · `artifacts/wam_phase2_geom_probe2_4routes.json` |
| 对照活页 | [`WAM_PHASE2_VGOAL_GEOM_COMPARISON.md`](WAM_PHASE2_VGOAL_GEOM_COMPARISON.md) |
| V1 全 16 路 vgoal | **对照完成后** |
| V2 几何 vs vgoal 对照 | **待 V1** |
| YOLO 替换 GT 检测器 | **未开始** |

## 基线（几何 · 已 close，勿与 vgoal 混报）

| 指标 | 值 |
|------|-----|
| Tag | `phase2-pass-20260908` |
| SR | 86.7% (13/15，route 8 spawn 异常排除) |
| SCR | 6.7% |
| 配置 | `toward_g` · cs=10 · tti=2.5 · max-steps 2000 |
| Artifact | `wam_phase2_e2_tti25_full16_20260908.json`（125 上） |

## 兄弟仓

| 仓 | 路径 | 角色 |
|----|------|------|
| `aerial-wam-v2` | 本仓 | π / WM / eval 主栈 |
| `aerial-vgoal-wam` | `~/Projects/aerial-vgoal-wam` | `vgoal.geometry` / `detector` / `tracker` |

## 下一刀

1. 125：`source env_4090.sh` → 短探针 `--episodes 2` → 全 16 路  
2. 同设置跑几何 `toward_g` 对照  
3. 填 V1 DECLARE（JSON 路径 + fallback 占比）
