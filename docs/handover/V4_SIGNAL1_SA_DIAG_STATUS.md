# V4 §A / §A.3 imagined return decomp (125, 2026-08-18)

- **status**: **A.2 done · A.3 done → 判定作废 · A.4 DONE = `fwdmax_ge_pi`（seed=0）；处置写法已修正（C1 不够，见末节）→ 「动作空间一致性裁定」已签 = **C2 有界策略分布**（2026-08-18，代码已落地）** (read-only)
- **⚠️ 本文档全部数字产自 pre-C2 无界策略类**（ckpt 无 `policy_class` ⇒ 载入判为 `unbounded_gaussian_legacy`），保留为**审计链**、可逐位回放；`v4_imagine_return_decomp.py` 只 evaluate 不训练，故仍能复现。**下一件 = 用 C2 从零重训后的 π 重跑 §A/§A.3/§A.4**，届时 `n_action_clipped` 应为 **0**（`--clip-actions` 成为 no-op），本文档**另起新节**记录、不覆盖旧数字。
- **⚠️ 读者先读「A.3 判定作废」再读 §A.4**：`b3_le_a` 字面成立但臂无效，「先修 RH」**不成立**；A.4 已跑，倒挂来自无界动作通道，**仍不是 RH 案**
- **seed=0**：A.4 / A.3traj 同 seed；A.2 两次无 seed 跑（`14d0f06` / `2afcb33`）同 ckpt 同 z0 结果不同（前飞 λG0 47.02→49.65，+5.6%），已 superseded 为审计链
- **script**: `experiments/aerial/scripts/v4_imagine_return_decomp.py` (`700dbe6` + `--clip-actions` / `--match-basis`)
- **A.2 JSON**: `artifacts/v4_imagine_return_decomp_20260818.json`
- **A.3 JSON**: `artifacts/v4_imagine_return_decomp_a3_20260818.json`（a0 匹配；判定作废）
- **A.3 log**: `logs/v4_imagine_return_decomp_a3_20260818.log`
- **A.4 JSON**: `artifacts/v4_imagine_return_decomp_a4_20260818.json`
- **A.3traj JSON**（未夹、`--match-basis traj`）: `artifacts/v4_imagine_return_decomp_a3traj_20260818.json`
- **joint log**: `logs/v4_imagine_return_decomp_a4_a3traj_20260818.log`
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

- ~~匹配幅度下 RH **仍更偏好 π 那个后向向量**（Σprogress 142 vs 前飞 83），不是「只是幅度更大」。~~ ← **作废**，见下
- `pi_imagined_arrival=false`：‖goal_rel‖ **涨**到 254，不是收到 0 → **不是** z 转移「以为到达」。**此条仍成立**。
- 幅度欠罚比 ≈ **33×**（相对单位前飞；无 seed，勿报两位有效数字）。

~~**处置（A.2 第二支）**：**先修 RH（另案）**，再执行 §4 In 表。~~ ← **已撤回（2026-08-18 复核）**。「不签「§4 充分」」仍然成立。

---

## ⚠️ A.3 判定作废（2026-08-18 复核）

`b3_le_a` 字面成立（59.85 ≤ 103.63），但**这条臂无效**，三个理由：

**1. 幅度根本没匹配上（~4.6×）** — `match_scale` 用 `act0_norm3_mean`=3.591，只匹配**第 0 步**。π **整条轨迹**平均 ‖a[:3]‖ **≈16.5**，两条独立算路互证：
- Σmaneuver 是加权项（`w_maneuver=0.01`）：单位臂 −0.15 → Σ‖a‖=15 ✓；(b3) −0.54 → 15×3.591=53.87 ✓；**π −2.47 → Σ‖a‖=247 → 16.5/步**。
- ‖goal_rel‖ 30→253.9 需累计位移 ≈224/15 = **14.9/步**。

脚本已算 `act_norm3_mean` 并落 JSON（`:331`），但 auto 分支取了 `act0_`（`:366`）——**A.3 设计错误，责任在提案方（我）**，与 A.2 那个洞同类。

