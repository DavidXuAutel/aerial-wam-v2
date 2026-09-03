# Aerial WAM 阶段 2 Runbook（诚实主航道 · 单目 + WAM 到点）

> **日期**：2026-08-28（主航道回锚）  
> **本文件是什么**：阶段 2 **唯一日常入口**——用单目 RGB + IMU + 高度计与世界模型把无人机导航到目标点。  
> **上游主航道**：[`RUNBOOK_wam_imagination.md`](RUNBOOK_wam_imagination.md)（阶段 1：想象到点）  
> **设计规格**：[`docs/superpowers/specs/2026-08-28-hierarchical-long-horizon-wam-design.md`](../../docs/superpowers/specs/2026-08-28-hierarchical-long-horizon-wam-design.md)  
> **实施计划**：[`docs/superpowers/plans/2026-08-28-hierarchical-long-horizon-10ms-wam.md`](../../docs/superpowers/plans/2026-08-28-hierarchical-long-horizon-10ms-wam.md)

与本文冲突时：**以本文件的诚实主航道为准**；往返凑长、Docking 替飞、关罩刷分一律视为偏离。  
**室内小空间**：同主航道尺度特化 → 见 sibling/`aerial-indoor-wam` 的 [`RUNBOOK_indoor_0xm.md`](../../../aerial-indoor-wam/experiments/aerial/RUNBOOK_indoor_0xm.md)；**禁止**另立夹具/GT-PD 室内方案。

---

## 0. 一页诚实结论

| 项 | 事实 |
|----|------|
| **允许传感** | **单目 RGB + IMU + 高度计（气压/测距）**。无 LiDAR / 无立体 / 无 RTK 作为默认产品假设 |
| **产品目标** | 上述传感 →（状态估计）→ WAM（编码 / 想象 / 策略）→ 飞到**目标点**；深度/三线罩只做安全底线 |
| **阶段 1 已证明** | 在约 50–150 m、坐标目标、合法短走廊上，局部栈可达 ~93% 到达、低碰撞 |
| **阶段 2 在扩什么** | 更长航程时，禁止把远点绝对坐标直接塞进 π；用**合法全局折线 + 局部胡萝卜**保持目标输入在分布内 |
| **合法折线从哪来** | 必须在可飞自由空间 \(\mathcal{F}\) 内搜索/示教得到（A\* / 拓扑 / 专家轨迹）。**两点直线插值非法** |
| **当前仿真诚实基准** | 16 条**原生 A\* 点到点**走廊（约 110–170 m）；过滤贴地坏标注。尚未声称已覆盖跨街区 200–500 m |
| **跨街区 200–500 m+** | 需要**全局走廊规划器**（地图/拓扑上 A\* 等）产出 \(P_{global}\)，再交给现有局部 WAM。不是局部模型单独能「脑补」公里级路径 |
| **目标坐标特权** | 评测里目标仍来自标注世界坐标 → `goal_rel`。**不是**「画面里认出目标」。真·视觉目标是 Method B / 另线，不得写成已解决 |
| **禁止冒充 WAM** | Pure Pursuit / MPC / Docking P 控 / 往返刷分 / 关罩 / 假到达合同 |

**成功定义**：同协议下 **到点 ∧ 少严重碰撞 ∧ 进度真实**，且飞行核是 π + 想象，不是外部跟踪器。

### 0.1 传感合同（冻结）

| 通道 | 角色 | 不做的事 |
|------|------|----------|
| **单目 RGB** | WAM 编码 / 想象避障的主视觉；可选 VIO 视觉前端 | 不是深度真值；不是目标检测（默认验收） |
| **IMU** | 姿态、角速度、线加速度；VIO / 互补滤波的核心 |  alone 不能给无漂 \(xy\) 绝对位姿 |
| **高度计** | \(z\) 锚定（气压或下视测距）；高度跟踪 / 贴地防护 | 不替代水平定位；气压有偏置/气象漂 |

**状态估计约定**：实机路径为  
`RGB + IMU + 高度计 → \(\hat p,\hat\psi,\hat v\)`（VIO 或等价滤波器）→ 与今日相同的 Subgoal / π / 想象接口。  
仿真默认验收仍可用 GT 位姿 **代理** 该估计器输出；**不得**把「GT 代理过门」写成「无定位传感已飞通」。

