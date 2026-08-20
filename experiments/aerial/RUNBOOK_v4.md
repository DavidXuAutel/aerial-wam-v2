# V4-MVP RUNBOOK（判据 v2，2026-08-20 签字后的干净执行稿）

> **本文件是什么**：V4 的**执行**入口 —— 按序做什么、每步产物是什么、跑前必须先定死什么、必须先实测什么、什么情况下停。
> **本文件不是什么**：不是判据的权威定义源。**判据的唯一权威口径 = [`V4_CRITERIA_REFREEZE_PROPOSAL_20260818.md`](../../docs/handover/V4_CRITERIA_REFREEZE_PROPOSAL_20260818.md) §4.6（含 §4.6.8–§4.6.12）**；签字记录 = 同文件 **§5.0**（16/16 行，2026-08-20）。本文件与 §4.6 有任何不一致 ⇒ **以 §4.6 为准**，并回来改本文件。
> **不得照 §1 / §2 实施**（那是事前预注册记录，已被 §4.5 D1–D4 证明与冻结实现冲突，按审计链保留不改写）。
> **判据已 re-freeze（2026-08-20）**：实施过程中改任何阈值 / band `[lo,hi]` / `n` / primary-secondary 划分 ⇒ 必须回 §5.0 **重开表重签**，不得就地改。

---

## 0. 一页速览

| | |
|---|---|
| **目标** | 分层到达：`S_open` 不退化 + `S_blocked` 逼障绕行（**「逼障」仅当 ⓪f 证出可行带才入 merge**） |
| **信号** | **V4-⓪**（近带深度）、**V4-⓿**（想象排序一致性）、**V4-①′**（分层到达）、**V4-④′**（安全不回归 + 反空过） |
| **merge** | `⓪ ∧ ⓿ ∧ ①′ ∧ ④′`，其中 `①′ = S_open primary 全过 ∧ S_blocked primary 全过` |
| **n** | 每层 **16**（合计 32）；不足 ⇒ `authoritative=false`，**禁止降 n** |
| **评测构型** | **shield-on 单一构型**，罩 = **现行第 (4) 代**（latch + 有界状态反馈后退）。**v5 不启用**，`P3.5` 本周期 **N/A** |
| **当前状态** | 判据已签字冻结；**下一步 = P3**。已完成：P0 ✅ / **P0c ✅**（正式跑 n=16 `authoritative=true`）/ **P1 ❌ FAIL**（仅 reward；修 = P4.5 后重跑）/ **P2 接线 ✅**（头 AUROC 仍待 P4.5）/ **P6 ✅**。`enable_policy_update` = **false** |
| **主张范围** | 只主张「**不退化 + 安全**」，**不主张「想象 AC 有增益」**；到达能力**仅覆盖机体前向扇区**；「主动终止」**不测** |

**机器分工**（不再逐次确认）：**8×H100** `a25689@10.239.121.25:31126` = 训练 / 数据 / 离线诊断；**4090** `10.229.20.125:41451` = **纯渲染**（gate、探针、planner、闭环 rollout 都在这跑）。

---

## 1. 前提链（**必须按序，不是并行**）

