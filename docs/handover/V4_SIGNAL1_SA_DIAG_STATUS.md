# V4 §A imagined return decomp (125, 2026-08-18)

- **status**: **done** (read-only)
- **script**: `experiments/aerial/scripts/v4_imagine_return_decomp.py` (`14d0f06`)
- **JSON**: `artifacts/v4_imagine_return_decomp_20260818.json`
- **log**: `logs/v4_imagine_return_decomp_20260818.log`
- **ckpt**: `v4_ac_ckpt_20260817_wm_rh_goal_rgb` + RH WM `wm_step_1000.pt`
- **z0**: headon `dataset_v0_headon_20260811` n=8 encode; `goal_rel0` = ①-eval ep0 `[+30, 0, 0.85]`; `body_vel0=0`
- **H / λ / γ**: 15 / 0.95 / 0.997
- **yaml / enable_policy_update**: untouched

## A.2 (pre-committed)

| Arm | Σ progress | Σ p_coll | Σ maneuver | Σ reward | λ G0 | a0 |
|---|---|---|---|---|---|---|
| (a) π | **+143.42** | −0.005 | −2.47 | +140.94 | **+104.72** | **[-2.92, -1.37, -0.92, -0.73]** |
| (b) forward `[+1,0,0,0]` | +61.50 | −0.005 | −0.15 | +61.35 | **+47.02** | [1,0,0,0] |
| (c) retreat `[-1,0,0,0]` | +9.32 | −0.005 | −0.15 | +9.17 | **+15.90** | [-1,0,0,0] |

**(c) λG0 ≱ (b)** → verdict **`b_gt_c`**.  
`(c)−(b)` 由 **progress** 主导（−52.18）；p_coll 差 **~0**；maneuver 差 0。

**判定**：想象目标**不**偏好后退。负 ① 不是「想象里 ①/④ 被碰撞项主导」。按提案 A.2：**§4 In 表修订可直接执行**（仍须签字 + V3 裁定 + unique-goals）。

## Residual (does not overturn A.2)

π 的 a0 仍是**后向大动作**（action_scale=3），但想象 Σprogress **高于**常量前飞。说明 RH 对 π 的大动作给了很高 progress，**不是**「常量后退优于常量前飞」。A.2 只比较 (b)/(c)；此残差可在 In 表落地后的重训里用多样 goal 消化，不另开 p_coll 配平案。