IMU+高度计 **降低** F8 缺口（尤其 \(z\) 与短时姿态），**不取消**水平定位：百米级仍须视觉惯性融合或外源；否则 CTE / `goal_rel` 会漂死。

### 0.2 可实现性分层（诚实评估）

| 范围 | 可实现？ | 条件 |
|------|----------|------|
| **A. 仿真 · 原生合法走廊 ~110–170 m · GT 位姿代理 + 坐标目标** | **高概率可达成**（门限 SR≥80% 量级） | Stick F1–F7；补齐 **F8–F12**；阶段 1 同栈已证 ~93% |
| **B. 仿真 · 跨区 200–500 m+ · 全局合法折线** | **工程可达成，但未交付** | Step M：地图/拓扑搜 \(P_{global}\subset\mathcal{F}\) |
| **C. 「零重训」扩到陌生视觉分布** | **不可默认承诺** | 胡萝卜只保 `goal_rel`；RGB/coll 可 OOD |
| **D. 无图陌生 + 无粗目标** | **当前栈不可交付** | 须建图/探索或先验拓扑 |
| **E. 实机 · RGB+IMU+高度计估计位姿 · 坐标/粗目标** | **主航道下一战役（可规划）** | 接通 VIO/滤波；用高度计收 \(z\)；噪声下重验 F3/F4/F12 |
| **F. 无坐标 · 画面认目标** | **另线 Method B** | 不与默认 SR 混报 |

**总判**：主航道 = **单目 + IMU + 高度计** 传感下的局部 WAM + 合法折线。仿真用 GT 位姿是估计器的 stub；实机用同一接口吃 \(\hat p\)。不是「仅 RGB、无惯性」神话。

---

## 1. 主航道结构（单目 + IMU + 高度计 + WAM）

```text
                    ┌─ 合法全局折线 P_global ⊂ F ─┐
                    │  （示教走廊 / 地图 A* / 拓扑） │
                    └────────────┬────────────────┘
                                 │
         RGB ──encode──► z       │
         IMU ─┐                  │  AdaptiveSubgoal
         高度计 ┴► 状态估计 \(\hat p,\hat\psi\) ─┼─► g_rel^body (20~55 m)
              （仿真可用 GT 代理） │
                                 │
                    π(a | z, g_rel) + ImaginationPlanner
                                 │
                    ThreeZone / 深度罩（仅安全）
                                 │
                               执行器
```

| 层 | 职责 | 输入 | 非职责 |
|----|------|------|--------|
| **传感/估计** | 产出 \(\hat p,\hat\psi\)（及可选 \(\hat v\)） | RGB、IMU、高度计 | 不做动作决策 |
| **全局** | 给出可飞参考折线 | 地图/拓扑/示教 + 粗目标 | 不做逐步视觉伺服 |
| **上层前瞻** | 投影 + 动态 \(R\) + CTE 归航 + \(v_{safe}\) | \(P_{global}\)、\(\hat p\)、\(\hat D_{fwd}\) | 不替换 π |
| **底层 WAM** | 单目想象选动作到局部子目标 | RGB、\(g_{rel}\) | 不吃 500 m 远点 |
| **安全罩** | 近障限速/急停 | \(\hat D\)、τ、\(p_{coll}\)；高度计可辅助贴地 | 不是导航大脑 |

---

## 2. 最早方案致命缺陷（对照主航道）

最早可工作形态 ≈：**原生走廊点到点 + Subgoal + 阶段 1 WAM**，首轮约 **50% 到达**。失败不是「再堆脚手架」，而是下列硬伤。  
F1–F7 是**最早方案层**缺陷；F8–F14 是审查后发现、**原 runbook 未写全**、仍会封顶 SR 的底层债。

### F1 — 全局路径不合法（几何）

* **现象**：跨段用直线 bridge / 手搓 U 转 → 穿楼、贴墙、spawn 即撞。  
* **机理**：折线 \(\not\subset \mathcal{F}\)。  
* **主航道解法**：  
  1. **近程验收**：只用原生 A\* / 示教走廊（`generate_long_routes.py` → `mainline_native`）。  
  2. **远程验收**：实现全局规划器，在占据/拓扑图上搜 \(P_{global}\)，**禁止**自由空间插值。  
  3. 陌生无精确坐标：粗目标（区域/语义/图像）→（有图则 A\*；无图则建图/拓扑探索）→ 合法折线 → 局部 WAM。