| 步 | 内容 | 跑在哪 | 产物 / 通过条件 | 状态 |
|---|---|---|---|---|
| **P0** | R1 落地（`imagine` aux progress = analytic Δ‖g‖） | H100 + 125 | 校准比值 **1.00 PASS**；① 仍 FAIL（`n=5` 非全权） | ✅ **DONE**（`30b9ff8` / `d96da1d`） |
| **P0c** | **修评测期丢局**（`v4_gate_run_partials.py` 的 `_run_one_resilient` 里 `if ep_on is None: continue` 吞局） | 125 | ①三互斥计数器落盘 `n_invalid_spawn` / `n_none_returned` / `n_pair_broken`；②用**预留 spare 起点**补扫到每层 16（spare 清单与消耗顺序**跑前落盘**，禁临时新采）；③仍不足 ⇒ `authoritative=false` **且必须报三计数器**；④**禁止用降 n 解决** | ✅ **DONE（2026-08-20）** — harness `e28baa9`；正式跑 `v4_gate_p0c_formal_20260820/`（`--target-n 16 --spare-count 16`）。**①**：`n_scored=16` `authoritative=true` spare_consumed=**8** / invalid=**3** / none=**0** / pair_broken=**5**。**④ on**：n=16 auth spare=**7** / inv=**3** / none=**0** / pair=**4**；**④ off**：spare=**9** / inv=**2** / none=**0** / pair=**7**；**④ v1**：spare=**11** / inv=**10** / none=**0** / pair=**1**。旧 actor 上 ①/④ 信号 `ok=False` **不否定** P0c（机制 PASS） |
| **P1** | 在 V4 实际用的 RH 线 WM 上重跑 **V1-②** + 校准子项 | H100 | V1-② 判据。注：「RH 头 forward ratio ∈ [0.8,1.2]」**已降为诊断**（R1 后 actor/aux 不再消费该读出） | ❌ **FAIL（2026-08-20）** — `wm_ckpt_r60_rh_20260816` step=1000，held-out 12/48 尾部，log `artifacts/v4_p1_fidelity_rh_20260820.log`。**按 §1.2.2（`v1_metrics.check_wm_fidelity`）重记**：reward ❌ `beat_frac=0.67 < 0.80`（`growth_ok=True`；`one_step_ok=True` — h=0 wm_mae **0.5817 <** mean-base **0.6508**）／p_coll **`null` N/A**（`coll_traj_pos=1 < 3`，raw AUROC 0.091 **不是**权威 FAIL）／done **PASS 但 vacuous**（`acc=0.994 == majority`）／recon+latent ✅（19.89 ≤ 25.0）。⇒ **FAIL 完全且仅由 reward 支撑**。修复走 **P4.5**（重训后重跑 P1），不跳过 |
| **P2** | **`p_coll` 复活** | H100 + 125 | 头 AUROC 达标 **不足以**收工：**collector 与 V4 gate 都必须以 `should_override(obs, wm_out=…)` 调用**。未接线 ⇒ ⓪f 重跑仍只测 D̂/τ 两通道 | ✅ **接线 DONE（`4e76865`）** — collector/gate 已传 `wm_out`。头侧：P1 上 coll **N/A**（pos<3）；AUROC claimed 仍待合适 held-out / **P4.5** 重训后重证 |
| **P3** | **V4-⓪ v2**（⓪a–⓪f，见 §2.1） | H100 离线 | **⓪f 是 `[lo,hi]` 的唯一合法依据**；P3 不出 ⓪f ⇒ 5ab 分叉无法裁 | 🔄 **IN FLIGHT（2026-08-20）** — harness `663d8bb`；H100 retry after `8a4e851`（tau mask broadcast）；log `logs/v4_p3_zero_20260820.log` → `artifacts/v4_zero_p3_20260820.json` |
| **P3.5** | ~~shield v5 回归验证~~ | — | **本周期 N/A**（5am / W2：v5 降 fallback，「不动 shield」）。`release_step[]` / `n_release` 仍落盘、无 v5 时恒 0 | 🚫 **N/A** |
| **P4** | **V4-⓿ v2**（想象排序一致性） | H100 + 125 | 含 ⓿d（真实侧 G 写死 = analytic）、⓿e（**teleport 能否复现同一 `z0` 须先实测**） | ⬜ |
| **P4.5** | 语料重采（`S_open : S_blocked ≈ 1:1`）+ WM 重训 ⇒ **重跑 P1 / P4** | H100 + 125 | 否则 P1 给一个注定被替换的 WM 发证 | ⬜ |
| **P5** | shield 触发深度 3.0 → 2.0 裁定 | — | **暂缓**；G1 之后其两个理由都失效 ⇒ **很可能完全不必要**；方向也可能相反（由撞点落盘裁定） | ⏸ |
| **P6** | `planner.action_limits` 夹到 `body_delta_limits(1/step_hz)` | 代码 | 现默认 `None` | ✅ **DONE（`4e76865`）** — `_build_planner` 设 `action_limits = body_delta_limits(1/step_hz)` |
| **P7-diag** | planner 纯前向跑 **诊断起点集 `S_diag`** | 125 | **只落盘不判**：逐步 `clearance_fov` ⇒ 得 `C_P7` 分布；判据里 `θ := undefined` | ⬜ |
| **⟶ 冻结** | 先冻 **`[lo,hi]`**（⓪f ∧ `hi ≤ Q_0.25(C_P7)` ∧ `hi ≤ 8 m`）**加时间戳** ⇒ 再在**同一份逐步 log** 上算 `band_frac` ⇒ 冻 **`θ = 0.8 × median_P7`**、冻 **`k`** | 离线 | **不必再飞**。**禁止**「看到 `band_frac` 分布后再改 `hi`」 | ⬜ |
| **P7-accept** | planner 在 **`S_accept`** 上跑 **§4.6.3 全判据**（此时 θ 已是外生常数） | 125 | `S_diag` ⟂ `{S_accept ∪ actor gate}`；**`S_accept` ≡ `S_gate`**（actor 必须飞同一批起点） | ⬜ |
| **⟶ 下车站** | **P7-accept 在 S_blocked FAIL ⇒ 停** | — | 见 §6 | — |
| **P8** | 才训 actor（**从零，禁 warm-start**）⇒ gate ①′ / ④′ | H100 训 + 125 gate | `enable_policy_update` 仍**由四信号全过前不翻** | ⬜ |

