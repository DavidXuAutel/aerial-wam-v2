# Aerial WAM v2 — 项目现状整理

> **日期**: 2026-08-14（由 `V0_GATE_STATUS.md` + `RUNBOOK_v0.md` 收敛，并标注迁移来源）  
> **代码来源**: `robomaster-tt-control` 分支 `aerial-rl-skeleton` @ `8a063be`  
> **阈值权威**: [frozen spec §4.1](superpowers/specs/2026-08-04-aerial-wam-v2-frozen-spec.md) — 本文只摘录，不新建第二真相源

---

## 1. 项目目标

重建 **goal-first 纯视觉世界模型**（DreamerV3 RSSM），从随机初始化干净重训，通过 V0 **四信号同权门禁**后，才允许打开：

- `world_model.depth_head.enable`
- `safety.kind`（shield）
- `corrector.enable_wm_update`

**禁止**在四信号 merge 通过前顺带打开 `enable_policy_update`（V4）。

旧 `wm_step_5000.pt` 已判定为单柱 RGB shortcut，**不可 warm-start**。

---

## 2. 一句话结论（2026-08-12）

**四信号从未在「同一 depth head + 一次 `_v0_gate --merge`」下合拢过。**

各信号在不同时间 / 机器 / checkpoint 上分别通过，但 merge 要求所有 partial JSON 并存且 `ok=true` → **merge 从未 exit 0**。

---

## 3. 四信号现状

| 信号 | 判据摘要 | 最后已知结果 | 还差什么 |
|---|---|---|---|
| **①a–c** | WM 训练健康：loss↓≥2%、recon 不劣、min entropy-frac ≥0.10 | 🟡 dry-run 数字全过，但语料 **dt-desync**（靠 `--allow-v0-desync` 逃生舱）→ **实质失格** | **重采合格语料** + 权威重训；或先用 `dataset_v1_rgb`(8 Hz) 出合格日志 |
| **①d** | holdout median AbsRel ≤ **0.30** | ✅ head B **0.0483**（local）；head A 0.132 | head B 上 **已完成**，不重跑 |
| **②** | N=16；progress ≥ random+5.0 **或** final_dist ≤ random−3.0 | ✅ 决定性通过（如 progress 24.13 vs −5.11） | 仅 **n<16**（用户决定不追 scan 喂满 16） |
| **③** | reprojection median rel err ≤ **0.25**；有效窗 ≥ **8** | ✅ head A **0.05–0.12**（GT-oracle ≈0.002） | **head B 上未跑** ← 唯一 depth 侧 gap |
| **④** | before ≥0.50；shield on/off near_coll ratio ≤0.80 | ✅ head B 稳健 PASS ×3（ratio 0.13/0.23/0.12） | 仅 **n<16** + `before=1.0` 合法空过 |

### 3.1 核心 gap：head 一致性

| 用途 | Checkpoint | 路径（H100） |
|---|---|---|
| ①③ 历史 verdict | **head A** | `depth_ckpt_da3_20260810` |
| ④ shield + ①d 权威 | **head B** | `depth_ckpt_da3_near_20260811`（`near_weight=3.0`） |

部署只用一个 head → **merge 必须同一 ckpt**。

→ **只需在 head B 上补跑 `--signals 3`**（①d 已在 head B PASS）。

**为何 ③ 要重跑、①d 不用**：①d 是全图聚合 AbsRel（远景/地面稀释近带）；③ 测**尺度**且在**接近窗**上重投影，而 `near_weight=3.0` 把近带压约 10×（6.415→0.645 m）——改动正落在被测量上。

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

在 \(N=16\) 个 rollout episode 上（当前实测 n=9~12，待 re-freeze）：

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
| ④b | 接触前干预比例 \(\ge 0.50\)（无接触集 → 合法空过 =1.0） |
| ④c | \(\mathrm{near\_coll\_rate\_on} / \mathrm{near\_coll\_rate\_off} \le 0.80\) |

Shield 触发深度：**3.0 m**（反应余量，re-freeze 注；度量带仍为 1.5 m）。

---

## 5. 基础设施

| 机器 | 地址 | 角色 |
|---|---|---|
| Mac | 本仓库 | 写代码 |
| H100 | `a25689@10.239.121.22:31126` | 训练、①③ 离线 gate、②④ rollout 客户端 |
| 4090 | `10.229.20.125:41451` | AirSim 渲染器 |

