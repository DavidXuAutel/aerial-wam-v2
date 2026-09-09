# Phase-2 + vgoal · 活页 STATUS

> **分支**：`project/phase2-vgoal`  
> **RUNBOOK**：[`RUNBOOK_phase2_vgoal.md`](RUNBOOK_phase2_vgoal.md)  
> **模块 README**：[`experiments/aerial/phase2-vgoal/README.md`](../../experiments/aerial/phase2-vgoal/README.md)

---

## 任务目标（产品一句话）

**单目纯视觉**：在指定方向或范围内，无人机自主 **搜寻 → 定位 → 抵近 → 伴飞**；成功仅认 `goal_from=vision`，禁止用 GT 世界坐标冒充视觉成功。

| 能力 | 含义 | 现有模块（`aerial-vgoal-wam`） |
|------|------|-------------------------------|
| **搜寻** | 扇区/区域覆盖扫描，未见目标时主动搜 | `AreaSearchPlanner`（割草机/螺旋）+ `bridge` SEARCHING 偏航 |
| **定位** | YOLO/开放词表 → 单目 D̂ 反投影 → 3D 相对位 | `detector` + `bbox_to_goal_rel` + `TargetTracker` |
| **抵近** | 拦截/飞到目标前站位点 | `DynamicTargetTracker` INTERCEPTING · `approach_standoff_m` |
| **伴飞** | 目标后方/上方保持 standoff | `DynamicTargetTracker` FOLLOWING（默认后 6 m · 上 3 m） |
| **语义** | 自然语言/类名 → 检测 prompt | `OpenVocabPromptDetector` · `prompt_classes` |

**底座**：Phase-2 outdoor π + TTI 罩 + planner（只负责运动与避障，不提供目标 GT）。

## 一句话（架构）

在 **Phase-2 outdoor close** 运动壳上，用单目 **检测 + 深度反投影 + 任务 FSM** 驱动 `goal_rel`；`aerial-vgoal-wam` 提供感知/搜索/伴飞模块，**不以旧 Method B 短评栈为主航道**。

## 架构 pivot

```text
旧 Method B 母体（弃作主航道）          新主航道（本 project）
────────────────────────────          ────────────────────────
step_e / m1a20 / max-steps 250        phase2-pass E2 ckpt + long routes + 2000 steps
VisualGoalWAMPolicy 独立闭环          Phase-2 env + shield + planner 为壳
SEARCHING = 慢速+偏航扫描              SEARCHING = YOLO/语义搜 + 可选 scene/toward_g 外环
室内 Building_99 语义轨               户外 env_airsim_16（室内语义另轨，不混入本 project）
```

| 层 | 来源 | 角色 |
|----|------|------|
| π / WM / TTI 罩 / planner | `aerial-wam-v2` Phase-2 close | **不动** |
| detector / tracker / geometry / 语义 prompt | `aerial-vgoal-wam` `vgoal.*` | 感知前端 |
| eval 入口 | `wam_vgoal_eval.py` → 收敛到 `VisualGoalWAMPolicy` + Phase-2 配置 | 待改 |

## 进度

| 项 | 状态 |
|----|------|
| 分支 `project/phase2-vgoal` | **已推** `github` + `origin` |
| V0 接线（GT 投影 + fallback） | **完成** · 证明可跑通，**非产品形态** |
| vgoal 4 路探针（0908） | SR 50% · det 8% · [`GEOM_COMPARISON`](WAM_PHASE2_VGOAL_GEOM_COMPARISON.md) |
| 几何对照 4 路（0909） | **完成** · SR 0%（日际方差，见对照活页） |
| vgoal 2 路复探（0909） | **完成** · SR 0% · `wam_vgoal_probe_125.json` |
| **M1+M2** YOLO + D̂ + Phase-2 壳 · 无 fallback | **代码已合入** `wam_vgoal_eval.py` |
| **M3** 区域搜寻 `AreaSearchPlanner` | 下一刀 |
| **P2** 语义导航（instruction → prompt → 开放词表检测） | P1 后 |
| V1 全 16 路（YOLO 臂） | 待 P1 |
| Phase-3 室内融合 | **本 project 不含** |

## 基线（几何 · 已 close，勿与 vgoal 探针混报）

| 指标 | 值 |
|------|-----|
| Tag | `phase2-pass-20260908` |
| SR | 86.7% (13/15) / full16 JSON 81.2% |
| 配置 | `toward_g` · cs=10 · tti=2.5 · max-steps 2000 |
| Artifact | `wam_phase2_e2_tti25_full16_20260908.json`（125） |

## 兄弟仓

| 仓 | 路径 | 本 project 用法 |
|----|------|-----------------|
| `aerial-wam-v2` | 本仓 | Phase-2 主栈 + eval |
| `aerial-vgoal-wam` | `~/Projects/aerial-vgoal-wam` | `detector` / `tracker` / `geometry` / `bridge`（需 Phase-2 参数化） |

## 下一刀

1. **`VisualGoalWAMPolicy` 接 Phase-2**：E2 ckpt · tti=2.5 · planner · long_eval 合同 · `seen_airsim16_long_routes.json`
2. **GT → YOLO**：`YOLOTargetDetector` + `bbox_to_goal_rel(D̂)`；报表分 `goal_from=vision|fallback`
3. **语义层**：复用 `OpenVocabPromptDetector` + `prompt_classes`（户外类表待定义）
4. 全 16 路 vgoal vs geom 同协议 DECLARE