---

## 2. 判据（执行口径，权威定义见 §4.6）

### 2.1 V4-⓪ 近带深度（P3）

| 子项 | PASS | 备注 |
|---|---|---|
| ⓪a | `median AbsRel ≤ 0.30` on `D_gt ∈ (0, 3.0]` | 不动 |
| ⓪b | support ≥ 1e4 px **且** `n_frames_with_near_px ≥ 100`、单帧贡献占比 ≤ 0.2 | 防「全部像素来自一帧」 |
| ⓪c | `p90 AbsRel ≤ 0.50`（同像素域） | median 允许一半像素任意坏 |
| ⓪d（功能项） | `P(D̂_fwd > trigger \| D_gt_fwd ≤ trigger) ≤ 0.05`，**且不得出现 ≥2 连续漏触发帧** | `trigger` = 部署 `min_depth_m` |
| ⓪e | 测试分布 = **部署分布**（评测起点集实际帧），不得只用训练 holdout | |
| **⓪f** | 在 **`D_gt ∈ (3.0, 8.0]`** 上报：`median AbsRel`、`p90 AbsRel`、**D̂ 误触发率** `P(D̂ < min_depth_m \| D_gt ∈ [lo,hi]) ≤ 0.05`、**τ 误触发率** `P(τ̂ < min_tau_s \| d_fwd/v_fwd ≥ 2·min_tau_s) ≤ 0.05`；逐帧 support 同 ⓪b | **⓪f 出数前 `[lo,hi]` 一律不填数** |

P5 若改 `min_depth_m` ⇒ **⓪d 与 ⓪f 必须按新 trigger 重测**。

### 2.2 V4-⓿ 想象排序一致性（P4）

`⓿a/b/c`：Spearman ρ median ≥ 0.50（`n_z0 ≥ 8`）、top-1 ≥ 0.50、**禁 Pearson、禁混 horizon**。
`⓿d`：**真实侧 G 写死 = analytic（纯位置几何）**，想象侧 = 模型自身。
`⓿e`：`z0` 来源 + **AirSim teleport 能否复现同一 `z0` 必须先实测**，不能假设。

### 2.3 V4-①′ 分层到达（P7 / P8）

**起点池**：用 `candidate_positions`（真实 rollout 位姿 + teleport 询问），**不用** `make_start_episodes`。
**准入只有两条**：`start_clearance_m ≥ 3.0` 实测通过；非 spawn-in-collision。**层标签只由探针给**（不做深度窗准入）。
**到达定义（已签死）**：`arrival ⟺ min_t dist(p_t, g) ≤ 3.0 m`（曾进入 3 m 球即算，离线由落盘位姿算）。**不改 rollout 控制流**（`max_steps` 跑满），路径长在**首次到达步 `T_arr`** 截断。

| 子项 | 层 | PASS |
|---|---|---|
| ①′a-o | S_open | `arrival_rate_actor ≥ 0.875` |
| ①′b-o | S_open | `median path_efficiency ≥ 0.90`，`path_efficiency = (‖g−p₀‖ − 3.0) / Σ_{t<T_arr}‖Δp_t‖` |
| ①′c-o | S_open | `hard_coll_rate_actor = 0` |
| ①′a-b | S_blocked | `arrival_rate_actor ≥ 0.50` |
| ①′b-b | S_blocked | **改为「分层器确定性自检」**：同起点重复探针 `R ≥ 3` 次标签一致率 **= 1.0**；不成立 ⇒ **gate 作废（harness 病）**，不是 actor FAIL。原「`arrival_rate_heuristic = 0`」降为构造性事实、只落盘 |
| ①′c-b | S_blocked | `median path_efficiency ≥ 0.70`（同上分子/截断口径） |
| ①′d-b | S_blocked | `median band_frac ≥ θ`；**primary / secondary 由 5ab 跑前分叉决定**（见 §3） |

