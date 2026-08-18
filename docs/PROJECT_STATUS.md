# Aerial WAM v2 — 项目现状整理

> **日期**: 2026-08-17（对齐 V4 活文档；V0 merge 08-14 / V1 merge 08-15）  
> **阅读顺序**: [handover/LIVING_DOCS.md](handover/LIVING_DOCS.md)  
> **代码来源**: `aerial-wam-v2` @ `main`（历史分支名 `aerial-rl-skeleton`）  
> **阈值权威**: [frozen spec §4.1](superpowers/specs/2026-08-04-aerial-wam-v2-frozen-spec.md) — 本文只摘录，不新建第二真相源

---

## 1. 项目目标

重建 **goal-first 纯视觉世界模型**（DreamerV3 RSSM），从随机初始化干净重训。

**V0（已完成 2026-08-14）**：四信号 merge PASS → 已翻：

- `world_model.depth_head.enable: true`
- `safety.kind: threshold`

**V1（已完成 2026-08-15 严谨 merge PASS）**：`dynamics.kind=torch` + `enable_wm_update` + τ/`foe_calibrated` + 双通道罩 — 见 [V1_GATE_STATUS](handover/V1_GATE_STATUS.md)。

**V4（进行中）**：想象 AC；`enable_policy_update` **仍 false** 直至 V4 merge PASS — 见 [V4_GATE_STATUS](handover/V4_GATE_STATUS.md)。

旧 `wm_step_5000.pt` 已判定为单柱 RGB shortcut，**不可 warm-start**。权威 V0 WM：`wm_ckpt_r60_20260814`；V4 RH 线另有 `wm_ckpt_r60_rh_20260816`。

---

## 2. 一句话结论（2026-08-17）

**✅ V0 / V1 均已 merge PASS。**  
**当前：V4-MVP** — ① **不可稳健达成**（goal-blind In 表 + 单 mock goal；方向为负待 §A）。待签字改 In 表。  
`enable_policy_update` **仍 false**。

---

## 3. 四信号现状（V0 — 已闭合）

| 信号 | 判据摘要 | r60 结果（2026-08-14） |
|---|---|---|
| **①a–c** | loss↓≥2%、recon 不劣、min entropy-frac ≥0.10 | ✅ loss 3.87→1.96；recon↓；min_ent 0.47；`authoritative=true` |
| **①d** | holdout AbsRel ≤ 0.30 | ✅ **0.0641**（r60 ft-head） |
| **②** | progress ≥ random+5.0 ∨ final_dist ≤ random−3.0 | ✅ progress **13.49** vs **−4.30**；**n=8** |
| **③** | reprojection median rel ≤ 0.25；n≥8 | ✅ median **0.212**；n=90 |
| **④** | ④c ratio ≤0.80（④b 有接触才测） | ✅ ④c ratio **0.113**；④b N/A（`n_contact=0`）；**n=8** |

### 3.1 r60 部署线（head 已统一）

| 资产 | 路径（H100 `~/aerial-rl-skeleton/.../artifacts/`） |
|---|---|
| 语料 | `dataset_v0_local_depth_r60_20260814`（51 npz / 48 usable） |
| 深度 | `depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt` |
| WM | `wm_ckpt_r60_20260814/wm_step_5000.pt` |
| Merge | `v0_gate_r60_20260814.json` |

**洞 2 ④b**：✅ 关闭（2026-08-17）— 空过为终态，实证=④c。  
**洞 3 V1-② coll**：✅ 定义关闭 + 诊断已测（r60 n-starts=4，`coll_traj_pos=5` / AUROC 0.972；**2026-08-17** WM-unseen held-out `dataset_v1_coll_heldout_20260817` → pos=**20** / AUROC=**0.977** / unique usable coll ep=**8**，`coll_claimed=true`）；**不改** 08-15 merge（仍 `coll_ok=null`）。headon coll=0 不可用。~~§4.1 n=16 vs 8~~ → **已 re-freeze 为 8**（2026-08-17）。

---

## 4. 公式与协议（§4.1 摘录）

### 4.1 信号 ①d — 深度 AbsRel

\[
\mathrm{AbsRel} = \mathrm{median}\left(\frac{|\hat{D} - D_{\mathrm{gt}}|}{D_{\mathrm{gt}}}\right)
\]

在 holdout 像素上，\(D_{\mathrm{gt}} \in (0, 200]\) m。过门：**AbsRel ≤ 0.30**。

### 4.2 信号 ①a–c — WM 训练曲线

在训练日志首尾各 \(k=\max(1, \lfloor N/10\rfloor)\) 步取均值：