### F2 — 远目标直接进 π（分布外）

* **现象**：把终点绝对距离塞进 `goal_rel`，策略退化。  
* **机理**：阶段 1 训练分布是短距相对目标。  
* **主航道解法**：强制 `obs.info["goal"]` / `goal_rel` = **局部胡萝卜**（20–55 m），全局终点只经投影与弧长进入上层。

### F3 — 急弯 / 近障速度包络不足（物理）

* **现象**：10 m/s 直道尚可，直角弯切角撞、近障刹不住。  
* **机理**：制动距离随 \(v^2\) 涨；\(\alpha\) 下限 + 过高 \(v_{min}\) 使近障仍过快；曲率限速未与 \(a_{lat}\) 对齐。  
* **主航道解法**：  
  * \(v_{safe}=\min(v_{cruise},\,v_{clear}(\hat D),\,\sqrt{a_{lat}/\kappa})\)；危险净空落到蠕行（对齐 ThreeZone \(v_{stop}\)）。  
  * 想象视野短，**不能**靠加大 H 假装看完弯道；弯道靠曲率收 \(R\) + 罩托底。

### F4 — CTE / 丢轨无自愈（跟踪）

* **现象**：偏出走廊后空转、`prog≈0` 或锁死。  
* **机理**：仅有单调弧长锁，设计中的 CTE>5 m 拉近归航未落地；错误搜索窗会加剧死锁。  
* **主航道解法**：实现 CTE 自愈（偏航大则缩短 \(R\) 形成汇入角）；丢轨诊断进日志；**禁止**用随机摆头 escape 冒充恢复。

### F5 — 安全罩未参与真实闭环（安全）

* **现象**：IR≈0 仍有硬撞。  
* **机理**：深度未进罩、`safety.kind` 为空、或限速上限绕过三线。  
* **主航道解法**：评测强制 `three_zone`；每步写入 `depth_min_pred`；最终 \(v_x\) 取 \(\min(v_{safe},\,v_{zone})\)；禁止关罩刷 SR。

### F6 — 到达与效率合同失真（验收）

* **现象**：未走完路径却「到达」、短切线 SPL=1。  
* **机理**：放宽 \(D_{rem}\)、Docking 抢飞、往返起终点重合。  
* **主航道解法**：设计合同 —— \(D_{rem}\le 3\,\mathrm{m}\) **且** \(\|p-g\|_2\le 3\,\mathrm{m}\)；进度 = \(s_{max}/L_{ref}\)；禁止 Docking/往返冒充到点。

### F7 — 用外部控制器冒充 WAM（主航道纪律）

* **现象**：终末 P 控、anti-stagnation 启发式、Pure Pursuit 替 π。  
* **机理**：指标上升但产品大脑不是 WAM。  
* **主航道解法**：闭环核仅允许 `LatentActorDeployPolicy` + `ImaginationPlanner` + Subgoal + Shield；其余一律旁支。

### F8 — GT 位姿 stub 与「传感已闭环」口径混淆

* **现象**：评测用 AirSim GT `position`/`yaw`；产品传感允许 **RGB + IMU + 高度计**，但估计器未接进 Subgoal/`goal_rel`。  
* **机理**：F8 不是「不许用 IMU」——**允许且应当用**。缺口是：（1）今日闭环吃的是 GT，不是 IMU+高度计+视觉融合的 \(\hat p\)；（2）仅 IMU+高度计 **不够** 无漂水平定位，百米级仍要 VIO（或等价）。高度计主要钉 \(z\)，显著缓解软高度旁路与贴地，不解决 \(xy\) CTE。  
* **主航道解法**：  
  1. 传感合同冻结为 RGB+IMU+高度计（§0.1）。  
  2. 仿真 SR 标明 **GT 代理位姿**；实机战役 = 同一接口换 \(\hat p\)（VIO），高度计进 \(z\)。  
  3. 禁止写成「纯 RGB、无惯性已导航」。

### F9 — Actor 米制 `goal_rel` 未归一化（表征）