**in-band 判定（`_breached` 逐字展开，缺一不可）** —— 一步计入 band **当且仅当**：
1. `D̂_fovmin ≥ 3.0` **∧** `τ̂ ≥ 1.0` **∧** `p_coll ≤ 0.5`（= `NOT _breached(step)`），**且**
2. `engaged == false`，**且**
3. `clearance_fov ∈ [lo, hi]`。

> 条件 1 与 2 是**合取不是替代**：`engaged=false` 只排除已 latch 的步，「本步刚破尚未 latch」仍会被误计入。

**band 是速度条件的**：在 clearance `d` 处不被接管要求 `v_fwd ≤ d / min_tau_s`（1.0 s）⇒ **「逼障」的可证明含义 = 「减速贴障通过」，不是高速贴障**；合格域定义在 `(clearance, v_fwd)` 联合平面上并跑前冻结。
**`clearance_fov` 定义**：离线位姿回放，取**整幅 GT 深度图的 min**（与 `depth_predictor.predict_min` 同几何，**不引入 FOV 外方位**）；`cone_clearances` 五向只作诊断。
**`band_frac` 两版都预注册、primary 取更严者**：(a) **进展加权**（一步入 band 还须在 `k` 步窗口内 `dist(p,g)` 严格下降）；(b) **路径长加权** `band_path_len / total_path_len`。旧的纯时间占比 `frac_steps_in_band` **降为诊断**。
**band 分母**：只计 `engaged=false` 且属到达局的步；接管步单独落盘。
**公共子集 `P`** = **P7 planner 到达的 start**（跑前确定、与被测策略无关），`P ⊆ S_accept` ⇒ **actor 的 gate 起点集必须 = `S_accept`**。`s ∈ P` 但 actor 未到达 ⇒ `path_efficiency := 0`、`frac_steps_in_band := 0` **计入 median**（不剔除、不 NaN）；要求 **`|P| ≥ 8`**，否则 ①′c-b/①′d-b 记 `authoritative=false`。
**诊断（不入 merge）**：`path_efficiency_heuristic`（shield-**off**，应 ≈1.0）+ shield-**on** 同项（= 经验效率上界兼罩过敏判别）；累计 yaw 转角（原地转 yaw 不被 `path_efficiency` 罚，只被 `max_steps` 约束）。
**盲对照臂（入报告不入 merge）**：用**时序打乱 / 错配帧**（**不用置零图** —— 那是 OOD）。三分支判读：① 盲臂 S_open 过 / S_blocked FAIL ⇒ gate 依赖视觉；② 两层都过 ⇒ **gate 与视觉无关，结论作废**；③ 两层都 FAIL ⇒ **inconclusive**，不得当作「依赖视觉」的证据。

### 2.4 V4-④′ 安全不回归 + 反空过（P8）

**只在 S_blocked 判**（S_open 的安全由 ①′c-o 承担）。

| 子项 | PASS |
|---|---|
| ④′a | `hard_coll_rate_on = 0` |
| ④′b | `near_coll_rate_on / near_coll_rate_off ≤ 0.80`（**`1.5 m` 与 `0.80` 一字不动**）；**可解释前提**：落盘两臂总步数 + 命中数 + 每局步数直方图，预注册「ratio 只在两臂步数量级可比时可解释」 |
| ④′c | 定义**遭遇机会** `K_off = #{steps: 前向 GT 深度 < 3.0 m, off 臂}`。`K_off ≥ 5` 且 `near_coll_rate_off == 0` ⇒ 记 **`N/A` 不入 merge（不是 FAIL）**；`K_off < 5` ⇒ 记 `vacuous` 不入 merge，**重跑有条件**：仅当 ①′a-b PASS 才重采起点补遭遇机会；①′a-b FAIL ⇒ gate 已 FAIL，**不重跑** |
| ④′d | 旧 ④b（接触前干预 ≥ 0.50）；`n_contact = 0` ⇒ N/A（洞 2 口径不动） |
| 诊断 | shield-**off** 臂 `hard_coll_rate` 随训练下降（④′ 现口径测的是**罩**不是策略，E2） |
| V1 对照臂 | **正式移除**，登记为已知代价 |

