# 125 Agent：Phase-2 全签战役（重训 π → 16 路 mainline）

> **日期**：2026-08-29  
> **强制 workspace**：`/home/yao/workspaces/aerial-wam-v2-phase2`  
> **Indoor**：禁止动 `/home/yao/aerial-indoor-wam`  
> **H100**：只经本机 `ssh h100-25`（用户 `a25689`）；Mac 不直连  
> **禁止**：Docking / 往返 / 关罩 / 开 escape / 放宽 3 m 到达 / 把坐标目标写成视觉目标

---

## 背景（诚实）

- 全修代码已落地；SCR smoke：**IR>0、SCR=0，但 SR=0%**。  
- 现 `v4_ac_ckpt_step_e_20260828` 的 `condition_on_goal=True`，但 **F9 `g_norm` 改变了 4 维语义**（原米制 → `û+log1p`），旧权不等价。  
- **全签** = H100 用当前代码重训 π → 拉回 125 → **16 路 native mainline** → 对照门限写 DECLARE（PASS/FAIL 如实）。

门限（runbook）：SR≥80% · SCR≤10% · SPL≥70% · ρ̄≥90% · IR≤25%。

---

## 步骤

### 0. 环境与杀旧作业

```bash
cd /home/yao/workspaces/aerial-wam-v2-phase2
# 杀本 workspace 旧 agent / 残留 long_eval（勿动 indoor）
pgrep -af 'wam_phase2_long_eval|aerial-wam-v2-phase2' | head
source /home/yao/aerial-wam-v2/experiments/aerial/scripts/env_4090.sh || true
# 代码：确保 fullfix 已在 WT；同步关键 py 到 ~/aerial-wam-v2 与 H100
```

### 1. H100：goal-cond + g_norm 想象 AC 重训

在 **125** 上：

```bash
# 拉齐代码到 H100（路径以 125 上实际为准，常见 /home/a25689/aerial-wam-v2）
ssh h100-25 'hostname; ls ~/aerial-wam-v2/experiments/aerial/rl/train_v4_ac.py'
# rsync WT 或 MAIN 的 actor_critic/goal_features/imagination/train_v4_ac 等到 H100
```

H100 训练（对齐 Step E 量级；**从零**，禁 warm-start 旧 AC）：

```bash
ssh h100-25 'bash -lc "
cd ~/aerial-wam-v2   # 或实际 repo
# 激活 H100 既有 venv / module（沿用上次 Step E 环境）
nohup python -m experiments.aerial.rl.train_v4_ac \
  --iters 500 \
  --device cuda \
  --dynamics torch \
  --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt \
  --ckpt-dir experiments/aerial/rl/artifacts/v4_ac_ckpt_phase2_gnorm_20260829 \
  --annotation artifacts/seen_airsim16_m1a20.json \
  --backend mock \
  --skip-collect \
  --dataset <既有 Step E 所用 offline RGB dataset 路径，125/H100 上查上次 E 命令> \
  > artifacts/train_v4_ac_phase2_gnorm_20260829.log 2>&1 &
echo TRAIN_PID=\$!
"'
```

若 `--dataset` / 语料路径不确定：在 H100/125 搜上次 Step E 日志或 `docs/handover` / `artifacts/*step_e*`，**复用同一语料**，只换代码（含 g_norm）与新 ckpt-dir。  
**验收训完**：ckpt 内 `config.condition_on_goal==True`；`actor` 首层 in_dim = latent_dim+4。

把 `v4_ac_latest.pt`（及 config）拉回：

- `~/aerial-wam-v2/experiments/aerial/rl/artifacts/v4_ac_ckpt_phase2_gnorm_20260829/`  
- 及 WT 同路径（或 symlink）

### 2. 125：16 路 mainline 全签评测

```bash
cd ~/aerial-wam-v2   # AirSim / env 以主树为准；代码已全修
source experiments/aerial/scripts/env_4090.sh
# 确认 AirSim 在；无冲突 eval
nohup $PYTHON_BIN experiments/aerial/scripts/wam_phase2_long_eval.py \
  --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt \
  --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_phase2_gnorm_20260829/v4_ac_latest.pt \
  --annotation artifacts/seen_airsim16_long_routes.json \
  --cruise-speed 10.0 \
  --planner --planner-horizon 5 \
  --max-steps 1000 \
  --out artifacts/wam_phase2_signoff_result_20260829.json \
  > artifacts/wam_phase2_signoff_20260829.log 2>&1 &
echo EVAL_PID=\$!
```

监控至结束。

### 3. 签核文档（必须写）

写到 WT：`docs/handover/WAM_PHASE2_SIGNOFF_DECLARE_20260829.md`

内容至少：

| 项 | 要求 |
|----|------|
| 训程 | H100 命令、iters、ckpt 路径、`condition_on_goal`、确认 g_norm 代码在训 |
| 指标 | SR/SCR/SPL/ρ̄/IR vs 门限；verdict PASS/FAIL **如实** |
| spawn_fail | n_spawn_fail_f1 |
| 失败条 | 按 F1–F14 归类（若 FAIL） |
| 纪律 | 无 Docking/往返/关罩/escape |
| 未签项 | 若 IR>25% 或 SR 不足：写明是 π 弱还是罩过干预；**不得**改门限凑 PASS |

同步 STATUS 副本到 `~/aerial-wam-v2/docs/handover/`。

### 4. 完成回复格式

- TRAIN ckpt 路径 + condition_on_goal  
- 16 路：SR/SCR/SPL/Prog/IR + verdict  
- DECLARE 路径  
- 若 FAIL：下一切主航道建议（一句）

---

## 停止条件

- H100 不可达 / 无语料 → 停，写 blocker，**不要**用旧 step_e ckpt 假装全签。  
- 评测中途崩 → 修接线后重跑，勿改到达半径。