* **现象**：`LatentActorCritic._feat_tensor` 仍 `concat(z, raw metres)`；回报头已 `û‖log1p(d)`，策略未对齐。  
* **机理**：20–55 m 胡萝卜数值 ≫ 隐特征 → 视觉梯度被冲垮，易退化为盲追坐标、撞弯道却被误诊为「只是 F3 限速」。  
* **主航道解法**：策略/价值与回报头同一套 `g_norm`；旧 ckpt 要么重训要么加载期明确 goal-blind 风险。**P0 代码债，未修则 SR 上限不可信。**

### F10 — Planner 每步 `encode` 打断流式后验（部署一致性）

* **现象**：`LatentActorDeployPolicy` 已走 `observe_and_advance`；`ImaginationPlanner.plan` 仍 `dynamics.encode(obs)` 重开隐状态。  
* **机理**：π 与想象评分看的 \(z\) 不是同一滤波轨迹 → 候选排序失真，弯道/避障候选被低估。  
* **主航道解法**：plan 必须吃部署当前 \(z\)（或同一后验接口），禁止评分路径单独失忆 encode。

### F11 — 单调弧长锁 × 无合法回退（死胡同）

* **现象**：CTE 归航假定 \(s_{\max}\) 前方路径仍可达；钻进死角或绕障后被楼挡住回廊时，锁禁止后退、F7 又禁 escape。  
* **机理**：上层只有「前进胡萝卜」，没有「沿 \(P_{global}\) 合法回退/换出口」。  
* **主航道解法**：折线本身无死胡同（全局规划质量）；或显式 **沿参考线回退模式**（减小 \(s\)，仍是主栈几何，不是随机摆头）。无此则密林/多出口场景 SR 有硬顶。

### F12 — 终末离散过冲（到达物理）

* **现象**：10 m/s @ 5 Hz ≈ 2 m/步；\(D_{rem}\le3\) ∧ \(d\le3\) 球可一步穿过；阶段 1 已见门廊超时（剩 ~10 m）。  
* **机理**：\(R\) 随剩余收缩，但 \(v_{safe}\) 未强制终末蠕行到与成功半径匹配。  
* **主航道解法**：\(D_{rem}\lesssim 2\cdot v\Delta t\) 时强制蠕行 / 降 \(v_x\)；保留段采样到达判定（已有），不靠 Docking P 控。

### F13 — 「零重训」对视觉域不成立（迁移）

* **现象**：设计写零模型重训扩到 200–800 m；胡萝卜只约束目标通道。  
* **机理**：新几何/光照下 encoder、\(p_{coll}\)、深度头仍可 OOD。  
* **主航道解法**：同域（AirSim16 类走廊）可零重训验收；跨域必须探针 + 必要时 coll/深度/策略补数据，不得写进默认「已证明」。

### F14 — 安全罩吃独立深度头，非 WAM 内生几何（安全依赖）

* **现象**：ThreeZone 依赖 `depth_predictor`；隐空间 coll 探针曾出现侧向危险 > 前向等失败模式。  
* **机理**：导航脑（想象）与安全底线（深度）两套几何；深度虚警→IR/紧急锁，漏检→SCR。  
* **主航道解法**：罩必开且可诊断；深度/coll 质量单独门禁；长期用 depth-aux / coll-geom 把几何压进 \(z\)，减少「两套真相」。

### F15 — 奖励合同 =「靠近目标 − 碰撞」，鼓励侧移蹭点（训练）

* **现象**：机头拧偏后 π 用侧向 `dy` 追胡萝卜，航向与折线切线夹角持续变大；沿轨 `s` 不动却仍「在靠近目标」。  
* **机理**：现行 `reward ≈ w_progress·Δd_goal − w_collision·risk − ε·‖a‖`（`w_maneuver≈0.01`）。产品目标是 **避障 + 沿合法走廊有效前进**，不是最短直线蹭终点。多旋翼物理允许侧飞，但跟廊任务不应把侧移当主追点手段。  
* **主航道解法（效率合同）** — 在保留避障绕行余量的前提下，惩罚**无效机动**，不是盲目罚路径变长：  
  1. **侧移比**：\|dy\|/max(\|dx\|,ε) 或侧向位移占比过高 → 罚；  
  2. **航向误差**：机头与胡萝卜/`path` 切线夹角大且仍大侧移 → 罚；  
  3. **空耗**：\(\Delta s_{\mathrm{true}}\approx 0\) 却耗步/耗能量 → 罚；  
  4. **相对参考线过长**：\(L_{\mathrm{act}}/L_{\mathrm{ref}}\) 超软上限才罚（允许合理绕障，禁止无意义盘旋）。  