---

## 3. 【跑前必须先判断 / 先冻结】—— 不定完不许开跑

> 纪律：下列每一项都必须**在看到相应数据之前**定死并**加时间戳落盘**。事后定 = p-hacking = 撞红线。
> 已签字的部分不得再动；标 ⬜ 的是**填空**（只许按已签公式机械填、只许缩窄），不是重新裁定。

| # | 要定的东西 | 谁定 / 怎么定 | 依赖 | 状态 |
|---|---|---|---|---|
| 1 | **`[lo, hi]`**（逼障带） | `lo = min_depth_m + δ`，`δ` = 「D̂ 与 τ 误触发率**均 ≤ 0.05**」的最小 clearance；宽度 1.5 m；`hi ≤ Q_0.25(C_P7)` **且** `hi ≤ 8 m`（后者**如实登记为拍的**，只与 ⓪f support 上界对齐） | **⓪f**（P3）+ **P7-diag** | ⬜ 待实测填 |
| 2 | **`θ`**（band 占用阈值） | `θ = 0.8 × median(band_frac_P7-diag)`，裕度系数 **0.8 已冻结**；**在已冻的 `[lo,hi]` 上、用同一份 P7-diag 逐步 log 算**（不必再飞）。若重导值 **< 0.10 ⇒ 属放松 ⇒ 须单独签字**，不得静默采用 | P7-diag（须先冻 `[lo,hi]`） | ⬜ 待实测填 |
| 3 | **`k`**（进展窗口） | 与 C1「进带前 k 步」的 `k` **是否同一个数未定 ⇒ 跑前必须一并冻结** | 无（人定） | ⬜ **待定，两处同时冻** |
| 4 | **`Q_0.25(C_P7)`** | `C_P7` = P7-diag 中 planner 在 S_blocked **实际经过的 clearance 分布**；分位 `p = 0.25` **已冻结** | P7-diag | ⬜ 待实测填 |
| 5 | **5ab 分叉：①′d-b 是 primary 还是 secondary** | ⓪f + τ 误触发出数后：**存在**同时满足「并集非介入」与「`hi ≤ Q_0.25(C_P7)`」的带 ⇒ 冻结该带、①′d-b **保持 primary**；**不存在** ⇒ **降 secondary（只报不入 merge）**，机制主张全部落到 **⓿ + P7** | ⓪f | ✅ **分叉规则已签死**（分支由数据选，不是人事后选） |
| 6 | **band 冻结的时序 vs P2** | 正式冻结**排在 P2 之后**；若为进度先用 P2 前的数 ⇒ 必须写 `band_frozen_before_p2 = true` 并标该带 **conditional**，P2 落地后**强制重跑 ⓪f + 重裁 5ab**，且**只许缩窄** | P2 | ✅ 规则已签；**走哪条须跑前声明** |
| 7 | **primary / secondary 划分** | 15 条全 AND ⇒ 误 FAIL ≈54% ⇒ 必须显式分开，**primary 条数跑前冻结** | 无 | ⬜ **待写死清单** |
| 8 | **OC 曲线 + seed 数 + 「两 seed 不一致」的裁决规则** | 每条判据**跑前**落盘 OC 曲线；预注册 seed 数与裁决规则；声明 primary/secondary | 需起点几何独立性成立 | ⬜ **待做** |
| 9 | **起点几何独立性下限** | 落盘起点两两最小间距；预注册下限 **≥ 10 m**；不满足 ⇒ 二项功效计算无效 ⇒ **重采起点** | 无 | ✅ 数值已提；⬜ 待实测校验 |
| 10 | **三个起点集的关系** | `S_diag` ⟂ `{S_accept ∪ actor gate}`；**`S_accept` ≡ `S_gate`**；训练起点集与三者**全部互斥**（seed / 场景区域显式互斥并落盘）。任何重叠 ⇒ `θ` 记 `authoritative=false` | 无 | ✅ **已签死** |
| 11 | **spare 起点清单与消耗顺序** | 跑前从同一起点池多采并落盘；**禁止临时新采**。**spare 池大小**：对 `target_n=16`，**`--spare-count=16`**（选项 1 固定缓冲；2026-08-20 人签） | 无 | ✅ **已定**（`--spare-count=16`） |
| 12 | **冻结清单** | 到达半径 3.0、`max_steps`、时间预算、`cruise_alt_m`、`goal_dist_m = 30`、**候选起点池来源（哪个 rollout dataset）**、探针参数。**v5 三参数（`release_depth_m`/`M`/上限）本周期不进冻结清单** | 无 | ⬜ **待逐项写死数值/出处** |
| 13 | **分层器重复次数 `R`** | `R ≥ 3`（含变 env seed / 渲染随机性），一致率必须 = 1.0 | 无 | ✅ 已定 |
| 14 | **`Δ`（5ag 非劣裕度）** | `Δ = 0` **已冻结在案**；因签 **5ag(B)** 本周期**无适用对象**，日后 V5 另案启用时**不得届时另议 `Δ`** | 无 | ✅ 已冻结（暂不适用） |
| 15 | **盲对照臂的打乱方式** | 同 episode 内随机换帧，或换用另一 start 的帧流；**不得用置零图** | 无 | ✅ 口径已定；⬜ 实现待定 |
| 16 | **到达定义** | `min_t dist(p_t, g) ≤ 3.0 m`，**不改 rollout 控制流** | 无 | ✅ **已签死** |