**2. 五条臂全在物理不可实现区** — `env.step_hz=5.0` ⇒ 部署每步硬夹 `body_delta_limits(0.2)` = **[1.0, 0.4, 0.4, 0.314]**（`env/action.py:57`；`collector.py:167` / `airsim_env.py:170`），**`imagine()` 不夹**（`imagination.py:120-127`）。所以：
- **(b) `[+1,0,0,0]` 恰是可实现的最大前飞步**：λG0 **49.65** vs 可实现最大后退 (c) **15.99** ⇒ **可实现集合内 RH 方向偏好正确（3.1×）**。
- π 的 103.63 只来自跑出该集合 3.6×→16×。`w_progress:w_maneuver = 100:1` 下「顶大 ‖a‖ 净赚」恒真，无需任何方向判断。
- (b3)@3.591 现实里夹回**就是 (b)**（已用真 `clip_body_delta` 验过）。A.3 测的是「无界打赢有界」= 权重的推论，**不是** RH 方向偏好。
- `action_scale=3.0` 是**增益不是界**（`_MLP` 末层裸 `nn.Linear`，`actor_critic.py:200`），幅度无上界；先前「饱和」说法已更正。
- RH 训练位移 = `body_vel × reward_dt=0.2` ≤ ~1 m/步 ⇒ 想象拿 3.6–16 m 查它是**幅度轴 OOD**，与 ‖goal_rel‖ 8.5× 是两条独立 OOD。

**3. (b3) 另被扣两刀** — 15×3.591=53.87 > 30 ⇒ 第 ~8.4 步**冲过目标**，末态 |30−53.87| = **23.87**（实测 23.9 ✓；(c3) 30+53.87=83.87 vs 83.9 ✓ —— 反向验证了 `_goal_dist_traj`）。上表「23.9（靠近）」是**读反**：冲过目标 23.9 m，后半程 goal 在身后。`_apply_a3` 只对 (a) 查 arrival（`:134`），未查 (b3)。

**另**：`p_coll ≈ 6e-4` 横跨所有臂（含 1 m/步、15 步头对头撞墙）⇒ 想象里**碰撞头近乎是死的**，④ 的想象刹车同样无信号。这是坏消息，不只是「碰撞项已排除」。另案。

## Next — §A.4（只读，realizable set）

`--clip-actions` 用**部署同一函数**包住策略（`imagine()` 本体不动），`--seed` / `--match-basis {a0,traj}` 同时补上；夹后 (b3)/(c3) 退化为 (b)/(c)，第二遍自动跳过。

| 观测（夹后 λG0） | 判定 | 处置 |
|---|---|---|
| **(b) ≥ (a)** → `fwdmax_ge_pi` | 倒挂全部来自无界动作通道 | 在 `imagine()` 落与部署同一 clip（一致性红线，非阈值），重跑 §A/§A.3 重推 ① 根因。**不是** RH 案 |
| **(a) > (b)** → `pi_gt_fwdmax` | 幅度可执行时 RH 仍偏好 π 方向 | A.2 第二支**确诊**：先修 RH（另案） |

命令见提案 §A.4。`δ_p=0.10` / `n=8` / yaml 均不动。

> **实测（2026-08-18 seed=0）已填**：触发第一支 **`fwdmax_ge_pi`**，见下一节。上表保留为事前判据，不改写。

---

## A.4 DONE（2026-08-18，seed=0，`--clip-actions`）

125 实测触发**第一支** **`fwdmax_ge_pi`**。limits = `body_delta_limits(1/5)` = **[1.0, 0.4, 0.4, 0.314]**。路径：`~/data`/`~/ckpt` 快捷方式不存在，改用 `dataset_v0_headon_20260811` + `v4_ac_ckpt_20260817_wm_rh_goal_rgb` + `wm_ckpt_r60_rh_20260816/wm_step_1000.pt`（与提案命令一致）。

| Arm | Σ progress | Σ p_coll | Σ maneuver | λ G0 | a0 / ‖a[:3]‖ | ‖goal_rel‖ 30→ |
|---|---|---|---|---|---|---|
| (a) π **clipped** | +13.56 | −0.006 | −0.178 | **+18.25** | `[-1.0, -0.309, -0.27, -0.163]` ‖a0[:3]‖=**1.12**；轨迹均值 **1.15** | **45.9**（仍远离；`arrived=false`） |
| (b) forward max `[+1,0,0,0]` | +62.60 | −0.006 | −0.150 | **+47.64** | unit = 可实现最大前飞 | 15.0（靠近，未到达） |
| (c) retreat max `[-1,0,0,0]` | +9.28 | −0.006 | −0.150 | +15.87 | unit = 可实现最大后退 | 45.0 |