| 子信号 | 条件 |
|---|---|
| a | \(\overline{\mathrm{loss}}_{\mathrm{tail}} \le 0.98 \cdot \overline{\mathrm{loss}}_{\mathrm{head}}\)（降 ≥2%） |
| b | \(\overline{\mathrm{recon}}_{\mathrm{tail}} \le \overline{\mathrm{recon}}_{\mathrm{head}}\) |
| c | \(\min_t \mathrm{post\_entropy\_frac}(t) \ge 0.10\) |

语料守卫：`_refuse_v0()` 拒绝标称 `step_hz > 8.5` 的 dt-desync 语料（除非 `--allow-v0-desync`，此时日志标 `authoritative=false`）。

### 4.3 信号 ② — 接近量 vs 随机

在 \(N=8\) 个 rollout episode 上（re-freeze 2026-08-17；原 16）：

\[
\text{PASS} \iff
\underbrace{\bar{P}_{\mathrm{policy}} \ge \bar{P}_{\mathrm{random}} + 5.0}_{\text{progress margin}}
\;\;\lor\;\;
\underbrace{\bar{d}_{\mathrm{policy}} \le \bar{d}_{\mathrm{random}} - 3.0\ \mathrm{m}}_{\text{distance margin}}
\]

### 4.4 信号 ③ — 深度尺度（当前：重投影估计器）

> **注意**：2026-08-10 起 ③ 已从「band-median Δ vs VIO」改为 **GT-proprio 位移 + 深度重投影** 估计器。详见 [signal3 reprojection handover](handover/2026-08-10-signal3-reprojection-estimator.md)。

对每个有效**接近窗**（前向余弦 ≥0.7、位移 ≥0.5 m、support 等，见 frozen spec §4.1 ③c–③e）：

\[
e_w = \frac{|\hat{s}_D - s_{\mathrm{VIO}}|}{\max(s_{\mathrm{VIO}}, \varepsilon)}, \quad \varepsilon = 10^{-3}
\]

其中 \(\hat{s}_D\) 来自重投影管线，\(s_{\mathrm{VIO}} = \|\Delta p\|\)（GT proprio 位移）。

过门：

\[
\mathrm{median}(e_w) \le 0.25, \quad n_{\mathrm{valid}} \ge 8
\]

**GT oracle**：把 \(\hat{D}\) 换为 GT depth 后的同一条 median — 当前语料上 ≈ **0.002**（head A 测 0.05–0.12 有余量）。

### 4.5 信号 ④ — Shield 有效性

在 near-obstacle 起点、shield on/off 配对 rollout 上：

| 子信号 | 条件 |
|---|---|
| ④b | 接触前干预比例 \(\ge 0.50\)；`n_contact=0` 时 **N/A**（`before_vacuous`；JSON 仍 emit 1.0 仅兼容，非测得） |
| ④c | \(\mathrm{near\_coll\_rate\_on} / \mathrm{near\_coll\_rate\_off} \le 0.80\)（④ 实证） |

Shield 触发深度：**3.0 m**（反应余量，re-freeze 注；度量带仍为 1.5 m）。

---

## 5. 基础设施

| 机器 | 地址 | 角色 |
|---|---|---|
| Mac | 本仓库 | 写代码 |
| H100 | `a25689@10.239.121.25:31126` | 训练、①③ 离线 gate、②④ rollout 客户端 |
| 4090 | `10.229.20.125:41451` | AirSim 渲染器 |

**两个 checkout（H100）**：

- `~/aerial-rl-skeleton` — 旧 checkout，**artifacts / 权重 / 语料** 在这里
- `~/robomaster-tt-control` — 新 clone，代码新、artifacts 空

Gate 命令里的 `--depth-ckpt` / `--dataset` 用 **`~/aerial-rl-skeleton/.../artifacts/` 绝对路径**，不要拷贝。

共享盘 `/home/a25689/aerial_cache_shared/` 存 runs；可拆卸盘上的语料跑 gate 前须 `ls` 确认已挂载。

---

## 6. 待办（V1 → V4）

详见 [V1_GATE_STATUS.md](handover/V1_GATE_STATUS.md) 与 [V1/V4 设计](design/2026-08-15-v1-v4-design.md)。

| 优先级 | 任务 |
|---|---|
| ~~**V1a-1**~~ | ✅ `_wm_train_validate` → `wm_ckpt_v1a_20260815` |
| ~~**V1a-2**~~ | ✅ `kind=torch` + `enable_wm_update=true` + corrector smoke |
| **V1b** | τ + 想象规划 + `DepthTauShield` + `_v1_gate` — **merge PASS（严谨）**；部署 flip FOE yaml 待人工 |
| **P0b** | shield 消费 `predict_cones()`（可选，会改 ④ 行为） |
| **n re-freeze** | ✅ **关闭**（2026-08-17）：frozen `n_eval_episodes=8`（**事后合法化**，非事前干净；合法性轴） |
| **洞 2 ④b 空过** | ✅ **关闭**（2026-08-17）：空过为终态；实证=④c |
| **洞 3 V1-② coll N/A** | ✅ 定义关闭；r60 诊断 + **held-out 20260817** `pos=20` / AUROC 0.977 / usable coll ep=8（`coll_claimed`）；**不改** 08-15 merge |
| **V1-① 功效②③** | ⏳ **待签字**：[提案](handover/V1_SIGNAL1_POWER_REFREEZE_PROPOSAL.md)；脆弱（0.8 局 / McNemar p≈0.5）已记；与 n re-freeze **正交** |
| **V4** | ① 不可稳健达成已记；方向为负待 [§A](handover/V4_SIGNAL1_STRUCTURAL_REFREEZE_PROPOSAL.md)；`enable_policy_update` 仍 false |