---

## 4. 【必须实测、不许假设】

> 红线：**「`step_hz` 实测不猜」**。下列每一项都有「假设错了就悄悄改变了被测系统」的实证前科。

| # | 必测项 | 为什么（前科 / 机制） | 不测的后果 |
|---|---|---|---|
| 1 | **`step_hz` 重测并冻结** | 必须在 **shield-on 且逐步跑 D̂/τ/p_coll** 的构型下测（D̂ 是网络前向，与渲染 GT 是两件事） | 全部时间口径（τ、制动余量、band 占比）失真 |
| 2 | **τ 预测器实测 `dt` 直方图 + 「是否用过 `dt_s` 默认回退」标志** | `tau_predictor.py:289` 默认 `dt_s=0.1`（10 Hz），而 `configs/aerial_rl.yaml:20` `step_hz=5.0`（dt=0.2）；`:330-333` 仅在 `obs.t` 有限且单调时才覆盖 ⇒ 回退一旦发生 **τ 秒数减半、触发面约翻倍 = 悄悄改了部署罩** | 用过回退 ⇒ **`authoritative=false`**（进 self-check） |
| 3 | **⓪f：`D_gt ∈ (3.0, 8.0]` 的 D̂ 精度 + D̂/τ 双通道误触发率** | ⓪a 的 support 只到 3.0 m ⇒ **GT > 3 m 区从未测过**；晚⁷ diag `P(over-read) = 0.377`（既非一致欠读也非一致过读）⇒ 从 `GT1.5→D̂0.645` 外推 gain **无依据** | `[lo,hi]` 无合法依据 ⇒ ①′d-b 不可裁 |
| 4 | **teleport 能否复现同一 `z0`**（⓿e） | 精确状态重置是 ⓿ 全部结论的前提 | ⓿ 的 ρ 可能测的是重置噪声 |
| 5 | **起点两两最小间距** | 「32 局 = 同点 32 射线」的老病（`make_start_episodes` 全局共用 `[0,0,cruise_alt]`） | B3 的二项功效计算无效 |
| 6 | **分层器标签一致率**（`R ≥ 3`） | 分层是 ①′ 全部结论的地基 | 不一致 ⇒ **gate 作废（harness 病）** |
| 7 | **`C_P7` clearance 分布 + `median band_frac`（P7-diag）** | 「逼障」与 `θ` 唯一合法锚 | `θ` 失锚、`hi` 变拍脑袋 |
| 8 | **`K_off`（off 臂遭遇机会）** | 旧 ④ 被横漂空过的直接病根 | ④ 记 PASS 而其实 vacuous |
| 9 | **S_open 的 `intervention_rate`**（应 ≈ 0） | S_open FAIL 时**分不清罩过敏还是策略坏** | ①′a-o 的 FAIL 无法归因 |
| 10 | **进带前 `k` 步的 `D̂_fovmin` / `v_fwd` / 侧向位移**（C1） | ①′d-b 只剩结果不剩机制 | 带为空 / 带很高时都无法解释 |
| 11 | **碰撞局撞点 7 项**（5d） | 三分失效源必须可分：`steps_to_collision`、`d_first_contact`、撞点前 5 步的 `D̂_forward` 与 `D_gt_forward`、`intervention` 标志、shield 触发步号 | 无法区分「深度不可信」/「shield 消费路径」/「反应余量不足」；**P5 的方向也无从裁定** |
| 12 | **`action_commanded`**（shield 覆盖**前**的指令动作，5e） | 否则策略行为与罩行为不可分离 | ④′ 只能测罩 |
| 13 | **GT 深度只允许离线位姿回放取** | 在线取 GT ⇒ ~3 Hz ⇒ **dt 变** ⇒ 改了被测系统（A2）。已核对：τ 通道是**纯视觉**（`use_gt_depth=False`），A2 与部署罩**不冲突**（H7） | 闭环速率与部署不一致 ⇒ 结论不可比 |

