# V4 §A / §A.3 imagined return decomp (125, 2026-08-18)

- **status**: **A.2 done · A.3 done** (read-only)
- **script**: `experiments/aerial/scripts/v4_imagine_return_decomp.py` (`2afcb33` + `--match-scale`)
- **A.2 JSON**: `artifacts/v4_imagine_return_decomp_20260818.json`
- **A.3 JSON**: `artifacts/v4_imagine_return_decomp_a3_20260818.json`
- **A.3 log**: `logs/v4_imagine_return_decomp_a3_20260818.log`
- **ckpt**: `v4_ac_ckpt_20260817_wm_rh_goal_rgb` + RH WM `wm_step_1000.pt`
- **z0**: headon n=8；`goal_rel0` = ①-eval ep0 `[+30, 0, 0.85]`；`body_vel0=0`
- **yaml / enable_policy_update**: untouched

## A.2 (unit magnitude; collision channel)

| Arm | Σ progress | Σ p_coll | Σ maneuver | λ G0 | a0 |
|---|---|---|---|---|---|
| (a) π | **+142.23** | −0.006 | −2.47 | **+103.63** | `[-3.13, -1.23, -0.18, -0.05]` ‖a0[:3]‖=**3.59** |
| (b) forward `[+1,0,0,0]` | +65.72 | −0.006 | −0.15 | +49.65 | unit |
| (c) retreat `[-1,0,0,0]` | +9.51 | −0.006 | −0.15 | +15.99 | unit |

Verdict **`b_gt_c`** — **碰撞项通道排除**（p_coll 差≈0）。A.2 不足以判 §4 充分（幅度通道）。

## A.3 (scale-matched; 2026-08-18)

`match_scale=3.591`（auto from π ‖a0[:3]‖）。

| Arm | Σ progress | Σ p_coll | Σ maneuver | λ G0 | ‖goal_rel‖ 30→ |
|---|---|---|---|---|---|
| (a) π | **+142.23** | −0.006 | −2.47 | **+103.63** | **253.9**（未到达；OOD） |
| (b3) forward @3.59 | +83.39 | −0.006 | −0.54 | **+59.85** | 23.9（靠近） |
| (c3) retreat @3.59 | +8.80 | −0.006 | −0.54 | +15.31 | 83.9 |

**(b3) λG0 59.85 ≰ (a) 103.63** → 预提交判据 **`b3_le_a`**.

- 匹配幅度下 RH **仍更偏好 π 那个后向向量**（Σprogress 142 vs 前飞 83），不是「只是幅度更大」。
- `pi_imagined_arrival=false`：‖goal_rel‖ **涨**到 254，不是收到 0 → **不是** z 转移「以为到达」。
- 幅度欠罚比 ≈ **33×**（相对单位前飞）。

**处置（A.2 第二支）**：**先修 RH（另案）**，再执行 §4 In 表。**不签「§4 充分」。** 多样 goal / 加 `goal_rel` 不能代替这次判定。

`enable_policy_update` 仍 **false**。
