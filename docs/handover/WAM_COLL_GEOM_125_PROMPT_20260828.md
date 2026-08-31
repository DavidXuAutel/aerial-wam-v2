# 125 Agent：coll 几何监督代码刀 + H100 重训 + B 复测

> **执行归属**：本任务 **一律在 125 Agent 完成**（含 H100 跳板）；Mac 只 `git push github` + handoff。  
> **权威**：[`experiments/aerial/RUNBOOK_wam_imagination.md`](../../experiments/aerial/RUNBOOK_wam_imagination.md) §B / §B′ / §D  
> **前置结论（勿重做）**：B′-1 **weak_geometry**；B′-2 window gap≈single **0.0018**；yaml-only **coll_rep** gap=**−0.0020** → **勿优先 B′-3 读出头短 FT**。

---

## 0. 你是谁 / 这一发要过什么闸

| 闸 | 现状 | 本发目标 |
|----|------|----------|
| **B（硬）** | `median_p_coll_gap ≈ 0.0018`（阈 **≥ 0.05**） | 重训后 gap **≥ 0.05** |
| **B′-1（诊断）** | window R²≈**−0.55**，readout=**weak_geometry** | R² 向正、或至少 MAE 明显下降 |
| **E** | 禁止 | B 未过 **不开 E** |
| **deploy 罩** | S-8j 深度头 | **禁止改** `safety.py` / 生产 yaml flip |

**根因判断**：latent 未编码可用近场几何；仅 yaml 加压 / coll_head 单独 FT 不够 → 须在 **WM 训练损失**里加 **深度辅助表征监督（Depth-Aux 穿透 RSSM）** + **几何条件化前/侧 hinge（Conditional Hinge，严禁无条件全局 Hinge）**。

> ⚠️ **B′-4 实测警示（2026-08-28 11:45）**：`wam_coll_oracle_gtdepth` 实测 median gap 为 **-0.108**（走廊/侧墙帧侧向危险高于前方）。**严禁对所有帧无脑施加前向 Hinge 惩罚**，否则会导致模型在开阔地带产生前飞虚警，学出“不敢往前飞”的残疾策略！

---

## 1. 拉代码

```bash
cd ~/aerial-wam-v2
git fetch github && git merge github/main
# 公司网也可：git fetch origin && git merge origin/main
git log -1 --oneline   # Mac 侧应 ≥ b054ece；含本 handoff 后更新
```

通路：`ssh cursor-125`（公司内网 **关 VPN**）；VPN 开时用 `cursor-125-public`。

---

## 2. P0 — 代码实现（125 本机）

### 2.1 改哪里

主文件：`experiments/aerial/rl/dynamics_torch.py`

对照（reward 头已有 feat_proj + aux，coll 仍是 bare linear）：

```text
reward: reward_feat_proj(h‖z) ‖ action ‖ goal/vel aux  → reward_head
coll（现）: (h‖z) ‖ action  → coll_head（Linear）
```

### 2.2 必须实现（按调整后的正确优先级）

**A. （最高优先级）Depth-Aux 穿透 RSSM/Encoder 表征监督（训练 only，GT depth）**

- **目标**：彻底治愈 B′-1 的 `weak_geometry`（$R^2 = -0.55$），让隐空间 $h \parallel z$ 拥有真实的 3D 几何与距离感。
- **做法**：
  - 在 `TorchDynamics` 中增加几何预测头（如 `depth_aux_head: Linear(feat_dim, 1)` 预测 $d_{\text{fwd}}$，或 3 维预测前/左/右 cone clearance）。
  - 在 `training_loss()` 里计算预测距离与 GT depth（`forward_min_depth_torch(depth)`）的 Huber Loss：
    $$L_{\text{depth\_aux}} = \text{Huber}(\log(1 + d_{\text{pred}}), \log(1 + d_{\text{gt}}))$$
  - **关键**：**梯度必须回传至 RSSM 和 image encoder**（不 detach 特征），权重 yaml `coll_fwd_depth_aux_weight: 1.0`。
  - **纪律**：仅训练期利用 GT depth 辅助梯度；推理/想象时不依赖外部深度。