---

## 5. 落盘契约（**缺字段 ⇒ gate 直接 `authoritative=false`**，进 self-check，不靠人工核）

- §1.0 全部原有字段
- `latch_step[]`、`release_step[]`、`n_release`、`frac_steps_engaged`、latch 时 `shield_channels`（无 v5 时 `release_step[]`/`n_release` 恒 0）
- 两臂**总步数与命中数**、每局步数直方图（E1）
- **累计 yaw 转角**（F2）
- `n_invalid_spawn` / `n_none_returned` / `n_pair_broken`（P0c）
- **碰撞局撞点 7 项**（5d，见 §4-11）
- **`action_commanded`**（shield 覆盖前的指令动作，5e）
- `angle(yaw_forward, velocity)`（5k）
- **`_breached` 三通道各自的布尔位** + `v_fwd` / `τ̂` / `p_coll` / `D̂_fovmin` / `engaged`（5z）—— **哪条通道破的必须可分离**，否则带为空时无法归因
- **τ 实测 dt 直方图 + `dt_s` 回退标志**（5ac-c）
- **S_open 的 `intervention_rate`**（C2）
- **进带前 k 步的 `D̂_fovmin` / `v_fwd` / 侧向位移**（C1）
- 逐步 `clearance_fov` + `cone_clearances` 五向分解（诊断）

---

## 6. 停止规则 / 下车站（预注册，FAIL 后不许「换个条件再跑一次」）

**P7-accept 在 S_blocked FAIL**（planner 纯前向 + 真实感知都到不了 ⇒ 该层在当前 WM / 罩 / 场景下**经验不可解**）⇒
1. **不进 P8**（不训 actor，`enable_policy_update` 保持 false）；
2. 判定 **「V4-MVP 的前提被否证」**，写进 `V4_GATE_STATUS.md`；
3. 退回 **WM / 感知侧**（P1 / P3 / P4.5 的重训与语料），或裁定 S_blocked 场景难度本身需 re-freeze（**另案，须新签字**）；
4. **明令禁止的三种反应**：降 S_blocked 到达率阈值 / 换更容易的起点集后宣布 P7 过 / 把 ①′ 只在 S_open 上判。

**已如实登记的最大风险（5am(d)）**：v5 不启用 ⇒ **一次触发即整局 latch、本局报废**（`safety.py` `if self._engaged: return True`），而 τ 通道在 `v = 5 m/s` 巡航下触发到 **≈5 m** ⇒ **①′a-b ≥ 0.50 的经验可解性完全押在 P7-accept 上**（G1 只论证了「带定义不与罩互斥」，**未论证到达率**）。P7-accept FAIL ⇒ 走上面的下车站，**不得就地放宽阈值、不得顺势启用 v5**。

**仍未预注册停止规则的缺口（R-16 剩余，如实登记）**：**⓪ / ⓿ / P3.5 各自 FAIL 后**没有下车站。

---

## 7. 主张范围（签字随附，**不得外推**）