**(b) 47.64 ≥ (a) 18.25**（差额 29.4）→ 预提交判据 **`fwdmax_ge_pi`**。

- 夹后 π **仍后向**（a0 x=−1.0，饱和到后退上限），但想象目标在可实现集合内**更偏好最大前飞**。倒挂（π 想象赢、真实 ① 输）来自**无界动作通道**，不是 RH 方向偏好。
- 夹后 (b)>(c) 仍成立（47.64 vs 15.87，3.0×）；与无 seed 口径 49.65/15.99 同号，量级差属 seed 钉死（本跑 seed=0）。
- p_coll 三臂仍 ≈6e-4（死头）——可实现 1 m/步下碰撞头仍不亮。
- `enable_policy_update` / yaml / `δ_p` / n **未动**。`imagine()` 本体仍不夹（本跑只包策略）。

**处置（已由事前表锁定）**：在 `imagine()` 落与部署同一 `clip_body_delta`（一致性红线，非阈值），然后重跑 §A。**不是** RH 案；**不**签「§4 充分」。是否本周期落 clip → 提案签字栏「动作空间一致性裁定」（提案方读法：属既有红线修不一致，可先落）。未签字前**不改** `imagination.py`。 ← **此处「落 clip」的写法已由本文末节修正（判定不变，只是 C1 不够）；原文保留不改写。**

### A.3traj 配套（同 seed=0，未夹，`--match-basis traj`）

纠 A.3 那个 a0=3.59 欠匹配。auto `match_scale` = π 轨迹均值 ‖a[:3]‖ = **15.59**（≈作废段反推的 16.5；相对 a0=3.13 为 **5.0×**，相对旧 A.3 的 3.59 为 **4.3×**）。

| Arm | Σ progress | Σ p_coll | Σ maneuver | λ G0 | ‖goal_rel‖ 30→ |
|---|---|---|---|---|---|
| (a) π 未夹 | **+143.74** | −0.006 | −2.47 | **+105.00** | **254.2**（未到达） |
| (b) unit forward | +62.60 | −0.006 | −0.150 | +47.64 | 15.0 |
| (b3) forward @15.59 | +14.24 | −0.006 | −2.34 | **+18.21** | **203.9**（过冲更狠） |
| (c3) retreat @15.59 | +49.52 | **−60.14** | −2.34 | +6.12 | 263.9 |

字面仍 `b3_le_a`（18.21 ≤ 105.00）——**预期**：未夹 π 靠顶 ‖a‖ 赢；此条**不**重新打开「先修 RH」。用途是印证作废理由 1：轨迹匹配后 (b3) 过冲 30→204，λG0 掉到 18.21 ≈ A.4 夹后 π 的 18.25。另：(c3)@15.59 的 p_coll **亮了**（Σ −60）——碰撞头在可实现 1 m/步下是死的，只在 15 m/步 OOD 才有信号；死头另案仍成立。

`clip_shrink_ratio` 跨文件：未夹轨迹 15.59 / 夹后 1.15 ≈ **13.6×**（A.4 JSON 内 `pi_act_norm3_mean_unclipped=null`，因 clip 跑未同时保留未夹 π）。

---

## ⚠️ A.4 处置措辞不足：字面 clip ≠ 一致性修（2026-08-18 复核）

**判定 `fwdmax_ge_pi` 与「不是 RH 案」都成立**；被撤的只是处置的**写法** —— 事前表里我写「在 `imagine()` 落与部署同一 clip」，只定了 clip 的**位置**，没检查它落进的是什么**估计量**。

读码事实：`imagine()` 纯 numpy 无梯度；actor 更新是 **REINFORCE** —— `corrector.py:176` → `actor_critic.update(rollout)`，`update()` 把 **`rollout.actions`** 交给 `evaluate_actions(z,a)` 算 `logp = Normal(mean,std).log_prob(a)` 再乘优势（`actor_critic.py:214-226`/`:257`/`:271`），**无梯度穿 `dynamics.step`**。