* **验收**：主指标在 **无 heading-assist** 下报；效率项 on/off 对照进 DECLARE。改奖励权重 = 改训程，须先声明再动手。

### F7 补充 — path heading assist（工程保险丝，非主航道胜利）

* **是什么**：CTE 仍小但 `cos(heading, tang)` 差时，在 π→planner 之后注入 `dyaw`（可衰减侧向）。  
* **可以**：部署层兜底 / ablation（类比限速罩）；必须可关、有 on/off 对照。  
* **不可以**：默认开着刷 SR，或写成「WAM 已学会跟线」。主航道 SR/CTE **默认 assist=OFF**。  
* **正道仍归 F4/F15**：CTE 自愈（缩短 \(R\)）+ 效率奖励；assist 不替代二者。

---

## 3. 解决方案总表（按优先级）

| 优先级 | 缺陷 | 动作 | 产物 / 准出 |
|--------|------|------|-------------|
| **P0** | F7 / F6 | 剥掉 Docking、往返、假到达；评测回主栈 | `wam_phase2_long_eval.py` 仅主栈；到达合同 3 m∧3 m |
| **P0** | F2 | 局部 `goal`/`goal_rel` 强制 | 单元/日志可审计子目标距离 ∈ [r_min, r_base] |
| **P0** | F5 / F14 | 强制 ThreeZone + depth 进罩；深度质量可诊断 | IR 可非零；SCR 下降可归因 |
| **P0** | F1-近 | 原生点到点基准，禁 bridge | `seen_airsim16_long_routes.json` = `mainline_native` |
| **P0** | F9 | Actor/Critic `g_norm` 对齐回报头 | 单测 + 必要时重训/声明 ckpt 风险 |
| **P0** | F10 | Planner 使用流式 \(z\)，禁评分路径失忆 encode | 部署与想象 \(z\) 同源可审计 |
| **P1** | F3 / F4 / F12 | 曲率·净空 \(v_{safe}\) + CTE + 终末蠕行 | `subgoal_generator` 单测；门廊不再系统性超时 |
| **P1** | **F15** | 效率合同：罚侧移主追 / 偏航空耗 / 空耗；保留绕障余量 | 奖励单测 + 声明后的补训/蒸馏；主指标 assist=OFF |
| **P1** | F11 | 合法回退或无死胡同折线 | 死角失败可归类，禁止随机 escape |
| **P1** | F1-远 | 全局 A\*/拓扑规划器 | 合法 200–500 m+ 折线数据集 + 评测门 |
| **P1** | F8 | 传感合同 RGB+IMU+高度计；GT=估计 stub；实机接 VIO/\(z\) | 口径一致；高度通道进高度跟踪 |
| **P2** | F7-assist | heading assist 仅 ablation/部署保险丝 | `long_eval`/`forensics` **默认 OFF**；on 只报工程增益 |
| **P2** | F13 / 视觉目标 | 域探针；Method B 另线 | 不得占用默认「坐标到点」验收叙述 |

---

## 4. 合法折线与「无精确坐标」导航（诚实口径）

**合法折线**：\(P_{global}\subset\mathcal{F}\)，来自地图搜索、拓扑最短路或示教；**不是**起点终点连线。

**陌生场景、不给厘米级坐标**：

1. 给粗目标（区域 / 语义 / 目标图像）；  
2. 有先验图 → 全局搜索出折线；无图 → 须建图或探索（超出当前默认交付）；  
3. 局部始终：单目 → \(z\) → π 追胡萝卜或近端视觉目标。  

局部 WAM **不能**单独承诺「无图、无折线、任意远点 100% 到达」。

---

## 5. 标准执行路线（步骤 H ~ L）

```text
[Phase 2 Honest Mainline]
  H  Subgoal + CTE + v_safe（单测）
  I  原生合法点到点基准（禁 bridge / 往返）
  J  主栈评测器（无 Docking / 无 escape）
  K  cursor-125 闭环（强制 three_zone）
  L  签署：SR/SCR/Prog/SPL/IR；失败条按 F1–F7 归类
  M  （可选下一战役）全局 A* 产出跨区合法长折线后再验收 200–500 m+
```

### Step H — 前瞻与限速

