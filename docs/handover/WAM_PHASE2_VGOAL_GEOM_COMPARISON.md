# vgoal probe2 × 几何 toward_g 对照（4 路同索引）

> **目的**：与 `wam_vgoal_probe2_4routes.json` 同 `--routes 0,1,2,3`、同 ckpt/tti/max-steps，隔离「视觉 vs 几何」差异。

## 工件路径（125 · `~/aerial-wam-v2/artifacts/`）

| 臂 | 文件 | 日志 | 完成 |
|----|------|------|------|
| vgoal（2026-09-08） | `wam_vgoal_probe2_4routes.json` | `wam_vgoal_probe2.log` | ✅ |
| 几何 toward_g（2026-09-09） | `wam_phase2_geom_probe2_4routes.json` | `wam_phase2_geom_probe2.log` | ✅ 16:47 |
| vgoal 短探针（2026-09-09） | `wam_vgoal_probe_125.json` | `logs/wam_vgoal_probe_125_20260909_160653.log` | ✅ |
| 全量 baseline | `wam_phase2_e2_tti25_full16_20260908.json` | — | tag close |

## 汇总

| 臂 | SR | SCR | closure | det_frac | 备注 |
|----|-----|-----|---------|----------|------|
| vgoal 0908（4 路） | **50%** | 25% | 0.72 | 8.4% | routes 0,2 ✅；fallback 主导 |
| geom 0909（4 路） | **0%** | 50% | 0.65 | — | 全失败；route 1,3 severe coll |
| vgoal 0909（2 路） | **0%** | 0% | 0.78 | 0.45% | routes 0,1；与 geom 同日同境 |

## 逐路对照表

| route_idx | base | geom 0909 | vgoal 0908 | vgoal 0909 | 判读 |
|-----------|------|-----------|------------|------------|------|
| 0 | 5 | ❌ 35.8 m | ✅ 2.95 m | ❌ 35.8 m | **日际波动**；0908 成功实为 fallback |
| 1 | 16 | ❌ 17.7 m · sev | ❌ 32.5 m | ❌ 34.4 m | 几何/vgoal 均难；0909 geom 更近但 sev coll |
| 2 | 7 | ❌ 36.1 m | ✅ 2.99 m | — | 同 route 0：日际差大 |
| 3 | 17 | ❌ 132.2 m · sev | ❌ 130.8 m · sev | — | 路/仿真问题；两臂一致崩 |

**结论（本批）**：
- 0909 几何 0% SR **不能**推翻 Phase-2 close（full16 仍 81–87%）；4 路探针方差大。
- vgoal 0908 的 50% SR **不能**宣称视觉优于几何——det≈8%，成功路实为 `toward_g` 回落。
- route 3 两臂均 early severe coll → 环境/路问题，非视觉独责。
- **下一阶段**：不以 GT 投影 + fallback 为主臂；切 **Phase-2 π + YOLO/语义检测 + `VisualGoalWAMPolicy` 接线**（见 STATUS）。

## 命令（几何臂 · 2026-09-09）

```bash
source experiments/aerial/scripts/env_4090.sh
python -m experiments.aerial.scripts.wam_phase2_long_eval \
  --subgoal-source toward_g \
  --annotation artifacts/seen_airsim16_long_routes.json \
  --routes 0,1,2,3 \
  --cruise-speed 10.0 --tti-coeff 2.5 --max-steps 2000 \
  --planner --planner-horizon 5 \
  --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_phase2_toward_g_20260905_112006/v4_ac_latest.pt \
  --out artifacts/wam_phase2_geom_probe2_4routes.json
```