**B. （条件触发）几何条件化的前/侧 coll hinge（Conditional Hinge）**

- **严禁无条件全局 Hinge**！必须带几何前置条件：
  - 取当前帧的 GT 几何：$d_{\text{fwd}}$ 以及侧向 $d_{\text{lat}} = \max(d_{\text{left}}, d_{\text{right}})$。
  - **仅当** $d_{\text{fwd}} \le \text{hinge\_fwd\_max\_m}$（默认 $4.0\text{ m}$）且 $d_{\text{lat}} > d_{\text{fwd}} + 0.5\text{ m}$（即**正前方确实受阻且侧向确有生路**）时，才计算该样本的 hinge loss：
    $$L_{\text{hinge}} = \text{relu}(\text{margin} - (p_{\text{coll\_fwd}} - p_{\text{coll\_lat}}))$$
  - 对于开阔地带（$d_{\text{fwd}} > 6.0\text{ m}$）或侧面更狭窄的帧，**mask 掉 Hinge 损失（权重为 0）**，防止注入虚假动作偏置。
- **动作对构造**：固定 `feature[:, t]`，构造 forward ($+x$) vs lateral ($\pm y$) 动作对。

**C. coll_feat_proj（可选）**

- 对齐 reward：`coll_feat_proj(h‖z) ‖ action`。

### 2.3 配置（`configs/aerial_rl.yaml` → `world_model:`）

新增键（示例，可调）：

```yaml
coll_fwd_depth_aux_weight: 1.0   # 特征层 depth-aux 权重（穿透 RSSM）
coll_rank_hinge_weight: 1.0      # 条件 Hinge 权重
coll_rank_hinge_margin: 0.15     # 条件 Hinge 边际
coll_hinge_fwd_max_m: 4.0        # 仅前方 <= 4m 且侧向开阔时激活 hinge
```

保留现有：`coll_near_depth_m: 5.0`，`coll_pos_weight: 0.0`（auto）。

### 2.4 单测（125 必绿再开 H100）

```bash
source experiments/aerial/scripts/env_4090.sh
export PYTHONPATH=$PWD
python -m pytest experiments/aerial/rl/tests/test_dynamics_torch.py -q
# 新增用例建议：
# - hinge>0 时 forward-lateral logit 差在 synthetic batch 上被推高
# - hinge_weight=0 时 loss 与旧路径兼容
# - coll_rep yaml 键被 from_config 读取
```

提交：`git commit` + `git push origin main`（125 bare）；Mac 侧再 `git push github` 镜像。

---

## 3. P1 — H100 重训 WM（125 SSH 跳板）

**禁止 Mac 直连 H100。**

```bash
ssh h100-25   # 125 上：~/.ssh/id_ed25519_h100
cd ~/aerial-wam-v2
source experiments/aerial/scripts/env_h100.sh
export PYTHONPATH=$PWD
```

| 项 | 值 |
|----|-----|
| **Init** | `experiments/aerial/rl/artifacts/wm_ckpt_coll_full_20260827/wm_step_1000.pt` |
| **Out dir** | `experiments/aerial/rl/artifacts/wm_ckpt_coll_geom_20260828/` |
| **Dataset** | `dataset_v0_p45_merged_20260821`（与 B 评测同包） |
| **Steps** | **500** 全量 WM（非仅 coll_head）；对照 coll_rep 失败经验：**不要**只训 coll 支路 |
| **Overlay yaml** | hinge + depth-aux 开；`coll_near_depth_m: 12`，`coll_pos_weight: 2` 可保留 |
| **Log** | `logs/wm_coll_geom_h100_20260828.log` |

代码同步 H100：bundle / rsync / `git pull`（与既往 H100 流程一致）。

**Learning gate（写进 log 摘要）**：recon 不爆炸、loss_coll / loss_hinge 有限、latent_norm 有界；gate FAIL 仍存 ckpt 但 **必须标注 FAIL**。