```bash
pytest experiments/aerial/rl/tests/test_subgoal_generator.py -v
```

准出：投影、单调锁、开阔 \(R\approx r_{base}\)、近障 creep、CTE 收缩 **全过**。

### Step I — 基准

```bash
python experiments/aerial/scripts/generate_long_routes.py
```

准出：`version` 含 `mainline_native`；起终点分离；无 synthetic bridge；贴地标注已 skip。

### Step J — 评测器

```bash
python experiments/aerial/scripts/wam_phase2_long_eval.py --mock --episodes 2
```

准出：栈为 Subgoal → π → Planner → Shield → step；日志可见局部 `goal` 与 `v_safe`。

### Step K — `.110` 实测

```bash
ssh a26125-110-public   # 或公司网 a26125-110
cd ~/aerial-wam-v2
source experiments/aerial/scripts/env_4090.sh
python experiments/aerial/scripts/wam_phase2_long_eval.py \
  --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt \
  --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_step_e_20260828/v4_ac_latest.pt \
  --annotation artifacts/seen_airsim16_long_routes.json \
  --cruise-speed 10.0 \
  --planner --planner-horizon 5 \
  --max-steps 1000 \
  --out artifacts/wam_phase2_accept_result.json
# 主航道默认：heading assist OFF（若 CLI 有开关，勿默认打开）
```

机器纪律：长评测 / 采集只在 **`.110`**（`ssh a26125-110-public`）；Mac 只做文档/同步/单测；**禁止碰 125 进程**；H100 仅经 125 跳板。

**逐场景硬门（2026-08-30）**：汇总 SR/Prog/IR **不得**单独当根因结论。每轮正式评测必须同时交付：

1. 每路：折线长度 / 曲率粗描 / 起终点几何（看标注，不是猜）  
2. 每路：flown vs ref XY、early/max CTE、fail tag（`wam_phase2_traj_forensics.py`）  
3. 至少 1 条代表失败路的短视频或逐步 shield/π 日志  

未看场景就开下一刀修码 = **浪费回合**（历史：假 Prog 掩盖假 `p_coll` 回退）。

### Step L — 门限与失败归类

| 指标 | 门限 | 说明 |
|------|------|------|
| 到达率 SR | ≥ 80% | `arrived := rem≤3 ∧ ‖p−G‖≤3`；**唯一到点主指标** |
| 严重碰撞 SCR | ≤ 10% | 安全 |
| SPL | ≥ 70% | 无灌水短路 |
| `mean_goal_closure` | 诊断 | \(1-d_{min}/d_0\)；看欧氏闭合 |
| `n_monotone_inflate` | 诊断 | Prog≥0.9 且 \(d_{min}≥30\) |
| 进度 \(\bar\rho\) | **诊断 only** | **不得**单独过门或冒充接近成功 |
| 干预率 IR | ≤ 25% | 罩是底线不是大脑 |

每条失败必须标 **F1–F15** 之一；禁止用「再加启发式」关闭该条。  
**DECLARE 模板**：先逐路表（tag / CTE / d_min），再写汇总；禁止只贴 mean Prog。主指标须注明 **heading_assist=on/off**。

### Step M — 跨区长程（未完成则不得宣称 200–500 m 已验收）

1. 接入/实现全局规划器（占据或拓扑 A\*）。  
2. 生成合法长折线集，复跑 K/L。  
3. 陌生场景另立「建图/视觉目标」战役，不与默认坐标到点混写。

---

## 6. 偏离清单（出现即停）

* 往返 / U 转 / 自由空间 bridge 充当「长程」  
* Docking、anti-stagnation、Pure Pursuit 替 π；**默认打开 heading assist 刷主指标**  
* 关罩或 `safety.kind=null`  
* 放宽到达合同或起终点重合刷 SR  
* 只加「靠近+少撞」、把侧移蹭点当成功；或用「最短路径」效率罚扼杀合法绕障  
* 把坐标目标结果写成「单目认出目标」；或把 GT 位姿写成「RGB+IMU+高度计定位已闭环」；或暗示「不要 IMU/高度计」  
* 宣称仅靠 IMU+高度计（无视觉融合）即可无漂完成 100 m+ 水平到点   
* 无全局规划却宣称跨街区 200–500 m 已过门  
* 忽略 F9/F10/F15 却宣称「阶段 1 已证明故 Phase 2 必过」  
* 只报汇总指标、不看每路场景几何/航迹就下刀修根因

