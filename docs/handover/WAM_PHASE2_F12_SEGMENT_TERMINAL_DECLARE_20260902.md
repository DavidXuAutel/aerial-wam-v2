# DECLARE · F12 段末可收敛（论证中 · 2026-09-02）

> **状态**：**论证 / 未启用** · 代码可 opt-in，**默认关闭**（`segment_length_m=0` · `terminal_pin_rem_m=0`）  
> **禁止**在未完成下方验证前当主航道默认、开 16 路、或宣称 F12 已修。

---

## 0. 假设（待证）

长线 SR=0 的主因是：滑动胡萝卜在 `rem > r` 时目标不可收敛 → π 缺阶段 1「到点」合同。  
设计解：中段封顶 + 终段钉 route 终点。

---

## 1. 用回锚数据做的否证 / 弱支持（先于改默认）

数据：`artifacts/wam_phase2_reanchor_stepe_result_20260830.json`（裸 `step_e` · 16 路）。

| 观察 | 数 | 对「不可收敛胡萝卜」假设 |
|------|-----|-------------------------|
| F12 路几乎都跑满 **1001 step** | 超时停，不是到点停 | 弱支持「末段合同」；更像 **时间/推进不够或绕圈** |
| `d_min` 聚类 **57–71 m** | 从未进最后 ~60 m 球 | 若 `true rem` 仍 >40，**terminal_pin 根本不会触发** |
| `progress_ratio≈1` 且 `d_min≈60` | path_end≡goal，Prog 与几何矛盾 | **强支持 Prog 虚高（单调锁）**，不是「差 20 m 胡萝卜」单独能解释 |
| `actual_length` ≫ `nominal`（常 1.5–4×） | 飞了很长仍 `d_min~60` | 支持 **低效/绕飞/偏航**，不支持「只差终段钉点」 |

法医文档已点名：`F_MONOTONE_INFLATE` / `F_TERMINAL_GAP`；R05 另案 `F_OFFTRACK`（与多数 F12 不同）。

**阶段结论：** 「先钉终点就能修 F12」**证据不足**；更优先验证的是：

1. 超时前 **真实** `s_true` / `rem_dist` / `cte` / `‖g_rel‖` 末 200 步曲线  
2. Prog 是否仍被锁虚高（cte_lock_freeze 之后是否改善）  
3. R05 刀刃（yaw/idle）与 F12 多数路是否同机制  

---

## 2. 验证计划（动手改默认之前）

### V1 — 只读复盘（零改行为）

任选 2 条高 Prog、`d_min∈[55,75]` 的回锚路 + R05：

* 逐步：`s_true`, `s_progress`, `rem_dist`, `cte`, `‖g_rel‖`, `d_goal`, `action`  
* 事前判据：  
  * 若末段 `rem_dist` 长期 **> terminal_pin 阈值** → 钉终点假设 **否**  
  * 若 `s_progress→L` 且 `s_true≪L` → 主因 **Prog 虚高**  
  * 若 `‖g_rel‖` 贴 `r_base` 平台、不随靠近缩小 → 才支持不可收敛胡萝卜  

### V2 — 对照实验（仍须 DECLARE 准出表）

仅在 V1 支持后：opt-in `segment_length_m=40` / `terminal_pin_rem_m=40` vs 默认 0，同 `step_e`、同 seed 路。

---

## 3. 代码落位（opt-in only）

`AdaptiveSubgoalGenerator` 已具备开关；**默认 0=与改前主航道等价**。  
单测覆盖 pin 行为；**不得**在验证前把默认改回 40。

---

## 4. 与最初设计的关系

「长线 = 多段阶段 1」**方向仍对**，但升格合同必须先用 **真实 rem/CTE/g_rel** 证明卡在「段不可收敛」，再改 subgoal 默认；不可用 Prog 或口头 F12 直接开刀。