**两个 checkout（H100）**：

- `~/aerial-rl-skeleton` — 旧 checkout，**artifacts / 权重 / 语料** 在这里
- `~/robomaster-tt-control` — 新 clone，代码新、artifacts 空

Gate 命令里的 `--depth-ckpt` / `--dataset` 用 **`~/aerial-rl-skeleton/.../artifacts/` 绝对路径**，不要拷贝。

共享盘 `/home/a25689/aerial_cache_shared/` 存 runs；可拆卸盘上的语料跑 gate 前须 `ls` 确认已挂载。

---

## 6. 待办（按依赖）

1. **A. head B 上跑 ③**（~分钟级，H100 离线）  
   ```bash
   python -m experiments.aerial.rl._v0_gate --signals 3 \
     --depth-ckpt ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/depth_ckpt_da3_near_20260811/depth_step_2000_da3_head.pt \
     --dataset ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_local_depth \
     --window 8 --max-windows 256 --device cuda \
     --emit artifacts/v0_partial_3_headB.json
   ```

2. **B'. 合格语料重跑 ①a–c** — 重采 **或** 先用 `dataset_v1_rgb`(16 ep @8 Hz) 出权威 `wm_train.jsonl` + `wm_train_meta.json`（`authoritative=true`）

3. **C. P0：shield 方向锥**（改 ④ 行为，merge 前完成）

4. **D. n 的 re-freeze** — `n_eval_episodes` 从 16 降到实测可达值（待用户定数）

5. **E. ②④ 重跑**（4090 渲染器 + P0 之后）→ emit partial

6. **F. `--merge` 四 partial** → exit 0 → 才翻 flags

---

## 7. 治理红线

- 四信号全过前 **不翻 flags**
- **不为凑过调 §4.1 阈值**；shield 控制律可改，阈值改需 re-freeze
- 代码走 git，**禁 scp 热补丁**
- 干净重训禁 warm-start 失效 ckpt

---

## 8. 关键资产（H100，不在 git）

| 资产 | 路径 |
|---|---|
| head A (DA3) | `.../depth_ckpt_da3_20260810/depth_step_2000_da3_head.pt` |
| head B (DA3 near) | `.../depth_ckpt_da3_near_20260811/depth_step_2000_da3_head.pt` |
| WM dry-run | `.../wm_ckpt_v2clean_20260810/`（非权威语料） |
| 本地深度语料 | `.../dataset_v0_local_depth` |
| 头对头 rollout 语料 | `.../dataset_v0_headon_20260811` |
| Step-4 RGB 语料 | `.../dataset_v1_rgb` |

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
| [V0_GATE_STATUS.md](handover/V0_GATE_STATUS.md) | Gate 活文档 / 待办 |
| [frozen spec](superpowers/specs/2026-08-04-aerial-wam-v2-frozen-spec.md) | 阈值 §4.1 |
| [pure-vision design v2](superpowers/specs/2026-08-03-aerial-wam-pure-vision-design-v2.md) | 架构 |
| [DA3 backbone](handover/2026-08-10-da3-depth-backbone.md) | 深度骨干 |
| [signal3 reprojection](handover/2026-08-10-signal3-reprojection-estimator.md) | ③ 估计器 |
| [sync & env](../experiments/aerial/scripts/RUNBOOK_sync_and_env.md) | 三机同步 |

---

## 11. 本仓库迁移说明

本目录 `/Users/xudazhong/Projects/aerial-wam-v2` 从 `robomaster-tt-control/.claude/worktrees/aerial-rl-skeleton` 提取，**仅含 V0 相关**：

- `experiments/aerial/rl/` — gate、训练、collector、DA3 vendored
- `experiments/aerial/sim_verify/` — Fork A 前置验证
- `experiments/aerial/scripts/` — sync / env / renderer（4 脚本）
- `configs/aerial_rl*.yaml`
- V0 文档子集

**未迁移**：FastWAM、B0/B1 orchestration、Tello 控制、collapse_fix 等。

H100 上 artifacts 仍指向旧 checkout 路径；后续可将 `sync_pull.sh` 的 remote/branch 指向本仓库新 remote。