---

## 7. 当前下一步（默认）

**主方案（2026-09-03 重置）**：[`docs/superpowers/specs/2026-09-03-phase2-goal-scene-nav-design.md`](../../docs/superpowers/specs/2026-09-03-phase2-goal-scene-nav-design.md)  
**实现计划**：[`docs/superpowers/plans/2026-09-03-phase2-goal-scene-nav.md`](../../docs/superpowers/plans/2026-09-03-phase2-goal-scene-nav.md)

```text
G + 场景 → WAM 外环生成近距意图 c* → Phase-1 执行 → 罩
停机：‖p−G‖≤3　｜　无预置航迹　｜　主尺度 200–500 m
```

1. **E0 已判**（[`WAM_PHASE2_GOAL_SCENE_E0_DECLARE.md`](../../docs/handover/WAM_PHASE2_GOAL_SCENE_E0_DECLARE.md)）：接线绿灯（`toward_g` closure 0.487 > `polyline` 0.370；`direct_g` 明确劣化），**导航红灯**（SR=0，F12 未解）。**下一刀**：跑 E1 `scene`（110/125 并行，各一路）并填 [`WAM_PHASE2_GOAL_SCENE_E1_DECLARE.md`](../../docs/handover/WAM_PHASE2_GOAL_SCENE_E1_DECLARE.md)（阈值已预注册）。  
2. 标注折线 / `--rolling-global` 仅作水位对照，不进主控默认。  
3. 禁止：古典跟线当北星；F15/assist 刷指标；把 Prog/CTE 当准出；用短距宣称 200–500 已过门。

**E0/E1 CLI（默认仍 `polyline`，DECLARE 前不改默认）**：

```bash
# E0 main
python -m experiments.aerial.scripts.wam_phase2_long_eval \
  --subgoal-source toward_g --planner --episodes 2 --max-steps 400 \
  --out artifacts/wam_phase2_e0_toward_g_probe.json

# ablation A / waterline / E1
  --subgoal-source direct_g
  --subgoal-source polyline
  --subgoal-source scene
```

### 7.1 多机并行（`--routes` + 合表）

两台 GPU 机都空闲时按路拆分，串行 ~1–1.5 h → 并行 ~20–40 min。**不拆标注文件**：`--routes` 收 0-based 标注下标并**覆盖 `--episodes`**，输出里的 `route_idx` / `base_route_idx` 仍是真下标。

```bash
# .110
python -m experiments.aerial.scripts.wam_phase2_long_eval --subgoal-source scene \
  --planner --routes 0 --max-steps 400 --out artifacts/wam_phase2_e1_scene_r01_110.json
# .125（同时）
python -m experiments.aerial.scripts.wam_phase2_long_eval --subgoal-source scene \
  --planner --routes 1 --max-steps 400 --out artifacts/wam_phase2_e1_scene_r02_125.json
# 合表（不需要 torch，Mac 也能跑）
python -m experiments.aerial.scripts.merge_phase2_split_eval \
  --out artifacts/wam_phase2_e1_scene_merged.json \
  artifacts/wam_phase2_e1_scene_r01_110.json artifacts/wam_phase2_e1_scene_r02_125.json
```

纪律：

- **单台 JSON 的 `Verdict` 是子集上的，无意义**；日志会打 `PARTIAL RUN: ...`。DECLARE 只准填合表 JSON 的数。
- 合表用**与评测器同一个 `aggregate_metrics`**，禁止手工平均（`max_intent_dev_deg` 是 max 不是 mean）。
- 臂身份不一致（`protocol_version` / `subgoal_source` / `goal_feat_mode` / `actor_ckpt` / `cruise_speed_m_s` / `rolling_global`）或两台 `--routes` 重叠 ⇒ 合表脚本 refuse 退出。
- **同一臂内换机会引入机器差**：若某路指标落在该臂 gate 阈值 ±0.05 内，先在与对照同机重跑该路再判。旁证：E0 route 01 `d_min` 110 = 52.28 / 125 = 52.25。
- ACCESS.md 中「125 不跑 eval」限制**已作废**（2026-09-03，原因是当时 125 在跑别的 project）。

**纪律**：输入只有 G+场景；「线」只是想象副产品；过门尺 **200–500 m**。