于是字面 clip = 用**未夹高斯**给**夹后动作**算 logp：

1. **似然错配** —— 夹后动作在盒面上，真实采样律是「盒内截断 + 盒面点质量」的混合，`Normal.log_prob` 不是它的密度 ⇒ REINFORCE 无偏性前提破掉。
2. **探索塌缩（可算）** —— `_log_std` 初值 −0.5 ⇒ σ=**0.6065** 四维同值，而上限 [1.0,0.4,0.4,0.3142]：σ 是后三维上限的 1.5–1.9 倍。逐维夹概率（mean=0）9.9%/51.0%/51.0%/60.4% ⇒ 四维**全在盒内**仅 **8.6%**；按现 ckpt mean `a0` 算 **3.4e-6** ⇒ 每个样本都是盒面原子，状态内动作方差≈0 ⇒ **学不出方向**。

⇒ 选项 **C1 字面 clip（不推荐单独落）/ C2 有界策略分布 `a = limits ⊙ tanh(u)` + 雅可比修正 logp（推荐，须从零重训）/ C3 pathwise（本周期不做）**，事前判据（`clip_helped` / `clip_insufficient` / `spurious_pass`）见提案 **§4.1**。

**另记（需核，不重开）**：`planner.default_candidates`（`planner.py:31-42`）也在**未夹空间**打分（含 `[max(|dx|,1.0),0,0,0]` 前飞臂），到 `collector.py:167` 才夹 ⇒ V1 部署侧同源不一致。V1-④ 已 PASS，**不**重开 08-15 merge；若落 C2 应同时覆盖候选集。

**下一件**：签字「动作空间一致性裁定」（C1/C2/C3/不落）；落哪个都在签字后才动代码，然后重跑 §A。门禁不动。

`enable_policy_update` 仍 **false**。

---

## ✅ 裁定 = C2，代码已落地（2026-08-18）

- 采样律改成 **`a = limits ⊙ tanh(u)`**、`logp` 减 / `ent` 加 `Σ log(limits(1−y²))`；`limits = body_delta_limits(1/step_hz)`，`step_hz=5.0` ⇒ **`[1.0, 0.4, 0.4, 0.31415927]`**（与 `collector.py:167` 同一组数）。`action_scale` **3.0 → 1.0** 并降级为 **pre-tanh gain**。
- 本文档所有 pre-C2 数字**可回放**：保留 `policy_class="unbounded_gaussian_legacy"`，且 `load_from_checkpoint` 见到缺 `policy_class` 的旧 payload 自动判 legacy 并 warn（两类张量形状相同，否则会**静默**载入新律）。但 `update()` 对 legacy **抛 `RuntimeError`** ⇒ 失效 ckpt **不可能被 warm-start**（红线「干净重训禁 warm-start 失效 ckpt」落成代码）。
- 「clip 已成 no-op」将来是**测出来**的：`ImaginedRollout.n_action_clipped` 计数 + `corrector` 在 `>0` 时 warn。C2 下单测实测 **0**；对故意越界策略（`[9,0,0,0]`，5 步）实测 **5**。
- 上文「另记」的 `planner.default_candidates`：`planner.action_limits` **默认 `None`** ⇒ V1 08-15 已 merge 的部署打分**逐位不变**（打开须 V1 re-gate，本周期不打开）。同源不一致**仍记在案、未修**。
- 验证：Mac 无 torch ⇒ 纯 numpy 独立验密度积分 1.000000/1.000000/1.000016/1.000000、熵恒等式 MC −2.129664 vs 解析 −2.128682；上文 σ=0.6065、8.6%、3.4e-6 全部复算一致。全量 `pytest experiments/aerial/rl/tests/` = **227 passed / 6 skipped**（6 例 torch 门控，**须在 H100/125 复跑**）；`_v4_gate --self-check` **PASS**。
- **未做**：§A/§A.3/§A.4 重跑、H100 从零重训、125 ① 再 gate（`n≥8`）。`enable_policy_update` 仍 **false**。
