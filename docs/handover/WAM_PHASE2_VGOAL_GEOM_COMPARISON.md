# vgoal probe2 × 几何 toward_g 对照（4 路同索引）

> **目的**：与 `wam_vgoal_probe2_4routes.json` 同 `--routes 0,1,2,3`、同 ckpt/tti/max-steps，隔离「视觉 vs 几何」差异。

## 工件路径（125 · `~/aerial-wam-v2/artifacts/`）

| 臂 | 文件 | 日志 |
|----|------|------|
| vgoal（2026-09-08） | `wam_vgoal_probe2_4routes.json` | `wam_vgoal_probe2.log` |
| 几何 toward_g（2026-09-09） | `wam_phase2_geom_probe2_4routes.json` | `wam_phase2_geom_probe2.log` |
| 全量 baseline | `wam_phase2_e2_tti25_full16_20260908.json` | — |

## 命令（几何臂 · 已启动 2026-09-09 16:25 CST）

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

## 标注索引 → base_route_idx

| route_idx | base_route_idx | vgoal 昨日结果（摘要） |
|-----------|----------------|------------------------|
| 0 | 5 | ✅ arrived · det 8% |
| 1 | 16 | ❌ timeout 32 m · det 0.4% |
| 2 | 7 | ✅ arrived · det 8% |
| 3 | 17 | ❌ 23 步 severe coll |

## 填表（几何跑完后）

| route_idx | base | geom arrived | geom d_final | vgoal arrived | vgoal d_final | 结论 |
|-----------|------|--------------|--------------|---------------|---------------|------|
| 0 | 5 | | | ✅ | 2.95 m | |
| 1 | 16 | | | ❌ | 32.5 m | |
| 2 | 7 | | | ✅ | 2.99 m | |
| 3 | 17 | | | ❌ | 130.8 m | |

**判读**：
- geom ✅ / vgoal ❌ → 视觉栈或回落伤害导航
- geom ❌ / vgoal ❌ → 路本身难或仿真问题
- geom ✅ / vgoal ✅ 且 det_frac≈0 → vgoal 成功实为几何回落