1. **不主张「想象 AC 有增益」**（5ag(B)）—— V4-MVP 只主张「**不退化 + 安全**」。⇒ **V4 不对「世界模型想象是否有用」出证**，该主张留 **V5 另案**（届时按配对检验 + 跑前冻结 `Δ=0` 预注册）。
2. **到达能力仅覆盖机体前向扇区**（5af(a)）—— **侧向 / 后向 goal 本周期不测**；In-表（goal 进 π 的表示）改动属 **V3 另案**。⇒ ①′ 结论**不得读成全向导航能力**。
3. **「主动终止」out of scope**（5p 后半）—— policy 自主停止**一条判据都没有**，登记为最终目标的未覆盖维度。
4. 「逼障」的可证明含义已收窄为「**贴着罩的 standoff 边缘、减速做紧绕行**」，**不是**「飞进 `[1.5, 3.0]` 近碰带」—— 后者被部署罩**结构性禁止**，任何要求它的判据都是在要求策略违反安全罩。

---

## 8. 红线（实施期间一条都不许碰）

- **四信号全过前不翻 flags**；`enable_policy_update` **绝不顺带打开**。
- **不为凑过调阈值 / shield 参数** —— shield **控制律**是被测系统（可改）；§4.1 **阈值**不可改（改需 re-freeze）。**不降低 V0/V1 阈值凑过**。
- **禁止 tied-zero 式「双零安全」冒充 ④**。
- 训练时 **shield / τ / depth 路径与 V1 部署一致**；**禁止为过 gate 关掉安全罩**。
- 代码走 **git**，**禁 scp 热补丁**；**`step_hz` 实测不猜**。
- 干净重训**禁 warm-start 失效 ckpt**；canonical `depth_step_5000.pt` **不动**；失效 ckpt **归档保留**。
- **goal 张量输入属 V3**，本周期不给 RSSM 加 goal 输入。
- **不 push GitHub**（除非明确要求）。
- **不降 `n`**（P0c 用补扫解决，不用降 n 解决）。

---

## 9. 已知残余风险（不解、只登记）

| 项 | 内容 |
|---|---|
| R-1 | 「绕大圈 vs 贴障」目标函数区分力弱（≈8%） |
| R-3 / P2 | `p_coll` 现为死值；**即使头活了，`collector.py:185` 仍不传 `wm_out`** ⇒ 第三条通道在采集环里可能仍是哑的 |
| R-16 剩余 | ⓪ / ⓿ / P3.5 各自 FAIL 后无预注册停止规则 |
| 5p 后半 | 「主动终止」零判据 |
| — | `S_blocked_tight` 的 `n` 未定 |
| — | ④′b 用**全场 min** vs ④′c 用**前向遭遇**，两者几何不同 |
| — | ~~P0c 的 spare 池大小未定量~~ → **已定** `--spare-count=16`（2026-08-20） |
| — | 无 v5 时「一次触发即报废」对 ①′a-b 的实际难度**未量化**（只能等 P7-accept 实测） |
| — | C1 的 `k` 与 5ac(a) 的 `k` 是否同一个数**未定** |
| P0b | shield 消费路径仍是 `predict_min`，`predict_cones()` 未接线 |
| — | 头一致性缺口：`depth_ckpt_da3_20260810` vs `depth_ckpt_da3_near_20260811` |
| — | `advance_goal_rel_body`（`goal_features.py:60-73`）**不按 `a[3]` 旋转** body-frame goal ⇒ 任何 yaw≠0 的臂喂给 RH 的 goal 失真（改它会改 §A 全部数字 ⇒ **走签字**） |
| — | ~~`planner.action_limits` 默认 `None`~~ → **P6 DONE**（`4e76865`）；yaml `imagination.horizon: 10` vs 权威 H=15；`open_ahead` 拒收数 708 vs 15（47×）扫描行为不稳 |

---

## 10. 变更记录

- **2026-08-20（实施进度入库）** —— 前提链表与 §0「当前状态」更新为：**P0c / P2 接线 / P6 DONE**；**P1 FAIL**（权威层仅 reward）；**下一步 = P3**。P0c 正式跑数值见 §1 行；`--spare-count=16` 已签（§3 #11）。不改判据 / 不翻 flag。
- **2026-08-20** —— 新建本文件（V4 执行 runbook 干净稿）。**为什么 / 依据**：§5.0 削减签字表 16/16 行已于 2026-08-20 签字冻结，权威判据（§4.6）已无未决二选一 ⇒ 需要一份**只讲怎么执行**的入口，把散在九轮复核里的「跑前必须冻结」（§3）与「必须实测」（§4）**收成两张可勾的清单**。本文件**不新增、不修改任何判据**；一切定义以提案 §4.6 为准。