---

## 7. 治理红线

- V0 flags **已翻**；V1/V4 flags **仍 OFF**，各阶段独立 gate
- **不为凑过调 §4.1 阈值**；shield 控制律可改，阈值改需 re-freeze
- 代码走 git，**禁 scp 热补丁**
- 干净重训禁 warm-start 失效 ckpt

---

## 8. 关键资产（H100，不在 git）

| 资产 | 路径 |
|---|---|
| **r60 语料（权威）** | `.../dataset_v0_local_depth_r60_20260814` |
| **r60 深度 ckpt** | `.../depth_ckpt_da3_r60_20260814/` |
| **r60 WM ckpt** | `.../wm_ckpt_r60_20260814/` |
| V0 merge verdict | `.../v0_gate_r60_20260814.json` |
| 头对头 rollout 语料 | `.../dataset_v0_headon_20260811` |
| 历史 head A/B | `depth_ckpt_da3_20260810` / `depth_ckpt_da3_near_20260811`（归档） |

---

## 9. 历史备注：Aug-5 band-median ③ 战役（已 superseded）

2026-08-05~06 曾用旧协议（band-median \(\hat{s}_D = |d_{L-1}-d_0|\) vs \(\|\Delta p\|\)）攻关 ③，结论已归档于原 worktree 的 `signal3_campaign_20260806`（若 H100 已落盘）。要点：

- GT oracle ≈ **0.229**，门槛 0.25 余量仅 0.021
- δ 扫描最好 D̂=0.268（δ=1.6）；增采 d18 **抬高** oracle 至 0.245
- Δ 监督密度（`wm-batch` 32）提升 Spearman，但 ③ 协议已切换至重投影

**当前权威 ③ 以 §4.4 重投影为准**；旧战役仅作踩坑记录，勿与 head B 补跑混淆。

---

## 10. 文档索引

| 文档 | 内容 |
|---|---|
| [RUNBOOK_v0.md](../experiments/aerial/RUNBOOK_v0.md) | 顶层入口 + §8 变更记录 |
| [V0_GATE_STATUS.md](handover/V0_GATE_STATUS.md) | V0 合拢记录（已 PASS） |
| [V1_GATE_STATUS.md](handover/V1_GATE_STATUS.md) | V1 三信号进度 |
| [V1/V4 设计](design/2026-08-15-v1-v4-design.md) | post-V0 阶段设计 |
| [frozen spec](superpowers/specs/2026-08-04-aerial-wam-v2-frozen-spec.md) | 阈值 §4.1 |
| [pure-vision design v2](superpowers/specs/2026-08-03-aerial-wam-pure-vision-design-v2.md) | 架构 |
| [DA3 backbone](handover/2026-08-10-da3-depth-backbone.md) | 深度骨干 |
| [signal3 reprojection](handover/2026-08-10-signal3-reprojection-estimator.md) | ③ 估计器 |
| [sync & env](../experiments/aerial/scripts/RUNBOOK_sync_and_env.md) | 三机同步 |

---

## 11. 本仓库迁移说明

本目录 `/Users/xudazhong/Projects/aerial-wam-v2` 从 `robomaster-tt-control/.claude/worktrees/aerial-rl-skeleton` @ `8a063be` 提取。

**已迁移（整棵 `experiments/aerial/`）**：

- `rl/` — V0 gate、WM 训练、collector、DA3 vendored
- `sim_verify/` — Fork A 前置验证
- `orchestration/` / `eval/` / `collapse_fix/` — B0/B1 编排与评测（v1 线，历史资产）
- `scripts/` — sync/env/renderer + B0/B1/collapse 脚本
- OpenFly 辅助：`convert_openfly_to_lerobot.py`、`path_expert.py`、`takeover.py` 等
- `configs/aerial_rl*.yaml` + V0/B0 相关 docs

**未迁移（刻意留在旧 monorepo）**：FastWAM `src/`、`configs/train.yaml` / libero / robotwin、Tello 真机控制。

H100 上 artifacts 仍指向旧 checkout 路径；后续可将 `sync_pull.sh` 的 remote/branch 指向本仓库新 remote。