训完 **拉回 125**（若 ckpt 只在 H100）：`scp` / rsync → 125 同路径。

---

## 4. P2 — 125 复测（B′-1 + B 主闸）

```bash
source experiments/aerial/scripts/env_4090.sh
export PYTHONPATH=$PWD
DS=experiments/aerial/rl/artifacts/dataset_v0_p45_merged_20260821
CKPT=experiments/aerial/rl/artifacts/wm_ckpt_coll_geom_20260828/wm_step_<N>.pt

# B′-1：latent 几何是否改善
$AERIAL_PY experiments/aerial/scripts/wam_latent_depth_probe.py \
  --dataset "$DS" --wm-ckpt "$CKPT" --stride 2 --max-samples 32 \
  --out artifacts/wam_latent_depth_probe_collgeom_20260828.json

# B 主闸（window encode，与 B′-2 一致）
$AERIAL_PY experiments/aerial/scripts/wam_imagine_coll_rank.py \
  --dataset "$DS" --wm-ckpt "$CKPT" --stride 2 --max-samples 32 \
  --encode-mode window --window 8 \
  --out artifacts/wam_imagine_coll_rank_collgeom_20260828.json
```

### 过关 / 不过关

| 结果 | 判定 | 下一发 |
|------|------|--------|
| B `median_p_coll_gap ≥ 0.05` | **B PASS** | 可计划 D 续训 / 准备 E（仍须 A 绿 + 语料） |
| B gap ↑ 但 < 0.05 | 有信号不足 | 调 margin/weight 或加 B2 depth-aux；**仍禁 E** |
| B gap ≈ 0 或负 | FAIL | 回看 hinge 是否 detach 错、动作对是否与 B 脚本一致；**勿**回到 yaml-only |
| B′-1 仍 weak_geometry | latent 仍差 | 加强 B2 或窗口级 coll 对比；**仍禁 B′-3 优先** |

基线对照（勿删）：

| 产物 | median_p_coll_gap |
|------|-------------------|
| `…_h100full_20260827.json` | **0.0018** |
| `…_collrep_20260828.json` | **−0.0020** |

---

## 5. 汇报（必做）

1. **代码**：`git log -1`、pytest 行数、改动的 yaml 键  
2. **H100**：steps、最终 ckpt 路径、learning gate PASS/FAIL、关键 loss 末值  
3. **B′-1**：`readout`、window R² / MAE（对比 probe_20260827）  
4. **B**：`median_p_coll_gap`、前/侧 `mean_p_coll`、`verdict.useful`  
5. 更新：
   - `experiments/aerial/RUNBOOK_wam_imagination.md` §7 表 B 行  
   - `docs/handover/V4_RUNBOOK_125_STATUS.md` 顶部「下一步」  
6. **禁止**：开 E、`enable_policy_update=true`、改 deploy 罩、用 B′-4 oracle 替代 B

---

## 6. 明确不要做

- ❌ 只做 `wam_coll_head_ft.py` / B′-3 读出头短 FT 而跳过 hinge+depth-aux  
- ❌ 未过 B 开 E 或改 F/G  
- ❌ 新开深度 FT / 罩子战役当主线  
- ❌ Mac 直连 H100 或 Mac 上长跑 GPU  

---

## 7. 参考产物路径

| 类型 | 路径 |
|------|------|
| 最佳 WM init | `wm_ckpt_coll_full_20260827/wm_step_1000.pt` |
| coll_rep（失败） | `wm_ckpt_coll_rep_20260828/wm_step_1500.pt` |
| B 基线 | `artifacts/wam_imagine_coll_rank_h100full_20260827.json` |
| B′-1 基线 | `artifacts/wam_latent_depth_probe_20260827.json` |
| C2 语料 | `dataset_wam_loop_20260827/`（31 ep，D 预热用，不替代 B） |
| 旧 handoff | `WAM_BPRIME_125_PROMPT_20260827.md`（已完成） |
