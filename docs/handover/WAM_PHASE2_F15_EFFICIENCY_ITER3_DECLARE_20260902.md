# DECLARE · F15 效率 iter3（2026-09-02）

> **状态**：**FAIL · 停** · 训练侧无改善 · 不扩 probe / 不再拧 `w_eff_*`  
> yaml 默认 `w_eff_*` 仍 **0**。

---

## 0. 为何停

iter2 后 R05 已从「不动」变成「会动但切线错」（ds=25 · cos@30=−0.13）。  
iter3 再抬 `w_eff_heading`（0.10）warm-start iter2：

| 项 | 值 |
|----|-----|
| ckpt | `v4_ac_ckpt_f15_eff_ft_iter3_20260902`（已训满 300） |
| 末 `mean_return` | ≈ **−65.2**（≈ iter2 −64.5，**无改善**） |
| 末 `mean_progress` | ≈ **0 / 负**（差于 iter2 ≈0.20） |

**Verdict：训练侧 FAIL。** 不跑 `.110` 否决 probe（成本不值）；不据此开 16 路。

---

## 1. 主航道读数（诚实）

| 阶段 | R05 现象 | 是否 baseline 病 |
|------|----------|------------------|
| F15 baseline（step_e） | idle≈98% · tiny dyaw · ds≈1.3 | **是** — yaw 死 + 空转 |
| F15 短训后 | 有推力 · cos_heading_ref 负 · CTE 升 | **否** — 训练副作用「乱动」 |

继续拧 `w_eff_*` = 在副作用上修参，**偏离主因**。

训练罚的是 carrot body `atan2`；验收关的是 **路径切线** `cos_heading_ref` → 量不对齐。

---

## 2. 冻结的下一步（非 F15 权重迭代）

1. **停** F15 iter 扩面；iter1/2/3 ckpt 仅作对照，**主指标勿用 F15 FT 冒充过门**。  
2. **回诊** step_e baseline · R05：yaw 死 / idle 的根因（actor vs subgoal vs planner 接线分离 log）。  
3. 若再动奖励：须新 DECLARE，且 heading 罚与 **`cos_heading_ref` 同源**；禁止再只调 `w_eff_*` 旋钮。  

### 禁止

assist · heading_reentry · cruise/subgoal 几何当主修 · 未声明抬 yaml 默认 `w_eff_*`
